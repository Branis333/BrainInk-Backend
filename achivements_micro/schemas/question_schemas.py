from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from enum import Enum

class DifficultyLevel(str, Enum):
    ELEMENTARY = "elementary"
    MIDDLE_SCHOOL = "middle_school" 
    HIGH_SCHOOL = "high_school"
    UNIVERSITY = "university"
    PROFESSIONAL = "professional"

class CreateQuestionRequest(BaseModel):
    question_text: str = Field(..., min_length=10, max_length=1000)
    option_a: str = Field(..., min_length=1, max_length=500)
    option_b: str = Field(..., min_length=1, max_length=500)
    option_c: str = Field(..., min_length=1, max_length=500)
    option_d: str = Field(..., min_length=1, max_length=500)
    correct_answer: str = Field(..., pattern="^[ABCD]$")
    subject: str = Field(..., min_length=2, max_length=50)
    topic: str = Field(..., min_length=2, max_length=100)
    difficulty_level: DifficultyLevel
    explanation: Optional[str] = Field(None, max_length=1000)
    source: Optional[str] = Field(None, max_length=200)
    points_value: Optional[int] = Field(10, ge=1, le=100)
    time_limit_seconds: Optional[int] = Field(30, ge=5, le=300)

class QuestionResponse(BaseModel):
    id: int
    question_text: str
    option_a: str
    option_b: str
    option_c: str
    option_d: str
    correct_answer: str
    subject: str
    topic: str
    difficulty_level: str
    explanation: Optional[str]
    source: Optional[str]
    points_value: int
    time_limit_seconds: int
    times_used: int
    correct_rate: float
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class QuestionListResponse(BaseModel):
    id: int
    question_text: str
    subject: str
    topic: str
    difficulty_level: str
    points_value: int
    times_used: int
    correct_rate: float
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True

class QuestionStatsResponse(BaseModel):
    total_questions: int
    active_questions: int
    by_subject: dict
    by_difficulty: dict
    by_topic: dict
    most_used_questions: list
    highest_correct_rate: list

class UpdateQuestionRequest(BaseModel):
    question_text: Optional[str] = Field(None, min_length=10, max_length=1000)
    option_a: Optional[str] = Field(None, min_length=1, max_length=500)
    option_b: Optional[str] = Field(None, min_length=1, max_length=500)
    option_c: Optional[str] = Field(None, min_length=1, max_length=500)
    option_d: Optional[str] = Field(None, min_length=1, max_length=500)
    correct_answer: Optional[str] = Field(None, pattern="^[ABCD]$")  # Changed regex to pattern
    subject: Optional[str] = Field(None, min_length=2, max_length=50)
    topic: Optional[str] = Field(None, min_length=2, max_length=100)
    difficulty_level: Optional[DifficultyLevel] = None
    explanation: Optional[str] = Field(None, max_length=1000)
    source: Optional[str] = Field(None, max_length=200)
    points_value: Optional[int] = Field(None, ge=1, le=100)
    time_limit_seconds: Optional[int] = Field(None, ge=5, le=300)
    is_active: Optional[bool] = None