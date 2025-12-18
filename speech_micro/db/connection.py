from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.exc import OperationalError, DisconnectionError
from sqlalchemy import text
from .database import SessionLocal
from typing import Annotated

def get_db():
    """Get database session with proper error handling"""
    db = None
    try:
        db = SessionLocal()
        # Test the connection with a simple query
        db.execute(text("SELECT 1"))
        yield db
    except (OperationalError, DisconnectionError) as e:
        print(f"Database connection error: {e}")
        if db:
            try:
                db.rollback()
            except:
                pass
        raise HTTPException(
            status_code=503, 
            detail="Database connection error. Please try again."
        )
    except Exception as e:
        print(f"Database session setup error: {e}")
        raise e
    finally:
        if db:
            try:
                db.close()
            except:
                pass

db_dependency = Annotated[Session, Depends(get_db)]