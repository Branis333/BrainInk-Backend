from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from Endpoints import auth
from db.connection import engine
import models.users_models as models

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

# Create database tables
models.Base.metadata.create_all(bind=engine)

# Include routers
app.include_router(auth.router)

@app.get("/")
def root():
    return {"message": "Welcome to BrainInk API"}