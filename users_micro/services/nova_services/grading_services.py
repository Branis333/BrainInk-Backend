from pathlib import Path
from typing import Any, Dict, Optional

from pypdf import PdfReader

from services.nova_services.nova_services import nova_service


class NovaGradingService:
	"""Minimal grading workflow using Bedrock Nova."""

	@staticmethod
	def _extract_pdf_text(pdf_path: str) -> str:
		reader = PdfReader(pdf_path)
		pages = []
		for page in reader.pages:
			pages.append(page.extract_text() or "")
		return "\n\n".join(pages).strip()

	@staticmethod
	def _build_prompts(
		*,
		assignment_title: str,
		assignment_description: str,
		rubric: str,
		max_points: int,
		feedback_type: str,
		student_name: str,
		submission_text: str,
	) -> Dict[str, str]:
		system_prompt = (
			"You are a strict, fair, and evidence-based academic grading assistant. "
			"Grade only from the provided assignment, rubric, and submission text. "
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

SUBMISSION:
{submission_text}

GRADING METHOD (must follow):
1) Identify the expected outcomes from the assignment + rubric.
2) Evaluate what the submission explicitly demonstrates.
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

			submission_text = NovaGradingService._extract_pdf_text(pdf_path)
			if not submission_text:
				return {"success": False, "error": "Could not extract readable text from PDF"}

			# Keep prompt bounded for predictable latency/cost.
			submission_text = submission_text[:12000]
			prompts = NovaGradingService._build_prompts(
				assignment_title=assignment_title,
				assignment_description=assignment_description,
				rubric=rubric,
				max_points=max_points,
				feedback_type=feedback_type,
				student_name=student_name or "Anonymous",
				submission_text=submission_text,
			)

			payload = await nova_service.generate_json(
				system_prompt=prompts["system"],
				user_prompt=prompts["user"],
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


nova_grading_service = NovaGradingService()
