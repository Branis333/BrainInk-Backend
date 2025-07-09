from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class ClassroomBase(BaseModel):
    name: str
    school_id: int
    description: Optional[str] = None
    capacity: Optional[int] = 30
    location: Optional[str] = None

class ClassroomCreate(ClassroomBase):
    teacher_id: Optional[int] = None
    subject_ids: Optional[List[int]] = []

class ClassroomUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    capacity: Optional[int] = None
    location: Optional[str] = None
    teacher_id: Optional[int] = None

class ClassroomOut(ClassroomBase):
    id: int
    teacher_id: Optional[int] = None
    created_date: datetime
    is_active: bool
    
    class Config:
        from_attributes = True

class ClassroomWithDetails(ClassroomOut):
    assigned_teacher: Optional[dict] = None
    student_count: int = 0
    subjects: Optional[List[dict]] = []
