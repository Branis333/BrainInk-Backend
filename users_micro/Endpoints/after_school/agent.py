"""
Kana Agent Endpoints

Conversational AI entrypoint powered by Gemini. Keeps lightweight server-side
session state so Kana can stay aware of the user's navigation context.
"""

import logging
from fastapi import APIRouter, Depends, HTTPException, status

from Endpoints.auth import get_current_user
from schemas.afterschool_schema import KanaChatRequest, KanaChatResponse
from services.agent_services import kana_agent_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/after-school/kana", tags=["Kana Agent"])

user_dependency = Depends(get_current_user)


@router.post("/chat", response_model=KanaChatResponse)
async def chat_with_kana(payload: KanaChatRequest, current_user: dict = user_dependency):
	"""Send a message to Kana and return the model's reply."""
	try:
		user_id = int(current_user.get("id")) if current_user else 0
		result = await kana_agent_service.chat(
			user_id=user_id,
			message=payload.message,
			session_id=payload.session_id,
			route=payload.route,
			screen_context=payload.screen_context,
			metadata=payload.metadata,
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
