"""
Kana Agent Endpoints

Conversational AI entrypoint powered by Gemini. Keeps lightweight server-side
session state so Kana can stay aware of the user's navigation context.
"""

import logging
from fastapi import APIRouter, Depends, HTTPException, status

from Endpoints.auth import get_current_user
from schemas.afterschool_schema import (
	KanaChatRequest,
	KanaChatResponse,
	KanaTTSRequest,
	KanaTTSResponse,
)
from services.agent_services import kana_agent_service
from services.kokoro_tts_service import kokoro_tts_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/after-school/kana", tags=["Kana Agent"])


user_dependency = Depends(get_current_user)


def _require_user_id(current_user: dict) -> int:
	if not current_user:
		raise HTTPException(
			status_code=status.HTTP_401_UNAUTHORIZED,
			detail="Missing authentication",
		)

	user_id_raw = current_user.get("user_id") or current_user.get("id")
	if user_id_raw is None:
		raise HTTPException(
			status_code=status.HTTP_401_UNAUTHORIZED,
			detail="Invalid authentication payload",
		)

	try:
		return int(user_id_raw)
	except (TypeError, ValueError) as exc:
		raise HTTPException(
			status_code=status.HTTP_401_UNAUTHORIZED,
			detail="Invalid user id in token",
		) from exc
@router.post("/chat", response_model=KanaChatResponse)
async def chat_with_kana(payload: KanaChatRequest, current_user: dict = user_dependency):
	"""Send a message to Kana and return the model's reply."""
	try:
		user_id = _require_user_id(current_user)
		result = await kana_agent_service.chat(
			user_id=user_id,
			message=payload.message,
			session_id=payload.session_id,
			route=payload.route,
			screen_context=payload.screen_context,
			metadata=payload.metadata,
			screen_capture=payload.screen_capture,
			screen_capture_mime=payload.screen_capture_mime,
			client_history=[h.dict() for h in payload.history] if payload.history else None,
		)
		return KanaChatResponse(**result)
	except PermissionError:
		raise HTTPException(
			status_code=status.HTTP_403_FORBIDDEN,
			detail="Session belongs to a different user",
		)
	except ValueError as exc:
		raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
	except Exception as exc:  # noqa: BLE001
		logger.exception("Kana chat failed", extra={"error": str(exc)})
		raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Kana failed to respond")
<<<<<<< HEAD


@router.post("/tts", response_model=KanaTTSResponse)
async def kana_tts(payload: KanaTTSRequest, current_user: dict = user_dependency):
	"""Generate Kokoro audio for Kana's reply."""
	_ = _require_user_id(current_user)
	try:
		result = await kokoro_tts_service.synthesize(
			text=payload.text,
			voice=payload.voice,
			speed=payload.speed or 1.0,
		)
		return KanaTTSResponse(**result)
	except ValueError as exc:
		raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
	except RuntimeError as exc:
		logger.exception("Kana TTS synthesis failed", extra={"error": str(exc)})
		raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Kana TTS is unavailable")
