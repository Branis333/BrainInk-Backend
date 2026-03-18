import json
from typing import Any, Dict, List, Optional

from pypdf import PdfReader

from services.nova_services.nova_services import nova_service


class NovaSyllabusService:
	"""Minimal syllabus generation workflow using Bedrock Nova."""

	@staticmethod
	def extract_pdf_text(file_path: str) -> str:
		reader = PdfReader(file_path)
		chunks: List[str] = []
		for page in reader.pages:
			chunks.append(page.extract_text() or "")
		return "\n\n".join(chunks).strip()

	@staticmethod
	def _build_prompts(
		*,
		textbook_text: str,
		term_length_weeks: int,
		subject_name: str,
		additional_preferences: Optional[Dict[str, Any]] = None,
	) -> Dict[str, str]:
		prefs = additional_preferences or {}
		system_prompt = (
			"You are an expert curriculum and syllabus design specialist. "
			"Create pedagogically sound, realistic weekly plans from textbook content. "
			"Return only valid JSON."
		)
		user_prompt = f"""
Create a complete {term_length_weeks}-week syllabus plan.

INPUT:
- Subject: {subject_name}
- Term length: {term_length_weeks} weeks
- Additional preferences: {json.dumps(prefs, ensure_ascii=True)}
- Textbook content:
{textbook_text}

INSTRUCTIONS:
1) Identify major units/topics and a logical progression.
2) Balance conceptual depth with practical activities.
3) Sequence from foundations to advanced topics.
4) Keep each week realistic in scope.
5) Include measurable learning objectives.
6) Include assignments that reinforce objectives.

OUTPUT SCHEMA (return ONLY this JSON):
{{
  "analysis_summary": "string",
  "content_overview": {{
    "total_chapters": number,
    "main_topics": ["string"],
    "difficulty_progression": "string",
    "estimated_study_hours_per_week": number
  }},
  "weekly_plans": [
    {{
      "week_number": 1,
      "title": "string",
      "description": "string",
      "learning_objectives": ["string"],
      "topics_covered": ["string"],
      "textbook_chapters": "string",
      "textbook_pages": "string",
      "assignments": ["string"],
      "resources": ["string"]
    }}
  ]
}}

Rules:
- Must include exactly {term_length_weeks} weekly_plans.
- week_number values must be 1..{term_length_weeks}.
- Return JSON only, no markdown.
""".strip()
		return {"system": system_prompt, "user": user_prompt}

	@staticmethod
	def _normalize_weekly_plans(weekly_plans: Any, term_length_weeks: int) -> List[Dict[str, Any]]:
		if not isinstance(weekly_plans, list):
			weekly_plans = []

		normalized: List[Dict[str, Any]] = []
		for i in range(term_length_weeks):
			raw = weekly_plans[i] if i < len(weekly_plans) and isinstance(weekly_plans[i], dict) else {}
			week_number = i + 1
			normalized.append(
				{
					"week_number": week_number,
					"title": str(raw.get("title", f"Week {week_number}")).strip() or f"Week {week_number}",
					"description": str(raw.get("description", "")).strip(),
					"learning_objectives": raw.get("learning_objectives", []) if isinstance(raw.get("learning_objectives"), list) else [],
					"topics_covered": raw.get("topics_covered", []) if isinstance(raw.get("topics_covered"), list) else [],
					"textbook_chapters": str(raw.get("textbook_chapters", "")).strip(),
					"textbook_pages": str(raw.get("textbook_pages", "")).strip(),
					"assignments": raw.get("assignments", []) if isinstance(raw.get("assignments"), list) else [],
					"resources": raw.get("resources", []) if isinstance(raw.get("resources"), list) else [],
				}
			)
		return normalized

	@staticmethod
	async def process_textbook(
		*,
		file_path: str,
		term_length_weeks: int,
		subject_name: str,
		additional_preferences: Optional[Dict[str, Any]] = None,
	) -> Dict[str, Any]:
		textbook_text = NovaSyllabusService.extract_pdf_text(file_path)
		if not textbook_text:
			raise ValueError("Could not extract text from textbook PDF")

		# Keep context bounded for stable model latency.
		textbook_text = textbook_text[:50000]
		prompts = NovaSyllabusService._build_prompts(
			textbook_text=textbook_text,
			term_length_weeks=term_length_weeks,
			subject_name=subject_name,
			additional_preferences=additional_preferences,
		)

		payload = await nova_service.generate_json(
			system_prompt=prompts["system"],
			user_prompt=prompts["user"],
			max_tokens=3500,
			temperature=0.35,
		)

		overview = payload.get("content_overview", {}) if isinstance(payload.get("content_overview"), dict) else {}
		analysis_data = {
			"analysis_summary": str(payload.get("analysis_summary", "")).strip(),
			"content_overview": {
				"total_chapters": overview.get("total_chapters", 0),
				"main_topics": overview.get("main_topics", []) if isinstance(overview.get("main_topics"), list) else [],
				"difficulty_progression": str(overview.get("difficulty_progression", "")).strip(),
				"estimated_study_hours_per_week": overview.get("estimated_study_hours_per_week", 0),
			},
		}

		weekly_plans = NovaSyllabusService._normalize_weekly_plans(payload.get("weekly_plans"), term_length_weeks)

		return {
			"analysis_data": analysis_data,
			"weekly_plans": weekly_plans,
			"ai_model_used": nova_service.model_id,
		}


nova_syllabus_service = NovaSyllabusService()
