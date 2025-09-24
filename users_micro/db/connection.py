from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from .database import engine, SessionLocal
from typing import Annotated
from models.users_models import Base

import os, time
from sqlalchemy import text

# ---------------------------------------------------------------------------
# Resilient schema ensure (keeps existing behavior but avoids hard crash)
# ---------------------------------------------------------------------------
INIT_RETRIES = int(os.getenv("DB_INIT_RETRIES", "6"))            # total attempts
INIT_BASE_DELAY = float(os.getenv("DB_INIT_BASE_DELAY", "1"))    # seconds

def _probe():
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))

def safe_create_all():
    for attempt in range(1, INIT_RETRIES + 1):
        try:
            _probe()
            Base.metadata.create_all(bind=engine)
            if attempt > 1:
                print(f"✅ Schema ensured after retry attempt {attempt}")
            else:
                print("✅ Schema ensured (first attempt)")
            return
        except Exception as e:
            print(f"⚠️ create_all attempt {attempt}/{INIT_RETRIES} failed: {e}")
            if attempt == INIT_RETRIES:
                print("❌ Final create_all attempt failed; continuing without fatal crash.")
                return
            time.sleep(INIT_BASE_DELAY * attempt)

# Execute guarded schema creation
safe_create_all()

def get_db():
    db = SessionLocal()
    try:
        yield db
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(status_code=500, detail="Database connection error")
    finally:
        db.close()

db_dependency = Annotated[Session, Depends(get_db)]
