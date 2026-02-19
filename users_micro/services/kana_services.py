"""
Kana Step Learning Service

Separate from legacy agent service. This service powers a guided, step-by-step
learning flow where:
- A student question is segmented into logical steps.
- Only one step is active at a time.
- Clarify chats are scoped to the active step context.
- Continue advances progression until completion.
"""

from __future__ import annotations

import asyncio
import base64
import logging
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from services.gemini_service import gemini_service
from tools.inline_attachment import build_inline_part

logger = logging.getLogger(__name__)

SESSION_TTL = timedelta(hours=8)
MAX_STEPS = 12
MIN_STEPS = 2
MAX_IMAGE_BYTES = 8 * 1024 * 1024


class KanaLearningService:
	def __init__(self) -> None:
		self._sessions: Dict[str, Dict[str, Any]] = {}
		self._lock = asyncio.Lock()

	async def start_session(
		self,
		*,
		user_id: int,
		question: str,
		route: Optional[str] = None,
		screen_context: Optional[str] = None,
		metadata: Optional[Dict[str, Any]] = None,
		image_base64: Optional[str] = None,
		image_mime: Optional[str] = None,
	) -> Dict[str, Any]:
		prompt = (question or "").strip()
		if not prompt:
			raise ValueError("Question cannot be empty")

		steps_payload = await self._generate_steps(
			question=prompt,
			route=route,
			screen_context=screen_context,
			metadata=metadata,
			image_base64=image_base64,
			image_mime=image_mime,
		)

		steps = self._normalize_steps(steps_payload)
		if not steps:
			raise RuntimeError("Kana could not generate learning steps")

		session_id = str(uuid.uuid4())
		now = datetime.utcnow()
		session = {
			"session_id": session_id,
			"user_id": user_id,
			"question": prompt,
			"route": route,
			"screen_context": screen_context,
			"metadata": metadata or {},
			"steps": steps,
			"current_step_index": 0,
			"clarify_threads": {},
			"completed": False,
			"created_at": now,
			"updated_at": now,
		}

		async with self._lock:
			self._prune_expired_locked()
			self._sessions[session_id] = session

		return self._build_public_state(session)

	async def get_session(self, *, user_id: int, session_id: str) -> Dict[str, Any]:
		async with self._lock:
			self._prune_expired_locked()
			session = self._require_session_locked(user_id=user_id, session_id=session_id)
			return self._build_public_state(session)

	async def clarify_current_step(
		self,
		*,
		user_id: int,
		session_id: str,
		message: str,
		image_base64: Optional[str] = None,
		image_mime: Optional[str] = None,
	) -> Dict[str, Any]:
		text = (message or "").strip()
		if not text:
			raise ValueError("Clarify message cannot be empty")

		async with self._lock:
			self._prune_expired_locked()
			session = self._require_session_locked(user_id=user_id, session_id=session_id)
			if session.get("completed"):
				raise ValueError("Session is already completed")

			step_index = int(session.get("current_step_index", 0))
			step = session["steps"][step_index]

			clarify_threads: Dict[str, List[Dict[str, Any]]] = session.setdefault("clarify_threads", {})
			step_key = str(step_index)
			thread = clarify_threads.setdefault(step_key, [])

		reply = await self._generate_clarification(
			question=session["question"],
			step=step,
			clarify_history=thread,
			learner_message=text,
			image_base64=image_base64,
			image_mime=image_mime,
		)

		turn_user = {
			"role": "user",
			"content": text,
			"timestamp": datetime.utcnow().isoformat() + "Z",
		}
		turn_assistant = {
			"role": "assistant",
			"content": reply,
			"timestamp": datetime.utcnow().isoformat() + "Z",
		}

		async with self._lock:
			session = self._require_session_locked(user_id=user_id, session_id=session_id)
			if session.get("completed"):
				raise ValueError("Session is already completed")
			step_index = int(session.get("current_step_index", 0))
			step_key = str(step_index)
			thread = session.setdefault("clarify_threads", {}).setdefault(step_key, [])
			thread.append(turn_user)
			thread.append(turn_assistant)
			session["updated_at"] = datetime.utcnow()
			state = self._build_public_state(session)

		return {
			"session": state,
			"clarify_reply": reply,
			"clarify_history": state.get("current_step", {}).get("clarify_history", []),
		}

	async def continue_step(self, *, user_id: int, session_id: str) -> Dict[str, Any]:
		async with self._lock:
			self._prune_expired_locked()
			session = self._require_session_locked(user_id=user_id, session_id=session_id)

			if session.get("completed"):
				return self._build_public_state(session)

			current_idx = int(session.get("current_step_index", 0))
			last_index = len(session["steps"]) - 1

			if current_idx >= last_index:
				session["completed"] = True
			else:
				session["current_step_index"] = current_idx + 1

			session["updated_at"] = datetime.utcnow()
			return self._build_public_state(session)

	async def restart_session(self, *, user_id: int, session_id: str) -> Dict[str, Any]:
		async with self._lock:
			self._prune_expired_locked()
			session = self._require_session_locked(user_id=user_id, session_id=session_id)
			session["current_step_index"] = 0
			session["completed"] = False
			session["clarify_threads"] = {}
			session["updated_at"] = datetime.utcnow()
			return self._build_public_state(session)

	async def _generate_steps(
		self,
		*,
		question: str,
		route: Optional[str],
		screen_context: Optional[str],
		metadata: Optional[Dict[str, Any]],
		image_base64: Optional[str],
		image_mime: Optional[str],
	) -> Dict[str, Any]:
		context_lines = [
			f"route={route or 'unknown'}",
			f"screen_context={screen_context or 'none'}",
		]
		if metadata:
			for key, value in metadata.items():
				context_lines.append(f"{key}={value}")

		attachments = self._build_image_attachments(image_base64=image_base64, image_mime=image_mime)
		prompt = (
			"You are Kana, an educational AI tutor for children and teens.\n"
			"Task: Break the learner's problem into concise, logical, ordered steps.\n"
			"Return ONLY valid JSON with this exact shape:\n"
			"{\n"
			"  \"problem_summary\": \"string\",\n"
			"  \"steps\": [\n"
			"    {\n"
			"      \"step_number\": 1,\n"
			"      \"title\": \"short step title\",\n"
			"      \"explanation\": \"clear explanation for this step\",\n"
			"      \"check_question\": \"short question to verify understanding\"\n"
			"    }\n"
			"  ]\n"
			"}\n"
			"Rules:\n"
			"- 2 to 8 steps only.\n"
			"- Keep each explanation actionable and child-friendly.\n"
			"- Do NOT solve all future steps inside one step.\n"
			"- No markdown, no code fences, no extra keys.\n\n"
			f"Learner question:\n{question}\n\n"
			f"Context:\n" + "\n".join(context_lines)
		)

		try:
			payload = await gemini_service._generate_json_response(
				prompt,
				attachments=attachments or None,
				temperature=0.25,
				max_output_tokens=1400,
			)
			if isinstance(payload, dict):
				return payload
		except Exception as exc:  # noqa: BLE001
			logger.warning("Kana step generation failed, using fallback", extra={"error": str(exc)})

		return {
			"problem_summary": question,
			"steps": [
				{
					"step_number": 1,
					"title": "Understand the problem",
					"explanation": "Restate what is being asked and identify the known values.",
					"check_question": "Can you point out what the problem asks you to find?",
				},
				{
					"step_number": 2,
					"title": "Apply the method",
					"explanation": "Choose the right rule or formula and apply it carefully to the known values.",
					"check_question": "Do you see why this rule fits the problem?",
				},
				{
					"step_number": 3,
					"title": "Verify the result",
					"explanation": "Check your final answer against the original problem and confirm it makes sense.",
					"check_question": "Does your answer satisfy the original question?",
				},
			],
		}

	async def _generate_clarification(
		self,
		*,
		question: str,
		step: Dict[str, Any],
		clarify_history: List[Dict[str, Any]],
		learner_message: str,
		image_base64: Optional[str],
		image_mime: Optional[str],
	) -> str:
		history_lines: List[str] = []
		for turn in clarify_history[-10:]:
			role = "Learner" if turn.get("role") == "user" else "Kana"
			content = (turn.get("content") or "").strip()
			if content:
				history_lines.append(f"{role}: {content}")

		history_block = "\n".join(history_lines) if history_lines else "(no prior clarification messages)"

		attachments = self._build_image_attachments(image_base64=image_base64, image_mime=image_mime)
		prompt = (
			"You are Kana in CLARIFY mode.\n"
			"Only explain the CURRENT STEP context.\n"
			"Do NOT advance to the next step.\n"
			"Be concise, concrete, and student-friendly.\n"
			"End with one short check-for-understanding question.\n\n"
			f"Original learner problem:\n{question}\n\n"
			"Current step data:\n"
			f"- step_number: {step.get('step_number')}\n"
			f"- title: {step.get('title')}\n"
			f"- explanation: {step.get('explanation')}\n"
			f"- check_question: {step.get('check_question')}\n\n"
			f"Clarify chat history for this same step:\n{history_block}\n\n"
			f"Latest learner clarify message:\n{learner_message}\n\n"
			"Return plain text only."
		)

		try:
			response = await gemini_service._generate_json_response(
				(
					"Return JSON only in shape {\"reply\":\"...\"}.\n"
					+ prompt
				),
				attachments=attachments or None,
				temperature=0.2,
				max_output_tokens=700,
			)
			reply = (response or {}).get("reply")
			if isinstance(reply, str) and reply.strip():
				return reply.strip()
		except Exception:
			pass

		try:
			model = gemini_service.config.get_model()
			if attachments:
				payload = gemini_service._build_content_payload(prompt, attachments)
			else:
				payload = prompt
			raw = await asyncio.to_thread(lambda: model.generate_content(payload))
			text = gemini_service._collect_candidate_text(raw).strip()
			if text:
				return text
		except Exception as exc:  # noqa: BLE001
			logger.warning("Kana clarification generation failed", extra={"error": str(exc)})

		return "Great question. In this step, focus on the rule being applied and why it matches the values we identified. Which part feels unclear right now?"

	def _normalize_steps(self, payload: Dict[str, Any]) -> List[Dict[str, Any]]:
		raw_steps = payload.get("steps") if isinstance(payload, dict) else None
		if not isinstance(raw_steps, list):
			return []

		normalized: List[Dict[str, Any]] = []
		for idx, item in enumerate(raw_steps[:MAX_STEPS]):
			if not isinstance(item, dict):
				continue
			title = str(item.get("title") or f"Step {idx + 1}").strip()
			explanation = str(item.get("explanation") or "").strip()
			if not explanation:
				continue
			check_question = str(item.get("check_question") or "Do you want to continue?").strip()
			step_number = item.get("step_number")
			try:
				parsed_step_number = int(step_number)
			except Exception:
				parsed_step_number = idx + 1

			normalized.append(
				{
					"step_number": parsed_step_number,
					"title": title,
					"explanation": explanation,
					"check_question": check_question,
				}
			)

		if len(normalized) < MIN_STEPS:
			return []

		for i, step in enumerate(normalized):
			step["step_number"] = i + 1
		return normalized

	def _build_public_state(self, session: Dict[str, Any]) -> Dict[str, Any]:
		steps: List[Dict[str, Any]] = session.get("steps", [])
		current_index = int(session.get("current_step_index", 0))
		completed = bool(session.get("completed"))

		if steps:
			current_index = max(0, min(current_index, len(steps) - 1))
			current_step = steps[current_index]
		else:
			current_step = None

		thread = session.get("clarify_threads", {}).get(str(current_index), [])

		return {
			"session_id": session["session_id"],
			"question": session.get("question"),
			"current_step_index": current_index,
			"total_steps": len(steps),
			"completed": completed,
			"current_step": {
				**(current_step or {}),
				"clarify_history": thread,
			} if current_step else None,
			"steps_overview": [
				{
					"step_number": step.get("step_number"),
					"title": step.get("title"),
					"is_current": idx == current_index and not completed,
					"is_completed": idx < current_index or completed,
				}
				for idx, step in enumerate(steps)
			],
			"route": session.get("route"),
			"screen_context": session.get("screen_context"),
			"updated_at": session.get("updated_at").isoformat() + "Z" if session.get("updated_at") else None,
		}

	def _require_session_locked(self, *, user_id: int, session_id: str) -> Dict[str, Any]:
		session = self._sessions.get(session_id)
		if not session:
			raise KeyError("Session not found")
		if session.get("user_id") != user_id:
			raise PermissionError("Session belongs to another user")
		return session

	def _prune_expired_locked(self) -> None:
		now = datetime.utcnow()
		expired_ids = [
			sid
			for sid, data in self._sessions.items()
			if now - data.get("updated_at", now) > SESSION_TTL
		]
		for sid in expired_ids:
			self._sessions.pop(sid, None)
		if expired_ids:
			logger.info("Pruned Kana learning sessions", extra={"count": len(expired_ids)})

	def _build_image_attachments(
		self,
		*,
		image_base64: Optional[str],
		image_mime: Optional[str],
	) -> List[Any]:
		if not image_base64:
			return []

		try:
			decoded = base64.b64decode(image_base64)
		except Exception:
			logger.warning("Invalid image base64 provided to Kana; skipping image context")
			return []

		if not decoded:
			return []
		if len(decoded) > MAX_IMAGE_BYTES:
			logger.warning("Kana image context too large; skipping", extra={"bytes": len(decoded)})
			return []

		mime = (image_mime or "image/jpeg").strip().lower()
		if not mime.startswith("image/"):
			mime = "image/jpeg"

		try:
			return [build_inline_part(data=decoded, mime_type=mime, display_name="kana-context-image")]
		except Exception as exc:  # noqa: BLE001
			logger.warning("Failed to build Kana image attachment", extra={"error": str(exc)})
			return []


kana_learning_service = KanaLearningService()

