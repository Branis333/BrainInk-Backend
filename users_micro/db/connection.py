from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from .database import engine, SessionLocal
from typing import Annotated
from models.users_models import Base
import time
import logging

# Setup logging
logger = logging.getLogger(__name__)

def create_tables_with_retry(max_retries=5, delay=2):
    """Create tables with retry mechanism for Render deployment"""
    for attempt in range(max_retries):
        try:
            logger.info(f"Attempting to create tables (attempt {attempt + 1}/{max_retries})...")
            Base.metadata.create_all(bind=engine)
            logger.info("✅ Database tables created successfully!")
            return True
        except Exception as e:
            logger.warning(f"❌ Attempt {attempt + 1} failed: {str(e)}")
            if attempt < max_retries - 1:
                logger.info(f"⏳ Retrying in {delay} seconds...")
                time.sleep(delay)
                delay *= 2  # Exponential backoff
            else:
                logger.error("❌ All attempts to create tables failed!")
                # Don't raise error on startup - let app start without initial table creation
                # Tables will be created on first database access
                return False
    return False

# Try to create tables, but don't fail startup if it doesn't work
try:
    create_tables_with_retry()
except Exception as e:
    logger.warning(f"⚠️ Could not create tables on startup: {e}. Tables will be created on first access.")

def get_db():
    db = SessionLocal()
    try:
        # Test connection and create tables if needed
        try:
            db.execute("SELECT 1")
        except Exception as conn_error:
            logger.warning(f"Database connection issue, attempting to create tables: {conn_error}")
            try:
                Base.metadata.create_all(bind=engine)
            except Exception as create_error:
                logger.error(f"Could not create tables: {create_error}")
        
        yield db
    except SQLAlchemyError as e:
        logger.error(f"Database error: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Database connection error")
    finally:
        db.close()


db_dependency = Annotated[Session, Depends(get_db)]
