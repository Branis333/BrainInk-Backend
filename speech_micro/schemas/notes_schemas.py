from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime

class GenerateNotesRequest(BaseModel):
    text: str = Field(..., description="Transcription text to convert to notes")
    subject: Optional[str] = Field(None, description="Subject area (e.g., 'Mathematics', 'History')")
    language: str = Field(default="en", description="Language code for the notes")

class StudyNotesResponse(BaseModel):
    id: int
    title: str
    brief_notes: str
    key_points: List[str] = Field(default_factory=list)
    summary: Optional[str] = None
    subject: Optional[str] = None
    language: Optional[str] = None
    word_count_original: Optional[int] = None
    word_count_notes: Optional[int] = None
    processing_time_seconds: Optional[float] = None
    is_favorite: bool = False
    view_count: int = 0
    created_at: str
    updated_at: str
    last_viewed: Optional[str] = None

class NotesListResponse(BaseModel):
    success: bool
    notes: List[StudyNotesResponse] = Field(default_factory=list)
    total_count: int = 0
    page: int = 1
    page_size: int = 20
    has_next: bool = False

class GenerateNotesResponse(BaseModel):
    success: bool
    notes_id: Optional[int] = None
    title: Optional[str] = None
    brief_notes: Optional[str] = None
    key_points: List[str] = Field(default_factory=list)
    summary: Optional[str] = None
    processing_time_seconds: float
    word_count_original: Optional[int] = None
    word_count_notes: Optional[int] = None
    created_at: Optional[str] = None
    error: Optional[str] = None

class UpdateNotesRequest(BaseModel):
    title: Optional[str] = None
    subject: Optional[str] = None
    is_favorite: Optional[bool] = None

class NotesStatsResponse(BaseModel):
    total_notes: int = 0
    total_subjects: int = 0
    favorite_count: int = 0
    most_used_language: Optional[str] = None
    average_processing_time: float = 0.0
    total_original_words: int = 0
    total_notes_words: int = 0
    compression_ratio: float = 0.0