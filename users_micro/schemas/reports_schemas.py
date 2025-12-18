from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any, Union
from datetime import datetime
from enum import Enum

# --- Enums for Pydantic ---
class ReportTypeEnum(str, Enum):
    student_progress = "student_progress"
    class_performance = "class_performance"
    subject_analytics = "subject_analytics"
    assignment_analysis = "assignment_analysis"
    grade_distribution = "grade_distribution"
    attendance_report = "attendance_report"
    teacher_performance = "teacher_performance"
    school_overview = "school_overview"

class ReportStatusEnum(str, Enum):
    pending = "pending"
    generating = "generating"
    completed = "completed"
    failed = "failed"
    expired = "expired"

class ReportFormatEnum(str, Enum):
    pdf = "pdf"
    excel = "excel"
    csv = "csv"
    json = "json"

class ReportFrequencyEnum(str, Enum):
    daily = "daily"
    weekly = "weekly"
    monthly = "monthly"
    quarterly = "quarterly"

class AccessLevelEnum(str, Enum):
    view = "view"
    download = "download"
    edit = "edit"

# --- Base Schemas ---
class ReportTemplateBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    report_type: ReportTypeEnum
    template_config: str  # JSON string
    is_active: bool = True
    is_default: bool = False

class ReportTemplateCreate(ReportTemplateBase):
    school_id: int

class ReportTemplateUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    template_config: Optional[str] = None
    is_active: Optional[bool] = None
    is_default: Optional[bool] = None

class ReportTemplateResponse(ReportTemplateBase):
    id: int
    school_id: int
    created_by: int
    created_date: datetime
    updated_date: datetime

    class Config:
        from_attributes = True

# --- Report Schemas ---
class ReportBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    report_type: ReportTypeEnum
    template_id: Optional[int] = None
    
    # Report scope
    subject_id: Optional[int] = None
    classroom_id: Optional[int] = None
    student_id: Optional[int] = None
    teacher_id: Optional[int] = None
    assignment_id: Optional[int] = None
    
    # Report parameters
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    parameters: Optional[str] = None  # JSON string
    format: ReportFormatEnum = ReportFormatEnum.pdf
    expires_date: Optional[datetime] = None
    is_public: bool = False

class ReportCreate(ReportBase):
    school_id: int

class ReportUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    status: Optional[ReportStatusEnum] = None
    format: Optional[ReportFormatEnum] = None
    expires_date: Optional[datetime] = None
    is_public: Optional[bool] = None

class ReportResponse(ReportBase):
    id: int
    school_id: int
    requested_by: int
    requested_date: datetime
    generated_date: Optional[datetime] = None
    status: ReportStatusEnum
    file_path: Optional[str] = None
    file_name: Optional[str] = None
    file_size: Optional[int] = None
    report_data: Optional[str] = None
    summary_stats: Optional[str] = None
    error_message: Optional[str] = None
    access_count: int
    last_accessed: Optional[datetime] = None

    class Config:
        from_attributes = True

# --- Report Generation Request Schema ---
class ReportGenerationRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    report_type: ReportTypeEnum
    template_id: Optional[int] = None
    
    # Report scope
    subject_id: Optional[int] = None
    classroom_id: Optional[int] = None
    student_id: Optional[int] = None
    teacher_id: Optional[int] = None
    assignment_id: Optional[int] = None
    
    # Date range
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    
    # Format and options
    format: ReportFormatEnum = ReportFormatEnum.pdf
    include_charts: bool = True
    include_summary: bool = True
    
    # Custom parameters
    custom_parameters: Optional[Dict[str, Any]] = None

    @validator('date_to')
    def validate_date_range(cls, v, values):
        if v and 'date_from' in values and values['date_from']:
            if v < values['date_from']:
                raise ValueError('date_to must be after date_from')
        return v

# --- Report Share Schemas ---
class ReportShareBase(BaseModel):
    shared_with_user_id: int
    access_level: AccessLevelEnum = AccessLevelEnum.view
    expires_date: Optional[datetime] = None

class ReportShareCreate(ReportShareBase):
    report_id: int

class ReportShareUpdate(BaseModel):
    access_level: Optional[AccessLevelEnum] = None
    expires_date: Optional[datetime] = None
    is_active: Optional[bool] = None

class ReportShareResponse(ReportShareBase):
    id: int
    report_id: int
    shared_by_user_id: int
    share_date: datetime
    is_active: bool
    access_count: int
    last_accessed: Optional[datetime] = None

    class Config:
        from_attributes = True

# --- Report Schedule Schemas ---
class ReportScheduleBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    template_id: int
    frequency: ReportFrequencyEnum
    schedule_config: str  # JSON cron-like configuration
    
    # Report scope
    subject_id: Optional[int] = None
    classroom_id: Optional[int] = None
    parameters: Optional[str] = None  # JSON parameters
    
    # Recipients
    recipient_emails: List[str] = Field(..., min_items=1)
    recipient_user_ids: Optional[List[int]] = None
    
    is_active: bool = True

class ReportScheduleCreate(ReportScheduleBase):
    school_id: int

class ReportScheduleUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    frequency: Optional[ReportFrequencyEnum] = None
    schedule_config: Optional[str] = None
    parameters: Optional[str] = None
    recipient_emails: Optional[List[str]] = None
    recipient_user_ids: Optional[List[int]] = None
    is_active: Optional[bool] = None

class ReportScheduleResponse(ReportScheduleBase):
    id: int
    school_id: int
    created_by: int
    created_date: datetime
    last_run_date: Optional[datetime] = None
    next_run_date: Optional[datetime] = None
    total_runs: int
    successful_runs: int
    failed_runs: int

    class Config:
        from_attributes = True

# --- Report Analytics Schemas ---
class ReportAnalytics(BaseModel):
    total_reports: int
    reports_by_type: Dict[str, int]
    reports_by_status: Dict[str, int]
    reports_by_format: Dict[str, int]
    most_requested_types: List[Dict[str, Any]]
    average_generation_time: Optional[float] = None
    success_rate: float
    storage_used: int  # in bytes

class StudentProgressData(BaseModel):
    student_id: int
    student_name: str
    total_assignments: int
    completed_assignments: int
    average_grade: float
    grade_trend: List[float]
    subject_performance: Dict[str, Dict[str, Any]]
    recent_activity: List[Dict[str, Any]]

class ClassPerformanceData(BaseModel):
    classroom_id: int
    classroom_name: str
    total_students: int
    average_class_grade: float
    grade_distribution: Dict[str, int]
    top_performers: List[Dict[str, Any]]
    struggling_students: List[Dict[str, Any]]
    subject_breakdown: Dict[str, Dict[str, Any]]

class SubjectAnalyticsData(BaseModel):
    subject_id: int
    subject_name: str
    total_assignments: int
    total_students: int
    average_grade: float
    grade_distribution: Dict[str, int]
    difficulty_analysis: Dict[str, Any]
    teacher_performance: Dict[str, Any]
    completion_rates: Dict[str, float]

# --- Quick Report Generation Schemas ---
class QuickReportRequest(BaseModel):
    report_type: ReportTypeEnum
    scope_id: int  # student_id, classroom_id, subject_id, etc.
    date_range_days: int = 30  # Last N days
    format: ReportFormatEnum = ReportFormatEnum.pdf

class ReportPreview(BaseModel):
    title: str
    summary: str
    key_metrics: Dict[str, Any]
    chart_data: Optional[Dict[str, Any]] = None
    recommendations: Optional[List[str]] = None

# --- Bulk Report Operations ---
class BulkReportRequest(BaseModel):
    report_type: ReportTypeEnum
    scope_type: str  # "students", "classrooms", "subjects"
    scope_ids: List[int]
    template_id: Optional[int] = None
    format: ReportFormatEnum = ReportFormatEnum.pdf
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None

class BulkReportResponse(BaseModel):
    batch_id: str
    total_reports: int
    status: str
    created_reports: List[int]
    failed_reports: List[Dict[str, Any]]

# --- Export Schemas ---
class ExportRequest(BaseModel):
    report_ids: List[int]
    format: ReportFormatEnum
    include_metadata: bool = True
    compress: bool = False

class ExportResponse(BaseModel):
    export_id: str
    file_path: str
    file_size: int
    expires_at: datetime