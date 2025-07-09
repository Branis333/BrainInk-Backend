from pydantic import BaseModel
from enum import Enum
from datetime import datetime
from typing import Optional

class AccessCodeType(str, Enum):
    student = "student"
    teacher = "teacher"

class AccessCodeBase(BaseModel):
    code_type: AccessCodeType
    school_id: int

class AccessCodeCreate(AccessCodeBase):
    email: str  # Email of the student/teacher this code is for

class AccessCodeOut(AccessCodeBase):
    id: int
    code: str
    email: str
    created_date: datetime
    is_active: bool
    
    class Config:
        from_attributes = True

class JoinSchoolRequest(BaseModel):
    school_name: str
    email: str
    access_code: str
