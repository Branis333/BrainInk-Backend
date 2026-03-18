"""
Kana Agent Service
Conversational helper powered by Gemini with lightweight in-memory session state.

Responsibilities
- Maintain short-lived chat sessions (TTL) so Kana can keep context across turns
- Inject route/screen context into prompts so replies stay relevant to where the user is
- Call Gemini with guarded fallbacks and trimmed history to control token use
"""

import asyncio
import base64
import logging
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import google.generativeai as genai

from services.gemini_service import gemini_service
from tools.inline_attachment import build_inline_part

logger = logging.getLogger(__name__)

# Session constraints
MAX_HISTORY_MESSAGES = 20  # keep last N turns to bound prompt size
SESSION_TTL = timedelta(hours=6)  # expire idle sessions automatically


class KanaAgentService:
	"""Lightweight conversational layer for Kana.

	We keep minimal state in memory (session_id -> history, metadata) to provide
	contextual answers without persisting to the database. Sessions are keyed by
	UUID and pruned after SESSION_TTL.
	"""

	def __init__(self) -> None:
		self._sessions: Dict[str, Dict[str, Any]] = {}
		self._lock = asyncio.Lock()

	async def chat(
		self,
		*,
		user_id: int,
		message: str,
		session_id: Optional[str] = None,
		route: Optional[str] = None,
		screen_context: Optional[str] = None,
		metadata: Optional[Dict[str, Any]] = None,
		screen_capture: Optional[str] = None,
		screen_capture_mime: Optional[str] = None,
		client_history: Optional[List[Dict[str, Any]]] = None,
	) -> Dict[str, Any]:
		"""Send a message to Kana and return the reply plus updated history."""
		text = (message or "").strip()
		if not text:
			raise ValueError("Message cannot be empty")

		async with self._lock:
			self._prune_expired()
			sess_id, session = self._ensure_session(session_id=session_id, user_id=user_id)

			history: List[Dict[str, Any]] = session.setdefault("history", [])
			if client_history and not history:
				# Trust client-provided history only when the server session is new/empty
				normalized: List[Dict[str, Any]] = []
				for turn in client_history:
					role = (turn.get("role") if isinstance(turn, dict) else None) or "user"
					content = (turn.get("content") if isinstance(turn, dict) else None) or ""
					if not str(content).strip():
						continue
					normalized.append({
						"role": role,
						"content": str(content).strip(),
						"route": turn.get("route") if isinstance(turn, dict) else None,
						"screen_context": turn.get("screen_context") if isinstance(turn, dict) else None,
						"timestamp": (turn.get("timestamp") if isinstance(turn, dict) else None) or datetime.utcnow().isoformat() + "Z",
					})
				if normalized:
					session["history"] = normalized[-MAX_HISTORY_MESSAGES:]
					history = session["history"]
			now = datetime.utcnow()

			# Record the user turn
			history.append({
				"role": "user",
				"content": text,
				"route": route,
				"screen_context": screen_context,
				"timestamp": now.isoformat() + "Z",
			})
			session["updated_at"] = now
			session["metadata"] = metadata or session.get("metadata") or {}

			# Trim history to the most recent N turns
			if len(history) > MAX_HISTORY_MESSAGES:
				session["history"] = history[-MAX_HISTORY_MESSAGES:]
				history = session["history"]

		attachments: List[Any] = []
		if screen_capture:
			try:
				data = base64.b64decode(screen_capture)
				mime_type = screen_capture_mime or "image/jpeg"
				if len(data) > 1_800_000:
					raise ValueError("screen capture too large; please compress further")
				attachments.append(build_inline_part(data=data, mime_type=mime_type))
			except Exception as exc:  # noqa: BLE001
				logger.warning(
					"Invalid screen capture provided; ignoring",
					extra={"error": str(exc)},
				)

		prompt = self._build_prompt(
			history=history,
			route=route,
			screen_context=screen_context,
			user_id=user_id,
			metadata=metadata,
			has_visual=bool(attachments),
		)

		reply_text, used_model = await self._invoke_gemini(prompt, attachments=attachments or None)

		assistant_turn = {
			"role": "assistant",
			"content": reply_text,
			"route": route,
			"screen_context": screen_context,
			"timestamp": datetime.utcnow().isoformat() + "Z",
		}

		async with self._lock:
			# Session could be pruned between calls, so ensure it still exists
			sess_id, session = self._ensure_session(session_id=sess_id, user_id=user_id)
			history = session.setdefault("history", [])
			history.append(assistant_turn)
			if len(history) > MAX_HISTORY_MESSAGES:
				session["history"] = history[-MAX_HISTORY_MESSAGES:]
			session["updated_at"] = datetime.utcnow()

		return {
			"session_id": sess_id,
			"reply": reply_text,
			"model": used_model,
			"history": session["history"],
			"route": route,
			"screen_context": screen_context,
		}

	def _ensure_session(self, *, session_id: Optional[str], user_id: int) -> Tuple[str, Dict[str, Any]]:
		"""Return an existing session or create a new one for the user."""
		if session_id and session_id in self._sessions:
			session = self._sessions[session_id]
			# If the user changes, treat it as invalid to avoid cross-user leaks
			if session.get("user_id") != user_id:
				raise PermissionError("Session belongs to a different user")
			return session_id, session

		sess_id = session_id or str(uuid.uuid4())
		session = {
			"user_id": user_id,
			"created_at": datetime.utcnow(),
			"updated_at": datetime.utcnow(),
			"history": [],
			"metadata": {},
		}
		self._sessions[sess_id] = session
		return sess_id, session

	def _prune_expired(self) -> None:
		"""Remove sessions that have been idle beyond SESSION_TTL."""
		now = datetime.utcnow()
		expired = [sid for sid, data in self._sessions.items() if now - data.get("updated_at", now) > SESSION_TTL]
		for sid in expired:
			self._sessions.pop(sid, None)
		if expired:
			logger.info("🧹 Pruned Kana sessions", extra={"expired": expired})

	def _build_prompt(
		self,
		*,
		history: List[Dict[str, Any]],
		route: Optional[str],
		screen_context: Optional[str],
		user_id: int,
		metadata: Optional[Dict[str, Any]],
		has_visual: bool = False,
	) -> str:
		"""Compose the prompt with system guidance, route-aware context, and history."""
		system_preamble = (
			"You are Kana, a concise, friendly educational co-pilot. "
			"Provide direct, actionable answers for the current screen. "
			"If you need more detail, ask one short clarifying question. "
			"Stay under 6 sentences, avoid emojis, and do not fabricate data."
		)

		context_lines = [
			f"Current route: {route or 'unknown'}",
			f"Screen context: {screen_context or 'none provided'}",
			f"User id: {user_id}",
			f"Visual context: {'screenshot attached' if has_visual else 'none provided'}",
		]
		if metadata:
			for key, value in metadata.items():
				context_lines.append(f"{key}: {value}")

		history_lines: List[str] = []
		for turn in history[-MAX_HISTORY_MESSAGES:]:
			role = turn.get("role", "user")
			content = (turn.get("content") or "").strip()
			if not content:
				continue
			prefix = "User" if role == "user" else "Kana"
			history_lines.append(f"{prefix}: {content}")

		history_block = "\n".join(history_lines).strip()

		prompt = (
			f"{system_preamble}\n\n"
			f"Context:\n" + "\n".join(context_lines) + "\n\n"
			f"Conversation so far:\n{history_block}\n\n"
			"Reply as Kana to the latest user message above."
		)
		return prompt

	async def _invoke_gemini(self, prompt: str, attachments: Optional[List[Any]] = None) -> Tuple[str, str]:
		"""Call Gemini with fallbacks, returning (text, model_name)."""
		last_error: Optional[Exception] = None

		if attachments:
			vision_sequence = [
				"gemini-1.5-flash-latest",
				"gemini-1.5-flash",
				"gemini-2.0-flash-latest",
				"gemini-2.0-flash",
				"gemini-2.5-flash-latest",
				"gemini-2.5-flash",
			]
			if getattr(gemini_service.config, "allow_paid", False):
				vision_sequence = [
					"gemini-1.0-pro-vision-latest",
					"gemini-pro-vision",
					"gemini-1.5-pro-latest",
				] + vision_sequence
			model_sequence = vision_sequence + [
				m for m in gemini_service.config.get_model_sequence() if m not in vision_sequence
			]
		else:
			model_sequence = gemini_service.config.get_model_sequence()

		for model_name in model_sequence:
			try:
				payload = (
					gemini_service._build_content_payload(prompt, attachments)
					if attachments
					else prompt
				)
				model = gemini_service.config.get_model(model_name)
				response = await asyncio.to_thread(
					lambda: model.generate_content(
						payload,
						generation_config=genai.types.GenerationConfig(
							temperature=0.35,
							max_output_tokens=768,
							top_p=0.9,
							top_k=32,
						),
						safety_settings=gemini_service.config.get_safety_settings(),
					)
				)

				text = gemini_service._collect_candidate_text(response)
				gemini_service._log_candidate_metadata(response, model_name=model_name)
				return text.strip(), model_name
			except Exception as exc:  # noqa: BLE001
				last_error = exc
				logger.warning(
					"Kana Gemini call failed; trying fallback",
					extra={
						"model_name": model_name,
						"error": str(exc),
						"has_attachments": bool(attachments),
					},
				)
				continue

		raise RuntimeError(f"Kana agent could not reach Gemini: {last_error}")


kana_agent_service = KanaAgentService()
