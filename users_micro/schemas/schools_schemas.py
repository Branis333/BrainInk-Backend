from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class SchoolBase(BaseModel):
    name: str
    address: str | None = None

class SchoolCreate(SchoolBase):
    principal_id: int

class SchoolOut(SchoolBase):
    id: int
    principal_id: int
    created_date: datetime
    is_active: bool
    
    class Config:
        from_attributes = True

class SchoolWithStats(SchoolOut):
    total_students: int
    total_teachers: int
    total_classrooms: int
    active_access_codes: int
    
    class Config:
        from_attributes = True
