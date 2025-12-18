from pydantic import BaseModel

class TeacherBase(BaseModel):
    user_id: int
    school_id: int
    classroom_id: int | None = None

class TeacherCreate(TeacherBase):
    pass

class TeacherOut(TeacherBase):
    id: int
    class Config:
        from_attributes = True
