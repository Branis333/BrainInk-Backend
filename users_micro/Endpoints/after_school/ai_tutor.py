from __future__ import annotations

from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from sqlalchemy.orm import Session

from db.connection import db_dependency
from Endpoints.auth import get_current_user
from schemas.ai_tutor_schemas import (
    SessionStartRequest,
    SessionStartResponse,
    TutorMessageRequest,
    TutorTurn,
    TutorCheckpointRequest,
    TutorCheckpointResponse,
    TutorSessionDetail,
    TutorInteractionOut,
    TutorMessageRole,
    TutorInputType,
    TutorSessionListItem,
    TutorSessionListResponse,
    TutorCompletionRequest,
    LessonPlanResponse,
    TutorSessionStatus,  # for typing
)
from schemas.ai_tutor_schemas import (
    BaseModel,
    Field,
)
from schemas.ai_tutor_schemas import TutorSessionStatus as TutorSessionStatusSchema, TutorCheckpointType
from services.ai_tutor_service import ai_tutor_service
from models.ai_tutor_models import AITutorInteraction, TutorInteractionRole, TutorInteractionInputType

router = APIRouter(prefix="/after-school/ai-tutor", tags=["AI Tutor"])

user_dependency = Depends(get_current_user)


@router.post("/sessions", response_model=SessionStartResponse, status_code=status.HTTP_201_CREATED)
async def start_ai_tutor_session(
    request: SessionStartRequest,
    db: db_dependency,
    current_user: dict = user_dependency,
):
    snapshot, tutor_turn = await ai_tutor_service.start_session(
        student_id=current_user["user_id"],
        request=request,
        db=db,
    )
    return SessionStartResponse(session=snapshot, tutor_turn=tutor_turn)


@router.post("/sessions/{session_id}/message", response_model=TutorTurn)
async def send_ai_tutor_message(
    session_id: int,
    message_request: TutorMessageRequest,
    db: db_dependency,
    current_user: dict = user_dependency,
):
    return await ai_tutor_service.process_student_message(
        session_id=session_id,
        student_id=current_user["user_id"],
        message_request=message_request,
        db=db,
    )


@router.post("/sessions/{session_id}/checkpoint", response_model=TutorCheckpointResponse)
async def submit_ai_tutor_checkpoint(
    session_id: int,
    db: db_dependency,
    checkpoint_type: TutorCheckpointType = Form(...),
    notes: Optional[str] = Form(None),
    artifact: Optional[UploadFile] = File(None),
    current_user: dict = user_dependency,
):
    file_bytes = await artifact.read() if artifact else None
    file_name = artifact.filename if artifact else None
    content_type = artifact.content_type if artifact else None

    checkpoint_request = TutorCheckpointRequest(checkpoint_type=checkpoint_type, notes=notes)

    return await ai_tutor_service.submit_checkpoint(
        session_id=session_id,
        student_id=current_user["user_id"],
        request=checkpoint_request,
        file_bytes=file_bytes,
        file_name=file_name,
        content_type=content_type,
        db=db,
    )


@router.post("/sessions/{session_id}/complete", response_model=TutorSessionDetail)
async def complete_ai_tutor_session(
    session_id: int,
    completion_request: TutorCompletionRequest,
    db: db_dependency,
    current_user: dict = user_dependency,
):
    snapshot = await ai_tutor_service.complete_session(
        session_id=session_id,
        student_id=current_user["user_id"],
        feedback=completion_request.feedback,
        db=db,
    )
    _, interactions = ai_tutor_service.get_session_detail(
        session_id=session_id,
        student_id=current_user["user_id"],
        db=db,
    )
    interactions_out = _serialize_interactions(interactions)
    return TutorSessionDetail(session=snapshot, interactions=interactions_out)


# IMPORTANT: Place static route "/sessions/resume" before dynamic "/sessions/{session_id}"
@router.get("/sessions/resume", response_model=SessionStartResponse)
async def resume_ai_tutor_session(
    db: db_dependency,
    current_user: dict = user_dependency,
    course_id: Optional[int] = None,
    block_id: Optional[int] = None,
    lesson_id: Optional[int] = None,
):
    """Resume the latest open AI Tutor session for the current user.

    Optional filters (course_id, block_id, lesson_id) can be supplied to
    target a specific content context. Returns the session snapshot and
    the next tutor turn (from the pre-generated lesson plan when available).
    """
    snapshot, tutor_turn = await ai_tutor_service.resume_session(
        student_id=current_user["user_id"],
        db=db,
        course_id=course_id,
        block_id=block_id,
        lesson_id=lesson_id,
    )
    return SessionStartResponse(session=snapshot, tutor_turn=tutor_turn)


@router.get("/sessions", response_model=TutorSessionListResponse)
async def list_ai_tutor_sessions(
    db: db_dependency,
    current_user: dict = user_dependency,
):
    sessions = ai_tutor_service.list_sessions(student_id=current_user["user_id"], db=db)
    items = [
        TutorSessionListItem(
            session_id=session.id,
            status=TutorSessionStatusSchema(session.status.value),
            course_id=session.course_id,
            block_id=session.block_id,
            lesson_id=session.lesson_id,
            created_at=session.started_at,
            updated_at=session.updated_at,
            completed_at=session.completed_at,
        )
        for session in sessions
    ]
    return TutorSessionListResponse(items=items, total=len(items))


@router.get("/sessions/{session_id}", response_model=TutorSessionDetail)
async def get_ai_tutor_session(
    session_id: int,
    db: db_dependency,
    current_user: dict = user_dependency,
):
    snapshot, interactions = ai_tutor_service.get_session_detail(
        session_id=session_id,
        student_id=current_user["user_id"],
        db=db,
    )
    interaction_models = _serialize_interactions(interactions)
    return TutorSessionDetail(session=snapshot, interactions=interaction_models)


def _serialize_interactions(interactions: List[AITutorInteraction]) -> List[TutorInteractionOut]:
    role_map = {
        TutorInteractionRole.SYSTEM: TutorMessageRole.system,
        TutorInteractionRole.TUTOR: TutorMessageRole.tutor,
        TutorInteractionRole.STUDENT: TutorMessageRole.student,
    }
    input_map = {
        TutorInteractionInputType.TEXT: TutorInputType.text,
        TutorInteractionInputType.VOICE: TutorInputType.voice,
        TutorInteractionInputType.CHECKPOINT: TutorInputType.checkpoint,
        TutorInteractionInputType.IMAGE: TutorInputType.checkpoint,
    }

    serialized: List[TutorInteractionOut] = []
    for interaction in interactions:
        role = role_map.get(interaction.role)
        if not role:
            continue
        input_type = input_map.get(interaction.input_type, TutorInputType.text)
        serialized.append(
            TutorInteractionOut(
                id=interaction.id,
                role=role,
                content=interaction.content,
                input_type=input_type,
                created_at=interaction.created_at,
            )
        )
    return serialized


class LearnerProfileResponse(BaseModel):
    learner_profile: dict = Field(default_factory=dict)


@router.get("/learner-profile", response_model=LearnerProfileResponse)
async def get_learner_profile(
    db: db_dependency,
    current_user: dict = user_dependency,
):
    # Prefer stored profile; fall back to computing from history
    from models.ai_tutor_models import LearnerProfile
    row = (
        db.query(LearnerProfile)
        .filter(LearnerProfile.student_id == current_user["user_id"], LearnerProfile.course_id == None)
        .first()
    )
    if row:
        profile = {
            "topics": row.topics or [],
            "recent_sessions": row.recent_sessions or [],
            "streak_days": row.streak_days or 0,
        }
    else:
        profile = ai_tutor_service._build_learner_profile(db, current_user["user_id"], course_id=None)
    return LearnerProfileResponse(learner_profile=profile)


@router.get("/sessions/{session_id}/lesson-plan", response_model=LessonPlanResponse)
async def get_lesson_plan(
    session_id: int,
    db: db_dependency,
    current_user: dict = user_dependency,
):
    plan = ai_tutor_service.get_lesson_plan(
        session_id=session_id,
        student_id=current_user["user_id"],
        db=db,
    )
    return LessonPlanResponse(lesson_plan=plan)
