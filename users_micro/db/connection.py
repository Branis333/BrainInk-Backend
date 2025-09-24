from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from .database import get_engine, get_session_local
from typing import Annotated
from models.users_models import Base

# Initialize engine and SessionLocal lazily
engine = None
SessionLocal = None

def initialize_database():
    """Initialize database connection and create tables"""
    global engine, SessionLocal
    if engine is None:
        try:
            engine = get_engine()
            SessionLocal = get_session_local()
            
            # Debug: Check if engine is actually set
            if engine is None:
                print("❌ Engine is still None after get_engine()")
                return
                
            # Try to create tables, but don't fail if it doesn't work
            Base.metadata.create_all(bind=engine)
            print("✅ Tables created successfully")
        except Exception as e:
            print(f"⚠️ Database initialization failed: {e}")
            print("🔄 Application will continue without initial table creation")
            # Ensure engine and SessionLocal are set even if table creation fails
            if engine is None:
                engine = get_engine()
            if SessionLocal is None:
                SessionLocal = get_session_local()

def get_db():
    # Initialize database if not already done
    if engine is None or SessionLocal is None:
        initialize_database()
    
    db = SessionLocal()
    try:
        yield db
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Database connection error")
    finally:
        db.close()


db_dependency = Annotated[Session, Depends(get_db)]
