from pydantic import BaseModel, EmailStr,validator,Field
from typing import List, Optional, Literal
from datetime import date,datetime


class ReturnUser(BaseModel):
    username: Optional[str] = None
    email: Optional[EmailStr] = None
    fname: Optional[str] = None
    lname: Optional[str] = None
    class Config:
        orm_mode = True
        from_attributes = True

    
   