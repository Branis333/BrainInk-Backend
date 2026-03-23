from pathlib import Path
from io import BytesIO
from typing import Any, Dict, List, Optional, Tuple
import re

from PIL import Image
from pypdf import PdfReader

from services.nova_services.nova_services import nova_service


class NovaGradingService:
	"""Vision-first grading workflow using Bedrock Nova."""

	MAX_IMAGES_PER_SUBMISSION = 12
	MAX_IMAGE_DIMENSION = 1800
	JPEG_QUALITY = 85
	MIN_MEANINGFUL_TEXT_CHARS = 30
	MIN_MEANINGFUL_WORDS = 6

	@staticmethod
	def _is_meaningful_submission_text(submission_text: str) -> bool:
		if not submission_text or not submission_text.strip():
			return False

		cleaned = re.sub(r"\s+", " ", submission_text).strip()
		if len(cleaned) < NovaGradingService.MIN_MEANINGFUL_TEXT_CHARS:
			return False

		words = re.findall(r"[A-Za-z0-9]{2,}", cleaned)
		if len(words) < NovaGradingService.MIN_MEANINGFUL_WORDS:
			return False

		# Reject highly repetitive/noisy OCR like "aaaa aaaa" or symbol-heavy artifacts.
		unique_ratio = (len(set(words)) / len(words)) if words else 0
		if unique_ratio < 0.25:
			return False

		return True

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
		submission_text: str = "",
	) -> Dict[str, str]:
		system_prompt = (
			"You are a strict, fair, and evidence-based academic grading assistant with vision capability. "
			"Grade only from the provided assignment, rubric, and submission images. "
			"Return only valid JSON without markdown, comments, or extra keys."
		)
		transcript_block = ""
		if submission_text and submission_text.strip():
			transcript_block = f"""
SUBMISSION OCR TRANSCRIPT (from the same PDF images):
{submission_text[:6000]}
"""

		user_prompt = f"""
You are grading one student submission.

GOAL:
- Produce an accurate, rubric-aligned score with clear teacher-quality feedback.
- Be strict and evidence-driven: do not award points without visible support in the submission.

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

{transcript_block}

GRADING METHOD (must follow):
1) Identify each rubric category and its expected evidence.
2) Evaluate what the submission explicitly demonstrates for each category.
3) Use the OCR transcript only to cross-check; if transcript conflicts with image evidence, trust the image evidence.
4) Assign points conservatively per rubric category based on demonstrated evidence.
5) Sum category points and ensure the total matches points_earned.
6) Deduct points for mathematical errors, missing steps, or unclear reasoning.
7) If evidence is weak or missing for a category, award low or zero points for that category.

SCORING CALIBRATION:
- 90-100%: Excellent mastery, complete and accurate, strong reasoning.
- 75-89%: Good understanding, minor gaps or clarity issues.
- 60-74%: Partial understanding, notable missing depth or errors.
- 40-59%: Limited understanding, major omissions or misconceptions.
- 0-39%: Minimal relevant evidence, mostly incorrect or off-task.

FEEDBACK QUALITY REQUIREMENTS:
- feedback must be 4-8 sentences in professional teacher tone with strong grammar.
- feedback must begin with: "Score: X/{max_points}."
- feedback must mention at least 3 rubric categories by name.
- strengths: 2-5 concrete positives tied to specific work shown.
- areas_for_improvement: 2-5 concrete, specific mistakes or missing steps.
- suggestions: 2-5 actionable next steps tied directly to weak rubric categories.
- Avoid generic language. Do not repeat rubric text without applying it to this student's work.

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
- If evidence is insufficient, assign low/zero points and explain exactly why.
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
		submission_text: Optional[str] = None,
	) -> Dict[str, Any]:
		try:
			if not Path(pdf_path).exists():
				return {"success": False, "error": "PDF file not found"}

			if submission_text is not None and not NovaGradingService._is_meaningful_submission_text(submission_text):
				return {
					"success": True,
					"points_earned": 0,
					"max_points": max_points,
					"percentage": 0,
					"feedback": "No meaningful submission content was detected in the uploaded file. The file appears blank, unreadable, or unrelated to the assignment. Please upload a clear and complete submission.",
					"strengths": [],
					"areas_for_improvement": [
						"Upload the correct assignment file",
						"Ensure the file contains readable written work",
						"Use clear scans/photos with adequate lighting and contrast",
					],
					"suggestions": [
						"Re-upload the correct file and resubmit for grading",
						"Verify all pages are visible and legible before submission",
					],
					"confidence": 99,
					"ai_model_used": nova_service.model_id,
					"insufficient_submission_evidence": True,
				}

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
				submission_text=(submission_text or ""),
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
