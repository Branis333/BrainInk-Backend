from dotenv import load_dotenv

# Load environment variables FIRST before any other imports
load_dotenv()

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import uvicorn

# Import routers
from endpoints.speech import router as speech_router
from endpoints.notes import router as notes_router
from endpoints.video_call import router as video_call_router

# Import database setup
from db.database import engine
# from models.speech_models import Base as SpeechBase
from models.notes_models import Base as NotesBase
from models.video_call_models import Base as VideoCallBase  # Add video call models

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("Creating database tables...")
    try:
        NotesBase.metadata.create_all(bind=engine)
        VideoCallBase.metadata.create_all(bind=engine)  # Create video call tables
        print("Database tables created successfully")
    except Exception as e:
        print(f"Error creating tables: {e}")
    
    yield
    
    # Shutdown
    print("Shutting down...")

app = FastAPI(
    title="BrainInk Speech & Notes API",
    description="Speech-to-text transcription and AI-powered study notes generation",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(speech_router)
app.include_router(notes_router)
app.include_router(video_call_router)

# Mount static files
app.mount("/test", StaticFiles(directory="test"), name="test")

@app.get("/")
async def root():
    return {
        "message": "BrainInk Speech & Notes API",
        "version": "1.0.0",
        "services": ["speech-to-text", "ai-study-notes", "video-calls"],
        "endpoints": {
            "speech": "/speech",
            "notes": "/notes",
            "video-calls": "/video-calls",
            "docs": "/docs"
        }
    }

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "brainink-api"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)