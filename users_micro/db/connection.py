from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from .database import engine, SessionLocal
from typing import Annotated
from models.users_models import Base

Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Database connection error")
    finally:
        db.close()


db_dependency = Annotated[Session, Depends(get_db)]
