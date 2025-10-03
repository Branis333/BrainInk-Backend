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

# Create engine with Supabase-optimized settings
engine = create_engine(
    DATABASE_URL,
    pool_size=int(os.getenv("DB_POOL_SIZE", 10)),
    max_overflow=int(os.getenv("DB_MAX_OVERFLOW", 20)),
    pool_timeout=int(os.getenv("DB_POOL_TIMEOUT", 30)),
    pool_recycle=int(os.getenv("DB_POOL_RECYCLE", 3600)),
    echo=False,  # Set to True for debugging
    # Add SSL settings for Supabase
    connect_args={
        "sslmode": "require",
        "options": "-c timezone=utc"
    }
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# Test connection function (optional)
def test_connection():
    try:
        with engine.connect() as connection:
            result = connection.execute("SELECT NOW();")
            print("Connection successful! Current time:", result.fetchone()[0])
            return True
    except Exception as e:
        print(f"Failed to connect: {e}")
        return False