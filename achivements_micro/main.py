from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from Endpoints import achivements as auth
from Endpoints import tournaments
from db.connection import engine
from db.database import test_connection
import models.models as models
import models.tournament_models as tournament_models
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
            
        # Create database tables for both models
        print("Creating database tables...")
        models.Base.metadata.create_all(bind=engine)
        tournament_models.Base.metadata.create_all(bind=engine)
        print("✅ All database tables created successfully!")
        
    except Exception as e:
        print(f"❌ Supabase connection failed: {e}")

# Include routers
app.include_router(auth.router)
app.include_router(tournaments.router)

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
    """Initialize database with default ranks, achievements, and tournament tables"""
    try:
        # Create tables if they don't exist
        print("Creating achievement tables...")
        models.Base.metadata.create_all(bind=engine)
        
        print("Creating tournament tables...")
        tournament_models.Base.metadata.create_all(bind=engine)
        
        print("✅ All tables created successfully!")
        
        return {
            "message": "Database initialized successfully!", 
            "tables_created": [
                "achievements", "ranks", "users", "user_achievements", "user_ranks", "otp",
                "tournaments", "tournament_participants", "tournament_brackets", 
                "tournament_matches", "tournament_invitations", "tournament_questions"
            ]
        }
    except Exception as e:
        return {"error": f"Initialization failed: {str(e)}"}

@app.get("/database-status")
def database_status():
    """Get detailed database status and table information"""
    try:
        with engine.connect() as connection:
            # Check if tables exist
            tables_query = text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
                ORDER BY table_name;
            """)
            result = connection.execute(tables_query)
            tables = [row[0] for row in result.fetchall()]
            
            return {
                "database_connected": True,
                "total_tables": len(tables),
                "tables": tables
            }
    except Exception as e:
        return {
            "database_connected": False,
            "error": str(e),
            "total_tables": 0,
            "tables": []
        }