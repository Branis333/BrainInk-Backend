from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

# --- Subject Schemas ---
class SubjectBase(BaseModel):
    name: str
    description: Optional[str] = None

class SubjectCreate(SubjectBase):
    school_id: int

class SubjectOut(SubjectBase):
    id: int
    school_id: int
    created_by: int
    created_date: datetime
    is_active: bool
    
    class Config:
        from_attributes = True

class SubjectWithDetails(SubjectOut):
    teacher_count: int
    student_count: int

# --- Subject Assignment Schemas ---
class SubjectTeacherAssignment(BaseModel):
    subject_id: int
    teacher_id: int

class SubjectStudentAssignment(BaseModel):
    subject_id: int
    student_id: int

# --- Subject with Teachers and Students ---
class TeacherInfo(BaseModel):
    id: int
    user_id: int
    name: str
    email: str
    
    class Config:
        from_attributes = True

class StudentInfo(BaseModel):
    id: int
    user_id: int
    name: str
    email: str
    
    class Config:
        from_attributes = True

class SubjectWithMembers(SubjectOut):
    teachers: List[TeacherInfo] = []
    students: List[StudentInfo] = []
