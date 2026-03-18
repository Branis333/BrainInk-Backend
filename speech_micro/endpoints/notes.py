from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
import sys
import os

# Add parent directory to path
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

from db.database import SessionLocal
from services.gemini_service import GeminiNotesService
from schemas.notes_schemas import (
    GenerateNotesRequest,
    GenerateNotesResponse,
    NotesListResponse,
    StudyNotesResponse
)

router = APIRouter(prefix="/notes", tags=["Study Notes"])

def get_db():
    """Database dependency"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/generate")
async def generate_study_notes(
    request: GenerateNotesRequest,
    user_id: int = Query(..., description="User ID"),
    db: Session = Depends(get_db)
):
    """Generate study notes from transcription text using Gemini AI"""
    
    try:
        gemini_service = GeminiNotesService(db)
        
        result = gemini_service.generate_study_notes(
            transcription_text=request.text,
            user_id=user_id,
            subject=request.subject,
            language=request.language
        )
        
        return result
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print(f"Error generating notes: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate study notes")

@router.get("/list")
async def get_user_notes(
    user_id: int = Query(..., description="User ID"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    db: Session = Depends(get_db)
):
    """Get user's study notes with pagination"""
    
    try:
        gemini_service = GeminiNotesService(db)
        result = gemini_service.get_user_notes(user_id, page, page_size)
        
        return result
        
    except Exception as e:
        print(f"Error getting user notes: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve notes")

@router.get("/{notes_id}")
async def get_notes_by_id(
    notes_id: int,
    user_id: int = Query(..., description="User ID"),
    db: Session = Depends(get_db)
):
    """Get specific study notes by ID"""
    
    try:
        gemini_service = GeminiNotesService(db)
        result = gemini_service.get_notes_by_id(notes_id, user_id)
        
        if not result["success"]:
            raise HTTPException(status_code=404, detail=result["error"])
        
        return result["notes"]
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error getting notes by ID: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve notes")

@router.delete("/{notes_id}")
async def delete_notes(
    notes_id: int,
    user_id: int = Query(..., description="User ID"),
    db: Session = Depends(get_db)
):
    """Delete study notes"""
    
    try:
        gemini_service = GeminiNotesService(db)
        result = gemini_service.delete_notes(notes_id, user_id)
        
        if not result["success"]:
            raise HTTPException(status_code=404, detail=result["error"])
        
        return {"message": result["message"]}
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error deleting notes: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete notes")