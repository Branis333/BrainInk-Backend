from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from Endpoints import auth, school_management, academic_management, grades, school_invitations, class_room, modules, syllabus, upload
from db.connection import engine
from db.database import test_connection
import models.users_models as models
import models.study_area_models as study_models
from sqlalchemy import text

app = FastAPI(
    title="BrainInk API",
    description="Backend API for BrainInk application with Study Area Management",
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
        total_endpoints = len(auth.router.routes) + len(school_management.router.routes) + len(academic_management.router.routes) + len(grades.router.routes) + len(school_invitations.router.routes) + len(class_room.router.routes) + len(modules.router.routes) + len(syllabus.router.routes) + len(upload.router.routes)
        print(f"🔄 Total endpoints: {total_endpoints}")
    except Exception as e:
        print(f"❌ Supabase connection failed: {e}")

# Create database tables
models.Base.metadata.create_all(bind=engine)
study_models.Base.metadata.create_all(bind=engine)

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