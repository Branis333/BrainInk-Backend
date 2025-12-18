from pydantic import BaseModel, EmailStr
from enum import Enum
from datetime import datetime
from typing import Optional, List

class InvitationType(str, Enum):
    student = "student"
    teacher = "teacher"

class SchoolInvitationCreate(BaseModel):
    email: EmailStr
    invitation_type: InvitationType
    school_id: int

class SchoolInvitationOut(BaseModel):
    id: int
    email: str
    invitation_type: InvitationType
    school_id: int
    school_name: str
    invited_by: int  # Principal's user ID
    invited_date: datetime
    is_used: bool
    used_date: Optional[datetime] = None
    is_active: bool
    
    class Config:
        from_attributes = True

class BulkInvitationCreate(BaseModel):
    emails: List[EmailStr]
    invitation_type: InvitationType
    school_id: int

class BulkInvitationResponse(BaseModel):
    success_count: int
    failed_count: int
    successful_invitations: List[SchoolInvitationOut]
    failed_emails: List[str]
    errors: List[str]

class JoinSchoolByEmailRequest(BaseModel):
    school_id: int
    
class JoinSchoolResponse(BaseModel):
    success: bool
    message: str
    school_name: str
    role: str
    school_id: int
