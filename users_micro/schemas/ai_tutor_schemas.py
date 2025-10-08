from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict, Any

from pydantic import BaseModel, Field


class TutorMessageRole(str, Enum):
    tutor = "tutor"
    student = "student"
    system = "system"


class TutorInputType(str, Enum):
    text = "text"
    voice = "voice"
    checkpoint = "checkpoint"


class TutorSessionStatus(str, Enum):
    initiated = "INITIATED"
    in_progress = "IN_PROGRESS"
    awaiting_checkpoint = "AWAITING_CHECKPOINT"
    completed = "COMPLETED"
    abandoned = "ABANDONED"
    error = "ERROR"


class SessionStartRequest(BaseModel):
    course_id: Optional[int] = Field(None, description="Course identifier")
    block_id: Optional[int] = Field(None, description="Course block identifier")
    lesson_id: Optional[int] = Field(None, description="Lesson identifier")
    persona: Optional[str] = Field(
        None,
        description="Optional persona keyword to adapt tutor style (e.g., 'friendly', 'energetic')",
    )
    preferred_learning_focus: Optional[str] = Field(
        None,
        description="Optional hints about the learner focus (e.g., vocabulary, problem-solving)",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "course_id": 21,
                "block_id": 83,
                "persona": "friendly",
                "preferred_learning_focus": "step-by-step reasoning",
            }
        }


class TutorMessageRequest(BaseModel):
    message: str = Field(..., min_length=1)
    input_type: TutorInputType = Field(TutorInputType.text)
    metadata: Optional[Dict[str, Any]] = None


class TutorCheckpointType(str, Enum):
    photo = "photo"
    reflection = "reflection"
    quiz = "quiz"


class TutorCheckpointRequest(BaseModel):
    checkpoint_type: TutorCheckpointType = Field(...)
    notes: Optional[str] = Field(None, description="Additional context supplied by the learner")


class TutorTurnCheckpoint(BaseModel):
    required: bool
    checkpoint_type: TutorCheckpointType
    instructions: str
    criteria: Optional[List[str]] = None


class TutorTurn(BaseModel):
    narration: str
    comprehension_check: Optional[str]
    follow_up_prompts: List[str] = Field(default_factory=list)
    checkpoint: Optional[TutorTurnCheckpoint] = None


class TutorSessionSnapshot(BaseModel):
    session_id: int
    status: TutorSessionStatus
    current_segment_index: int
    total_segments: int
    last_tutor_turn: Optional[TutorTurn] = None
    created_at: datetime
    updated_at: datetime


class TutorInteractionOut(BaseModel):
    id: int
    role: TutorMessageRole
    content: str
    input_type: TutorInputType
    created_at: datetime

    class Config:
        orm_mode = True


class TutorSessionDetail(BaseModel):
    session: TutorSessionSnapshot
    interactions: List[TutorInteractionOut]


class TutorCheckpointResponse(BaseModel):
    checkpoint_id: int
    status: str
    ai_feedback: Optional[Dict[str, Any]] = None
    score: Optional[float] = None


class TutorCompletionRequest(BaseModel):
    feedback: Optional[str] = None


class TutorSessionListItem(BaseModel):
    session_id: int
    status: TutorSessionStatus
    course_id: Optional[int]
    block_id: Optional[int]
    lesson_id: Optional[int]
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime]


class TutorSessionListResponse(BaseModel):
    items: List[TutorSessionListItem]
    total: int


class SessionStartResponse(BaseModel):
    session: TutorSessionSnapshot
    tutor_turn: TutorTurn
