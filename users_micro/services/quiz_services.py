import logging
from typing import Any, Dict, List, Optional

from services.gemini_service import gemini_service


logger = logging.getLogger(__name__)


class QuizService:
	"""
	Ephemeral practice quiz generation service backed by Gemini.

	Generates 5-question multiple-choice quizzes (not persisted) from:
	- Assignment details + student's feedback
	- Course block content and learning objectives
	- Student notes AI analysis (summary, key points, etc.)

	Return shape (dict):
	{
	  "title": str,
	  "topic": Optional[str],
	  "questions": [
		 {
		   "id": int,
		   "question": str,
		   "options": [str, str, str, str],
		   "correct_index": int,  # 0..3
		   "explanation": Optional[str]
		 }, ... (exactly 5)
	  ]
	}
	"""

	def __init__(self):
		# Composition pattern consistent with other services
		self.gemini = gemini_service

	async def generate_from_assignment(
		self,
		*,
		assignment_title: str,
		assignment_description: Optional[str],
		assignment_instructions: Optional[str],
		learning_outcomes: Optional[List[str]],
		feedback: Optional[str],
		subject: Optional[str] = None,
	) -> Dict[str, Any]:
		prompt = self._build_quiz_prompt(
			context_title=f"Practice Quiz: {assignment_title}",
			context_blocks=[
				("Subject", subject),
				("Assignment Description", assignment_description),
				("Instructions", assignment_instructions),
				("Learning Outcomes", self._join_list(learning_outcomes)),
				("Student Feedback (Focus learning gaps)", feedback),
			],
		)
		return await self._call_gemini(prompt)

	async def generate_from_block(
		self,
		*,
		block_title: str,
		block_description: Optional[str],
		block_content: Optional[str],
		learning_objectives: Optional[List[str]],
		subject: Optional[str] = None,
	) -> Dict[str, Any]:
		prompt = self._build_quiz_prompt(
			context_title=f"Practice Quiz from Block: {block_title}",
			context_blocks=[
				("Subject", subject),
				("Block Description", block_description),
				("Learning Objectives", self._join_list(learning_objectives)),
				("Content", block_content),
			],
		)
		return await self._call_gemini(prompt)

	async def generate_from_notes(
		self,
		*,
		note_title: str,
		summary: Optional[str],
		key_points: Optional[List[str]],
		main_topics: Optional[List[str]],
		learning_concepts: Optional[List[str]],
		subject: Optional[str] = None,
	) -> Dict[str, Any]:
		prompt = self._build_quiz_prompt(
			context_title=f"Practice Quiz from Notes: {note_title}",
			context_blocks=[
				("Subject", subject),
				("Summary", summary),
				("Key Points", self._join_list(key_points)),
				("Main Topics", self._join_list(main_topics)),
				("Learning Concepts", self._join_list(learning_concepts)),
			],
		)
		return await self._call_gemini(prompt)

	# -------------------------------
	# Internals
	# -------------------------------
	def _build_quiz_prompt(self, *, context_title: str, context_blocks: List[tuple]) -> str:
		parts = [f"You are a helpful teacher. Create a concise practice quiz strictly grounded in the provided context.\n\n",
				 f"CONTEXT TITLE: {context_title}\n"]
		for label, value in context_blocks:
			if value:
				parts.append(f"{label}:\n{value}\n\n")

		parts.append(
			"""
REQUIREMENTS:
- Generate EXACTLY 5 multiple-choice questions.
- Each question MUST have 4 options.
- Include the correct option index (0-3) and a short explanation.
- Keep questions specific to the context; avoid unrelated content.
- Use age-appropriate, encouraging wording.

Return STRICT JSON, no markdown, matching this schema:
{
  "title": "Short quiz title",
  "topic": "Main topic (optional)",
  "questions": [
	{
	  "id": 1,
	  "question": "...",
	  "options": ["...","...","...","..."],
	  "correct_index": 2,
	  "explanation": "..."
	}
  ]
}

Rules:
- correct_index must be an integer from 0 to 3, matching options.
- Provide only valid JSON in the final answer.
"""
		)
		return "".join(parts)

	async def _call_gemini(self, prompt: str) -> Dict[str, Any]:
		logger.info("Generating practice quiz via Gemini")
		result = await self.gemini._generate_json_response(
			prompt=prompt,
			attachments=None,
			temperature=0.3,
			max_output_tokens=2048,
		)
		# Best-effort normalization
		return self._normalize_quiz_payload(result)

	def _normalize_quiz_payload(self, data: Dict[str, Any]) -> Dict[str, Any]:
		try:
			title = str(data.get("title") or "Practice Quiz")
			topic = data.get("topic")
			questions = data.get("questions") or []
			norm_qs: List[Dict[str, Any]] = []
			for i, q in enumerate(questions[:5]):
				# Ensure question item is a dict
				if not isinstance(q, dict):
					# Try to parse if it's a JSON string
					try:
						import json as _json
						if isinstance(q, str):
							q = _json.loads(q)
						else:
							# Skip unsupported type
							continue
					except Exception:
						# Skip invalid item
						continue

				text = str(q.get("question") or q.get("text") or "")
				options = q.get("options") or []
				# Fallback if model returned dict of options
				if isinstance(options, dict):
					options = [options.get(k) for k in sorted(options.keys()) if options.get(k)]
				elif isinstance(options, str):
					# Split into lines or semicolon list
					parts = [p.strip() for p in options.replace(";", "\n").splitlines() if p.strip()]
					options = parts
				options = [str(o) for o in options][:4]
				while len(options) < 4:
					options.append("")

				cidx = q.get("correct_index")
				if cidx is None:
					# Try letter mapping then text match
					correct_answer = q.get("correct_answer")
					if isinstance(correct_answer, str):
						letter = correct_answer.strip().upper()
						map_letter = {"A": 0, "B": 1, "C": 2, "D": 3}
						cidx = map_letter.get(letter)
						if cidx is None and options:
							# Match exact text to options
							try:
								cidx = options.index(correct_answer.strip())
							except ValueError:
								cidx = 0
					else:
						cidx = 0
				try:
					cidx = int(cidx)
				except Exception:
					cidx = 0
				cidx = max(0, min(3, cidx))

				norm_qs.append({
					"id": int(q.get("id") or i + 1),
					"question": text,
					"options": options,
					"correct_index": cidx,
					"explanation": q.get("explanation") or "",
				})

			# Ensure exactly 5
			if len(norm_qs) < 5:
				pad = 5 - len(norm_qs)
				for j in range(pad):
					norm_qs.append({
						"id": len(norm_qs) + 1,
						"question": "",
						"options": ["", "", "", ""],
						"correct_index": 0,
						"explanation": "",
					})

			return {"title": title, "topic": topic, "questions": norm_qs[:5]}
		except Exception:
			logger.exception("Failed to normalize quiz payload; returning minimal stub")
			return {"title": "Practice Quiz", "questions": []}

	@staticmethod
	def _join_list(values: Optional[List[str]]) -> Optional[str]:
		if not values:
			return None
		try:
			return "\n".join([str(v) for v in values if v])
		except Exception:
			return ", ".join([str(v) for v in values if v])


# Singleton instance
quiz_service = QuizService()

