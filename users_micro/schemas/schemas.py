from pydantic import BaseModel, EmailStr,conlist, validator,root_validator,ValidationError,Field
from typing import List, Optional, Literal
from datetime import date, datetime
from schemas.return_schemas import ReturnUser


class CreateUserRequest(BaseModel):  # registeration Schema
    fname: Optional[str] = None
    lname: Optional[str] = None
    username: Optional[str] = None
    email: Optional[EmailStr] = None
    password: Optional[str] = None
    class Config:
        orm_mode = True
        from_attributes = True


class Token(BaseModel):  # token validation schema
    access_token: Optional[str] = None
    token_type: Optional[str] = None
    UserInfo: ReturnUser
    class Config:
        orm_mode = True
        from_attributes = True



class FromData(BaseModel):  # token validation schema
    username: Optional[str]
    password: Optional[str]
    class Config:
        orm_mode = True
        from_attributes = True

class UserLogin(BaseModel):  # login schema
    username: Optional[str] = None
    password: Optional[str] = None
    class Config:
        orm_mode = True
        from_attributes = True

