from __future__ import annotations

import asyncio
import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from models.ai_tutor_models import (
    AITutorSession,
    AITutorInteraction,
    AITutorCheckpoint,
    TutorSessionStatus,
    TutorInteractionRole,
    TutorInteractionInputType,
    TutorCheckpointStatus,
)
from models.afterschool_models import CourseBlock, CourseLesson
from schemas.ai_tutor_schemas import (
    SessionStartRequest,
    TutorTurn,
    TutorTurnCheckpoint,
    TutorMessageRequest,
    TutorCheckpointRequest,
    TutorSessionSnapshot,
    TutorSessionStatus as TutorSessionStatusSchema,
    TutorCheckpointResponse,
)
from services.gemini_service import gemini_service


class AITutorService:
    """Core orchestrator for AI tutor sessions"""

    def __init__(self):
        self.gemini = gemini_service

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    async def start_session(
        self,
        student_id: int,
        request: SessionStartRequest,
        db: Session,
    ) -> Tuple[TutorSessionSnapshot, TutorTurn]:
        content_text, content_meta = self._load_learning_content(db, request)
        segments = self._segment_content(content_text)

        if not segments:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Selected content does not contain any readable text",
            )

        session = AITutorSession(
            student_id=student_id,
            course_id=request.course_id,
            block_id=request.block_id,
            lesson_id=request.lesson_id,
            status=TutorSessionStatus.IN_PROGRESS,
            current_segment_index=0,
            content_segments=[{"index": idx, "text": seg} for idx, seg in enumerate(segments)],
            persona_config={
                "persona": request.persona or "friendly",
                "learning_focus": request.preferred_learning_focus or "balanced"
            },
            tutor_settings={"source": content_meta},
        )
        db.add(session)
        db.flush()

        # Log system guidance for traceability
        system_message = AITutorInteraction(
            session_id=session.id,
            role=TutorInteractionRole.SYSTEM,
            content=json.dumps({
                "persona": session.persona_config,
                "content_meta": content_meta,
            }),
            input_type=TutorInteractionInputType.TEXT,
        )
        db.add(system_message)
        db.flush()

        tutor_turn = await self._generate_tutor_turn(db, session, learner_message=None)
        db.commit()
        db.refresh(session)
        return self._snapshot(session), tutor_turn

    async def process_student_message(
        self,
        session_id: int,
        student_id: int,
        message_request: TutorMessageRequest,
        db: Session,
    ) -> TutorTurn:
        session = self._require_session(db, session_id, student_id)

        if session.status in {TutorSessionStatus.COMPLETED, TutorSessionStatus.ABANDONED}:
            raise HTTPException(status_code=400, detail="Session is no longer active")

        interaction = AITutorInteraction(
            session_id=session.id,
            role=TutorInteractionRole.STUDENT,
            content=message_request.message,
            input_type=self._map_input_type(message_request.input_type),
            metadata_payload=message_request.metadata,
        )
        db.add(interaction)
        db.flush()

        tutor_turn = await self._generate_tutor_turn(db, session, learner_message=message_request.message)
        db.commit()
        db.refresh(session)
        return tutor_turn

    async def submit_checkpoint(
        self,
        session_id: int,
        student_id: int,
        request: TutorCheckpointRequest,
        file_bytes: Optional[bytes],
        file_name: Optional[str],
        content_type: Optional[str],
        db: Session,
    ) -> TutorCheckpointResponse:
        session = self._require_session(db, session_id, student_id)

        active_checkpoint = self._get_latest_open_checkpoint(session)
        if not active_checkpoint:
            raise HTTPException(status_code=400, detail="No checkpoint is awaiting submission")

        temp_file_path = None
        if file_bytes:
            temp_dir = Path(tempfile.mkdtemp(prefix="ai_tutor_"))
            temp_file_path = temp_dir / (file_name or "checkpoint_upload")
            temp_file_path.write_bytes(file_bytes)
            active_checkpoint.media_file_path = str(temp_file_path)
            active_checkpoint.media_mime_type = content_type

        active_checkpoint.status = TutorCheckpointStatus.ANALYZING
        active_checkpoint.response_payload = {
            "notes": request.notes,
            "submitted_at": datetime.utcnow().isoformat(),
        }
        db.flush()

        try:
            analysis = await self.gemini.analyze_student_work_with_gemini(
                prompt=active_checkpoint.prompt,
                file_path=str(temp_file_path) if temp_file_path else None,
                mime_type=content_type,
                learner_notes=request.notes,
            )
            active_checkpoint.ai_feedback = analysis.get("feedback")
            active_checkpoint.score = analysis.get("score")
            active_checkpoint.status = TutorCheckpointStatus.COMPLETED
            active_checkpoint.completed_at = datetime.utcnow()

            # Log tutor response based on analysis
            tutor_message = analysis.get("tutor_message")
            if tutor_message:
                db.add(
                    AITutorInteraction(
                        session_id=session.id,
                        role=TutorInteractionRole.TUTOR,
                        content=tutor_message,
                        input_type=TutorInteractionInputType.TEXT,
                        metadata_payload={"analysis": active_checkpoint.ai_feedback},
                    )
                )

            # Optionally advance to next segment automatically
            await self._advance_after_checkpoint(db, session, analysis)

        finally:
            if temp_file_path and temp_file_path.exists():
                try:
                    temp_file_path.unlink()
                    temp_file_path.parent.rmdir()
                except OSError:
                    pass

        db.commit()
        db.refresh(session)

        return TutorCheckpointResponse(
            checkpoint_id=active_checkpoint.id,
            status=active_checkpoint.status.value,
            ai_feedback=active_checkpoint.ai_feedback,
            score=active_checkpoint.score,
        )

    async def complete_session(
        self,
        session_id: int,
        student_id: int,
        feedback: Optional[str],
        db: Session,
    ) -> TutorSessionSnapshot:
        session = self._require_session(db, session_id, student_id)
        session.status = TutorSessionStatus.COMPLETED
        session.completed_at = datetime.utcnow()
        session.current_segment_index = min(
            session.current_segment_index,
            len(session.content_segments) - 1,
        )
        session.updated_at = datetime.utcnow()

        if feedback:
            db.add(
                AITutorInteraction(
                    session_id=session.id,
                    role=TutorInteractionRole.STUDENT,
                    content=f"SESSION_FEEDBACK::{feedback}",
                    input_type=TutorInteractionInputType.TEXT,
                )
            )
        db.commit()
        db.refresh(session)

        return self._snapshot(session)

    def get_session_detail(
        self,
        session_id: int,
        student_id: int,
        db: Session,
    ) -> Tuple[TutorSessionSnapshot, List[AITutorInteraction]]:
        session = self._require_session(db, session_id, student_id)
        snapshot = self._snapshot(session)
        return snapshot, session.interactions

    def list_sessions(
        self,
        student_id: int,
        db: Session,
    ) -> List[AITutorSession]:
        return (
            db.query(AITutorSession)
            .filter(AITutorSession.student_id == student_id)
            .order_by(AITutorSession.started_at.desc())
            .all()
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _load_learning_content(
        self,
        db: Session,
        request: SessionStartRequest,
    ) -> Tuple[str, Dict[str, Any]]:
        if request.block_id:
            block = (
                db.query(CourseBlock)
                .filter(CourseBlock.id == request.block_id)
                .first()
            )
            if not block:
                raise HTTPException(status_code=404, detail="Course block not found")
            if request.course_id and block.course_id != request.course_id:
                raise HTTPException(status_code=400, detail="Block does not belong to provided course")
            return (
                block.content or "",
                {
                    "type": "block",
                    "title": block.title,
                    "week": block.week,
                    "block_number": block.block_number,
                    "course_id": block.course_id,
                },
            )

        if request.lesson_id:
            lesson = (
                db.query(CourseLesson)
                .filter(CourseLesson.id == request.lesson_id)
                .first()
            )
            if not lesson:
                raise HTTPException(status_code=404, detail="Lesson not found")
            if request.course_id and lesson.course_id != request.course_id:
                raise HTTPException(status_code=400, detail="Lesson does not belong to provided course")
            return (
                lesson.content or "",
                {
                    "type": "lesson",
                    "title": lesson.title,
                    "course_id": lesson.course_id,
                },
            )

        raise HTTPException(status_code=400, detail="Either block_id or lesson_id must be provided")

    def _segment_content(self, text: str) -> List[str]:
        paragraphs = [p.strip() for p in text.split("\n") if p.strip()]
        segments: List[str] = []
        buffer: List[str] = []
        word_limit = 180

        for paragraph in paragraphs:
            words = paragraph.split()
            if len(words) >= word_limit:
                segments.append(paragraph)
                continue

            if sum(len(p.split()) for p in buffer) + len(words) <= word_limit:
                buffer.append(paragraph)
            else:
                if buffer:
                    segments.append(" ".join(buffer))
                buffer = [paragraph]

        if buffer:
            segments.append(" ".join(buffer))

        return segments

    async def _generate_tutor_turn(
        self,
        db: Session,
        session: AITutorSession,
        learner_message: Optional[str],
    ) -> TutorTurn:
        current_segment = session.content_segments[session.current_segment_index]
        history_payload = [
            {
                "role": interaction.role.value.lower(),
                "content": interaction.content,
                "input_type": interaction.input_type.value.lower(),
                "created_at": interaction.created_at.isoformat(),
            }
            for interaction in session.interactions[-10:]
        ]

        tutor_response = await self.gemini.generate_ai_tutor_turn(
            persona=session.persona_config,
            content_segment=current_segment,
            history=history_payload,
            learner_message=learner_message,
            total_segments=len(session.content_segments),
            current_index=session.current_segment_index,
        )

        tutor_turn = TutorTurn(**tutor_response)

        db.add(
            AITutorInteraction(
                session_id=session.id,
                role=TutorInteractionRole.TUTOR,
                content=tutor_turn.narration,
                input_type=TutorInteractionInputType.TEXT,
                metadata_payload={
                    "checkpoint": tutor_turn.checkpoint.dict() if tutor_turn.checkpoint else None,
                    "follow_up_prompts": tutor_turn.follow_up_prompts,
                },
            )
        )
        db.flush()

        if tutor_turn.checkpoint and tutor_turn.checkpoint.required:
            session.status = TutorSessionStatus.AWAITING_CHECKPOINT
            checkpoint = AITutorCheckpoint(
                session_id=session.id,
                checkpoint_type=tutor_turn.checkpoint.checkpoint_type.value,
                prompt=tutor_turn.checkpoint.instructions,
            )
            db.add(checkpoint)
        else:
            session.status = TutorSessionStatus.IN_PROGRESS
            if tutor_response.get("advance_segment", True):
                session.current_segment_index = min(
                    session.current_segment_index + 1,
                    len(session.content_segments) - 1,
                )

        session.updated_at = datetime.utcnow()
        return tutor_turn

    def _require_session(self, db: Session, session_id: int, student_id: int) -> AITutorSession:
        session = (
            db.query(AITutorSession)
            .filter(AITutorSession.id == session_id, AITutorSession.student_id == student_id)
            .first()
        )
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        return session

    def _get_latest_open_checkpoint(self, session: AITutorSession) -> Optional[AITutorCheckpoint]:
        for checkpoint in reversed(session.checkpoints):
            if checkpoint.status in {TutorCheckpointStatus.PENDING_ANALYSIS, TutorCheckpointStatus.ANALYZING}:
                return checkpoint
        return None

    async def _advance_after_checkpoint(
        self,
        db: Session,
        session: AITutorSession,
        analysis: Dict[str, Any],
    ):
        should_repeat = analysis.get("needs_review")
        if should_repeat:
            session.status = TutorSessionStatus.IN_PROGRESS
            session.updated_at = datetime.utcnow()
            return

        session.status = TutorSessionStatus.IN_PROGRESS
        session.current_segment_index = min(
            session.current_segment_index + 1,
            len(session.content_segments) - 1,
        )
        session.updated_at = datetime.utcnow()

    def _map_input_type(self, input_type: str) -> TutorInteractionInputType:
        mapping = {
            "text": TutorInteractionInputType.TEXT,
            "voice": TutorInteractionInputType.VOICE,
            "checkpoint": TutorInteractionInputType.CHECKPOINT,
        }
        return mapping.get(input_type, TutorInteractionInputType.TEXT)

    def _snapshot(self, session: AITutorSession) -> TutorSessionSnapshot:
        status_schema = TutorSessionStatusSchema(session.status.value)
        return TutorSessionSnapshot(
            session_id=session.id,
            status=status_schema,
            current_segment_index=session.current_segment_index,
            total_segments=len(session.content_segments),
            last_tutor_turn=None,
            created_at=session.started_at,
            updated_at=session.updated_at,
        )


ai_tutor_service = AITutorService()
