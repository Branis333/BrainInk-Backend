from pydantic import BaseModel
from models.study_area_models import UserRole

class RoleBase(BaseModel):
    name: UserRole
    description: str | None = None

class RoleCreate(RoleBase):
    pass

class RoleOut(RoleBase):
    id: int
    
    class Config:
        from_attributes = True
