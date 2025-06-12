from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from Endpoints import friends, squads
from db.database import engine, test_connection
import models.friends_models as friends_models
import models.squad_models as squad_models
from sqlalchemy import text
import os

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("🚀 Starting Friends & Squads service...")
    print(f"Environment: {os.getenv('ENVIRONMENT', 'development')}")
    print(f"Port: {os.getenv('PORT', 'not set')}")
    
    # Test database connection
    print("Testing database connection...")
    try:
        with engine.connect() as connection:
            result = connection.execute(text("SELECT NOW() as current_time;"))
            row = result.fetchone()
            print(f"✅ Database connection successful!")
            print(f"Database time: {row[0]}")
            
            # Test if squad tables exist
            try:
                squad_count = connection.execute(text("SELECT COUNT(*) FROM squads")).fetchone()
                print(f"✅ Squad tables accessible - Total squads: {squad_count[0]}")
            except Exception as e:
                print(f"⚠️ Squad tables may not exist yet: {e}")
                
    except Exception as e:
        print(f"❌ Database connection failed: {e}")

    # Create database tables
    print("Creating database tables...")
    try:
        friends_models.Base.metadata.create_all(bind=engine)
        print("✅ Friends tables created/verified")
    except Exception as e:
        print(f"❌ Error creating friends tables: {e}")

    try:
        squad_models.Base.metadata.create_all(bind=engine)
        print("✅ Squad tables created/verified")
    except Exception as e:
        print(f"❌ Error creating squad tables: {e}")
    
    print("✅ Friends & Squads service startup complete!")
    
    yield  # Application runs here
    
    # Shutdown
    print("🛑 Shutting down Friends & Squads service...")

app = FastAPI(
    title="BrainInk Friends & Squads API",
    description="Friends, Chat, and Squad microservice for BrainInk application",
    version="1.0.0",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "HEAD", "OPTIONS"],  # Added HEAD
    allow_headers=["*"],
)

# Include routers
app.include_router(friends.router)
app.include_router(squads.router)

# Support both GET and HEAD for root endpoint
@app.get("/")
@app.head("/")
def root():
    return {
        "message": "Welcome to BrainInk Friends & Squads API",
        "services": ["friends", "chat", "squads", "battles", "leagues"],
        "version": "1.0.0",
        "status": "running",
        "port": os.getenv("PORT", "not set")
    }

# Support both GET and HEAD for health check
@app.get("/health")
@app.head("/health")
def health_check():
    """Health check endpoint"""
    try:
        with engine.connect() as connection:
            # Test basic connection
            connection.execute(text("SELECT 1"))
            
            # Test friends tables
            try:
                friends_count = connection.execute(text("SELECT COUNT(*) FROM friendships")).fetchone()
                friends_status = "accessible"
            except Exception:
                friends_count = [0]
                friends_status = "not_accessible"
            
            # Test squad tables
            try:
                squads_count = connection.execute(text("SELECT COUNT(*) FROM squads")).fetchone()
                squad_tables_status = "accessible"
            except Exception:
                squads_count = [0]
                squad_tables_status = "not_accessible"
            
            db_status = "connected"
    except Exception as e:
        db_status = "disconnected"
        friends_count = [0]
        squads_count = [0]
        friends_status = "error"
        squad_tables_status = "error"
    
    return {
        "status": "healthy",
        "services": ["friends", "squads"],
        "database": db_status,
        "tables": {
            "friends": {
                "count": friends_count[0] if friends_count else 0,
                "status": friends_status
            },
            "squads": {
                "count": squads_count[0] if squads_count else 0,
                "status": squad_tables_status
            }
        }
    }

# Simple ping endpoint for health checks
@app.get("/ping")
@app.head("/ping")
def ping():
    """Simple ping endpoint"""
    return {"message": "pong", "timestamp": "2024-01-01T00:00:00Z"}

# Rest of your endpoints...
@app.get("/services")
def get_services():
    """Get available services and endpoints"""
    return {
        "friends_service": {
            "endpoints": [
                "/friends/request/send/{user_id}",
                "/friends/request/respond/{user_id}",
                "/friends/list/{user_id}",
                "/friends/message/send/{user_id}",
                "/friends/conversation/{user_id}/{friend_username}"
            ]
        },
        "squads_service": {
            "endpoints": [
                "/squads/create",
                "/squads/user/{user_id}/squads",
                "/squads/join/{squad_id}",
                "/squads/message/send",
                "/squads/messages/{squad_id}",
                "/squads/study-leagues",
                "/squads/battles",
                "/squads/challenge"
            ]
        }
    }