from sqlalchemy import create_engine, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import QueuePool
import os
import time
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

# Validate DATABASE_URL exists
if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is not set")

print(f"Database URL configured: {DATABASE_URL[:20]}..." if DATABASE_URL else "No DATABASE_URL found")

# Enhanced engine configuration for Render deployment
engine = create_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_size=int(os.getenv("DB_POOL_SIZE", 2)),  # Reduced for Render free tier
    max_overflow=int(os.getenv("DB_MAX_OVERFLOW", 3)),  # Reduced for Render free tier
    pool_timeout=int(os.getenv("DB_POOL_TIMEOUT", 30)),
    pool_recycle=int(os.getenv("DB_POOL_RECYCLE", 1800)),  # 30 minutes
    pool_pre_ping=True,  # Important - validates connections before use
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
    """Test database connection with enhanced retry logic"""
    max_retries = 5
    base_delay = 1
    
    for attempt in range(max_retries):
        try:
            print(f"Testing database connection (attempt {attempt + 1}/{max_retries})...")
            
            with engine.connect() as connection:
                result = connection.execute(text("SELECT NOW() as current_time, version() as db_version;"))
                current_time = result.fetchone()
                print(f"✅ Database connection successful!")
                print(f"Database time: {current_time[0]}")
                print(f"Database version: {current_time[1][:50]}...")
                return True
                
        except Exception as e:
            print(f"❌ Connection attempt {attempt + 1} failed: {e}")
            
            if attempt < max_retries - 1:
                delay = base_delay * (2 ** attempt)  # Exponential backoff
                print(f"Retrying in {delay} seconds...")
                time.sleep(delay)
            else:
                print(f"❌ Failed to connect after {max_retries} attempts")
                return False
    
    return False

def test_connection_simple():
    """Simple connection test for health checks"""
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
            return True
    except Exception as e:
        print(f"Simple connection test failed: {e}")
        return False

def get_db_with_retry():
    """Get database session with retry logic"""
    max_retries = 3
    base_delay = 1
    
    for attempt in range(max_retries):
        try:
            db = SessionLocal()
            # Test the connection
            db.execute(text("SELECT 1"))
            return db
        except Exception as e:
            print(f"Database session attempt {attempt + 1} failed: {e}")
            if 'db' in locals():
                try:
                    db.close()
                except:
                    pass
                    
            if attempt < max_retries - 1:
                delay = base_delay * (2 ** attempt)
                time.sleep(delay)
            else:
                raise e

def check_database_health():
    """Comprehensive database health check"""
    try:
        with engine.connect() as connection:
            # Test basic connection
            connection.execute(text("SELECT 1"))
            
            # Test if our tables exist
            try:
                result = connection.execute(text("""
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name IN ('users', 'friendships', 'squads', 'squad_memberships')
                """))
                tables = [row[0] for row in result.fetchall()]
                
                return {
                    "connection": "healthy",
                    "tables_found": tables,
                    "tables_count": len(tables)
                }
            except Exception as table_error:
                return {
                    "connection": "healthy",
                    "tables_error": str(table_error),
                    "tables_count": 0
                }
                
    except Exception as e:
        return {
            "connection": "failed",
            "error": str(e)
        }

# Test connection on import (for debugging)
if __name__ == "__main__":
    print("Testing database connection...")
    if test_connection():
        print("✅ Database is ready!")
        health = check_database_health()
        print(f"Health check: {health}")
    else:
        print("❌ Database connection failed!")