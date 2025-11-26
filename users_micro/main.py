from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from Endpoints import auth, school_management, academic_management, grades, school_invitations, class_room, modules, syllabus, upload, kana_service, reports, calendar
from Endpoints.after_school import (
    course,
    grades as after_school_grades,
    uploads as after_school_uploads,
    reading_assistant,
    quiz as after_school_quiz,
    assignments as after_school_assignments,
    ai_tutor as after_school_ai_tutor,
    notes as after_school_notes,
    notifications,
)
from Endpoints import payments
from Endpoints.after_school.notification_scheduler import setup_notification_scheduler
from db.database import get_engine, test_connection
from dotenv import load_dotenv
import logging

# Logger setup
logger = logging.getLogger("brainink.main")
logging.basicConfig(level=logging.INFO)

# Load environment variables
load_dotenv()
import models.users_models as models
import models.study_area_models as study_models
import models.afterschool_models as afterschool_models
import models.reading_assistant_models as reading_models
import models.ai_tutor_models as ai_tutor_models
import models.payments_models as payments_models
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

# Test database connection on startup
@app.on_event("startup")
async def startup_event():
    print("Testing database connection (lazy engine)...")
    try:
        engine = get_engine()
        with engine.connect() as connection:
            result = connection.execute(text("SELECT NOW() as current_time"))
            row = result.fetchone()
            print(f"✅ Database connection OK. Time: {row[0]}")
    except Exception as e:
        print(f"⚠️ Database not available at startup: {e}")
    # Log routers (no DB dependency)
    total_endpoints = sum(len(r.routes) for r in [auth.router, school_management.router, academic_management.router, grades.router, school_invitations.router, class_room.router, modules.router, syllabus.router, upload.router, kana_service.router, reports.router, calendar.router, course.router, after_school_grades.router, after_school_uploads.router, reading_assistant.router, after_school_assignments.router])
    print(f"🔄 Total endpoints loaded: {total_endpoints}")
    
    # Setup notification scheduler
    print("🔔 Setting up notification scheduler...")
    scheduler = setup_notification_scheduler()
    if scheduler:
        print("✅ Notification scheduler started successfully")
    else:
        print("⚠️ Notification scheduler failed to start")

"""Remove eager table creation; handled in startup_event with lazy engine."""

# Defer table creation to startup to avoid engine None issues

@app.on_event("startup")
async def create_tables_startup():
    try:
        engine = get_engine()
        for base in [models.Base, study_models.Base, afterschool_models.Base, reading_models.Base, ai_tutor_models.Base, payments_models.Base]:
            base.metadata.create_all(bind=engine, checkfirst=True)
        logger.info("✅ Tables ensured (lazy engine)")
    except Exception as e:
        logger.warning(f"⚠️ Table ensure failed: {e}")

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
app.include_router(after_school_uploads.legacy_router)  # Legacy compatibility for older mobile clients
app.include_router(reading_assistant.router)  # Already has prefix /after-school/reading-assistant
app.include_router(after_school_quiz.router)  # New: /after-school/quiz (ephemeral practice quizzes)
app.include_router(after_school_assignments.router)  # New: /after-school/assignments
app.include_router(after_school_ai_tutor.router)  # New: /after-school/ai-tutor
app.include_router(after_school_notes.router)  # New: /after-school/notes (image-based student notes with AI analysis)
app.include_router(notifications.router)  # New: /after-school/notifications (push notification system)
app.include_router(payments.router)  # New: /payments/flutterwave
app.include_router(payments.sub_router)  # Alias: /subscriptions/status for mobile client compatibility

@app.get("/")
def root():
    return {"message": "Welcome to BrainInk API"}

@app.get("/_debug/routes")
def list_routes():
    """Return a list of all registered routes (method + path).
    Helpful for quickly confirming which endpoints are live in this process.
    """
    routes = []
    for route in app.router.routes:
        try:
            methods = sorted([m for m in getattr(route, 'methods', set()) if m not in {"HEAD", "OPTIONS"}])
            path = getattr(route, 'path', None) or getattr(route, 'path_format', '')
            routes.append({
                "methods": methods,
                "path": path
            })
        except Exception:
            continue
    # Sort by path for readability
    routes.sort(key=lambda r: r["path"])
    return {"count": len(routes), "routes": routes}

@app.get("/health")
def health_check():
    """Health check endpoint with database status"""
    try:
        engine = get_engine()
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
            db_status = "connected"
    except Exception:
        db_status = "disconnected"
    
    return {
        "status": "healthy",
        "database": db_status
    }