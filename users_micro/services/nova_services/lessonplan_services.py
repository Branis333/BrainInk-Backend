from io import BytesIO
from typing import Any, Dict, List, Optional

from pypdf import PdfReader

from services.nova_services.nova_services import nova_service


class NovaLessonPlanService:
	"""Minimal Nova service for generating structured lesson plans."""

	@staticmethod
	def extract_pdf_text_from_bytes(file_bytes: bytes) -> str:
		reader = PdfReader(BytesIO(file_bytes))
		pages: List[str] = []
		for page in reader.pages:
			pages.append(page.extract_text() or "")
		return "\n\n".join(pages).strip()

	@staticmethod
	def _build_prompts(
		*,
		subject_name: str,
		classroom_name: str,
		title: str,
		description: str,
		duration_minutes: int,
		learning_objectives_hint: List[str],
		source_context: str,
	) -> Dict[str, str]:
		objectives_text = "\n".join([f"- {obj}" for obj in learning_objectives_hint]) if learning_objectives_hint else "- Not provided"
		system_prompt = (
			"You are an expert K-12 instructional designer and classroom pedagogy specialist. "
			"Create practical, high-quality lesson plans that are realistic for classroom delivery. "
			"Return only valid JSON."
		)
		user_prompt = f"""
Create one complete lesson plan.

CONTEXT:
- Subject: {subject_name}
- Classroom: {classroom_name}
- Requested title: {title}
- Teacher description: {description}
- Duration minutes target: {duration_minutes}
- Teacher objective hints:
{objectives_text}

Optional source context:
{source_context if source_context else "No uploaded source context provided."}

INSTRUCTIONS:
1) Align the plan tightly to the subject and teacher context.
2) Ensure pacing fits a single class period of approximately {duration_minutes} minutes.
3) Provide clear, measurable learning objectives.
4) Activities should be ordered and classroom-actionable.
5) Include differentiation through at least one activity or strategy.
6) Include formative assessment strategy tied to objectives.
7) Homework should reinforce lesson outcomes and be realistic.
8) Materials should be specific and concise.

OUTPUT RULES:
- Return ONLY one JSON object.
- No markdown, no extra keys, no commentary.
- Use concise, professional educator language.

REQUIRED JSON SCHEMA:
{{
  "title": "string",
  "description": "string",
  "duration_minutes": number,
  "learning_objectives": ["string"],
  "activities": ["string"],
  "materials_needed": ["string"],
  "assessment_strategy": "string",
  "homework": "string"
}}

CONSTRAINTS:
- learning_objectives: 4-8 items
- activities: 5-12 ordered steps
- materials_needed: 3-12 items
- duration_minutes: integer between 10 and 240
""".strip()
		return {"system": system_prompt, "user": user_prompt}

	@staticmethod
	def _clean_string_list(values: Optional[List[Any]]) -> List[str]:
		cleaned: List[str] = []
		for item in values or []:
			text = str(item).strip()
			if text:
				cleaned.append(text)
		return cleaned

	@staticmethod
	async def generate_lesson_plan(
		*,
		subject_name: str,
		classroom_name: str,
		title: str,
		description: str,
		duration_minutes: int,
		learning_objectives_hint: Optional[List[str]] = None,
		source_context: str = "",
	) -> Dict[str, Any]:
		prompts = NovaLessonPlanService._build_prompts(
			subject_name=subject_name,
			classroom_name=classroom_name,
			title=title,
			description=description,
			duration_minutes=duration_minutes,
			learning_objectives_hint=learning_objectives_hint or [],
			source_context=source_context[:12000],
		)

		payload = await nova_service.generate_json(
			system_prompt=prompts["system"],
			user_prompt=prompts["user"],
			max_tokens=2600,
			temperature=0.3,
		)

		generated_duration = int(float(payload.get("duration_minutes", duration_minutes)))
		generated_duration = max(10, min(240, generated_duration))

		return {
			"title": str(payload.get("title", title)).strip()[:200] or title,
			"description": str(payload.get("description", description)).strip() or description,
			"duration_minutes": generated_duration,
			"learning_objectives": NovaLessonPlanService._clean_string_list(payload.get("learning_objectives")) or (learning_objectives_hint or []),
			"activities": NovaLessonPlanService._clean_string_list(payload.get("activities")),
			"materials_needed": NovaLessonPlanService._clean_string_list(payload.get("materials_needed")),
			"assessment_strategy": str(payload.get("assessment_strategy", "")).strip() or None,
			"homework": str(payload.get("homework", "")).strip() or None,
			"ai_model_used": nova_service.model_id,
		}


nova_lessonplan_service = NovaLessonPlanService()
