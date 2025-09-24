from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from Endpoints import auth, school_management, academic_management, grades, school_invitations, class_room, modules, syllabus, upload, kana_service, reports, calendar
from Endpoints.after_school import course, grades as after_school_grades, uploads as after_school_uploads, reading_assistant
from db.connection import engine
from db.database import test_connection
from dotenv import load_dotenv
import logging
import sys
import os

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Run startup initialization if not already done
try:
    logger.info("🚀 Initializing BrainInk Backend...")
    
    # Initialize database tables safely
    try:
        import models.users_models as models
        import models.study_area_models as study_models
        import models.afterschool_models as afterschool_models
        import models.reading_assistant_models as reading_models
        
        # Safe table creation with error handling
        from db.database import engine
        from models.users_models import Base
        
        logger.info("📊 Creating database tables...")
        Base.metadata.create_all(bind=engine, checkfirst=True)
        logger.info("✅ Database tables ready!")
        
    except Exception as db_error:
        logger.warning(f"⚠️ Database initialization issue: {db_error}")
        logger.info("🔄 Application will continue - tables will be created on first access")
        
except Exception as startup_error:
    logger.error(f"❌ Startup error: {startup_error}")
    logger.info("🔄 Continuing with application startup...")

from sqlalchemy import text

app = FastAPI(
    title="BrainInk API",
    description="Backend API for BrainInk application with Study Area Management",
    version="1.0.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173", 
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
        "https://brainink.vercel.app",
        "https://brain-ink.vercel.app",  # Add both Vercel URLs
        "https://brainink.org",
        "https://www.brainink.org",
        "https://brainink-frontend.onrender.com"
        # Remove "*" wildcard when using credentials
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "HEAD", "PATCH"],
    allow_headers=[
        "Accept",
        "Accept-Language",
        "Content-Language", 
        "Content-Type",
        "Authorization",
        "X-Requested-With",
        "Origin",
        "Cache-Control",
        "Pragma"
    ],
    expose_headers=["*"]
)

# Health check endpoint for Render
@app.get("/health")
async def health_check():
    """Health check endpoint for deployment monitoring"""
    try:
        with engine.connect() as connection:
            result = connection.execute(text("SELECT 1"))
            db_status = "healthy"
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        db_status = f"unhealthy: {str(e)}"
    
    return {
        "status": "healthy" if db_status == "healthy" else "degraded",
        "database": db_status,
        "service": "BrainInk Backend API",
        "version": "1.0.0"
    }

# Root endpoint
@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "BrainInk Backend API is running!",
        "status": "healthy",
        "docs": "/docs",
        "health": "/health"
    }

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
            
        # Verify all routers are loaded
        print(f"✅ Loaded auth router with {len(auth.router.routes)} endpoints")
        print(f"✅ Loaded school_management router with {len(school_management.router.routes)} endpoints")
        print(f"✅ Loaded academic_management router with {len(academic_management.router.routes)} endpoints")
        print(f"✅ Loaded grades router with {len(grades.router.routes)} endpoints")
        print(f"✅ Loaded school_invitations router with {len(school_invitations.router.routes)} endpoints")
        print(f"✅ Loaded class_room router with {len(class_room.router.routes)} endpoints")
        print(f"✅ Loaded modules router with {len(modules.router.routes)} endpoints")
        print(f"✅ Loaded syllabus router with {len(syllabus.router.routes)} endpoints")
        print(f"✅ Loaded upload router with {len(upload.router.routes)} endpoints")
        print(f"✅ Loaded kana_service router with {len(kana_service.router.routes)} endpoints")
        print(f"✅ Loaded reports router with {len(reports.router.routes)} endpoints")
        print(f"✅ Loaded calendar router with {len(calendar.router.routes)} endpoints")
        print(f"✅ Loaded after_school course router with {len(course.router.routes)} endpoints")
        print(f"✅ Loaded after_school grades router with {len(after_school_grades.router.routes)} endpoints")
        print(f"✅ Loaded after_school uploads router with {len(after_school_uploads.router.routes)} endpoints")
        print(f"✅ Loaded reading assistant router with {len(reading_assistant.router.routes)} endpoints")
        total_endpoints = len(auth.router.routes) + len(school_management.router.routes) + len(academic_management.router.routes) + len(grades.router.routes) + len(school_invitations.router.routes) + len(class_room.router.routes) + len(modules.router.routes) + len(syllabus.router.routes) + len(upload.router.routes) + len(kana_service.router.routes) + len(reports.router.routes) + len(calendar.router.routes) + len(course.router.routes) + len(after_school_grades.router.routes) + len(after_school_uploads.router.routes) + len(reading_assistant.router.routes)
        print(f"🔄 Total endpoints: {total_endpoints}")
    except Exception as e:
        logger.warning(f"⚠️ Router loading issue: {e}")

# Additional table creation (fallback if startup script didn't run)
try:
    logger.info("🔄 Ensuring all model tables exist...")
    models.Base.metadata.create_all(bind=engine, checkfirst=True)
    study_models.Base.metadata.create_all(bind=engine, checkfirst=True)
    afterschool_models.Base.metadata.create_all(bind=engine, checkfirst=True) 
    reading_models.Base.metadata.create_all(bind=engine, checkfirst=True)
    logger.info("✅ All model tables verified!")
except Exception as e:
    logger.warning(f"⚠️ Additional table creation warning: {e}")
    logger.info("🔄 Application will continue...")

# Include routers
app.include_router(auth.router)
app.include_router(school_management.router, prefix="/study-area")
app.include_router(academic_management.router, prefix="/study-area/academic")
app.include_router(grades.router, prefix="/study-area/grades")
app.include_router(school_invitations.router, prefix="/study-area")
app.include_router(class_room.router, prefix="/study-area")
app.include_router(modules.router, prefix="/study-area/modules/quizzes")
app.include_router(syllabus.router, prefix="/study-area")
app.include_router(upload.router, prefix="/study-area")
app.include_router(kana_service.router, prefix="/kana")
app.include_router(reports.router, prefix="/study-area/reports")
app.include_router(calendar.router, prefix="/study-area/calendar")

# Include after-school learning endpoints
app.include_router(course.router)  # Already has prefix /after-school/courses
app.include_router(after_school_grades.router)  # Already has prefix /after-school/sessions  
app.include_router(after_school_uploads.router)  # Already has prefix /after-school/uploads
app.include_router(reading_assistant.router)  # Already has prefix /after-school/reading-assistant

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