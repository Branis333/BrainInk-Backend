from pydantic import BaseModel
from datetime import datetime
from typing import Optional
from models.study_area_models import SchoolRequestStatus

class SchoolRequestBase(BaseModel):
    school_name: str
    school_address: Optional[str] = None

class SchoolRequestCreate(SchoolRequestBase):
    pass

class SchoolRequestUpdate(BaseModel):
    status: SchoolRequestStatus
    admin_notes: Optional[str] = None

class SchoolRequestOut(SchoolRequestBase):
    id: int
    principal_id: int
    request_date: datetime
    status: SchoolRequestStatus
    admin_notes: Optional[str] = None
    reviewed_by: Optional[int] = None
    reviewed_date: Optional[datetime] = None
    
    class Config:
        from_attributes = True

class SchoolRequestWithPrincipal(SchoolRequestOut):
    principal_name: str
    principal_email: str
    
    class Config:
        from_attributes = True
