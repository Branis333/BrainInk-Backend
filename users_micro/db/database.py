from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv()

# Option 1: Use full DATABASE_URL (recommended for your current setup)
DATABASE_URL = os.getenv("DATABASE_URL")

# Option 2: Build from components (if you prefer Supabase's approach)
# USER = os.getenv("DB_USER", "postgres")
# PASSWORD = os.getenv("DB_PASSWORD")
# HOST = os.getenv("DB_HOST")
# PORT = os.getenv("DB_PORT", "5432")
# DBNAME = os.getenv("DB_NAME", "postgres")
# DATABASE_URL = f"postgresql://{USER}:{PASSWORD}@{HOST}:{PORT}/{DBNAME}"

# Global variable to hold the engine (will be created lazily)
engine = None

def get_engine():
    """Create engine lazily only when needed"""
    global engine
    if engine is None:
        if not DATABASE_URL:
            raise ValueError("DATABASE_URL environment variable is not set")
            
        # Ensure DATABASE_URL has SSL mode
        db_url = DATABASE_URL
        if "sslmode=" not in db_url and "postgresql://" in db_url:
            separator = "&" if "?" in db_url else "?"
            db_url = f"{db_url}{separator}sslmode=require"
            
        # Create engine with Render/Supabase-optimized settings
        engine = create_engine(
            db_url,
            pool_size=int(os.getenv("DB_POOL_SIZE", 5)),  # Reduced for Render's free tier
            max_overflow=int(os.getenv("DB_MAX_OVERFLOW", 10)),  # Reduced for better stability
            pool_timeout=int(os.getenv("DB_POOL_TIMEOUT", 30)),
            pool_recycle=int(os.getenv("DB_POOL_RECYCLE", 1800)),  # 30 minutes instead of 1 hour
            pool_pre_ping=True,  # Test connections before use - CRITICAL for Render
            echo=False,  # Set to True for debugging
            # Enhanced SSL and connection settings for Render
            connect_args={
                "sslmode": "require",
                "options": "-c timezone=utc",
                "connect_timeout": 10,  # Connection timeout
                "application_name": "BrainInk-Backend"
            }
        )
    return engine

def get_session_local():
    """Create SessionLocal lazily only when needed"""
    engine = get_engine()
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# Test connection function (optional)
def test_connection():
    try:
        engine = get_engine()
        from sqlalchemy import text
        with engine.connect() as connection:
            result = connection.execute(text("SELECT NOW();"))
            print("Connection successful! Current time:", result.fetchone()[0])
            return True
    except Exception as e:
        print(f"Failed to connect: {e}")
        return False