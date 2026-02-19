from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel, Field

from Endpoints.auth import get_current_user
from services.kana_services import kana_learning_service
from services.transcribe_service import transcribe_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/after-school/kana-learning", tags=["Kana Learning"])
user_dependency = Depends(get_current_user)


class KanaLearningStartRequest(BaseModel):
	question: str = Field(..., min_length=1, max_length=1500)
	route: Optional[str] = None
	screen_context: Optional[str] = None
	metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)
	image_base64: Optional[str] = Field(None, description="Optional base64 image for visual context")
	image_mime: Optional[str] = Field(None, description="MIME type for image_base64 (e.g. image/jpeg)")


class KanaClarifyRequest(BaseModel):
	message: str = Field(..., min_length=1, max_length=1200)
	image_base64: Optional[str] = Field(None, description="Optional base64 image for visual context")
	image_mime: Optional[str] = Field(None, description="MIME type for image_base64 (e.g. image/jpeg)")


class KanaStepOverviewItem(BaseModel):
	step_number: int
	title: str
	is_current: bool
	is_completed: bool


class KanaClarifyTurn(BaseModel):
	role: str
	content: str
	timestamp: Optional[str] = None


class KanaCurrentStep(BaseModel):
	step_number: int
	title: str
	explanation: str
	check_question: str
	clarify_history: List[KanaClarifyTurn] = Field(default_factory=list)


class KanaLearningSessionState(BaseModel):
	session_id: str
	question: str
	current_step_index: int
	total_steps: int
	completed: bool
	current_step: Optional[KanaCurrentStep] = None
	steps_overview: List[KanaStepOverviewItem] = Field(default_factory=list)
	route: Optional[str] = None
	screen_context: Optional[str] = None
	updated_at: Optional[str] = None


class KanaClarifyResponse(BaseModel):
	session: KanaLearningSessionState
	clarify_reply: str
	clarify_history: List[KanaClarifyTurn] = Field(default_factory=list)


def _require_user_id(current_user: dict) -> int:
	if not current_user:
		raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing authentication")
	user_id_raw = current_user.get("user_id") or current_user.get("id")
	if user_id_raw is None:
		raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authentication payload")
	try:
		return int(user_id_raw)
	except (TypeError, ValueError) as exc:
		raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid user id in token") from exc


@router.post("/sessions", response_model=KanaLearningSessionState, status_code=status.HTTP_201_CREATED)
async def start_kana_learning_session(payload: KanaLearningStartRequest, current_user: dict = user_dependency):
	try:
		user_id = _require_user_id(current_user)
		state = await kana_learning_service.start_session(
			user_id=user_id,
			question=payload.question,
			route=payload.route,
			screen_context=payload.screen_context,
			metadata=payload.metadata,
			image_base64=payload.image_base64,
			image_mime=payload.image_mime,
		)
		return KanaLearningSessionState(**state)
	except ValueError as exc:
		raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
	except Exception as exc:  # noqa: BLE001
		logger.exception("Failed to start Kana learning session", extra={"error": str(exc)})
		raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Kana could not start this session")


@router.get("/sessions/{session_id}", response_model=KanaLearningSessionState)
async def get_kana_learning_session(session_id: str, current_user: dict = user_dependency):
	try:
		user_id = _require_user_id(current_user)
		state = await kana_learning_service.get_session(user_id=user_id, session_id=session_id)
		return KanaLearningSessionState(**state)
	except KeyError:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
	except PermissionError:
		raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Session belongs to another user")
	except Exception as exc:  # noqa: BLE001
		logger.exception("Failed to load Kana session", extra={"error": str(exc), "session_id": session_id})
		raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Could not load session")


@router.post("/sessions/{session_id}/clarify", response_model=KanaClarifyResponse)
async def clarify_kana_step(
	session_id: str,
	payload: KanaClarifyRequest,
	current_user: dict = user_dependency,
):
	try:
		user_id = _require_user_id(current_user)
		result = await kana_learning_service.clarify_current_step(
			user_id=user_id,
			session_id=session_id,
			message=payload.message,
			image_base64=payload.image_base64,
			image_mime=payload.image_mime,
		)
		return KanaClarifyResponse(
			session=KanaLearningSessionState(**result["session"]),
			clarify_reply=result["clarify_reply"],
			clarify_history=[KanaClarifyTurn(**item) for item in result.get("clarify_history", [])],
		)
	except KeyError:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
	except PermissionError:
		raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Session belongs to another user")
	except ValueError as exc:
		raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
	except Exception as exc:  # noqa: BLE001
		logger.exception("Kana clarify failed", extra={"error": str(exc), "session_id": session_id})
		raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Kana clarify failed")


@router.post("/sessions/{session_id}/continue", response_model=KanaLearningSessionState)
async def continue_kana_step(session_id: str, current_user: dict = user_dependency):
	try:
		user_id = _require_user_id(current_user)
		state = await kana_learning_service.continue_step(user_id=user_id, session_id=session_id)
		return KanaLearningSessionState(**state)
	except KeyError:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
	except PermissionError:
		raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Session belongs to another user")
	except Exception as exc:  # noqa: BLE001
		logger.exception("Kana continue failed", extra={"error": str(exc), "session_id": session_id})
		raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Kana continue failed")


@router.post("/sessions/{session_id}/restart", response_model=KanaLearningSessionState)
async def restart_kana_session(session_id: str, current_user: dict = user_dependency):
	try:
		user_id = _require_user_id(current_user)
		state = await kana_learning_service.restart_session(user_id=user_id, session_id=session_id)
		return KanaLearningSessionState(**state)
	except KeyError:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
	except PermissionError:
		raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Session belongs to another user")
	except Exception as exc:  # noqa: BLE001
		logger.exception("Kana restart failed", extra={"error": str(exc), "session_id": session_id})
		raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Kana restart failed")


@router.post("/sessions/audio", response_model=KanaLearningSessionState, status_code=status.HTTP_201_CREATED)
async def start_kana_learning_session_from_audio(
	audio: UploadFile = File(..., description="Audio question to transcribe and start Kana session"),
	route: Optional[str] = Form(default=None),
	screen_context: Optional[str] = Form(default=None),
	metadata: Optional[str] = Form(default=None, description="Optional JSON string metadata"),
	current_user: dict = user_dependency,
):
	"""Start Kana step-learning by transcribing an uploaded audio clip first."""
	try:
		user_id = _require_user_id(current_user)
		file_bytes = await audio.read()
		transcription = await transcribe_service.transcribe_audio(
			file_bytes=file_bytes,
			filename=audio.filename or "audio",
		)
		question = (transcription.get("transcript") or "").strip()
		if not question:
			raise ValueError("Transcription was empty")

		parsed_metadata: Dict[str, Any] = {}
		if metadata:
			try:
				maybe = json.loads(metadata)
				if isinstance(maybe, dict):
					parsed_metadata = maybe
			except Exception:
				parsed_metadata = {}

		parsed_metadata.update({
			"input_type": "audio",
			"audio_filename": audio.filename,
			"audio_mime_type": transcription.get("mime_type"),
			"transcription_model": transcription.get("model"),
		})

		state = await kana_learning_service.start_session(
			user_id=user_id,
			question=question,
			route=route,
			screen_context=screen_context,
			metadata=parsed_metadata,
		)
		return KanaLearningSessionState(**state)
	except ValueError as exc:
		raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
	except RuntimeError as exc:
		raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
	except Exception as exc:  # noqa: BLE001
		logger.exception("Failed to start Kana session from audio", extra={"error": str(exc)})
		raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Kana audio start failed")


@router.post("/sessions/{session_id}/clarify/audio", response_model=KanaClarifyResponse)
async def clarify_kana_step_from_audio(
	session_id: str,
	audio: UploadFile = File(..., description="Audio clarify message to transcribe"),
	current_user: dict = user_dependency,
):
	"""Clarify current step by transcribing an uploaded audio question first."""
	try:
		user_id = _require_user_id(current_user)
		file_bytes = await audio.read()
		transcription = await transcribe_service.transcribe_audio(
			file_bytes=file_bytes,
			filename=audio.filename or "audio",
		)
		message = (transcription.get("transcript") or "").strip()
		if not message:
			raise ValueError("Transcription was empty")

		result = await kana_learning_service.clarify_current_step(
			user_id=user_id,
			session_id=session_id,
			message=message,
		)
		return KanaClarifyResponse(
			session=KanaLearningSessionState(**result["session"]),
			clarify_reply=result["clarify_reply"],
			clarify_history=[KanaClarifyTurn(**item) for item in result.get("clarify_history", [])],
		)
	except KeyError:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
	except PermissionError:
		raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Session belongs to another user")
	except ValueError as exc:
		raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
	except RuntimeError as exc:
		raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
	except Exception as exc:  # noqa: BLE001
		logger.exception("Kana audio clarify failed", extra={"error": str(exc), "session_id": session_id})
		raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Kana audio clarify failed")

