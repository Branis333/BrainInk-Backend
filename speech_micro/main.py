from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from endpoints.speech import router as speech_router
import os
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(
    title="BrainInk Speech-to-Text API",
    description="Microservice for converting speech to text",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure this properly for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(speech_router)

@app.get("/")
async def root():
    return {"message": "Welcome to BrainInk Speech-to-Text API"}

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "speech-to-text",
        "version": "1.0.0"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)