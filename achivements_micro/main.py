from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from Endpoints import achivements as auth
from db.connection import engine
from db.database import test_connection
import models.models as models
from sqlalchemy import text

app = FastAPI(
    title="BrainInk API",
    description="Backend API for BrainInk application",
    version="1.0.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Test database connection on startup
@app.on_event("startup")
async def startup_event():
    print("Testing Supabase connection...")
    try:
        # Test connection directly here
        with engine.connect() as connection:
            result = connection.execute(text("SELECT NOW() as current_time, version() as db_version;"))
            row = result.fetchone()
            print(f"✅ Supabase connection successful!")
            print(f"Database time: {row[0]}")
            print(f"Database version: {row[1]}")
    except Exception as e:
        print(f"❌ Supabase connection failed: {e}")

# Create database tables
models.Base.metadata.create_all(bind=engine)

# Include routers
app.include_router(auth.router)

@app.get("/")
def root():
    return {"message": "Welcome to BrainInk API"}

@app.get("/health")
def health_check():
    """Health check endpoint with database status"""
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
            db_status = "connected"
    except Exception:
        db_status = "disconnected"
    
    return {
        "status": "healthy",
        "database": db_status
    }

@app.post("/initialize-database")
def initialize_database():
    """Initialize database with default ranks and achievements"""
    try:
        from init_db import main as init_main
        success = init_main()
        if success:
            return {"message": "Database initialized successfully!"}
        else:
            return {"error": "Failed to initialize database"}
    except Exception as e:
        return {"error": f"Initialization failed: {str(e)}"}