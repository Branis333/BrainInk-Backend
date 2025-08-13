from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

# --- Assignment Schemas ---

class AssignmentBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=200, description="Assignment title")
    description: str = Field(..., min_length=10, max_length=1000, description="Detailed assignment description")
    rubric: str = Field(..., min_length=1, max_length=2000, description="Grading rubric and criteria")
    subtopic: Optional[str] = Field(None, max_length=100, description="Assignment subtopic")
    max_points: int = Field(100, ge=1, le=1000, description="Maximum points for this assignment")
    due_date: Optional[datetime] = Field(None, description="Assignment due date")

class AssignmentCreate(AssignmentBase):
    subject_id: int

class AssignmentUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, min_length=1, max_length=1000)
    rubric: Optional[str] = Field(None, min_length=10, max_length=2000)
    subtopic: Optional[str] = Field(None, max_length=100)
    max_points: Optional[int] = Field(None, ge=1, le=1000)
    due_date: Optional[datetime] = None
    is_active: Optional[bool] = None

class AssignmentResponse(AssignmentBase):
    id: int
    subject_id: int
    teacher_id: int
    created_date: datetime
    is_active: bool
    
    # Include subject and teacher info
    subject_name: Optional[str] = None
    teacher_name: Optional[str] = None
    
    class Config:
        from_attributes = True

class AssignmentWithGrades(AssignmentResponse):
    grades: List['GradeResponse'] = []
    total_students: int = 0
    graded_count: int = 0
    average_score: Optional[float] = None

# --- Grade Schemas ---

class GradeBase(BaseModel):
    points_earned: int = Field(..., ge=0)
    feedback: Optional[str] = None

class GradeCreate(GradeBase):
    assignment_id: int
    student_id: int
    ai_generated: Optional[bool] = False
    ai_confidence: Optional[int] = None

class GradeUpdate(BaseModel):
    points_earned: Optional[int] = Field(None, ge=0)
    feedback: Optional[str] = None

class GradeResponse(GradeBase):
    id: int
    assignment_id: int
    student_id: int
    teacher_id: int
    graded_date: datetime
    is_active: bool
    
    # Include related info
    assignment_title: Optional[str] = None
    assignment_max_points: Optional[int] = None
    student_name: Optional[str] = None
    teacher_name: Optional[str] = None
    percentage: Optional[float] = None
    
    class Config:
        from_attributes = True

# --- Grade Check Schemas ---

class GradeCheckResponse(BaseModel):
    already_graded: bool
    assignment_id: int
    assignment_title: str
    student_id: int
    student_name: str
    max_points: int
    grade_id: Optional[int] = None
    points_earned: Optional[int] = None
    percentage: Optional[float] = None
    feedback: Optional[str] = None
    graded_date: Optional[str] = None
    teacher_id: Optional[int] = None

class GradeDetailResponse(BaseModel):
    id: int
    assignment_id: int
    assignment_title: str
    assignment_description: str
    assignment_rubric: str
    student_id: int
    student_name: str
    points_earned: int
    max_points: int
    percentage: float
    feedback: Optional[str] = None
    graded_date: Optional[str] = None
    teacher_id: int
    ai_generated: Optional[bool] = False
    ai_confidence: Optional[int] = None

class StudentGradeReport(BaseModel):
    student_id: int
    student_name: str
    subject_id: int
    subject_name: str
    grades: List[GradeResponse] = []
    total_assignments: int = 0
    completed_assignments: int = 0
    average_percentage: Optional[float] = None

class SubjectGradesSummary(BaseModel):
    subject_id: int
    subject_name: str
    total_assignments: int = 0
    total_students: int = 0
    grades_given: int = 0
    average_class_score: Optional[float] = None
    assignments: List[AssignmentWithGrades] = []

# --- Bulk Grading Schemas ---

class BulkGradeItem(BaseModel):
    student_id: int
    points_earned: int = Field(..., ge=0)
    feedback: Optional[str] = None

class BulkGradeCreate(BaseModel):
    assignment_id: int
    grades: List[BulkGradeItem]

class BulkGradeResponse(BaseModel):
    successful_grades: List[GradeResponse] = []
    failed_grades: List[dict] = []
    total_processed: int = 0
    total_successful: int = 0
    total_failed: int = 0

# Update forward references
AssignmentWithGrades.model_rebuild()

# --- New Enhanced Schemas for Image Upload and PDF Generation Workflow ---

class StudentImageUpload(BaseModel):
    assignment_id: int = Field(..., description="Assignment ID")
    student_id: int = Field(..., description="Student ID")
    image_description: Optional[str] = Field(None, max_length=500, description="Optional image description")

class ImageUploadResponse(BaseModel):
    id: int
    assignment_id: int
    student_id: int
    filename: str
    original_filename: str
    file_path: str
    file_size: int
    mime_type: str
    upload_date: datetime
    is_processed: bool = False
    
    # Include related info
    assignment_title: Optional[str] = None
    student_name: Optional[str] = None
    subject_name: Optional[str] = None
    
    class Config:
        from_attributes = True

class StudentPDF(BaseModel):
    id: int
    assignment_id: int
    student_id: int
    pdf_filename: str
    pdf_path: str
    image_count: int
    generated_date: datetime
    is_graded: bool = False
    grade_id: Optional[int] = None
    
    # Include related info
    assignment_title: Optional[str] = None
    student_name: Optional[str] = None
    subject_name: Optional[str] = None
    max_points: Optional[int] = None
    
    class Config:
        from_attributes = True

class AssignmentImageSummary(BaseModel):
    assignment_id: int
    assignment_title: str
    subject_name: str
    total_students: int
    students_with_images: int
    students_with_pdfs: int
    total_images: int
    students_data: List[dict] = []  # [{student_id, student_name, image_count, has_pdf, pdf_id}]

class BulkPDFGenerationRequest(BaseModel):
    assignment_id: int = Field(..., description="Assignment to generate PDFs for")
    
class BulkPDFGenerationResponse(BaseModel):
    success: bool
    assignment_id: int
    total_students: int
    pdfs_generated: int
    pdfs_failed: int
    generated_pdfs: List[StudentPDF] = []
    errors: List[dict] = []

class GradingSessionCreate(BaseModel):
    assignment_id: int = Field(..., description="Assignment to create grading session for")
    
class GradingSessionResponse(BaseModel):
    id: int
    assignment_id: int
    teacher_id: int
    subject_id: int
    created_date: datetime
    is_completed: bool = False
    
    # Related data
    assignment_title: Optional[str] = None
    subject_name: Optional[str] = None
    teacher_name: Optional[str] = None
    student_pdfs: List[StudentPDF] = []
    total_students: int = 0
    graded_count: int = 0
    
    class Config:
        from_attributes = True

class AutoGradeRequest(BaseModel):
    session_id: int = Field(..., description="Grading session ID")
    feedback_type: str = Field(default="detailed", pattern="^(detailed|summary|both)$")
    use_ai_grading: bool = Field(default=True, description="Use AI for automatic grading")
    
class AutoGradeResponse(BaseModel):
    success: bool
    session_id: int
    assignment_id: int
    total_students: int
    successfully_graded: int
    failed_gradings: int
    average_score: Optional[float] = None
    processed_at: datetime
    student_results: List[dict] = []
    batch_summary: dict
    errors: List[dict] = []

# --- Bulk Upload Schemas ---

class BulkUploadStudentInfo(BaseModel):
    student_id: int
    student_name: str
    has_pdf: bool = False
    pdf_id: Optional[int] = None
    image_count: int = 0
    generated_date: Optional[str] = None
    is_graded: bool = False

class AssignmentStudentsResponse(BaseModel):
    assignment_id: int
    assignment_title: str
    subject_name: str
    total_students: int
    students: List[BulkUploadStudentInfo] = []

class BulkUploadResponse(BaseModel):
    success: bool = True
    message: str = "PDF created successfully"
    assignment_id: int
    student_id: int
    pdf_id: int
    pdf_filename: str
    student_name: str
    assignment_title: str
    total_images: int
    generated_date: datetime

class BulkUploadDeleteResponse(BaseModel):
    message: str
    assignment_id: int
    student_id: int
    deleted_filename: str
