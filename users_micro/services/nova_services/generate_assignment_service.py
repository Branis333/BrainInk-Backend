from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from services.nova_services.nova_services import nova_service


class NovaQuizService:
	"""Minimal quiz generation workflow using Bedrock Nova."""

	@staticmethod
	def _build_prompts(
		*,
		description: str,
		num_questions: int,
		difficulty: str,
		subject: str,
		student_level: str,
		weakness_areas: Optional[List[str]] = None,
		context: str = "",
	) -> Dict[str, str]:
		weakness_text = ", ".join(weakness_areas or []) or "general understanding"
		system_prompt = (
			"You are an expert educational assessment designer. "
			"Create rigorous, fair, curriculum-aligned quizzes. "
			"Return only valid JSON."
		)
		user_prompt = f"""
Generate an educational quiz.

CONTEXT:
- Description: {description}
- Subject: {subject}
- Difficulty: {difficulty}
- Student level: {student_level}
- Weakness areas: {weakness_text}
- Additional context: {context}

REQUIREMENTS:
1) Generate exactly {num_questions} unique questions.
2) Each question must have exactly 4 options.
3) Questions must test understanding and reasoning, not just recall.
4) Align each question to at least one weakness area when possible.
5) Include concise but instructional explanations.
6) Keep language level appropriate for {student_level}.
7) Make distractors plausible and non-trivial.

QUALITY BAR:
- Avoid ambiguous wording.
- Avoid trick questions.
- Ensure exactly one correct option per question.
- Ensure content accuracy.

Return ONLY this JSON schema:
{{
  "title": "string",
  "description": "string",
  "difficulty": "{difficulty}",
  "subject": "{subject}",
  "questions": [
    {{
      "question": "string",
      "options": ["string", "string", "string", "string"],
      "correctAnswer": 0,
      "explanation": "string",
      "topic": "string",
      "weaknessArea": "string"
    }}
  ]
}}

Rules:
- correctAnswer must be an integer index from 0 to 3.
- Return only JSON, no markdown.
""".strip()
		return {"system": system_prompt, "user": user_prompt}

	@staticmethod
	def _normalize_questions(questions: List[Dict[str, Any]], max_items: int) -> List[Dict[str, Any]]:
		normalized: List[Dict[str, Any]] = []
		for q in questions:
			if not isinstance(q, dict):
				continue
			options = q.get("options")
			if not isinstance(options, list) or len(options) != 4:
				continue

			try:
				correct = int(q.get("correctAnswer", 0))
			except Exception:
				correct = 0
			if correct < 0 or correct > 3:
				correct = 0

			normalized.append(
				{
					"id": f"q_{datetime.now(timezone.utc).timestamp()}_{len(normalized)}",
					"question": str(q.get("question", "")).strip(),
					"options": [str(o) for o in options],
					"correctAnswer": correct,
					"explanation": str(q.get("explanation", "")).strip(),
					"topic": str(q.get("topic", "General")).strip() or "General",
					"weakness_area": str(q.get("weaknessArea", "General Understanding")).strip() or "General Understanding",
					"difficulty": "medium",
				}
			)
			if len(normalized) >= max_items:
				break
		return normalized

	@staticmethod
	async def generate_quiz(
		*,
		description: str,
		num_questions: int = 5,
		difficulty: str = "medium",
		subject: str = "General",
		student_level: str = "intermediate",
		weakness_areas: Optional[List[str]] = None,
		context: str = "",
	) -> Dict[str, Any]:
		prompts = NovaQuizService._build_prompts(
			description=description,
			num_questions=num_questions,
			difficulty=difficulty,
			subject=subject,
			student_level=student_level,
			weakness_areas=weakness_areas,
			context=context,
		)

		payload = await nova_service.generate_json(
			system_prompt=prompts["system"],
			user_prompt=prompts["user"],
			max_tokens=2200,
			temperature=0.4,
		)

		questions = NovaQuizService._normalize_questions(payload.get("questions", []), num_questions)
		if not questions:
			raise ValueError("Nova quiz response did not contain valid questions")

		for q in questions:
			q["difficulty"] = difficulty

		return {
			"title": str(payload.get("title", f"Quiz: {subject}")).strip() or f"Quiz: {subject}",
			"description": str(payload.get("description", "AI-generated quiz")).strip() or "AI-generated quiz",
			"difficulty": difficulty,
			"subject": subject,
			"questions": questions,
			"generated_by": "nova_ai",
			"ai_model_used": nova_service.model_id,
		}


nova_quiz_service = NovaQuizService()
