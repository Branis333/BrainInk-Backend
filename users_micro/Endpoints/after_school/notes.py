"""
Student Notes Endpoints
API routes for uploading notes as images and AI-powered analysis using Gemini Vision
Students upload handwritten or printed school notes as images (JPG, PNG, GIF, BMP, WEBP)
System uses Gemini Vision API directly to analyze images and extract summary, key points, and concepts

NOTE: These notes are STANDALONE - not tied to courses or assignments
"""

import logging
import json
import aiofiles
import hashlib
from pathlib import Path
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends, File, UploadFile, Form, status, Query
from fastapi.responses import JSONResponse
from sqlalchemy import and_, desc, or_
from sqlalchemy.orm import Session

from users_micro.db.connection import db_dependency
from Endpoints.auth import get_current_user
from models.afterschool_models import StudentNote, NoteAnalysisLog
from schemas.afterschool_schema import (
    StudentNoteCreate, StudentNoteUpdate, StudentNoteOut, StudentNoteListResponse,
    NoteUploadResponse, NoteAnalysisResponse, MessageResponse,
    ObjectiveQuizResponse, FlashcardsResponse, QuizGradeRequest, Flashcard, QuizQuestion,
    QuizSubmitRequest, QuizSubmitResponse
)
from services.notes_service import notes_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/after-school/notes", tags=["Student Notes & AI Analysis"])

# Dependency for current user
user_dependency = Depends(get_current_user)

# Upload directory for notes
NOTES_UPLOAD_DIR = Path("uploads/notes")
NOTES_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# Configuration
MAX_FILE_SIZE = 20 * 1024 * 1024  # 20MB
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"}


# ===============================
# UTILITY FUNCTIONS
# ===============================

def generate_unique_filename(original_filename: str, user_id: int, note_id: int) -> str:
    """Generate unique filename while preserving extension"""
    file_ext = Path(original_filename).suffix.lower()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    unique_name = f"note_{note_id}_user_{user_id}_{timestamp}_{original_filename}"
    return unique_name


def _to_list(value):
    """Best-effort conversion of potentially stringified JSON arrays to actual lists.
    - If value is already a list or None, return as-is
    - If value is a JSON string representing a list, parse it
    - If it's a comma-separated string, split to list
    - If it's an empty string or 'null', return None
    """
    if value is None or isinstance(value, list):
        return value
    if isinstance(value, (bytes, bytearray)):
        try:
            value = value.decode("utf-8", errors="ignore")
        except Exception:
            value = str(value)
    if isinstance(value, str):
        s = value.strip()
        if not s or s.lower() == "null":
            return None
        # Try JSON first
        try:
            parsed = json.loads(s)
            if isinstance(parsed, list):
                return parsed
        except Exception:
            pass
        # Fallback: comma-separated
        if "," in s:
            return [part.strip() for part in s.split(",") if part.strip()]
        # As a last resort, wrap string in list if it looks like a bracket-starting fragment
        if s.startswith("[") and s.endswith("]"):
            try:
                parsed = json.loads(s + "")
                if isinstance(parsed, list):
                    return parsed
            except Exception:
                return None
        return [s]
    # Unknown type -> coerce to string list
    return [str(value)]


def _normalise_note_instance(note: StudentNote) -> StudentNote:
    """Mutate ORM instance fields to expected types for Pydantic serialization."""
    note.key_points = _to_list(getattr(note, "key_points", None))
    note.main_topics = _to_list(getattr(note, "main_topics", None))
    note.learning_concepts = _to_list(getattr(note, "learning_concepts", None))
    note.questions_generated = _to_list(getattr(note, "questions_generated", None))
    note.tags = _to_list(getattr(note, "tags", None))
    return note


# ===============================
# NOTE UPLOAD & ANALYSIS (SINGLE ENDPOINT)
# ===============================

@router.post("/upload", response_model=dict, status_code=status.HTTP_201_CREATED)
async def upload_and_analyze_notes(
    db: db_dependency,
    current_user: dict = user_dependency,
    title: str = Form(..., description="Note title"),
    files: List[UploadFile] = File(..., description="Note image files (JPG, PNG, GIF, BMP, WEBP)"),
    description: Optional[str] = Form(None, description="Optional description"),
    subject: Optional[str] = Form(None, description="Subject/topic"),
    course_id: Optional[int] = Form(None, description="Link to course (optional - for organizational purposes only)"),
    tags: Optional[str] = Form(None, description="Comma-separated tags")
):
    """
    Upload one or more student notes as images and analyze them with Gemini Vision AI.
    
    This endpoint combines upload and analysis in ONE step:
    1. Validates and saves image files
    2. Sends images DIRECTLY to Gemini Vision API (no OCR)
    3. Returns comprehensive analysis including summary, key points, topics, and study questions
    
    These notes are STANDALONE - not tied to courses or assignments.
    The course_id is optional and only used for organizational purposes.
    
    Supports: JPG, PNG, GIF, BMP, WEBP image formats
    Returns: Note details with AI analysis results
    """
    user_id = current_user["user_id"]
    
    # Convert course_id=0 to None to avoid FK constraint violations
    if course_id == 0:
        course_id = None
    
    try:
        if not files or len(files) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No files provided"
            )
        
        # Validate all files are images & size constraints early
        invalid_files = []
        oversized_files = []
        valid_files: List[UploadFile] = []
        for file in files:
            if not file.filename:
                invalid_files.append("<no name>")
                continue
            ext = Path(file.filename).suffix.lower()
            if ext not in ALLOWED_EXTENSIONS:
                invalid_files.append(file.filename)
                continue
            # Size check
            if hasattr(file, 'size') and file.size and file.size > MAX_FILE_SIZE:
                oversized_files.append(f"{file.filename} ({round(file.size/1024/1024,2)}MB)")
                continue
            valid_files.append(file)

        if invalid_files:
            raise HTTPException(status_code=400, detail=f"Invalid file types: {', '.join(invalid_files)}. Allowed: JPG, PNG, GIF, BMP, WEBP")
        if oversized_files:
            raise HTTPException(status_code=400, detail=f"Oversized files: {', '.join(oversized_files)} > {MAX_FILE_SIZE//1024//1024}MB limit")
        if not valid_files:
            raise HTTPException(status_code=400, detail="No valid image files found after validation")

        # Reset file pointers and read image data
        image_files_data = []
        image_filenames = []
        for f in valid_files:
            try:
                if hasattr(f.file, 'seek') and f.file.seekable():
                    f.file.seek(0)
                img_bytes = await f.read()
                image_files_data.append(img_bytes)
                image_filenames.append(f.filename)
            except Exception as read_err:
                raise HTTPException(status_code=500, detail=f"Failed to read image file {f.filename}: {read_err}")
        
        logger.info(f"📸 Loaded {len(image_files_data)} images for notes analysis")
        
        # Calculate content hash from all images combined
        hasher = hashlib.sha256()
        for img_data in image_files_data:
            hasher.update(img_data)
        content_hash = hasher.hexdigest()
        
        # Calculate total size of all images
        total_size = sum(len(img_data) for img_data in image_files_data)
        
        # Parse tags
        parsed_tags = [tag.strip() for tag in tags.split(',')] if tags else []
        
        # Create database record
        student_note = StudentNote(
            user_id=user_id,
            course_id=course_id,
            title=title,
            description=description,
            subject=subject,
            tags=parsed_tags if parsed_tags else None,
            original_filename=", ".join(image_filenames),  # Store all filenames
            file_type="images",
            file_size=total_size,
            processing_status="processing",
            ai_processed=False
        )
        
        db.add(student_note)
        db.flush()  # Get ID
        
        # Save images to upload directory
        saved_file_paths = []
        for idx, (img_data, img_filename) in enumerate(zip(image_files_data, image_filenames)):
            unique_filename = generate_unique_filename(f"{idx+1}_{img_filename}", user_id, student_note.id)
            file_path = NOTES_UPLOAD_DIR / unique_filename
            try:
                async with aiofiles.open(file_path, 'wb') as f:
                    await f.write(img_data)
                saved_file_paths.append(str(file_path))
            except Exception as save_err:
                raise HTTPException(status_code=500, detail=f"Failed to save image file: {save_err}")
        
        # Store primary file path (first image) for database reference
        primary_file_path = saved_file_paths[0] if saved_file_paths else None
        student_note.file_path = primary_file_path
        
        db.commit()
        db.refresh(student_note)
        
        # Process with AI using Gemini Vision (NO OCR!)
        logger.info(f"🤖 Starting Gemini Vision analysis for note {student_note.id}")
        start_time = datetime.utcnow()
        
        # Initialize results
        analysis_result = None
        
        try:
            # Analyze notes using Gemini Vision directly on images
            analysis_result = await notes_service.analyze_notes_from_images(
                image_files=image_files_data,
                image_filenames=image_filenames,
                note_title=title,
                note_subject=subject,
                note_description=description
            )
            
            processing_duration = (datetime.utcnow() - start_time).total_seconds()
            
            # Update database with analysis results
            if analysis_result and analysis_result.get("success"):
                student_note.summary = analysis_result.get("summary")
                student_note.key_points = analysis_result.get("key_points")
                student_note.main_topics = analysis_result.get("main_topics")
                student_note.learning_concepts = analysis_result.get("learning_concepts")
                student_note.questions_generated = analysis_result.get("questions_generated")
                student_note.objectives = analysis_result.get("objectives")
                student_note.ai_processed = True
                student_note.processing_status = "completed"
                student_note.processed_at = datetime.utcnow()
                
                logger.info(f"✅ AI analysis completed for note {student_note.id}")
            else:
                student_note.processing_status = "failed"
                student_note.processing_error = analysis_result.get("error", "Unknown error") if analysis_result else "AI analysis failed"
                logger.error(f"❌ AI analysis failed for note {student_note.id}: {student_note.processing_error}")
            
            db.commit()
            db.refresh(student_note)
            
            # Log analysis attempt
            log_entry = NoteAnalysisLog(
                note_id=student_note.id,
                user_id=user_id,
                processing_type="vision_analysis",
                status=student_note.processing_status,
                processing_duration_seconds=processing_duration,
                error_message=student_note.processing_error if not analysis_result.get("success") else None,
                result_data=analysis_result
            )
            db.add(log_entry)
            db.commit()
            
        except Exception as ai_err:
            logger.error(f"❌ Error during AI analysis: {ai_err}")
            student_note.processing_status = "failed"
            student_note.processing_error = str(ai_err)
            db.commit()
            analysis_result = {"success": False, "error": str(ai_err)}
        
        # Return comprehensive response
        return JSONResponse({
            "success": True,
            "message": "Notes uploaded and analyzed successfully" if student_note.ai_processed else "Notes uploaded but analysis failed",
            "note_id": student_note.id,
            "title": student_note.title,
            "subject": student_note.subject,
            "total_images": len(valid_files),
            "total_size": total_size,
            "content_hash": content_hash,
            "image_files": [Path(p).name for p in saved_file_paths],
            "ai_processed": student_note.ai_processed,
            "processing_status": student_note.processing_status,
            "processing_error": student_note.processing_error,
            "analysis_results": {
                "summary": student_note.summary,
                "key_points": student_note.key_points,
                "main_topics": student_note.main_topics,
                "learning_concepts": student_note.learning_concepts,
                "questions_generated": student_note.questions_generated,
                "objectives": student_note.objectives,
            } if student_note.ai_processed else None,
            "processed_at": student_note.processed_at.isoformat() if student_note.processed_at else None,
            "created_at": student_note.created_at.isoformat() if student_note.created_at else None
        })
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading and analyzing notes: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error uploading and analyzing notes: {str(e)}"
        )


@router.get("/{note_id}", response_model=StudentNoteOut)
async def get_student_note(
    note_id: int,
    db: db_dependency,
    current_user: dict = user_dependency
):
    """Get detailed information about a student note"""
    user_id = current_user["user_id"]
    
    note = db.query(StudentNote).filter(
        and_(
            StudentNote.id == note_id,
            StudentNote.user_id == user_id
        )
    ).first()
    
    if not note:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Note not found"
        )
    
    return _normalise_note_instance(note)


@router.get("", response_model=StudentNoteListResponse)
async def list_student_notes(
    db: db_dependency,
    current_user: dict = user_dependency,
    course_id: Optional[int] = Query(None, description="Filter by course (optional)"),
    subject: Optional[str] = Query(None, description="Filter by subject (optional)"),
    is_starred: Optional[bool] = Query(None, description="Filter by starred status (optional)"),
    limit: int = Query(100, ge=1, le=200, description="Maximum results"),
    offset: int = Query(0, ge=0, description="Pagination offset")
):
    """
    Get all notes for the current user.
    
    Returns all notes belonging to the authenticated user, ordered by most recent first.
    Supports optional filtering by course_id, subject, or starred status.
    """
    user_id = current_user["user_id"]
    
    # Base query - get ALL notes for this user
    query = db.query(StudentNote).filter(StudentNote.user_id == user_id)
    
    # Apply optional filters
    if course_id is not None:
        query = query.filter(StudentNote.course_id == course_id)
    
    if subject:
        query = query.filter(StudentNote.subject.ilike(f"%{subject}%"))
    
    if is_starred is not None:
        query = query.filter(StudentNote.is_starred == is_starred)
    
    # Get total count
    total = query.count()
    
    # Get paginated results, ordered by most recent first
    notes = query.order_by(desc(StudentNote.created_at)).offset(offset).limit(limit).all()
    # Normalise any legacy/stringified JSON fields to lists for safe serialization
    notes = [_normalise_note_instance(n) for n in notes]
    
    return StudentNoteListResponse(total=total, notes=notes)


# ===============================
# OBJECTIVE QUIZ & FLASHCARDS
# ===============================

@router.post("/{note_id}/objectives/{objective_index}/quiz", response_model=ObjectiveQuizResponse)
async def generate_objective_quiz(
    note_id: int,
    objective_index: int,
    db: db_dependency,
    current_user: dict = user_dependency,
    num_questions: int = Form(7, ge=5, le=10),
):
    """Generate 5-10 MCQ questions for a specific objective."""
    user_id = current_user["user_id"]

    note: StudentNote = db.query(StudentNote).filter(
        and_(StudentNote.id == note_id, StudentNote.user_id == user_id)
    ).first()
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    if not note.objectives or not isinstance(note.objectives, list):
        raise HTTPException(status_code=400, detail="Objectives not available for this note")

    # Support 1-based objective index from client; normalise to 0-based
    idx = objective_index
    if idx >= len(note.objectives) and 1 <= objective_index <= len(note.objectives):
        idx = objective_index - 1
    if idx < 0 or idx >= len(note.objectives):
        raise HTTPException(status_code=400, detail="Invalid objective index")

    obj = note.objectives[idx]
    objective_text = obj.get("objective") if isinstance(obj, dict) else str(obj)
    objective_summary = obj.get("summary") if isinstance(obj, dict) else None

    questions = await notes_service.generate_quiz_for_objective(objective_text, objective_summary, num_questions)
    return ObjectiveQuizResponse(
        note_id=note.id,
        objective_index=idx,
        objective=objective_text,
        num_questions=len(questions),
        questions=[QuizQuestion(**q) for q in questions],
        generated_at=datetime.utcnow(),
    )


@router.post("/{note_id}/objectives/{objective_index}/quiz/grade", response_model=MessageResponse)
async def submit_objective_quiz_grade(
    note_id: int,
    objective_index: int,
    payload: QuizGradeRequest,
    db: db_dependency,
    current_user: dict = user_dependency,
):
    """Store/update the latest grade percentage and a short performance summary for an objective."""
    user_id = current_user["user_id"]
    note: StudentNote = db.query(StudentNote).filter(
        and_(StudentNote.id == note_id, StudentNote.user_id == user_id)
    ).first()
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    if not note.objectives or not isinstance(note.objectives, list):
        raise HTTPException(status_code=400, detail="Objectives not available for this note")

    # Normalise index
    idx = objective_index
    if idx >= len(note.objectives) and 1 <= objective_index <= len(note.objectives):
        idx = objective_index - 1
    if idx < 0 or idx >= len(note.objectives):
        raise HTTPException(status_code=400, detail="Invalid objective index")

    progress = note.objective_progress or []
    # Ensure list large enough
    while len(progress) < len(note.objectives):
        progress.append({})
    progress[idx] = {
        "objective_index": idx,
        "latest_grade": float(payload.grade_percentage),
        "performance_summary": payload.performance_summary or "",
        "last_quiz_at": datetime.utcnow().isoformat(),
    }
    note.objective_progress = progress
    note.updated_at = datetime.utcnow()
    db.commit()

    return MessageResponse(message="Objective quiz grade stored successfully")


@router.post("/{note_id}/objectives/{objective_index}/flashcards", response_model=FlashcardsResponse)
async def generate_objective_flashcards(
    note_id: int,
    objective_index: int,
    db: db_dependency,
    current_user: dict = user_dependency,
    count: int = Form(8, ge=5, le=10),
):
    """Generate flashcards for a specific objective and persist them on the note."""
    user_id = current_user["user_id"]

    note: StudentNote = db.query(StudentNote).filter(
        and_(StudentNote.id == note_id, StudentNote.user_id == user_id)
    ).first()
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    if not note.objectives or not isinstance(note.objectives, list):
        raise HTTPException(status_code=400, detail="Objectives not available for this note")

    idx = objective_index
    if idx >= len(note.objectives) and 1 <= objective_index <= len(note.objectives):
        idx = objective_index - 1
    if idx < 0 or idx >= len(note.objectives):
        raise HTTPException(status_code=400, detail="Invalid objective index")

    obj = note.objectives[idx]
    content = obj.get("summary") or obj.get("objective") or note.summary or ""
    cards = await notes_service.generate_flashcards_from_content(content, count)

    # Persist in objective_flashcards
    existing = note.objective_flashcards or []
    while len(existing) < len(note.objectives):
        existing.append([])
    existing[idx] = cards
    note.objective_flashcards = existing
    note.updated_at = datetime.utcnow()
    db.commit()

    return FlashcardsResponse(
        note_id=note.id,
        scope="objective",
        objective_index=idx,
        count=len(cards),
        flashcards=[Flashcard(**c) for c in cards],
        generated_at=datetime.utcnow(),
    )


@router.post("/{note_id}/flashcards", response_model=FlashcardsResponse)
async def generate_overall_flashcards(
    note_id: int,
    db: db_dependency,
    current_user: dict = user_dependency,
    count: int = Form(8, ge=5, le=10),
):
    """Generate flashcards from the entire note summary and persist them."""
    user_id = current_user["user_id"]
    note: StudentNote = db.query(StudentNote).filter(
        and_(StudentNote.id == note_id, StudentNote.user_id == user_id)
    ).first()
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    if not note.summary:
        raise HTTPException(status_code=400, detail="Note has no summary yet")

    cards = await notes_service.generate_flashcards_from_content(note.summary, count)
    note.overall_flashcards = cards
    note.updated_at = datetime.utcnow()
    db.commit()

    return FlashcardsResponse(
        note_id=note.id,
        scope="overall",
        objective_index=None,
        count=len(cards),
        flashcards=[Flashcard(**c) for c in cards],
        generated_at=datetime.utcnow(),
    )


# ===============================
# SIMPLE ROUTES (OBJECTIVE VIA PARAM)
# ===============================

@router.post("/{note_id}/quiz", response_model=ObjectiveQuizResponse)
async def generate_quiz_from_note(
    note_id: int,
    db: db_dependency,
    current_user: dict = user_dependency,
    num_questions: int = Form(7, ge=5, le=10),
    objective_index: int = Form(..., description="Objective index (1-based or 0-based)")
):
    """Wrapper: generate quiz for a specific objective using simpler route."""
    return await generate_objective_quiz(
        note_id=note_id,
        objective_index=objective_index,
        db=db,
        current_user=current_user,
        num_questions=num_questions,
    )


@router.post("/{note_id}/quiz/submit", response_model=QuizSubmitResponse)
async def submit_quiz_answers(
    note_id: int,
    payload: QuizSubmitRequest,
    db: db_dependency,
    current_user: dict = user_dependency,
):
    """Submit quiz answers for a specific objective, compute grade, store progress, and return results."""
    user_id = current_user["user_id"]

    note: StudentNote = db.query(StudentNote).filter(
        and_(StudentNote.id == note_id, StudentNote.user_id == user_id)
    ).first()
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    if not note.objectives or not isinstance(note.objectives, list):
        raise HTTPException(status_code=400, detail="Objectives not available for this note")

    # Normalise index
    idx = payload.objective_index
    if idx >= len(note.objectives) and 1 <= payload.objective_index <= len(note.objectives):
        idx = payload.objective_index - 1
    if idx < 0 or idx >= len(note.objectives):
        raise HTTPException(status_code=400, detail="Invalid objective index")

    # Compute score
    questions = payload.questions
    answers = payload.user_answers
    if not questions or not answers or len(questions) != len(answers):
        raise HTTPException(status_code=400, detail="questions and user_answers length must match and be non-empty")

    total = len(questions)
    correct = 0
    for q, a in zip(questions, answers):
        try:
            if int(a) == int(q.answer_index):
                correct += 1
        except Exception:
            continue
    grade_percentage = round((correct / total) * 100, 2)

    # Optional performance summary generation
    perf_summary = None
    try:
        obj = note.objectives[idx]
        objective_text = obj.get("objective") if isinstance(obj, dict) else str(obj)
        summary_text = obj.get("summary") if isinstance(obj, dict) else ""
        feedback_prompt = (
            f"Provide a single short paragraph (max 4 sentences) of feedback for a student who scored {grade_percentage}% "
            f"on the objective '{objective_text}'. Base it on this objective summary: {summary_text}."
        )
        fb = await notes_service.generate_flashcards_from_content(feedback_prompt, count=1)
        # Reuse flashcard generator to get concise text; pick 'back' or 'front' as feedback container
        if fb:
            perf_summary = fb[0].get("back") or fb[0].get("front")
    except Exception:
        perf_summary = None

    # Persist progress
    progress = note.objective_progress or []
    while len(progress) < len(note.objectives):
        progress.append({})
    progress[idx] = {
        "objective_index": idx,
        "latest_grade": grade_percentage,
        "performance_summary": perf_summary or "",
        "last_quiz_at": datetime.utcnow().isoformat(),
    }
    note.objective_progress = progress
    note.updated_at = datetime.utcnow()
    db.commit()

    return QuizSubmitResponse(
        note_id=note.id,
        objective_index=idx,
        total_questions=total,
        correct_count=correct,
        grade_percentage=grade_percentage,
        performance_summary=perf_summary,
        submitted_at=datetime.utcnow(),
    )


@router.post("/{note_id}/flashcards", response_model=FlashcardsResponse)
async def generate_flashcards_for_note(
    note_id: int,
    db: db_dependency,
    current_user: dict = user_dependency,
    count: int = Form(8, ge=5, le=10),
    objective_index: int = Form(..., description="Objective index (1-based or 0-based)")
):
    """Wrapper: generate flashcards for a specific objective using simpler route."""
    return await generate_objective_flashcards(
        note_id=note_id,
        objective_index=objective_index,
        db=db,
        current_user=current_user,
        count=count,
    )


@router.get("/search/query", response_model=StudentNoteListResponse)
async def search_student_notes(
    db: db_dependency,
    current_user: dict = user_dependency,
    q: str = Query(..., min_length=1, description="Search query (searches title, subject, and tags)"),
    sort_by: str = Query("recent", description="Sort by: recent, title, subject"),
    limit: int = Query(100, ge=1, le=200, description="Maximum results"),
    offset: int = Query(0, ge=0, description="Pagination offset")
):
    """
    Search student notes by title, subject, and tags.
    
    Query Parameter 'q':
    - Searches in note title (case-insensitive)
    - Searches in note subject (case-insensitive)
    - Searches in note tags
    - Searches in note summary (AI analysis results)
    
    Sort Options:
    - recent: Most recently created first (default)
    - title: Alphabetically by title
    - subject: Grouped by subject
    """
    user_id = current_user["user_id"]
    
    # Base query - get all notes for this user
    query = db.query(StudentNote).filter(StudentNote.user_id == user_id)
    
    # Apply search filter - search across multiple fields
    search_pattern = f"%{q}%"
    query = query.filter(
        or_(
            StudentNote.title.ilike(search_pattern),
            StudentNote.subject.ilike(search_pattern),
            StudentNote.summary.ilike(search_pattern),
            StudentNote.description.ilike(search_pattern),
            # For tags, we search if the tag is in the JSON array
        )
    )
    
    # Get total count after search
    total = query.count()
    
    # Apply sorting
    if sort_by == "title":
        query = query.order_by(StudentNote.title.asc())
    elif sort_by == "subject":
        query = query.order_by(StudentNote.subject.asc(), desc(StudentNote.created_at))
    else:  # Default: recent
        query = query.order_by(desc(StudentNote.created_at))
    
    # Apply pagination
    notes = query.offset(offset).limit(limit).all()
    notes = [_normalise_note_instance(n) for n in notes]
    
    return StudentNoteListResponse(total=total, notes=notes)


@router.put("/{note_id}", response_model=StudentNoteOut)
async def update_student_note(
    note_id: int,
    update_data: StudentNoteUpdate,
    db: db_dependency,
    current_user: dict = user_dependency
):
    """Update student note metadata"""
    user_id = current_user["user_id"]
    
    note = db.query(StudentNote).filter(
        and_(
            StudentNote.id == note_id,
            StudentNote.user_id == user_id
        )
    ).first()
    
    if not note:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Note not found"
        )
    
    # Update fields if provided
    update_dict = update_data.dict(exclude_unset=True)
    for field, value in update_dict.items():
        setattr(note, field, value)
    
    note.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(note)
    
    return note


@router.delete("/{note_id}", response_model=MessageResponse)
async def delete_student_note(
    note_id: int,
    db: db_dependency,
    current_user: dict = user_dependency
):
    """Delete a student note"""
    user_id = current_user["user_id"]
    
    note = db.query(StudentNote).filter(
        and_(
            StudentNote.id == note_id,
            StudentNote.user_id == user_id
        )
    ).first()
    
    if not note:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Note not found"
        )
    
    # Delete associated file if exists
    if note.file_path and Path(note.file_path).exists():
        try:
            Path(note.file_path).unlink()
            logger.info(f"Deleted note file: {note.file_path}")
        except Exception as e:
            logger.warning(f"Failed to delete note file: {e}")
    
    # Delete analysis logs
    db.query(NoteAnalysisLog).filter(NoteAnalysisLog.note_id == note_id).delete()
    
    # Delete note
    db.delete(note)
    db.commit()
    
    return MessageResponse(
        message=f"Note '{note.title}' deleted successfully"
    )


# ===============================
# NOTES ANALYTICS & STATISTICS
# ===============================

@router.get("/user/statistics", response_model=dict)
async def get_user_notes_statistics(
    db: db_dependency,
    current_user: dict = user_dependency
):
    """Get statistics about user's uploaded notes"""
    user_id = current_user["user_id"]
    
    notes_query = db.query(StudentNote).filter(StudentNote.user_id == user_id)
    
    total_notes = notes_query.count()
    processed_notes = notes_query.filter(StudentNote.ai_processed == True).count()
    failed_notes = notes_query.filter(StudentNote.processing_status == "failed").count()
    
    # Get subject distribution
    subject_dist = {}
    for note in notes_query.all():
        if note.subject:
            subject_dist[note.subject] = subject_dist.get(note.subject, 0) + 1
    
    # Calculate storage usage
    total_storage = sum(note.file_size or 0 for note in notes_query.all())
    
    return {
        "total_notes": total_notes,
        "processed_notes": processed_notes,
        "failed_notes": failed_notes,
        "pending_notes": total_notes - processed_notes - failed_notes,
        "subject_distribution": subject_dist,
        "total_storage_bytes": total_storage,
        "total_storage_mb": round(total_storage / (1024 * 1024), 2)
    }


@router.get("/health", tags=["Health"])
async def notes_service_health_check():
    """Health check for notes service"""
    return {
        "status": "healthy",
        "service": "student-notes",
        "timestamp": datetime.utcnow().isoformat(),
        "supported_formats": list(["png", "jpg", "jpeg", "bmp", "gif", "webp"]),
        "max_file_size_mb": 20
    }
