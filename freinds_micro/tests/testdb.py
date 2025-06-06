from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from Endpoints import friends
from db.database import engine, test_connection
import models.friends_models as models
from sqlalchemy import text

app = FastAPI(
    title="BrainInk Friends API",
    description="Friends and Chat microservice for BrainInk application",
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
    print("Testing database connection for Friends service...")
    try:
        with engine.connect() as connection:
            result = connection.execute(text("SELECT NOW() as current_time;"))
            row = result.fetchone()
            print(f"✅ Database connection successful!")
            print(f"Database time: {row[0]}")
    except Exception as e:
        print(f"❌ Database connection failed: {e}")

# Create database tables
models.Base.metadata.create_all(bind=engine)

# Include routers
app.include_router(friends.router)

@app.get("/")
def root():
    return {"message": "Welcome to BrainInk Friends API"}

@app.get("/health")
def health_check():
    """Health check endpoint"""
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
            db_status = "connected"
    except Exception:
        db_status = "disconnected"
    
    return {
        "status": "healthy",
        "service": "friends",
        "database": db_status
    }