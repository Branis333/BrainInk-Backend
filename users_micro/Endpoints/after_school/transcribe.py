import logging
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status

from Endpoints.auth import get_current_user
from services.transcribe_service import transcribe_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/after-school/transcribe", tags=["Transcription"])
user_dependency = Depends(get_current_user)


@router.post("/audio")
async def transcribe_audio(
	audio: UploadFile = File(..., description="Audio file to transcribe"),
	instructions: str = Form(
		default=None,
		description="Optional guidance (e.g., 'strip filler words', 'summarize at end')",
	),
	current_user: dict = user_dependency,
):
	"""Transcribe an uploaded audio clip using Gemini and return plain text."""

	if not current_user:
		raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing authentication")

	try:
		file_bytes = await audio.read()
		result = await transcribe_service.transcribe_audio(
			file_bytes=file_bytes,
			filename=audio.filename or "audio",
			instructions=instructions,
		)
		return result
	except ValueError as exc:
		raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
	except RuntimeError as exc:
		raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
	except Exception as exc:  # noqa: BLE001
		logger.exception("Unexpected transcription error", extra={"error": str(exc)})
		raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Transcription failed")
