from pydantic import BaseModel

class StudentBase(BaseModel):
    user_id: int
    school_id: int
    classroom_id: int | None = None

class StudentCreate(StudentBase):
    pass

class StudentOut(StudentBase):
    id: int
    class Config:
        from_attributes = True
