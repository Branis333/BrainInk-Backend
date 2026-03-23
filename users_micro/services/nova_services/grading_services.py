from pathlib import Path
from io import BytesIO
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image
from pypdf import PdfReader

from services.nova_services.nova_services import nova_service


class NovaGradingService:
	"""Vision-first grading workflow using Bedrock Nova."""

	MAX_IMAGES_PER_SUBMISSION = 12
	MAX_IMAGE_DIMENSION = 1800
	JPEG_QUALITY = 85

	@staticmethod
	def _normalize_image_bytes(raw_bytes: bytes, source_ext: str) -> Optional[Tuple[bytes, str]]:
		if not raw_bytes:
			return None

		ext = (source_ext or "").lower().strip().lstrip(".")
		if ext == "jpg":
			ext = "jpeg"

		# Keep PNG/JPEG as-is when reasonably sized.
		if ext in {"jpeg", "png"} and len(raw_bytes) <= 4 * 1024 * 1024:
			return raw_bytes, ext

		try:
			with Image.open(BytesIO(raw_bytes)) as img:
				img = img.convert("RGB")
				img.thumbnail((
					NovaGradingService.MAX_IMAGE_DIMENSION,
					NovaGradingService.MAX_IMAGE_DIMENSION,
				))

				out = BytesIO()
				img.save(out, format="JPEG", quality=NovaGradingService.JPEG_QUALITY, optimize=True)
				return out.getvalue(), "jpeg"
		except Exception:
			return None

	@staticmethod
	def _extract_pdf_images(pdf_path: str) -> List[Dict[str, Any]]:
		reader = PdfReader(pdf_path)
		images: List[Dict[str, Any]] = []

		for page_number, page in enumerate(reader.pages, start=1):
			if len(images) >= NovaGradingService.MAX_IMAGES_PER_SUBMISSION:
				break

			page_images = list(page.images or [])
			if not page_images:
				continue

			# Prefer larger embedded images first per page.
			page_images.sort(key=lambda img: len(getattr(img, "data", b"")), reverse=True)

			for image_index, image_file in enumerate(page_images, start=1):
				if len(images) >= NovaGradingService.MAX_IMAGES_PER_SUBMISSION:
					break

				raw_bytes = getattr(image_file, "data", b"")
				name = str(getattr(image_file, "name", ""))
				ext = Path(name).suffix.lower().lstrip(".") if name else ""

				normalized = NovaGradingService._normalize_image_bytes(raw_bytes, ext)
				if not normalized:
					continue

				image_bytes, image_format = normalized
				images.append(
					{
						"bytes": image_bytes,
						"format": image_format,
						"page_number": page_number,
						"image_index": image_index,
					}
				)

		return images

	@staticmethod
	def _build_prompts(
		*,
		assignment_title: str,
		assignment_description: str,
		rubric: str,
		max_points: int,
		feedback_type: str,
		student_name: str,
		submission_image_count: int,
	) -> Dict[str, str]:
		system_prompt = (
			"You are a strict, fair, and evidence-based academic grading assistant with vision capability. "
			"Grade only from the provided assignment, rubric, and submission images. "
			"Return only valid JSON without markdown, comments, or extra keys."
		)
		user_prompt = f"""
You are grading one student submission.

GOAL:
- Produce an accurate, rubric-aligned score and high-quality actionable feedback.
- Be strict but fair: do not over-credit missing evidence and do not under-credit correct work.

GRADING CONTEXT:
- Assignment title: {assignment_title}
- Assignment description: {assignment_description}
- Rubric: {rubric}
- Max points: {max_points}
- Requested feedback type: {feedback_type}
- Student name: {student_name}

SUBMISSION VISUAL INPUT:
- {submission_image_count} page image(s) are attached in this request.
- Read and interpret handwritten/printed content directly from the images.
- Extract relevant evidence from diagrams, equations, and written responses.

GRADING METHOD (must follow):
1) Identify the expected outcomes from the assignment + rubric.
2) Evaluate what the submission images explicitly demonstrate.
3) Match demonstrated evidence to rubric criteria.
4) Deduct points for inaccuracies, omissions, weak reasoning, or rubric misses.
5) Keep scoring proportional to quality and completeness.
6) If rubric details are vague, infer reasonable academic criteria from assignment description.

SCORING CALIBRATION:
- 90-100%: Excellent mastery, complete and accurate, strong reasoning.
- 75-89%: Good understanding, minor gaps or clarity issues.
- 60-74%: Partial understanding, notable missing depth or errors.
- 40-59%: Limited understanding, major omissions or misconceptions.
- 0-39%: Minimal relevant evidence, mostly incorrect or off-task.

FEEDBACK QUALITY REQUIREMENTS:
- feedback must summarize score rationale in 3-8 sentences.
- strengths: 2-5 concrete positives tied to actual submission evidence.
- areas_for_improvement: 2-5 concrete gaps or mistakes.
- suggestions: 2-5 actionable next steps the student can apply immediately.
- Avoid vague comments like "do better". Be specific and instructional.

CONFIDENCE GUIDELINES:
- 85-100: clear evidence and rubric alignment.
- 60-84: some ambiguity or partial evidence.
- 0-59: low confidence due to weak/unclear submission evidence.

OUTPUT RULES:
- Return ONLY one JSON object.
- Do not include markdown fences.
- Do not include any keys outside the required schema.
- points_earned must be an integer in [0, {max_points}].
- confidence must be an integer in [0, 100].
- If evidence is insufficient, give conservative scoring and explain why in feedback.
- Never fabricate student content.

REQUIRED JSON SCHEMA:
{{
	"points_earned": number,
	"feedback": "string",
	"confidence": number,
	"strengths": ["string"],
	"areas_for_improvement": ["string"],
	"suggestions": ["string"]
}}

""".strip()
		return {"system": system_prompt, "user": user_prompt}

	@staticmethod
	async def grade_assignment_pdf(
		pdf_path: str,
		assignment_title: str,
		assignment_description: str,
		rubric: str,
		max_points: int,
		feedback_type: str = "detailed",
		student_name: Optional[str] = None,
	) -> Dict[str, Any]:
		try:
			if not Path(pdf_path).exists():
				return {"success": False, "error": "PDF file not found"}

			submission_images = NovaGradingService._extract_pdf_images(pdf_path)
			if not submission_images:
				return {"success": False, "error": "Could not extract readable page images from PDF"}

			prompts = NovaGradingService._build_prompts(
				assignment_title=assignment_title,
				assignment_description=assignment_description,
				rubric=rubric,
				max_points=max_points,
				feedback_type=feedback_type,
				student_name=student_name or "Anonymous",
				submission_image_count=len(submission_images),
			)

			payload = await nova_service.generate_json_with_images(
				system_prompt=prompts["system"],
				user_prompt=prompts["user"],
				images=submission_images,
				max_tokens=2200,
			)

			points_earned = int(float(payload.get("points_earned", 0)))
			points_earned = max(0, min(max_points, points_earned))

			confidence = int(float(payload.get("confidence", 80)))
			confidence = max(0, min(100, confidence))

			percentage = round((points_earned / max_points) * 100, 2) if max_points > 0 else 0

			return {
				"success": True,
				"points_earned": points_earned,
				"max_points": max_points,
				"percentage": percentage,
				"feedback": str(payload.get("feedback", "")),
				"strengths": payload.get("strengths", []),
				"areas_for_improvement": payload.get("areas_for_improvement", []),
				"suggestions": payload.get("suggestions", []),
				"confidence": confidence,
				"ai_model_used": nova_service.model_id,
			}
		except Exception as e:
			return {"success": False, "error": f"Nova grading error: {str(e)}"}

	@staticmethod
	async def extract_text_from_pdf_with_vision(
		pdf_path: str,
		max_images: int = 8,
	) -> Dict[str, Any]:
		"""Extract text from image-based PDF pages using Nova vision input."""
		all_images: List[Dict[str, Any]] = []
		selected_images: List[Dict[str, Any]] = []
		try:
			if not Path(pdf_path).exists():
				return {"success": False, "error": "PDF file not found"}

			all_images = NovaGradingService._extract_pdf_images(pdf_path)
			if not all_images:
				return {"success": False, "error": "Could not extract readable page images from PDF"}

			max_images = max(1, min(20, int(max_images)))
			selected_images = all_images[:max_images]

			system_prompt = (
				"You are a high-accuracy OCR and document understanding assistant. "
				"Read all attached page images and extract visible text faithfully. "
				"Return only valid JSON."
			)
			user_prompt = """
Extract text from the attached document page images.

Instructions:
1) Read handwritten and printed content from all attached images.
2) Preserve natural reading order as best as possible.
3) Keep line breaks between major sections where possible.
4) Do not invent missing text.
5) If a region is unreadable, skip it instead of guessing.

Return ONLY this JSON schema:
{
  "extracted_text": "string",
  "confidence": 0
}
""".strip()

			payload = await nova_service.generate_json_with_images(
				system_prompt=system_prompt,
				user_prompt=user_prompt,
				images=selected_images,
				max_tokens=2600,
				temperature=0.0,
			)

			extracted_text = str(payload.get("extracted_text", "")).strip()
			confidence = int(float(payload.get("confidence", 70)))
			confidence = max(0, min(100, confidence))

			if not extracted_text:
				return {
					"success": False,
					"error": "Vision extraction returned empty text",
					"image_count": len(selected_images),
					"total_images_available": len(all_images),
				}

			return {
				"success": True,
				"extracted_text": extracted_text,
				"text_length": len(extracted_text),
				"confidence": confidence,
				"image_count": len(selected_images),
				"total_images_available": len(all_images),
				"ai_model_used": nova_service.model_id,
			}
		except Exception as e:
			error_text = str(e)
			if "Unable to locate credentials" in error_text:
				error_text = (
					"Nova vision extraction error: Unable to locate AWS credentials. "
					"Set AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, and AWS_REGION "
					"(and AWS_SESSION_TOKEN if using temporary credentials)."
				)
			else:
				error_text = f"Nova vision extraction error: {error_text}"

			return {
				"success": False,
				"error": error_text,
				"image_count": len(selected_images),
				"total_images_available": len(all_images),
			}


nova_grading_service = NovaGradingService()
