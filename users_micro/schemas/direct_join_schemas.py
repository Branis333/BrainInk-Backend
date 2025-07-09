from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class DirectSchoolJoinRequest(BaseModel):
    school_id: int
    email: str

class SchoolSelectionResponse(BaseModel):
    id: int
    name: str
    address: Optional[str]
    principal_name: Optional[str]
    total_students: int
    total_teachers: int
    is_accepting_applications: bool = True
    created_date: datetime
    user_role: Optional[str] = None  # Role of current user in this school

class JoinRequestResponse(BaseModel):
    message: str
    status: str
    school_name: str
    request_id: Optional[int] = None
    note: str
    success: Optional[bool] = None
    school_id: Optional[int] = None
    role: Optional[str] = None
