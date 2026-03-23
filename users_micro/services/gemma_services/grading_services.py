from pathlib import Path
from io import BytesIO
from typing import Any, Dict, List, Optional, Tuple
import re

from PIL import Image
from pypdf import PdfReader

from services.gemma_services.gemma_services import gemma_service


class GemmaGradingService:
	"""Vision-first grading workflow using Bedrock Gemma."""

	MAX_IMAGES_PER_SUBMISSION = 12
	MAX_IMAGE_DIMENSION = 1800
	JPEG_QUALITY = 85
	MIN_MEANINGFUL_TEXT_CHARS = 30
	MIN_MEANINGFUL_WORDS = 6

	@staticmethod
	def _parse_rubric_criteria_with_points(rubric: str) -> List[Dict[str, Any]]:
		"""Best-effort parser for rubric rows so we can return deterministic criterion scores when evidence is insufficient."""
		rows: List[Dict[str, Any]] = []
		if not rubric or not rubric.strip():
			return rows

		for raw_line in rubric.splitlines():
			line = raw_line.strip()
			if not line:
				continue
			lower_line = line.lower()
			if lower_line.startswith("category") or lower_line.startswith("criterion"):
				continue

			category = ""
			max_points = 0

			# Format: Criterion|5|description
			if "|" in line:
				parts = [p.strip() for p in line.split("|") if p.strip()]
				if len(parts) >= 2:
					category = parts[0]
					try:
						max_points = int(float(parts[1]))
					except Exception:
						max_points = 0

			# Format: Criterion\t5\tDescription
			if not category and "\t" in line:
				parts = [p.strip() for p in line.split("\t") if p.strip()]
				if len(parts) >= 2:
					category = parts[0]
					try:
						max_points = int(float(parts[1]))
					except Exception:
						max_points = 0

			# Format: Criterion ... Max: 7
			if not category:
				max_match = re.search(r"max\s*[:=]\s*(\d+(?:\.\d+)?)", line, flags=re.IGNORECASE)
				if max_match:
					try:
						max_points = int(float(max_match.group(1)))
					except Exception:
						max_points = 0
					category = re.sub(r"max\s*[:=]\s*\d+(?:\.\d+)?", "", line, flags=re.IGNORECASE).strip(" -:\t")

			# Fallback: take first token group as category and look for first number as points.
			if not category:
				num_match = re.search(r"(\d+(?:\.\d+)?)", line)
				if num_match:
					try:
						max_points = int(float(num_match.group(1)))
					except Exception:
						max_points = 0
					category = line[:num_match.start()].strip(" -:\t") or line
				else:
					category = line

			if category:
				rows.append({
					"criterion": category,
					"max_points": max(0, max_points),
				})

		if not rows:
			rows.append({"criterion": "Overall rubric", "max_points": 0})

		return rows

	@staticmethod
	def _build_rubric_paragraph_prompts(
		*,
		assignment_title: str,
		rubric: str,
		max_points: int,
		submission_image_count: int,
		submission_text: str = "",
	) -> Dict[str, str]:
		system_prompt = (
			"You are a strict, evidence-based teacher grading assistant with vision capability. "
			"Grade using only the rubric and the student's submission evidence from attached images. "
			"Return only valid JSON."
		)

		transcript_block = ""
		if submission_text and submission_text.strip():
			transcript_block = f"""
SUBMISSION OCR TRANSCRIPT (cross-check only):
{submission_text[:7000]}
"""

		user_prompt = f"""
You are grading one student submission.

INPUTS:
- Assignment title: {assignment_title}
- Rubric:
{rubric}
- Total max points: {max_points}
- Attached submission page images: {submission_image_count}

{transcript_block}

CRITICAL REQUIREMENTS:
1) For each rubric criterion, provide a short paragraph (2-4 sentences) explaining the awarded score.
2) Use evidence from the student's actual work (equations, steps, values, statements, or missing work).
3) Do NOT just restate the rubric language.
4) If evidence is missing, explicitly say what is missing and why points were lost.
5) Keep feedback concise and teacher-like.
6) points_awarded must be between 0 and criterion max_points.
7) total_points must equal the sum of criterion points_awarded.

OUTPUT JSON SCHEMA (ONLY this object):
{{
  "criterion_feedback": [
    {{
      "criterion": "string",
      "points_awarded": 0,
      "max_points": 0,
			"paragraph": "string",
			"evidence_snippet": "string"
    }}
  ],
  "total_points": 0,
  "overall_conclusion": "string",
  "confidence": 0
}}

STYLE:
- Each paragraph should read like: what the student did, what is correct/incorrect, and why this score.
- evidence_snippet should quote a short concrete element from the submission (formula, value, step, or statement).
- overall_conclusion should be 2-4 sentences summarizing overall performance and one next-step recommendation.
""".strip()

		return {"system": system_prompt, "user": user_prompt}

	@staticmethod
	def _is_meaningful_submission_text(submission_text: str) -> bool:
		if not submission_text or not submission_text.strip():
			return False

		cleaned = re.sub(r"\s+", " ", submission_text).strip()
		if len(cleaned) < GemmaGradingService.MIN_MEANINGFUL_TEXT_CHARS:
			return False

		words = re.findall(r"[A-Za-z0-9]{2,}", cleaned)
		if len(words) < GemmaGradingService.MIN_MEANINGFUL_WORDS:
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
					GemmaGradingService.MAX_IMAGE_DIMENSION,
					GemmaGradingService.MAX_IMAGE_DIMENSION,
				))

				out = BytesIO()
				img.save(out, format="JPEG", quality=GemmaGradingService.JPEG_QUALITY, optimize=True)
				return out.getvalue(), "jpeg"
		except Exception:
			return None

	@staticmethod
	def _extract_pdf_images(pdf_path: str) -> List[Dict[str, Any]]:
		reader = PdfReader(pdf_path)
		images: List[Dict[str, Any]] = []

		for page_number, page in enumerate(reader.pages, start=1):
			if len(images) >= GemmaGradingService.MAX_IMAGES_PER_SUBMISSION:
				break

			page_images = list(page.images or [])
			if not page_images:
				continue

			# Prefer larger embedded images first per page.
			page_images.sort(key=lambda img: len(getattr(img, "data", b"")), reverse=True)

			for image_index, image_file in enumerate(page_images, start=1):
				if len(images) >= GemmaGradingService.MAX_IMAGES_PER_SUBMISSION:
					break

				raw_bytes = getattr(image_file, "data", b"")
				name = str(getattr(image_file, "name", ""))
				ext = Path(name).suffix.lower().lstrip(".") if name else ""

				normalized = GemmaGradingService._normalize_image_bytes(raw_bytes, ext)
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

			if submission_text is not None and not GemmaGradingService._is_meaningful_submission_text(submission_text):
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
					"ai_model_used": gemma_service.model_id,
					"insufficient_submission_evidence": True,
				}

			submission_images = GemmaGradingService._extract_pdf_images(pdf_path)
			if not submission_images:
				return {"success": False, "error": "Could not extract readable page images from PDF"}

			prompts = GemmaGradingService._build_prompts(
				assignment_title=assignment_title,
				assignment_description=assignment_description,
				rubric=rubric,
				max_points=max_points,
				feedback_type=feedback_type,
				student_name=student_name or "Anonymous",
				submission_image_count=len(submission_images),
				submission_text=(submission_text or ""),
			)

			payload = await gemma_service.generate_json_with_images(
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
				"ai_model_used": gemma_service.model_id,
			}
		except Exception as e:
			return {"success": False, "error": f"Gemma grading error: {str(e)}"}

	@staticmethod
	async def extract_text_from_pdf_with_vision(
		pdf_path: str,
		max_images: int = 8,
	) -> Dict[str, Any]:
		"""Extract text from image-based PDF pages using Gemma vision input."""
		all_images: List[Dict[str, Any]] = []
		selected_images: List[Dict[str, Any]] = []
		try:
			if not Path(pdf_path).exists():
				return {"success": False, "error": "PDF file not found"}

			all_images = GemmaGradingService._extract_pdf_images(pdf_path)
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

			payload = await gemma_service.generate_json_with_images(
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
				"ai_model_used": gemma_service.model_id,
			}
		except Exception as e:
			error_text = str(e)
			if "Unable to locate credentials" in error_text:
				error_text = (
					"Gemma vision extraction error: Unable to locate AWS credentials. "
					"Set AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, and AWS_REGION "
					"(and AWS_SESSION_TOKEN if using temporary credentials)."
				)
			else:
				error_text = f"Gemma vision extraction error: {error_text}"

			return {
				"success": False,
				"error": error_text,
				"image_count": len(selected_images),
				"total_images_available": len(all_images),
			}

	@staticmethod
	async def grade_pdf_with_rubric_paragraphs(
		pdf_path: str,
		rubric: str,
		assignment_title: str = "Assignment",
		max_points: int = 100,
		max_images: int = 8,
	) -> Dict[str, Any]:
		"""Return per-rubric scored paragraph feedback and overall conclusion for a PDF submission."""
		try:
			if not Path(pdf_path).exists():
				return {"success": False, "error": "PDF file not found"}

			if not rubric or not rubric.strip():
				return {"success": False, "error": "Rubric is required"}

			max_images = max(1, min(20, int(max_images)))
			all_images = GemmaGradingService._extract_pdf_images(pdf_path)
			if not all_images:
				return {"success": False, "error": "Could not extract readable page images from PDF"}

			submission_images = all_images[:max_images]

			extraction_result = await GemmaGradingService.extract_text_from_pdf_with_vision(
				pdf_path=pdf_path,
				max_images=max_images,
			)
			submission_text = extraction_result.get("extracted_text", "") if extraction_result.get("success") else ""

			# Deterministic guard for blank/garbage submissions to prevent inflated grades.
			if not GemmaGradingService._is_meaningful_submission_text(submission_text):
				rubric_rows = GemmaGradingService._parse_rubric_criteria_with_points(rubric)
				criterion_feedback = []
				for row in rubric_rows:
					criterion = row.get("criterion", "Criterion")
					row_max = int(row.get("max_points", 0) or 0)
					criterion_feedback.append(
						{
							"criterion": criterion,
							"points_awarded": 0,
							"max_points": row_max,
							"paragraph": "No meaningful evidence was detected in the submission for this rubric criterion. The uploaded work appears blank, unreadable, or unrelated to the task.",
							"evidence_snippet": "No readable student evidence detected",
							"score_display": f"0/{row_max}" if row_max > 0 else "0",
						}
					)

				return {
					"success": True,
					"criterion_feedback": criterion_feedback,
					"total_points": 0,
					"max_points": max_points,
					"percentage": 0,
					"overall_conclusion": "The submission does not contain enough readable work to grade reliably. The student should re-upload a clear and complete submission.",
					"confidence": 99,
					"submission_text": submission_text,
					"image_count": len(submission_images),
					"total_images_available": len(all_images),
					"ai_model_used": gemma_service.model_id,
					"insufficient_submission_evidence": True,
				}

			prompts = GemmaGradingService._build_rubric_paragraph_prompts(
				assignment_title=assignment_title,
				rubric=rubric,
				max_points=max_points,
				submission_image_count=len(submission_images),
				submission_text=submission_text,
			)

			payload = await gemma_service.generate_json_with_images(
				system_prompt=prompts["system"],
				user_prompt=prompts["user"],
				images=submission_images,
				max_tokens=2600,
				temperature=0.2,
			)

			raw_items = payload.get("criterion_feedback") if isinstance(payload.get("criterion_feedback"), list) else []
			criterion_feedback: List[Dict[str, Any]] = []
			total_points = 0

			for item in raw_items:
				if not isinstance(item, dict):
					continue

				criterion = str(item.get("criterion", "")).strip()
				paragraph = str(item.get("paragraph", "")).strip()
				evidence_snippet = str(item.get("evidence_snippet", "")).strip()
				if not criterion:
					continue

				try:
					item_max = int(float(item.get("max_points", 0)))
				except Exception:
					item_max = 0
				item_max = max(0, item_max)

				try:
					awarded = int(float(item.get("points_awarded", 0)))
				except Exception:
					awarded = 0
				awarded = max(0, min(item_max if item_max > 0 else max_points, awarded))

				total_points += awarded

				criterion_feedback.append(
					{
						"criterion": criterion,
						"points_awarded": awarded,
						"max_points": item_max,
						"paragraph": paragraph,
						"evidence_snippet": evidence_snippet,
						"score_display": f"{awarded}/{item_max}" if item_max > 0 else str(awarded),
					}
				)

			if not criterion_feedback:
				return {
					"success": False,
					"error": "Model did not return criterion-level rubric feedback",
					"ai_model_used": gemma_service.model_id,
				}

			try:
				model_total = int(float(payload.get("total_points", total_points)))
			except Exception:
				model_total = total_points
			resolved_total = min(max_points, max(0, total_points if total_points != model_total else model_total))

			try:
				confidence = int(float(payload.get("confidence", 80)))
			except Exception:
				confidence = 80
			confidence = max(0, min(100, confidence))

			overall_conclusion = str(payload.get("overall_conclusion", "")).strip()
			if not overall_conclusion:
				overall_conclusion = "The submission shows partial mastery of the rubric criteria. Focus on the lower-scoring areas for improvement in the next attempt."

			percentage = round((resolved_total / max_points) * 100, 2) if max_points > 0 else 0

			return {
				"success": True,
				"criterion_feedback": criterion_feedback,
				"total_points": resolved_total,
				"max_points": max_points,
				"percentage": percentage,
				"overall_conclusion": overall_conclusion,
				"confidence": confidence,
				"submission_text": submission_text,
				"image_count": len(submission_images),
				"total_images_available": len(all_images),
				"ai_model_used": gemma_service.model_id,
			}
		except Exception as e:
			return {"success": False, "error": f"Gemma rubric paragraph grading error: {str(e)}"}

gemma_grading_service = GemmaGradingService()
