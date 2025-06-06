from sqlalchemy import create_engine, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import QueuePool
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

# Enhanced engine configuration for better connection handling
engine = create_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_size=int(os.getenv("DB_POOL_SIZE", 5)),
    max_overflow=int(os.getenv("DB_MAX_OVERFLOW", 10)),
    pool_timeout=int(os.getenv("DB_POOL_TIMEOUT", 30)),
    pool_recycle=int(os.getenv("DB_POOL_RECYCLE", 1800)),  # 30 minutes
    pool_pre_ping=True,  # This is important - validates connections before use
    pool_reset_on_return='commit',
    echo=False,  # Set to True for debugging SQL queries
    connect_args={
        "connect_timeout": 60,
        "application_name": "friends_microservice",
        "options": "-c default_transaction_isolation=read_committed"
    }
)

SessionLocal = sessionmaker(
    autocommit=False, 
    autoflush=False, 
    bind=engine,
    expire_on_commit=False  # Prevent expired object errors
)

Base = declarative_base()

def get_database():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def test_connection():
    """Test database connection with retry logic"""
    max_retries = 3
    for attempt in range(max_retries):
        try:
            with engine.connect() as connection:
                result = connection.execute(text("SELECT NOW() as current_time, version() as db_version;"))
                current_time = result.fetchone()
                print(f"Database time: {current_time[0]}")
                print(f"Database version: {current_time[1]}")
                return True
        except Exception as e:
            print(f"Connection attempt {attempt + 1} failed: {e}")
            if attempt == max_retries - 1:
                print(f"Failed to connect after {max_retries} attempts")
                return False
    return False

def get_db_with_retry():
    """Get database session with retry logic"""
    max_retries = 3
    for attempt in range(max_retries):
        try:
            db = SessionLocal()
            # Test the connection
            db.execute(text("SELECT 1"))
            return db
        except Exception as e:
            print(f"Database connection attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                if 'db' in locals():
                    db.close()
                continue
            else:
                raise e