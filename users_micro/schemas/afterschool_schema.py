from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict
from datetime import datetime

# ===============================
# COURSE SCHEMAS
# ===============================

class TextbookCourseCreate(BaseModel):
    """Schema for creating courses from textbook file uploads using AI"""
    title: str = Field(..., min_length=1, max_length=200, description="Course title")
    subject: str = Field(..., min_length=1, max_length=100, description="Subject (Math, Science, English, etc.)")
    textbook_source: Optional[str] = Field(None, description="Source information about the textbook")
    
    # Course structure
    total_weeks: int = Field(8, ge=1, le=52, description="Total duration in weeks")
    blocks_per_week: int = Field(2, ge=1, le=5, description="Number of learning blocks per week")
    
    # Target audience
    age_min: int = Field(3, ge=3, le=16, description="Minimum age for course")
    age_max: int = Field(16, ge=3, le=16, description="Maximum age for course")
    difficulty_level: str = Field("intermediate", description="Difficulty level")
    
    # Additional options
    include_assignments: bool = Field(True, description="Generate assignments automatically")
    include_resources: bool = Field(True, description="Generate resource links (videos, articles)")
    
    @validator('difficulty_level')
    def validate_difficulty(cls, v):
        allowed_levels = ['beginner', 'intermediate', 'advanced']
        if v not in allowed_levels:
            raise ValueError(f'Difficulty level must be one of: {allowed_levels}')
        return v
    
    @validator('age_max')
    def validate_age_range(cls, v, values):
        if 'age_min' in values and v < values['age_min']:
            raise ValueError('age_max must be greater than or equal to age_min')
        return v

class TextbookCourseForm(BaseModel):
    """Schema for form data when creating courses from file uploads"""
    title: str
    subject: str
    textbook_source: Optional[str] = None
    total_weeks: int = 8
    blocks_per_week: int = 2
    age_min: int = 3
    age_max: int = 16
    difficulty_level: str = "intermediate"
    include_assignments: bool = True
    include_resources: bool = True

class CourseCreate(BaseModel):
    """Traditional course creation schema (legacy support)"""
    title: str = Field(..., min_length=1, max_length=200, description="Course title")
    subject: str = Field(..., min_length=1, max_length=100, description="Subject (Math, Science, English, etc.)")
    description: Optional[str] = Field(None, description="Course description")
    age_min: int = Field(3, ge=3, le=16, description="Minimum age for course")
    age_max: int = Field(16, ge=3, le=16, description="Maximum age for course")
    difficulty_level: str = Field("beginner", description="Difficulty level")
    
    @validator('difficulty_level')
    def validate_difficulty(cls, v):
        allowed_levels = ['beginner', 'intermediate', 'advanced']
        if v not in allowed_levels:
            raise ValueError(f'Difficulty level must be one of: {allowed_levels}')
        return v
    
    @validator('age_max')
    def validate_age_range(cls, v, values):
        if 'age_min' in values and v < values['age_min']:
            raise ValueError('age_max must be greater than or equal to age_min')
        return v

class CourseUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    subject: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    age_min: Optional[int] = Field(None, ge=3, le=16)
    age_max: Optional[int] = Field(None, ge=3, le=16)
    difficulty_level: Optional[str] = None
    is_active: Optional[bool] = None
    
    @validator('difficulty_level')
    def validate_difficulty(cls, v):
        if v is not None:
            allowed_levels = ['beginner', 'intermediate', 'advanced']
            if v not in allowed_levels:
                raise ValueError(f'Difficulty level must be one of: {allowed_levels}')
        return v

class CourseOut(BaseModel):
    id: int
    title: str
    subject: str
    description: Optional[str]
    age_min: int
    age_max: int
    difficulty_level: str
    created_by: int
    is_active: bool
    
    # Enhanced fields with default values for backward compatibility
    total_weeks: int = Field(default=8, description="Total duration in weeks")
    blocks_per_week: int = Field(default=2, description="Number of learning blocks per week")
    textbook_source: Optional[str] = Field(default=None, description="Source textbook information")
    textbook_content: Optional[str] = Field(default=None, description="Original textbook content")
    generated_by_ai: bool = Field(default=False, description="Whether course was AI-generated")
    
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
    
    @validator('total_weeks', pre=True, always=True)
    def validate_total_weeks(cls, v):
        """Ensure total_weeks is never None"""
        return v if v is not None else 8
    
    @validator('blocks_per_week', pre=True, always=True)
    def validate_blocks_per_week(cls, v):
        """Ensure blocks_per_week is never None"""
        return v if v is not None else 2
    
    @validator('generated_by_ai', pre=True, always=True)
    def validate_generated_by_ai(cls, v):
        """Ensure generated_by_ai is never None"""
        return v if v is not None else False

# ===============================
# BLOCK SCHEMAS
# ===============================

class CourseBlockOut(BaseModel):
    id: int
    course_id: int
    week: int
    block_number: int
    title: str
    description: Optional[str]
    learning_objectives: Optional[List[str]]
    content: Optional[str]
    duration_minutes: int
    resources: Optional[List[Dict[str, str]]]
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class CourseBlockCreate(BaseModel):
    week: int = Field(..., ge=1, description="Week number")
    block_number: int = Field(..., ge=1, description="Block number within week")
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    learning_objectives: List[str] = Field(default_factory=list)
    content: Optional[str] = None
    duration_minutes: int = Field(45, ge=5, le=180)
    resources: List[Dict[str, str]] = Field(default_factory=list)

# ===============================
# ASSIGNMENT SCHEMAS
# ===============================

class CourseAssignmentOut(BaseModel):
    id: int
    course_id: int
    title: str
    description: str
    assignment_type: str
    instructions: Optional[str]
    duration_minutes: int
    points: int
    rubric: Optional[str]
    week_assigned: Optional[int]
    due_days_after_assignment: int
    submission_format: Optional[str]
    learning_outcomes: Optional[List[str]]
    generated_by_ai: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class StudentAssignmentOut(BaseModel):
    id: int
    user_id: int
    assignment_id: int
    course_id: int
    assigned_at: datetime
    due_date: datetime
    submitted_at: Optional[datetime]
    status: str
    submission_file_path: Optional[str]
    submission_content: Optional[str]
    grade: Optional[float]
    ai_grade: Optional[float]
    manual_grade: Optional[float]
    feedback: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# ===============================
# LESSON SCHEMAS
# ===============================

class LessonCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200, description="Lesson title")
    content: Optional[str] = Field(None, description="Lesson content/instructions")
    learning_objectives: Optional[str] = Field(None, description="What students should learn")
    order_index: int = Field(1, ge=1, description="Order of lesson in course")
    estimated_duration: int = Field(30, ge=5, le=180, description="Estimated duration in minutes")

class LessonUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    content: Optional[str] = None
    learning_objectives: Optional[str] = None
    order_index: Optional[int] = Field(None, ge=1)
    estimated_duration: Optional[int] = Field(None, ge=5, le=180)
    is_active: Optional[bool] = None

class LessonOut(BaseModel):
    id: int
    course_id: int
    title: str
    content: Optional[str]
    learning_objectives: Optional[str]
    order_index: int
    estimated_duration: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class CourseWithLessons(CourseOut):
    lessons: List[LessonOut] = []

class CourseWithBlocks(CourseOut):
    blocks: List[CourseBlockOut] = []
    assignments: List[CourseAssignmentOut] = []

class ComprehensiveCourseOut(CourseOut):
    """Complete course information including blocks, lessons, and assignments"""
    blocks: List[CourseBlockOut] = []
    lessons: List[LessonOut] = []
    assignments: List[CourseAssignmentOut] = []
    total_blocks: int = 0
    estimated_total_duration: int = 0  # in minutes

# ===============================
# STUDY SESSION SCHEMAS
# ===============================

class StudySessionStart(BaseModel):
    course_id: int = Field(..., description="Course ID")
    lesson_id: Optional[int] = Field(None, description="Lesson ID (for legacy courses)")
    block_id: Optional[int] = Field(None, description="Course Block ID (for AI-generated courses)")
    
    @validator('lesson_id')
    def validate_lesson_or_block(cls, v, values):
        block_id = values.get('block_id')
        if not v and not block_id:
            raise ValueError('Either lesson_id or block_id must be provided')
        if v and block_id:
            raise ValueError('Cannot specify both lesson_id and block_id')
        return v

class StudySessionEnd(BaseModel):
    completion_percentage: float = Field(..., ge=0, le=100, description="Completion percentage")
    status: str = Field("completed", description="Session status")
    
    @validator('status')
    def validate_status(cls, v):
        allowed_statuses = ['completed', 'abandoned']
        if v not in allowed_statuses:
            raise ValueError(f'Status must be one of: {allowed_statuses}')
        return v

class StudySessionOut(BaseModel):
    id: int
    user_id: int
    course_id: int
    lesson_id: Optional[int]  # Made optional for block-based sessions
    block_id: Optional[int]  # Added for AI-generated course blocks
    started_at: datetime
    ended_at: Optional[datetime]
    duration_minutes: Optional[int]
    ai_score: Optional[float]
    ai_feedback: Optional[str]
    ai_recommendations: Optional[str]
    status: str
    completion_percentage: float
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# ===============================
# AI SUBMISSION SCHEMAS
# ===============================

class AISubmissionCreate(BaseModel):
    course_id: int = Field(..., description="Course ID")
    lesson_id: Optional[int] = Field(default=None, description="Lesson ID (for legacy courses)")
    block_id: Optional[int] = Field(default=None, description="Course Block ID (for AI-generated courses)")
    session_id: int = Field(..., description="Study session ID")
    assignment_id: Optional[int] = Field(default=None, description="Assignment ID (if submission is for assignment)")
    submission_type: str = Field(..., description="Type of submission")
    
    @validator('lesson_id', 'block_id', 'assignment_id', pre=True, always=True)
    def validate_nullable_ids(cls, v):
        """Ensure nullable IDs handle None gracefully"""
        return v if v is not None else None
    
    @validator('submission_type')
    def validate_submission_type(cls, v):
        allowed_types = ['homework', 'quiz', 'practice', 'assessment']
        if v not in allowed_types:
            raise ValueError(f'Submission type must be one of: {allowed_types}')
        return v
    
    @validator('lesson_id')
    def validate_lesson_or_block(cls, v, values):
        block_id = values.get('block_id')
        if not v and not block_id:
            raise ValueError('Either lesson_id or block_id must be provided')
        return v

class AISubmissionUpdate(BaseModel):
    ai_processed: Optional[bool] = None
    ai_score: Optional[float] = Field(None, ge=0, le=100)
    ai_feedback: Optional[str] = None
    ai_corrections: Optional[str] = None
    ai_strengths: Optional[str] = None
    ai_improvements: Optional[str] = None
    requires_review: Optional[bool] = None

class AISubmissionOut(BaseModel):
    id: int
    user_id: int
    course_id: int
    lesson_id: Optional[int] = Field(default=None)  # Made optional for block-based sessions
    block_id: Optional[int] = Field(default=None)  # New field for AI-generated course blocks
    session_id: int
    assignment_id: Optional[int] = Field(default=None)  # New field for assignment submissions
    submission_type: str
    original_filename: Optional[str]
    file_path: Optional[str]
    file_type: Optional[str]
    ai_processed: bool = Field(default=False)
    ai_score: Optional[float]
    ai_feedback: Optional[str]
    ai_corrections: Optional[str]
    ai_strengths: Optional[str]
    ai_improvements: Optional[str]
    requires_review: bool = Field(default=False)
    reviewed_by: Optional[int]
    manual_score: Optional[float]
    manual_feedback: Optional[str]
    submitted_at: datetime
    processed_at: Optional[datetime]
    reviewed_at: Optional[datetime]

    class Config:
        from_attributes = True
    
    @validator('ai_processed', pre=True, always=True)
    def validate_ai_processed(cls, v):
        """Ensure ai_processed is never None"""
        return v if v is not None else False
    
    @validator('requires_review', pre=True, always=True)
    def validate_requires_review(cls, v):
        """Ensure requires_review is never None"""
        return v if v is not None else False

# ===============================
# STUDENT PROGRESS SCHEMAS
# ===============================

class StudentProgressOut(BaseModel):
    id: int
    user_id: int
    course_id: int
    lessons_completed: int
    total_lessons: int
    completion_percentage: float
    average_score: Optional[float]
    total_study_time: int
    sessions_count: int
    started_at: datetime
    last_activity: datetime
    completed_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# ===============================
# RESPONSE SCHEMAS
# ===============================

class MessageResponse(BaseModel):
    message: str

class AIGradingResponse(BaseModel):
    submission_id: int
    ai_score: float
    ai_feedback: str
    ai_corrections: Optional[str]
    ai_strengths: Optional[str]
    ai_improvements: Optional[str]
    processed_at: datetime

class CourseListResponse(BaseModel):
    courses: List[CourseOut]
    total: int

class LessonListResponse(BaseModel):
    lessons: List[LessonOut]
    total: int

class StudySessionListResponse(BaseModel):
    sessions: List[StudySessionOut]
    total: int

class StudentDashboard(BaseModel):
    user_id: int
    active_courses: List[CourseOut]
    recent_sessions: List[StudySessionOut]
    progress_summary: List[StudentProgressOut]
    total_study_time: int
    average_score: Optional[float]