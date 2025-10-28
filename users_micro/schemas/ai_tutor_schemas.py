from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict, Any

from pydantic import BaseModel, Field
try:
    # Pydantic v2
    from pydantic import ConfigDict  # type: ignore
except Exception:  # pragma: no cover
    ConfigDict = None  # type: ignore


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
    grade_level: Optional[int] = Field(
        None,
        description="Optional override for student grade level (1-12) to adjust language style",
        ge=1,
        le=12,
    )
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
                "grade_level": 5,
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


# ------------------------------
# Lesson plan data contracts
# ------------------------------

class LessonPlanSnippet(BaseModel):
    snippet: str = Field(..., description="Exact text span or paraphrase to highlight/explain")
    explanation: str = Field(..., description="Primary explanation for the snippet")
    easier_explanation: Optional[str] = Field(None, description="Pre-generated simpler explanation shown only once if the learner struggles")
    question: Optional[str] = Field(None, description="Optional comprehension question for this snippet")
    follow_ups: List[str] = Field(default_factory=list, description="Optional follow-up prompts for curiosity")
    checkpoint: Optional[TutorTurnCheckpoint] = Field(None, description="Optional checkpoint pre-authored for this snippet")


class LessonPlanSegment(BaseModel):
    index: int
    title: Optional[str] = None
    text: Optional[str] = Field(None, description="Source text of this segment for client-side highlighting")
    snippets: List[LessonPlanSnippet]


class LessonPlan(BaseModel):
    module_title: Optional[str] = None
    segments: List[LessonPlanSegment]


class LessonPlanResponse(BaseModel):
    lesson_plan: LessonPlan


class TutorSessionSnapshot(BaseModel):
    session_id: int
    status: TutorSessionStatus
    current_segment_index: int
    total_segments: int
    last_tutor_turn: Optional[TutorTurn] = None
    created_at: datetime
    updated_at: datetime


# ------------------------------
# Lesson plan contracts (backend schema)
# ------------------------------

class LessonPlanCheckpoint(BaseModel):
    required: bool
    checkpoint_type: TutorCheckpointType
    instructions: str
    criteria: Optional[List[str]] = None


class LessonPlanSnippet(BaseModel):
    snippet: str
    explanation: str
    easier_explanation: Optional[str] = None
    enrichment_explanation: Optional[str] = None
    question: Optional[str] = None
    follow_ups: List[str] = Field(default_factory=list)
    checkpoint: Optional[LessonPlanCheckpoint] = None


class LessonPlanSegment(BaseModel):
    index: int
    title: Optional[str] = None
    text: Optional[str] = None
    difficulty: Optional[str] = None  # easy|medium|hard
    snippets: List[LessonPlanSnippet]


class LessonPlan(BaseModel):
    module_title: Optional[str] = None
    segments: List[LessonPlanSegment]


class LessonPlanResponse(BaseModel):
    lesson_plan: LessonPlan


class TutorInteractionOut(BaseModel):
    id: int
    role: TutorMessageRole
    content: str
    input_type: TutorInputType
    created_at: datetime

    # Pydantic v2 renamed orm_mode -> from_attributes
    if ConfigDict is not None:  # v2 path
        model_config = ConfigDict(from_attributes=True)
    else:  # v1 fallback
        class Config:  # type: ignore
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
