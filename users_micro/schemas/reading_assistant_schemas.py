from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum

# ===============================
# ENUMS
# ===============================

class ReadingLevel(str, Enum):
    KINDERGARTEN = "kindergarten"
    GRADE_1 = "grade_1"
    GRADE_2 = "grade_2"
    GRADE_3 = "grade_3"

class DifficultyLevel(str, Enum):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"

class ContentType(str, Enum):
    SENTENCE = "sentence"
    PARAGRAPH = "paragraph"
    STORY = "story"

class FeedbackType(str, Enum):
    ENCOURAGEMENT = "encouragement"
    CORRECTION = "correction"
    SUGGESTION = "suggestion"
    PRONUNCIATION_TIP = "pronunciation_tip"

# ===============================
# READING CONTENT SCHEMAS
# ===============================

class ReadingContentCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    content: str = Field(..., min_length=1)
    content_type: ContentType
    reading_level: ReadingLevel
    difficulty_level: DifficultyLevel = DifficultyLevel.BEGINNER
    vocabulary_words: Optional[Dict[str, str]] = None  # word: definition
    learning_objectives: Optional[List[str]] = None
    phonics_focus: Optional[List[str]] = None  # sounds/patterns being taught

class ReadingContentOut(BaseModel):
    id: int
    title: str
    content: str
    content_type: str
    reading_level: str
    difficulty_level: str
    vocabulary_words: Optional[Dict[str, str]]
    learning_objectives: Optional[List[str]]
    phonics_focus: Optional[List[str]]
    word_count: int
    estimated_reading_time: Optional[int]
    complexity_score: Optional[float]
    created_at: datetime
    
    class Config:
        from_attributes = True

class ReadingContentUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    difficulty_level: Optional[DifficultyLevel] = None
    vocabulary_words: Optional[Dict[str, str]] = None
    learning_objectives: Optional[List[str]] = None
    phonics_focus: Optional[List[str]] = None
    is_active: Optional[bool] = None

# ===============================
# READING SESSION SCHEMAS
# ===============================

class ReadingSessionStart(BaseModel):
    content_id: int
    session_type: str = Field(default="practice", pattern="^(practice|assessment|guided)$")

class ReadingSessionOut(BaseModel):
    id: int
    student_id: int
    content_id: int
    session_type: str
    started_at: datetime
    completed_at: Optional[datetime]
    total_duration: Optional[int]
    accuracy_score: Optional[float]
    fluency_score: Optional[float]
    pronunciation_score: Optional[float]
    overall_score: Optional[float]
    strengths: Optional[List[str]]
    areas_for_improvement: Optional[List[str]]
    suggested_next_content: Optional[List[Dict]]
    is_completed: bool
    
    class Config:
        from_attributes = True

# ===============================
# READING ATTEMPT SCHEMAS
# ===============================

class ReadingAttemptStart(BaseModel):
    session_id: int
    content_id: int

class WordAnalysis(BaseModel):
    target_word: str
    spoken_word: Optional[str]
    word_position: int
    is_correct: bool
    pronunciation_accuracy: Optional[float]
    phonetic_errors: Optional[List[str]]
    pronunciation_tip: Optional[str]

class ReadingAttemptResult(BaseModel):
    transcribed_text: str
    word_accuracy: List[WordAnalysis]
    pronunciation_errors: List[Dict[str, Any]]
    reading_speed: float  # words per minute
    pauses_analysis: Dict[str, Any]
    accuracy_percentage: float
    fluency_score: float
    pronunciation_score: float

class ReadingAttemptOut(BaseModel):
    id: int
    session_id: int
    attempt_number: int
    transcribed_text: Optional[str]
    word_accuracy: Optional[List[Dict]]
    pronunciation_errors: Optional[List[Dict]]
    reading_speed: Optional[float]
    accuracy_percentage: Optional[float]
    fluency_score: Optional[float]
    pronunciation_score: Optional[float]
    duration: Optional[int]
    started_at: datetime
    completed_at: Optional[datetime]
    
    class Config:
        from_attributes = True

# ===============================
# AUDIO PROCESSING SCHEMAS
# ===============================

class AudioUploadRequest(BaseModel):
    session_id: int
    content_id: int
    attempt_number: Optional[int] = 1

class AudioAnalysisResponse(BaseModel):
    success: bool
    attempt_id: int
    transcribed_text: str
    analysis_results: ReadingAttemptResult
    feedback_message: str
    audio_feedback_url: Optional[str] = None
    next_suggestions: List[Dict[str, Any]]
    pronunciation_urls: Optional[Dict[str, Dict[str, Any]]] = None  # word -> pronunciation info

class LiveAudioSession(BaseModel):
    session_id: str
    content_id: int
    chunk_duration: int = Field(default=5, ge=1, le=10)  # seconds per chunk

# ===============================
# FEEDBACK SCHEMAS
# ===============================

class FeedbackCreate(BaseModel):
    session_id: int
    feedback_type: FeedbackType
    message: str
    focus_area: Optional[str] = None
    difficulty_adjustment: Optional[str] = None

class FeedbackOut(BaseModel):
    id: int
    session_id: int
    feedback_type: str
    message: str
    audio_message_path: Optional[str]
    focus_area: Optional[str]
    difficulty_adjustment: Optional[str]
    is_delivered: bool
    created_at: datetime
    
    class Config:
        from_attributes = True

# ===============================
# PROGRESS TRACKING SCHEMAS
# ===============================

class ProgressUpdate(BaseModel):
    accuracy_score: Optional[float] = None
    fluency_score: Optional[float] = None
    session_completed: bool = False
    words_read_correctly: Optional[int] = None
    reading_time: Optional[int] = None  # seconds

class ReadingProgressOut(BaseModel):
    id: int
    student_id: int
    current_reading_level: str
    current_difficulty: str
    total_sessions: int
    total_reading_time: int
    average_accuracy: Optional[float]
    average_fluency: Optional[float]
    words_read_correctly: int
    strengths: Optional[List[str]]
    challenges: Optional[List[str]]
    vocabulary_learned: Optional[List[str]]
    next_level_requirements: Optional[Dict[str, Any]]
    updated_at: datetime
    
    class Config:
        from_attributes = True

class GoalCreate(BaseModel):
    goal_type: str = Field(..., pattern="^(accuracy|fluency|vocabulary|level_up)$")
    target_value: float = Field(..., ge=0, le=100)
    target_date: Optional[datetime] = None
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None

class GoalOut(BaseModel):
    id: int
    student_id: int
    goal_type: str
    target_value: float
    current_value: float
    target_date: Optional[datetime]
    title: str
    description: Optional[str]
    is_achieved: bool
    achieved_at: Optional[datetime]
    created_at: datetime
    
    class Config:
        from_attributes = True

# ===============================
# DASHBOARD SCHEMAS
# ===============================

class StudentReadingDashboard(BaseModel):
    """Comprehensive dashboard for student reading progress"""
    student_info: Dict[str, Any]
    current_progress: ReadingProgressOut
    recent_sessions: List[ReadingSessionOut]
    active_goals: List[GoalOut]
    achievements: List[Dict[str, Any]]
    recommended_content: List[ReadingContentOut]
    weekly_stats: Dict[str, Any]
    
class TeacherReadingDashboard(BaseModel):
    """Dashboard for teachers/parents to monitor student progress"""
    students_overview: List[Dict[str, Any]]
    class_averages: Dict[str, float]
    struggling_students: List[Dict[str, Any]]
    top_performers: List[Dict[str, Any]]
    content_engagement: List[Dict[str, Any]]

# ===============================
# AI ANALYSIS SCHEMAS
# ===============================

class PronunciationAnalysis(BaseModel):
    word: str
    target_pronunciation: str  # IPA or phonetic
    actual_pronunciation: str
    accuracy_score: float
    issues: List[str]  # specific pronunciation problems
    practice_tips: List[str]

class FluentReadingAnalysis(BaseModel):
    words_per_minute: float
    pause_patterns: List[Dict[str, Any]]
    rhythm_score: float
    expression_score: float
    recommendations: List[str]

class ComprehensionCheck(BaseModel):
    """For future expansion - reading comprehension analysis"""
    questions: List[Dict[str, str]]
    suggested_follow_up: List[str]
    
# ===============================
# CONTENT GENERATION SCHEMAS
# ===============================

class GenerateContentRequest(BaseModel):
    """Request to AI-generate age-appropriate reading content"""
    reading_level: ReadingLevel
    difficulty_level: DifficultyLevel
    content_type: ContentType
    topic: Optional[str] = None
    vocabulary_focus: Optional[List[str]] = None
    phonics_patterns: Optional[List[str]] = None
    word_count_target: Optional[int] = None

class BulkContentGenerate(BaseModel):
    """Generate multiple pieces of content for a curriculum"""
    reading_level: ReadingLevel
    difficulty_levels: List[DifficultyLevel]
    content_types: List[ContentType]
    topics: List[str]
    count_per_combination: int = Field(default=3, ge=1, le=10)

# ===============================
# RESPONSE SCHEMAS
# ===============================

class MessageResponse(BaseModel):
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None

class ReadingListResponse(BaseModel):
    success: bool
    total_count: int
    items: List[ReadingContentOut]
    pagination: Optional[Dict[str, Any]] = None

class SessionListResponse(BaseModel):
    success: bool
    total_count: int
    sessions: List[ReadingSessionOut]
    pagination: Optional[Dict[str, Any]] = None