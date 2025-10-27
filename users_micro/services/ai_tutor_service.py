from __future__ import annotations

import asyncio
import json
import logging
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
    LearnerProfile,
    TutorSessionStatus,
    TutorInteractionRole,
    TutorInteractionInputType,
    TutorCheckpointStatus,
)
from db.database import get_engine, Base
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


logger = logging.getLogger(__name__)


class AITutorService:
    """Core orchestrator for AI tutor sessions"""

    def __init__(self):
        self.gemini = gemini_service
        # Checkpoint throttling config (env-overridable)
        try:
            self.min_gap_segments = int(os.getenv("AI_TUTOR_CHECKPOINT_MIN_GAP", "3"))
        except Exception:
            self.min_gap_segments = 3
        try:
            self.dedupe_window = int(os.getenv("AI_TUTOR_CHECKPOINT_DEDUPE_WINDOW", "5"))
        except Exception:
            self.dedupe_window = 5
        try:
            self.same_type_backoff = int(os.getenv("AI_TUTOR_CHECKPOINT_SAME_TYPE_BACKOFF", "2"))
        except Exception:
            self.same_type_backoff = 2

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

        # Reuse an existing in-progress session for this student/content instead of creating a new one.
        # This ensures the pre-generated lesson plan and state are preserved across app restarts.
        try:
            from models.ai_tutor_models import AITutorSession as _Sess, TutorSessionStatus as _Stat
            existing = (
                db.query(_Sess)
                .filter(
                    _Sess.student_id == student_id,
                    _Sess.course_id == getattr(request, "course_id", None),
                    _Sess.block_id == getattr(request, "block_id", None),
                    _Sess.lesson_id == getattr(request, "lesson_id", None),
                    _Sess.status.in_([_Stat.IN_PROGRESS, _Stat.AWAITING_CHECKPOINT]),
                )
                .order_by(_Sess.updated_at.desc())
                .first()
            )
        except Exception:
            logger.exception("Failed querying for existing AI tutor session; proceeding to create new")
            existing = None

        if existing:
            # Make sure a lesson plan exists (older sessions might not have it)
            try:
                await self._ensure_lesson_plan(db, existing, content_text, segments)
                db.flush()
            except Exception:
                logger.exception("Failed ensuring lesson plan for existing session")

            # Generate the next tutor turn from the plan (or fallback rules)
            tutor_turn = await self._generate_tutor_turn(db, existing, learner_message=None)
            db.commit()
            db.refresh(existing)
            return self._snapshot(existing), tutor_turn

        # Derive grade level from course metadata when available
        def _derive_grade_from_meta(meta: Dict[str, Any]) -> Optional[int]:
            try:
                course_info = meta or {}
                age_min = course_info.get("course_age_min")
                age_max = course_info.get("course_age_max")
                age = None
                if isinstance(age_min, int):
                    age = age_min
                elif isinstance(age_max, int):
                    age = age_max
                if age is None:
                    return None
                # Rough mapping: Grade ≈ age - 5 (6->1st, 7->2nd, ...)
                g = max(1, min(12, int(age) - 5))
                return g
            except Exception:
                return None

        # Prefer explicit request override; else derive from course age
        grade_level = None
        try:
            if getattr(request, "grade_level", None):
                grade_level = max(1, min(12, int(request.grade_level)))
        except Exception:
            grade_level = None
        if grade_level is None:
            grade_level = _derive_grade_from_meta(content_meta)

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
                "learning_focus": request.preferred_learning_focus or "balanced",
                "grade_level": grade_level,
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

        # Ensure learner profile table exists (safe no-op if already present)
        try:
            engine = get_engine()
            Base.metadata.create_all(bind=engine)
        except Exception:
            logger.exception("Failed to ensure tables via create_all")

    # Build lesson plan up-front (pre-generated explanations, questions, checkpoints)
        await self._ensure_lesson_plan(db, session, content_text, segments)

        # Build learner profile snapshot from historical sessions/checkpoints
        try:
            profile = self._build_learner_profile(db, student_id, request.course_id)
            settings = session.tutor_settings or {}
            settings["learner_profile"] = profile
            session.tutor_settings = settings
            db.flush()
        except Exception:
            logger.exception("Failed to compute learner profile snapshot")

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
        # If serving from a lesson plan and we were awaiting a response, advance pointer now
        settings = session.tutor_settings or {}
        plan = settings.get("lesson_plan")
        if plan:
            state = settings.get("plan_state") or {}
            awaiting = state.get("awaiting")
            if awaiting == "question":
                # Mark answered and advance to next snippet
                state["awaiting"] = None
                seg_idx = int(state.get("segment_index", 0))
                sn_idx = int(state.get("snippet_index", 0))
                segs = (plan.get("segments") or [])
                if seg_idx < len(segs):
                    total_snips = len(segs[seg_idx].get("snippets", []) )
                    if sn_idx + 1 < total_snips:
                        state["snippet_index"] = sn_idx + 1
                    else:
                        state["segment_index"] = seg_idx + 1
                        state["snippet_index"] = 0
                settings["plan_state"] = state
                session.tutor_settings = settings
                session.updated_at = datetime.utcnow()

        tutor_turn = await self._generate_tutor_turn(db, session, learner_message=message_request.message)
        db.commit()
        db.refresh(session)
        return tutor_turn

    async def resume_session(
        self,
        student_id: int,
        db: Session,
        course_id: Optional[int] = None,
        block_id: Optional[int] = None,
        lesson_id: Optional[int] = None,
    ) -> Tuple[TutorSessionSnapshot, TutorTurn]:
        """Resume the latest open session for a student (optionally filtered by course/block/lesson),
        ensuring a lesson plan exists and returning the next tutor turn without regenerating content.
        """
        from models.ai_tutor_models import AITutorSession as _Sess, TutorSessionStatus as _Stat

        q = (
            db.query(_Sess)
            .filter(
                _Sess.student_id == student_id,
                _Sess.status.in_([_Stat.IN_PROGRESS, _Stat.AWAITING_CHECKPOINT]),
            )
        )
        if course_id is not None:
            q = q.filter(_Sess.course_id == course_id)
        if block_id is not None:
            q = q.filter(_Sess.block_id == block_id)
        if lesson_id is not None:
            q = q.filter(_Sess.lesson_id == lesson_id)

        session = q.order_by(_Sess.updated_at.desc()).first()
        if not session:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No open session to resume")

        # Ensure a lesson plan exists; older sessions may not have one
        try:
            # Reconstruct segments text from stored session content
            seg_texts: List[str] = []
            try:
                seg_texts = [str(s.get("text", "")) for s in (session.content_segments or [])]
            except Exception:
                seg_texts = []
            content_text = " ".join([t for t in seg_texts if t])
            await self._ensure_lesson_plan(db, session, content_text, seg_texts or [""])
            db.flush()
        except Exception:
            logger.exception("Failed ensuring lesson plan during resume; proceeding")

        tutor_turn = await self._generate_tutor_turn(db, session, learner_message=None)
        db.commit()
        db.refresh(session)
        return self._snapshot(session), tutor_turn

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

    def get_lesson_plan(
        self,
        session_id: int,
        student_id: int,
        db: Session,
    ) -> Dict[str, Any]:
        session = self._require_session(db, session_id, student_id)
        settings = session.tutor_settings or {}
        plan = settings.get("lesson_plan")
        if not plan:
            # No plan available; return an empty structure to keep client robust
            return {"module_title": None, "segments": []}
        return plan

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
            # Pull course metadata including age range to derive grade
            try:
                course = block.course
                course_meta = {
                    "course_title": getattr(course, "title", None),
                    "course_subject": getattr(course, "subject", None),
                    "course_age_min": getattr(course, "age_min", None),
                    "course_age_max": getattr(course, "age_max", None),
                    "course_difficulty": getattr(course, "difficulty_level", None),
                }
            except Exception:
                course_meta = {}
            return (
                block.content or "",
                {
                    "type": "block",
                    "title": block.title,
                    "week": block.week,
                    "block_number": block.block_number,
                    "course_id": block.course_id,
                    **course_meta,
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
            # Pull course metadata including age range to derive grade
            try:
                course = lesson.course
                course_meta = {
                    "course_title": getattr(course, "title", None),
                    "course_subject": getattr(course, "subject", None),
                    "course_age_min": getattr(course, "age_min", None),
                    "course_age_max": getattr(course, "age_max", None),
                    "course_difficulty": getattr(course, "difficulty_level", None),
                }
            except Exception:
                course_meta = {}
            return (
                lesson.content or "",
                {
                    "type": "lesson",
                    "title": lesson.title,
                    "course_id": lesson.course_id,
                    **course_meta,
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

        # If we have a pre-generated lesson plan, serve the next planned turn
        lesson_plan = (session.tutor_settings or {}).get("lesson_plan")
        if lesson_plan:
            tutor_turn = self._tutor_turn_from_plan(session)
            # Log tutor turn for history
            db.add(
                AITutorInteraction(
                    session_id=session.id,
                    role=TutorInteractionRole.TUTOR,
                    content=tutor_turn.narration,
                    input_type=TutorInteractionInputType.TEXT,
                    metadata_payload={
                        "checkpoint": tutor_turn.checkpoint.dict() if tutor_turn.checkpoint else None,
                        "follow_up_prompts": tutor_turn.follow_up_prompts,
                        "source": "lesson_plan",
                    },
                )
            )
            db.flush()
            # Update high-level status (awaiting checkpoint or active)
            if tutor_turn.checkpoint and tutor_turn.checkpoint.required:
                session.status = TutorSessionStatus.AWAITING_CHECKPOINT
            else:
                session.status = TutorSessionStatus.IN_PROGRESS
            session.updated_at = datetime.utcnow()
            tutor_response = {"advance_segment": False}
        else:
            # Fallback: on-the-fly generation for legacy sessions
            try:
                tutor_response = await self.gemini.generate_ai_tutor_turn(
                    persona=session.persona_config,
                    content_segment=current_segment,
                    history=history_payload,
                    learner_message=learner_message,
                    total_segments=len(session.content_segments),
                    current_index=session.current_segment_index,
                )
            except ValueError as empty_response_error:
                logger.warning(
                    "Gemini returned no text for session %s segment %s: %s",
                    session.id,
                    session.current_segment_index,
                    empty_response_error,
                )
                tutor_response = self._fallback_tutor_turn()
            except Exception:
                logger.exception(
                    "Gemini call failed for session %s segment %s; using fallback narrator",
                    session.id,
                    session.current_segment_index,
                )
                tutor_response = self._fallback_tutor_turn()

            tutor_turn = TutorTurn(**tutor_response)

        if not lesson_plan:
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

        # Backend checkpoint throttling and deduplication
        if tutor_turn.checkpoint and tutor_turn.checkpoint.required:
            should_create = self._should_create_checkpoint(session, tutor_turn)
            if should_create:
                session.status = TutorSessionStatus.AWAITING_CHECKPOINT
                checkpoint = AITutorCheckpoint(
                    session_id=session.id,
                    checkpoint_type=tutor_turn.checkpoint.checkpoint_type.value,
                    prompt=tutor_turn.checkpoint.instructions,
                )
                db.add(checkpoint)
                # Track last checkpoint segment and prompt for throttling
                settings = session.tutor_settings or {}
                settings["last_checkpoint_segment_index"] = session.current_segment_index
                settings["last_checkpoint_prompt"] = self._normalise_text(tutor_turn.checkpoint.instructions)
                session.tutor_settings = settings
            else:
                # Treat as a regular turn without creating a checkpoint; respect advance_segment
                session.status = TutorSessionStatus.IN_PROGRESS
                if tutor_response.get("advance_segment", True):
                    session.current_segment_index = min(
                        session.current_segment_index + 1,
                        len(session.content_segments) - 1,
                    )
        else:
            session.status = TutorSessionStatus.IN_PROGRESS
            if tutor_response.get("advance_segment", True):
                session.current_segment_index = min(
                    session.current_segment_index + 1,
                    len(session.content_segments) - 1,
                )

        session.updated_at = datetime.utcnow()
        return tutor_turn

    # ------------------------------
    # Lesson plan helpers
    # ------------------------------
    async def _ensure_lesson_plan(
        self,
        db: Session,
        session: AITutorSession,
        content_text: str,
        segments: List[str],
    ) -> None:
        settings = session.tutor_settings or {}
        if settings.get("lesson_plan"):
            session.tutor_settings = settings
            return

        segment_payload = [{"index": i, "text": seg} for i, seg in enumerate(segments)]
        try:
            plan = await self.gemini.generate_lesson_plan_for_segments(
                persona=session.persona_config,
                module_title=(session.tutor_settings or {}).get("source", {}).get("title"),
                segments=segment_payload,
            )
        except Exception:
            logger.exception("Failed to pre-generate lesson plan; proceeding without one")
            plan = None

        if plan and isinstance(plan, dict) and plan.get("segments"):
            settings["lesson_plan"] = plan
            settings["plan_state"] = {
                "segment_index": 0,
                "snippet_index": 0,
                "awaiting": None,  # 'question' | 'checkpoint' | None
                "retry_used_for": {},  # key: f"{seg}:{snip}" -> bool
                "force_easier": False,
            }
            session.tutor_settings = settings
            db.flush()

    def _get_plan(self, session: AITutorSession) -> Optional[Dict[str, Any]]:
        return (session.tutor_settings or {}).get("lesson_plan")

    def _get_plan_state(self, session: AITutorSession) -> Dict[str, Any]:
        st = (session.tutor_settings or {}).get("plan_state") or {}
        return {
            "segment_index": int(st.get("segment_index", 0)),
            "snippet_index": int(st.get("snippet_index", 0)),
            "awaiting": st.get("awaiting"),
            "retry_used_for": st.get("retry_used_for", {}),
            "force_easier": bool(st.get("force_easier", False)),
        }

    def _save_plan_state(self, session: AITutorSession, state: Dict[str, Any]) -> None:
        settings = session.tutor_settings or {}
        settings["plan_state"] = state
        session.tutor_settings = settings

    def _tutor_turn_from_plan(self, session: AITutorSession) -> TutorTurn:
        plan = self._get_plan(session)
        state = self._get_plan_state(session)
        seg_idx = state["segment_index"]
        sn_idx = state["snippet_index"]
        force_easier = state.get("force_easier", False)
        force_enrichment = bool(state.get("force_enrichment", False))

        segments = plan.get("segments", []) if plan else []
        if seg_idx >= len(segments):
            # No more content - mark complete
            session.status = TutorSessionStatus.COMPLETED
            session.updated_at = datetime.utcnow()
            return TutorTurn(
                narration="Awesome work! You've reached the end of this module.",
                comprehension_check=None,
                follow_up_prompts=[],
                checkpoint=None,
            )

        seg = segments[seg_idx]
        snippets = seg.get("snippets", [])
        if not snippets:
            # Advance to next segment if empty
            state["segment_index"] = seg_idx + 1
            state["snippet_index"] = 0
            self._save_plan_state(session, state)
            return self._tutor_turn_from_plan(session)

        snip = snippets[min(sn_idx, max(0, len(snippets) - 1))]
        key = f"{seg_idx}:{sn_idx}"
        retry_used_for = state.get("retry_used_for", {})
        use_easier = bool(force_easier) and bool(snip.get("easier_explanation"))

        # Difficulty adaptation: if enrichment is available and we have strong recent performance, use it
        use_enrichment = False
        if not use_easier:
            # Look at recent checkpoint scores to gauge proficiency
            recent_scores = [cp.score for cp in (session.checkpoints or []) if cp.score is not None]
            avg = sum(recent_scores[-3:]) / max(1, len(recent_scores[-3:])) if recent_scores[-3:] else None
            if force_enrichment or (avg is not None and avg >= 85.0):
                use_enrichment = bool(snip.get("enrichment_explanation"))

        if use_easier:
            narration_text = snip.get("easier_explanation") or snip.get("explanation") or "Let's break this down simply."
        elif use_enrichment:
            narration_text = snip.get("enrichment_explanation") or snip.get("explanation") or "Let's deepen our understanding."
        else:
            narration_text = snip.get("explanation") or "Let's explore this idea."
        question = snip.get("question")
        follow = snip.get("follow_ups") or []
        cp = snip.get("checkpoint")

        # Determine awaiting state
        awaiting = None
        if cp and cp.get("required"):
            awaiting = "checkpoint"
        elif question:
            awaiting = "question"

        state["awaiting"] = awaiting
        state["force_easier"] = False  # reset after serving
        state["force_enrichment"] = False
        # Do NOT advance here; advancement occurs after response or checkpoint
        self._save_plan_state(session, state)
        # Keep session-level index aligned for client UIs
        try:
            session.current_segment_index = int(seg_idx)
        except Exception:
            pass

        checkpoint_model = None
        if cp and cp.get("required"):
            # Normalize to TutorTurnCheckpoint
            ctype = cp.get("checkpoint_type") or "reflection"
            criteria = cp.get("criteria") or []
            checkpoint_model = TutorTurnCheckpoint(
                required=True,
                checkpoint_type=ctype,  # Pydantic will coerce enum
                instructions=cp.get("instructions") or "Show your thinking.",
                criteria=list(criteria),
            )

        # Add a tiny bridge: reference what came before and what's next
        bridge_parts: List[str] = []
        prev_snippet_text = None
        if sn_idx > 0 and len(snippets) >= 2:
            prev_snippet_text = snippets[sn_idx-1].get("snippet")
        elif seg_idx > 0:
            prev_seg_snips = (plan.get("segments", [])[seg_idx-1] or {}).get("snippets", [])
            if prev_seg_snips:
                prev_snippet_text = prev_seg_snips[0].get("snippet")
        next_snippet_text = None
        if sn_idx + 1 < len(snippets):
            next_snippet_text = snippets[sn_idx+1].get("snippet")
        elif seg_idx + 1 < len(plan.get("segments", [])):
            next_seg = plan.get("segments", [])[seg_idx+1]
            if next_seg and next_seg.get("snippets"):
                next_snippet_text = next_seg["snippets"][0].get("snippet")

        if prev_snippet_text:
            bridge_parts.append("Building on what you just saw: " + prev_snippet_text[:120].rstrip() + ("…" if len(prev_snippet_text) > 120 else ""))
        if next_snippet_text:
            bridge_parts.append("Up next, we’ll look at: " + next_snippet_text[:120].rstrip() + ("…" if len(next_snippet_text) > 120 else ""))
        # Weave learner profile context lightly (prior mastery and progress)
        try:
            lp = (session.tutor_settings or {}).get("learner_profile") or {}
            best_topic = None
            best_score = -1
            for t in (lp.get("topics") or []):
                sc = t.get("avg_score")
                if isinstance(sc, (int, float)) and sc > best_score:
                    best_score = sc
                    best_topic = t
            if best_topic and best_score >= 80:
                bridge_parts.insert(0, f"You’ve been strong in {best_topic.get('name','this topic')} lately (≈{int(best_score)}%).")
            last_seen = (lp.get("recent_sessions") or [])[:1]
            if last_seen:
                ls = last_seen[0]
                if ls.get("title") and not any("last time" in p.lower() for p in bridge_parts):
                    bridge_parts.insert(0, f"Last time, you covered {ls.get('title')}.")
        except Exception:
            pass

        # Always anchor the explanation to the exact text snippet for grounding
        anchor_line = None
        try:
            snippet_text = (snip.get("snippet") or "").strip()
            if snippet_text:
                anchor_line = f"From the text: \"{snippet_text[:180]}\""
        except Exception:
            anchor_line = None

        # Simplify explanation language (short sentences, common words)
        try:
            grade = None
            try:
                grade = (session.persona_config or {}).get("grade_level")
            except Exception:
                grade = None
            narration_text = self._simplify_text(narration_text, grade_level=grade)
        except Exception:
            pass

        if anchor_line:
            narration_text = anchor_line + "\n\n" + narration_text.strip()

        if bridge_parts:
            narration_text = narration_text.strip() + "\n\n" + " ".join(bridge_parts)

        return TutorTurn(
            narration=narration_text,
            comprehension_check=question,
            follow_up_prompts=list(follow)[:3],
            checkpoint=checkpoint_model,
        )

    def _simplify_text(self, text: str, grade_level: Optional[int] = None) -> str:
        """Apply lightweight readability simplifications without changing meaning.

        Heuristics:
        - Replace some complex words with simpler ones.
        - Keep sentences short (split on commas/and if very long).
        - Limit to ~3 sentences for clarity.
        """
        import re

        if not text:
            return text

        # Common replacements
        replacements = {
            "utilize": "use",
            "utilises": "uses",
            "demonstrates": "shows",
            "illustrates": "shows",
            "fundamental": "basic",
            "underlying": "basic",
            "manifests": "shows",
            "constitutes": "is",
            "occurs": "happens",
            "subsequently": "then",
            "consequently": "so",
            "therefore": "so",
            "component": "part",
            "mechanism": "way",
            "concept": "idea",
            "phenomena": "things that happen",
            "phenomenon": "thing that happens",
            "conserved": "kept the same",
            "transfer": "move",
            "transfers": "moves",
            "transferred": "moved",
            "convert": "change",
            "converts": "changes",
            "conversion": "change",
        }

        def simple_replace(t: str) -> str:
            def repl(match: re.Match) -> str:
                w = match.group(0)
                low = w.lower()
                rep = replacements.get(low)
                if not rep:
                    return w
                # Preserve capitalization
                if w.istitle():
                    return rep.capitalize()
                if w.isupper():
                    return rep.upper()
                return rep
            return re.sub(r"[A-Za-z]+", repl, t)

        text = simple_replace(text)

        # Split into sentences
        sentences = re.split(r"(?<=[.!?])\s+", text.strip())
        cleaned: list[str] = []
        for s in sentences:
            s = s.strip()
            if not s:
                continue
            # Choose target word length by grade (younger -> shorter)
            max_words = 22
            if isinstance(grade_level, int):
                if grade_level <= 3:
                    max_words = 12
                elif grade_level <= 5:
                    max_words = 16
                elif grade_level <= 7:
                    max_words = 20
                else:
                    max_words = 22
            # If very long (>max_words), split on commas or 'and'
            words = s.split()
            if len(words) > max_words:
                # Try commas first
                parts = re.split(r",\s+|\s+and\s+", s)
                for p in parts:
                    p = p.strip()
                    if p and p[-1] not in ".!?":
                        p += "."
                    if p:
                        cleaned.append(p)
            else:
                if s and s[-1] not in ".!?":
                    s += "."
                cleaned.append(s)

        # Limit total sentences based on grade
        max_sentences = 3
        if isinstance(grade_level, int) and grade_level <= 3:
            max_sentences = 2
        return " ".join(cleaned[:max_sentences]).strip()

    def _build_learner_profile(self, db: Session, student_id: int, course_id: Optional[int]) -> Dict[str, Any]:
        """Compute a lightweight per-student profile from historical sessions and checkpoints.

        No new tables required: we summarize recent sessions and topic mastery from stored checkpoints.
        """
        # Pull last 12 sessions for this student (optionally filter by course)
        q = db.query(AITutorSession).filter(AITutorSession.student_id == student_id)
        if course_id:
            q = q.filter(AITutorSession.course_id == course_id)
        sessions = (
            q.order_by(AITutorSession.started_at.desc())
             .limit(12)
             .all()
        )

        topics: Dict[str, List[float]] = {}
        recent_sessions: List[Dict[str, Any]] = []
        for s in sessions:
            src = (s.tutor_settings or {}).get("source") or {}
            title = src.get("title") or src.get("block_title") or src.get("lesson_title") or "Session"
            topic_key = self._topic_key_from_source(src)
            # Collect checkpoint scores
            scores = [cp.score for cp in (s.checkpoints or []) if cp.score is not None]
            avg_score = (sum(scores) / len(scores)) if scores else None
            if topic_key and avg_score is not None:
                topics.setdefault(topic_key, []).append(avg_score)
            recent_sessions.append({
                "session_id": s.id,
                "title": title,
                "date": s.started_at.isoformat() if s.started_at else None,
                "avg_score": avg_score,
            })

        topic_summaries = [
            {"key": k, "name": k, "avg_score": round(sum(v)/len(v), 1), "samples": len(v)}
            for k, v in topics.items() if v
        ]
        topic_summaries.sort(key=lambda x: (x["avg_score"] if x["avg_score"] is not None else -1), reverse=True)
        recent_sessions = recent_sessions[:8]

        data = {
            "topics": topic_summaries,
            "recent_sessions": recent_sessions,
        }
        # Upsert into learner_profiles for persistence and fast retrieval
        try:
            row = (
                db.query(LearnerProfile)
                .filter(LearnerProfile.student_id == student_id, LearnerProfile.course_id == course_id)
                .first()
            )
            if not row:
                row = LearnerProfile(student_id=student_id, course_id=course_id)
                db.add(row)
            row.topics = data.get("topics")
            row.recent_sessions = data.get("recent_sessions")
            row.updated_at = datetime.utcnow()
            db.flush()
        except Exception:
            logger.exception("Failed to upsert LearnerProfile")
        return data

    def _topic_key_from_source(self, src: Dict[str, Any]) -> Optional[str]:
        title = (src or {}).get("title") or (src or {}).get("block_title") or (src or {}).get("lesson_title")
        if not title:
            return None
        return str(title).strip()

    def _normalise_text(self, text: Optional[str]) -> str:
        if not text:
            return ""
        # Simple normalisation for dedupe: lowercase, collapse whitespace, strip punctuation at ends
        cleaned = " ".join(str(text).lower().strip().split())
        return cleaned

    def _should_create_checkpoint(self, session: AITutorSession, tutor_turn: TutorTurn) -> bool:
        """Decide whether to create a checkpoint, throttling duplicates and frequency.

        Rules:
        - If the same checkpoint (type + normalised prompt) appeared in the last 3 checkpoints, skip.
        - Enforce a minimum segment gap (default 2) between checkpoints unless no prior checkpoint.
        """
        if not tutor_turn.checkpoint or not tutor_turn.checkpoint.required:
            return False

        # No throttling if this is the very first checkpoint in session
        recent_checkpoints = list(session.checkpoints or [])
        if not recent_checkpoints:
            return True

        settings = session.tutor_settings or {}
        last_cp_segment = settings.get("last_checkpoint_segment_index")

        if isinstance(last_cp_segment, int):
            # If too soon since last checkpoint, skip creating a new one
            if (session.current_segment_index - last_cp_segment) < self.min_gap_segments:
                return False

        # Dedupe by comparing against last few checkpoint prompts and types
        target_type = tutor_turn.checkpoint.checkpoint_type.value
        target_prompt_norm = self._normalise_text(tutor_turn.checkpoint.instructions)
        same_type_count = 0
        window = max(1, self.dedupe_window)
        for cp in reversed(recent_checkpoints[-window:]):
            try:
                # Exact prompt duplicate within window
                if (cp.checkpoint_type == target_type) and (self._normalise_text(cp.prompt) == target_prompt_norm):
                    return False
                # Track consecutive same-type density in window
                if cp.checkpoint_type == target_type:
                    same_type_count += 1
            except Exception:
                continue

        # Avoid repeating same checkpoint type too frequently even with different wording
        if same_type_count >= max(1, self.same_type_backoff):
            return False

        return True

    def _fallback_tutor_turn(self) -> Dict[str, Any]:
        return {
            "narration": (
                "I'm having trouble generating a new explanation right now, so let's recap the key idea we just covered."
            ),
            "comprehension_check": "Can you summarize the most important point from the last section in your own words?",
            "follow_up_prompts": [],
            "checkpoint": None,
            "advance_segment": False,
        }

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
        # If we have a lesson plan, handle advancement within plan pointers
        settings = session.tutor_settings or {}
        plan = settings.get("lesson_plan")
        if plan:
            state = settings.get("plan_state") or {}
            seg_idx = int(state.get("segment_index", 0))
            sn_idx = int(state.get("snippet_index", 0))
            segs = (plan.get("segments") or [])

            needs_review = bool(analysis.get("needs_review"))
            # If review needed and easier explanation exists and not yet used, set flag to replay easier
            if seg_idx < len(segs):
                snippets = segs[seg_idx].get("snippets", [])
                if sn_idx < len(snippets):
                    easier = snippets[sn_idx].get("easier_explanation")
                    retry_used_for = state.get("retry_used_for", {})
                    key = f"{seg_idx}:{sn_idx}"
                    if needs_review and easier and not retry_used_for.get(key):
                        state["force_easier"] = True
                        retry_used_for[key] = True
                        state["retry_used_for"] = retry_used_for
                        state["awaiting"] = None
                        settings["plan_state"] = state
                        session.tutor_settings = settings
                        session.status = TutorSessionStatus.IN_PROGRESS
                        session.updated_at = datetime.utcnow()
                        return

            # Otherwise advance to the next snippet/segment; if strong performance, nudge enrichment
            score = analysis.get("score")
            if isinstance(score, (int, float)) and score >= 85:
                state["force_enrichment"] = True

            # Otherwise advance to the next snippet/segment
            state["awaiting"] = None
            if seg_idx < len(segs):
                total_snips = len(segs[seg_idx].get("snippets", []))
                if sn_idx + 1 < total_snips:
                    state["snippet_index"] = sn_idx + 1
                else:
                    state["segment_index"] = seg_idx + 1
                    state["snippet_index"] = 0
            settings["plan_state"] = state
            session.tutor_settings = settings
            session.status = TutorSessionStatus.IN_PROGRESS
            session.updated_at = datetime.utcnow()
            return

        # Legacy path: segment-based
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

        # Update persistent learner profile quickly after each checkpoint
        try:
            self._update_learner_profile_after_checkpoint(db, session, analysis)
        except Exception:
            logger.exception("Failed to update learner profile after checkpoint")

    def _update_learner_profile_after_checkpoint(self, db: Session, session: AITutorSession, analysis: Dict[str, Any]):
        score = analysis.get("score")
        if score is None:
            return
        try:
            row = (
                db.query(LearnerProfile)
                .filter(LearnerProfile.student_id == session.student_id, LearnerProfile.course_id == session.course_id)
                .first()
            )
            if not row:
                row = LearnerProfile(student_id=session.student_id, course_id=session.course_id)
                db.add(row)
            # Topic key from source title
            src = (session.tutor_settings or {}).get("source") or {}
            topic_key = self._topic_key_from_source(src) or "General"
            topics = list(row.topics or [])
            found = None
            for t in topics:
                if t.get("key") == topic_key:
                    found = t
                    break
            if found:
                n = int(found.get("samples") or 0)
                avg = float(found.get("avg_score") or 0.0)
                new_avg = ((avg * n) + float(score)) / float(n + 1)
                found["avg_score"] = round(new_avg, 1)
                found["samples"] = n + 1
            else:
                topics.append({"key": topic_key, "name": topic_key, "avg_score": float(score), "samples": 1})
            # Update recent_sessions entry for this session
            recent = list(row.recent_sessions or [])
            updated = False
            for rs in recent:
                if rs.get("session_id") == session.id:
                    rs["avg_score"] = float(score)
                    updated = True
                    break
            if not updated:
                title = src.get("title") or src.get("block_title") or src.get("lesson_title") or "Session"
                recent.insert(0, {
                    "session_id": session.id,
                    "title": title,
                    "date": session.started_at.isoformat() if session.started_at else None,
                    "avg_score": float(score),
                })
                recent = recent[:8]

            row.topics = topics
            row.recent_sessions = recent
            row.updated_at = datetime.utcnow()
            db.flush()
        except Exception:
            logger.exception("Error updating LearnerProfile row")

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
