from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

# --- Assignment Schemas ---

class AssignmentBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    subtopic: Optional[str] = Field(None, max_length=100)
    max_points: int = Field(100, ge=1, le=1000)
    due_date: Optional[datetime] = None

class AssignmentCreate(AssignmentBase):
    subject_id: int

class AssignmentUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
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
