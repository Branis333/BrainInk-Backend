from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum

class SyllabusStatusEnum(str, Enum):
    draft = "draft"
    active = "active"
    archived = "archived"

# --- Request Schemas ---

class SyllabusCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    subject_id: int
    term_length_weeks: int = Field(default=16, ge=1, le=52)

class SyllabusUpdateRequest(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    term_length_weeks: Optional[int] = Field(None, ge=1, le=52)
    status: Optional[SyllabusStatusEnum] = None

class WeeklyPlanCreateRequest(BaseModel):
    week_number: int = Field(..., ge=1)
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    learning_objectives: Optional[List[str]] = None
    topics_covered: Optional[List[str]] = None
    textbook_chapters: Optional[str] = None
    textbook_pages: Optional[str] = None
    assignments: Optional[List[str]] = None
    resources: Optional[List[str]] = None
    notes: Optional[str] = None

class WeeklyPlanUpdateRequest(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    learning_objectives: Optional[List[str]] = None
    topics_covered: Optional[List[str]] = None
    textbook_chapters: Optional[str] = None
    textbook_pages: Optional[str] = None
    assignments: Optional[List[str]] = None
    resources: Optional[List[str]] = None
    notes: Optional[str] = None

class TextbookUploadRequest(BaseModel):
    syllabus_id: int
    processing_preferences: Optional[Dict[str, Any]] = None

class StudentProgressUpdateRequest(BaseModel):
    current_week: Optional[int] = Field(None, ge=1)
    completed_weeks: Optional[List[int]] = None

# --- Response Schemas ---

class WeeklyPlanResponse(BaseModel):
    id: int
    syllabus_id: int
    week_number: int
    title: str
    description: Optional[str]
    learning_objectives: Optional[List[str]]
    topics_covered: Optional[List[str]]
    textbook_chapters: Optional[str]
    textbook_pages: Optional[str]
    assignments: Optional[List[str]]
    resources: Optional[List[str]]
    notes: Optional[str]
    created_date: datetime
    updated_date: datetime
    is_active: bool

    class Config:
        from_attributes = True

class SyllabusResponse(BaseModel):
    id: int
    title: str
    description: Optional[str]
    subject_id: int
    subject_name: Optional[str]  # Include subject name for convenience
    created_by: int
    creator_name: Optional[str]  # Include creator name for convenience
    term_length_weeks: int
    textbook_filename: Optional[str]
    textbook_path: Optional[str]
    ai_processing_status: str
    ai_analysis_data: Optional[Dict[str, Any]]
    status: SyllabusStatusEnum
    created_date: datetime
    updated_date: datetime
    is_active: bool
    weekly_plans: Optional[List[WeeklyPlanResponse]] = None

    class Config:
        from_attributes = True

class SyllabusListResponse(BaseModel):
    id: int
    title: str
    description: Optional[str]
    subject_id: int
    subject_name: Optional[str]
    created_by: int
    creator_name: Optional[str]
    term_length_weeks: int
    textbook_filename: Optional[str]
    ai_processing_status: str
    status: SyllabusStatusEnum
    created_date: datetime
    updated_date: datetime
    total_weeks: int  # Count of weekly plans
    completed_weeks: Optional[int] = None  # For student view

    class Config:
        from_attributes = True

class StudentSyllabusProgressResponse(BaseModel):
    id: int
    student_id: int
    syllabus_id: int
    current_week: int
    completed_weeks: List[int]
    progress_percentage: int
    last_accessed: datetime
    created_date: datetime
    updated_date: datetime

    class Config:
        from_attributes = True

class SyllabusWithProgressResponse(BaseModel):
    syllabus: SyllabusResponse
    progress: Optional[StudentSyllabusProgressResponse]

    class Config:
        from_attributes = True

# --- K.A.N.A. AI Integration Schemas ---

class TextbookAnalysisRequest(BaseModel):
    textbook_content: str
    term_length_weeks: int
    subject_name: str
    additional_preferences: Optional[Dict[str, Any]] = None

class TextbookAnalysisResponse(BaseModel):
    success: bool
    message: str
    analysis_data: Optional[Dict[str, Any]]
    suggested_weekly_plans: Optional[List[Dict[str, Any]]]

class AIGeneratedWeeklyPlan(BaseModel):
    week_number: int
    title: str
    description: str
    learning_objectives: List[str]
    topics_covered: List[str]
    textbook_chapters: str
    textbook_pages: str
    assignments: List[str]
    resources: List[str]

class KanaProcessingResponse(BaseModel):
    success: bool
    message: str
    processing_id: Optional[str]
    weekly_plans: Optional[List[AIGeneratedWeeklyPlan]]
