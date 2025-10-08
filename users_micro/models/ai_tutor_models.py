from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional, List

from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    DateTime,
    Boolean,
    ForeignKey,
    Float,
    JSON,
)
from sqlalchemy.orm import relationship
from sqlalchemy.types import Enum as SQLEnum

from db.database import Base


class TutorSessionStatus(Enum):
    INITIATED = "INITIATED"
    IN_PROGRESS = "IN_PROGRESS"
    AWAITING_CHECKPOINT = "AWAITING_CHECKPOINT"
    COMPLETED = "COMPLETED"
    ABANDONED = "ABANDONED"
    ERROR = "ERROR"


class TutorInteractionRole(Enum):
    SYSTEM = "SYSTEM"
    TUTOR = "TUTOR"
    STUDENT = "STUDENT"


class TutorInteractionInputType(Enum):
    TEXT = "TEXT"
    VOICE = "VOICE"
    IMAGE = "IMAGE"
    CHECKPOINT = "CHECKPOINT"


class TutorCheckpointStatus(Enum):
    PENDING_ANALYSIS = "PENDING_ANALYSIS"
    ANALYZING = "ANALYZING"
    COMPLETED = "COMPLETED"
    NEEDS_RETRY = "NEEDS_RETRY"


class AITutorSession(Base):
    __tablename__ = "ai_tutor_sessions"
    __allow_unmapped__ = True

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, nullable=False)
    course_id = Column(Integer, nullable=True)
    block_id = Column(Integer, nullable=True)
    lesson_id = Column(Integer, nullable=True)

    status = Column(SQLEnum(TutorSessionStatus), nullable=False, default=TutorSessionStatus.INITIATED)
    current_segment_index = Column(Integer, nullable=False, default=0)
    content_segments = Column(JSON, nullable=False, default=list)
    persona_config = Column(JSON, nullable=True)
    tutor_settings = Column(JSON, nullable=True)

    started_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    last_error = Column(Text, nullable=True)

    interactions: List["AITutorInteraction"] = relationship(
        "AITutorInteraction",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="AITutorInteraction.created_at",
    )
    checkpoints: List["AITutorCheckpoint"] = relationship(
        "AITutorCheckpoint",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="AITutorCheckpoint.created_at",
    )


class AITutorInteraction(Base):
    __tablename__ = "ai_tutor_interactions"
    __allow_unmapped__ = True

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("ai_tutor_sessions.id"), nullable=False, index=True)

    role = Column(SQLEnum(TutorInteractionRole), nullable=False)
    content = Column(Text, nullable=False)
    input_type = Column(SQLEnum(TutorInteractionInputType), nullable=False, default=TutorInteractionInputType.TEXT)
    output_type = Column(String(50), nullable=True)
    latency_ms = Column(Float, nullable=True)
    metadata_payload = Column("metadata", JSON, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    session: AITutorSession = relationship("AITutorSession", back_populates="interactions")


class AITutorCheckpoint(Base):
    __tablename__ = "ai_tutor_checkpoints"
    __allow_unmapped__ = True

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("ai_tutor_sessions.id"), nullable=False, index=True)

    checkpoint_type = Column(String(50), nullable=False)
    prompt = Column(Text, nullable=False)
    status = Column(SQLEnum(TutorCheckpointStatus), nullable=False, default=TutorCheckpointStatus.PENDING_ANALYSIS)
    ai_feedback = Column(JSON, nullable=True)
    response_payload = Column(JSON, nullable=True)
    score = Column(Float, nullable=True)

    media_file_path = Column(String(500), nullable=True)
    media_mime_type = Column(String(100), nullable=True)

    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    session: AITutorSession = relationship("AITutorSession", back_populates="checkpoints")
