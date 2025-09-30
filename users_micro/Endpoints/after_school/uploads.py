from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends, status, UploadFile, File, Form, Query
from fastapi.responses import Response, JSONResponse
from typing import List, Optional
from sqlalchemy.orm import Session, joinedload
from pathlib import Path
import os
import shutil
import uuid
import asyncio
import aiofiles
from PIL import Image
import io
import hashlib

from db.connection import db_dependency
from Endpoints.auth import get_current_user
from models.afterschool_models import (
    Course, CourseLesson, CourseBlock, StudySession, AISubmission, CourseAssignment
)
from schemas.afterschool_schema import (
    AISubmissionCreate, AISubmissionOut, AIGradingResponse, MessageResponse
)
from services.gemini_service import gemini_service
import base64

router = APIRouter(prefix="/after-school/uploads", tags=["After-School File Uploads"])

# Dependency for current user
user_dependency = Depends(get_current_user)

# Configuration
MAX_FILE_SIZE = 20 * 1024 * 1024  # 20MB
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".pdf", ".txt", ".doc", ".docx"}
UPLOAD_DIR = Path("uploads/after_school")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# ===============================
# UTILITY FUNCTIONS
# ===============================

def validate_file(file: UploadFile) -> tuple[bool, str]:
    """Validate uploaded file"""
    if not file.filename:
        return False, "No filename provided"
    
    # Check file extension
    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in ALLOWED_EXTENSIONS:
        return False, f"File type {file_ext} not allowed. Allowed types: {', '.join(ALLOWED_EXTENSIONS)}"
    
    # Check file size
    if file.size and file.size > MAX_FILE_SIZE:
        return False, f"File size exceeds maximum allowed size of {MAX_FILE_SIZE // (1024*1024)}MB"
    
    return True, "Valid"

def generate_unique_filename(original_filename: str, user_id: int, session_id: int) -> str:
    """Generate unique filename while preserving extension"""
    file_ext = Path(original_filename).suffix.lower()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    unique_name = f"session_{session_id}_user_{user_id}_{timestamp}_{uuid.uuid4().hex[:8]}{file_ext}"
    return unique_name

async def save_uploaded_file(file: UploadFile, file_path: Path) -> bool:
    """Save uploaded file to specified path"""
    try:
        async with aiofiles.open(file_path, 'wb') as f:
            content = await file.read()
            await f.write(content)
        return True
    except Exception as e:
        print(f"Error saving file: {e}")
        return False

# Removed simulation; real grading is performed via services.gemini_service

# Normalize Gemini grading payload to our AISubmission fields
def normalize_ai_grading(grading: dict, max_points: int = 100) -> dict:
    """Normalize Gemini grading payload to our AISubmission fields and types.

    - ai_score: float 0-100 if available
    - ai_feedback: string
    - ai_strengths/improvements/corrections: strings (bullet-joined if list)
    """
    if not isinstance(grading, dict):
        return {"error": "Invalid grading payload"}

    # Prefer explicit percentage; otherwise compute from score/max_points
    percentage = grading.get("percentage")
    score = grading.get("score")
    ai_score: Optional[float] = None
    try:
        if isinstance(percentage, (int, float)):
            ai_score = float(percentage)
        elif isinstance(score, (int, float)) and isinstance(max_points, (int, float)) and max_points > 0:
            ai_score = (float(score) / float(max_points)) * 100
        # Clamp and round
        if ai_score is not None:
            ai_score = max(0.0, min(100.0, round(ai_score, 2)))
    except Exception:
        ai_score = None

    # Compose feedback fields
    overall_feedback = grading.get("overall_feedback") or grading.get("detailed_feedback") or grading.get("feedback")

    def to_text(value) -> Optional[str]:
        if value is None:
            return None
        if isinstance(value, str):
            return value
        if isinstance(value, list):
            # Join list items as bullets
            try:
                items = [str(v).strip() for v in value if v is not None]
                items = [i for i in items if i]
                return "\n".join([f"- {i}" for i in items]) if items else None
            except Exception:
                return "\n".join(map(str, value))
        # Fallback string conversion for dict/other types
        try:
            import json as _json
            return _json.dumps(value, ensure_ascii=False)
        except Exception:
            return str(value)

    strengths_raw = grading.get("strengths") or []
    improvements_raw = grading.get("improvements") or grading.get("recommendations") or []
    corrections_raw = grading.get("corrections") or []

    normalized = {
        "ai_score": ai_score,
        "ai_feedback": to_text(overall_feedback),
        "ai_strengths": to_text(strengths_raw),
        "ai_improvements": to_text(improvements_raw),
        "ai_corrections": to_text(corrections_raw),
        "raw": grading,
    }
    return normalized

def resize_image_for_pdf(image: Image.Image, max_width: float, max_height: float) -> tuple:
    """
    Resize image to fit within PDF page dimensions while maintaining aspect ratio
    Returns (new_width, new_height)
    """
    img_width, img_height = image.size
    
    # Calculate scaling factor to fit within max dimensions
    width_ratio = max_width / img_width
    height_ratio = max_height / img_height
    scale_factor = min(width_ratio, height_ratio, 1.0)  # Don't scale up
    
    new_width = int(img_width * scale_factor)
    new_height = int(img_height * scale_factor)
    
    return new_width, new_height

async def create_pdf_from_images(files: List[UploadFile], pdf_filename: str) -> tuple[bytes, str]:
    """
    Create PDF from uploaded image files
    Returns (pdf_bytes, content_hash)
    """
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.lib.utils import ImageReader
    
    # Create PDF in memory
    pdf_buffer = io.BytesIO()
    c = canvas.Canvas(pdf_buffer, pagesize=A4)
    page_width, page_height = A4
    
    # Margins
    margin = 50
    usable_width = page_width - (2 * margin)
    usable_height = page_height - (2 * margin)
    
    for file in files:
        try:
            # Reset file pointer
            if hasattr(file.file, 'seek'):
                file.file.seek(0)
            
            # Read image data
            image_data = await file.read()
            image_stream = io.BytesIO(image_data)
            
            # Open image with PIL
            pil_image = Image.open(image_stream)
            
            # Convert to RGB if needed
            if pil_image.mode in ('RGBA', 'LA', 'P'):
                pil_image = pil_image.convert('RGB')
            
            # Resize image to fit page
            new_width, new_height = resize_image_for_pdf(pil_image, usable_width, usable_height)
            
            if new_width != pil_image.width or new_height != pil_image.height:
                pil_image = pil_image.resize((new_width, new_height), Image.Resampling.LANCZOS)
            
            # Convert PIL image to ImageReader for ReportLab
            img_buffer = io.BytesIO()
            pil_image.save(img_buffer, format='JPEG', quality=85)
            img_buffer.seek(0)
            
            # Calculate position to center image
            x = margin + (usable_width - new_width) / 2
            y = margin + (usable_height - new_height) / 2
            
            # Draw image on PDF
            c.drawImage(ImageReader(img_buffer), x, y, width=new_width, height=new_height)
            c.showPage()  # Start new page for next image
            
        except Exception as e:
            print(f"Error processing image {file.filename}: {e}")
            continue
    
    # Finalize PDF
    c.save()
    pdf_bytes = pdf_buffer.getvalue()
    
    # Generate content hash
    content_hash = hashlib.sha256(pdf_bytes).hexdigest()[:16]
    
    return pdf_bytes, content_hash

# ===============================
# BULK PDF GENERATION ENDPOINTS
# ===============================

@router.post("/bulk-upload-to-pdf")
async def bulk_upload_images_to_pdf_session(
    db: db_dependency,
    current_user: dict = user_dependency,
    session_id: int = Form(..., description="Study session ID"),
    submission_type: str = Form("homework", description="Type of submission"),
    files: List[UploadFile] = File(..., description="Multiple image files to combine into PDF"),
    # New contextual metadata
    course_id: Optional[int] = Form(None, description="Course ID (optional, can be derived from session)"),
    lesson_id: Optional[int] = Form(None, description="Lesson ID (optional, can be derived from session)"),
    block_id: Optional[int] = Form(None, description="Block ID (optional, can be derived from session)"),
    assignment_id: Optional[int] = Form(None, description="Assignment ID (optional)"),
    storage_mode: str = Form("database", description="Storage mode: 'database' (default)"),
    skip_db: bool = Form(False, description="If true, only generate PDF and return; do not persist (debug)")
):
    """
    Upload multiple image files for a study session and combine them into a single PDF.
    
    - **session_id**: Study session the images belong to
    - **submission_type**: Type of submission (homework, quiz, practice, assessment)
    - **files**: List of image files (JPG, PNG, GIF, BMP, WEBP)
    - Returns: PDF file containing all images as separate pages
    
    The API will:
    1. Validate user access to study session
    2. Validate all uploaded files are images
    3. Convert and resize images to fit PDF pages
    4. Combine all images into a single PDF document
    5. Save submission record in database with AI processing
    6. Return the generated PDF file
    """
    
    try:
        user_id = current_user["user_id"]
        
        # Get and validate study session
        session = db.query(StudySession).options(
            joinedload(StudySession.course),
            joinedload(StudySession.lesson),
            joinedload(StudySession.block)
        ).filter(
            StudySession.id == session_id,
            StudySession.user_id == user_id
        ).first()
        
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Study session not found or doesn't belong to you"
            )
        
        if session.status != "in_progress":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Can only submit work for active study sessions"
            )
        
        # Validate that files are provided
        if not files:
            raise HTTPException(status_code=400, detail="No files provided")
        
        # Validate all files are images & size constraints early
        invalid_files = []
        oversized_files = []
        valid_files: List[UploadFile] = []
        for file in files:
            if not file.filename:
                invalid_files.append("<no name>")
                continue
            ext = Path(file.filename).suffix.lower()
            if ext not in [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"]:
                invalid_files.append(file.filename)
                continue
            # Size check
            if hasattr(file, 'size') and file.size and file.size > MAX_FILE_SIZE:
                oversized_files.append(f"{file.filename} ({round(file.size/1024/1024,2)}MB)")
                continue
            valid_files.append(file)

        if invalid_files:
            raise HTTPException(status_code=400, detail=f"Invalid file types: {', '.join(invalid_files)}")
        if oversized_files:
            raise HTTPException(status_code=400, detail=f"Oversized files: {', '.join(oversized_files)} > {MAX_FILE_SIZE//1024//1024}MB limit")
        if not valid_files:
            raise HTTPException(status_code=400, detail="No valid image files found after validation")

        # Reset file pointers
        for f in valid_files:
            try:
                if hasattr(f.file, 'seek') and f.file.seekable():
                    f.file.seek(0)
            except Exception:
                pass
        
        # Generate PDF filename (support lesson- or block-anchored sessions)
        course_title = session.course.title.replace(" ", "_").replace("/", "_")
        if session.lesson is not None:
            anchor_title = session.lesson.title.replace(" ", "_").replace("/", "_")
        elif getattr(session, 'block', None) is not None:
            anchor_title = f"week{session.block.week}_block{session.block.block_number}_" + session.block.title.replace(" ", "_").replace("/", "_")
        else:
            anchor_title = "session"
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        pdf_filename = f"session_{session_id}_{course_title}_{anchor_title}_{timestamp}.pdf"
        
        # Create PDF from images (returns bytes and hash)
        try:
            pdf_bytes, content_hash = await create_pdf_from_images(valid_files, pdf_filename)
        except Exception as gen_err:
            raise HTTPException(status_code=500, detail=f"Failed to generate PDF from images: {gen_err}")
        pdf_size = len(pdf_bytes)
        
        print(f"📄 Created PDF in memory: {pdf_size} bytes, hash: {content_hash}")

        # Early return for debug mode (skip DB persistence)
        if skip_db:
            return Response(
                content=pdf_bytes,
                media_type="application/pdf",
                headers={
                    "X-Debug-Skip-DB": "true",
                    "X-Generated-Only": "true",
                    "X-Content-Hash": content_hash,
                    "Content-Disposition": f"attachment; filename={pdf_filename}"
                }
            )

        # Save PDF file to uploads directory
        unique_filename = generate_unique_filename(pdf_filename, user_id, session_id)
        file_path = UPLOAD_DIR / unique_filename
        
        try:
            async with aiofiles.open(file_path, 'wb') as f:
                await f.write(pdf_bytes)
        except Exception as save_err:
            raise HTTPException(status_code=500, detail=f"Failed to save PDF file: {save_err}")
        
        # Create AI submission record
        # Use provided parameters or fall back to session values
        final_course_id = course_id if course_id is not None else session.course_id
        final_lesson_id = lesson_id if lesson_id is not None else session.lesson_id
        final_block_id = block_id if block_id is not None else session.block_id
        
        submission = AISubmission(
            user_id=user_id,
            course_id=final_course_id,
            lesson_id=final_lesson_id,
            block_id=final_block_id,
            session_id=session_id,
            assignment_id=assignment_id,
            submission_type=submission_type,
            original_filename=pdf_filename,
            file_path=str(file_path),
            file_type="pdf",
            ai_processed=False
        )
        
        db.add(submission)
        db.commit()
        db.refresh(submission)
        
        # Process with AI (real grading via Gemini)
        try:
            # Prepare assignment context if available
            assignment_title = f"{submission_type.capitalize()} Submission"
            assignment_description = ""
            rubric = ""
            max_points = 100
            if assignment_id:
                assignment: Optional[CourseAssignment] = db.query(CourseAssignment).filter(CourseAssignment.id == assignment_id).first()
                if assignment:
                    assignment_title = assignment.title or assignment_title
                    assignment_description = assignment.description or ""
                    rubric = getattr(assignment, 'rubric', '') or ''
                    max_points = getattr(assignment, 'points', 100) or 100

            # Grade using Gemini's native file processing (handles OCR for scanned/image PDFs)
            grading = await gemini_service.grade_submission_from_file(
                file_bytes=pdf_bytes,
                filename=pdf_filename,
                assignment_title=assignment_title,
                assignment_description=assignment_description,
                rubric=rubric,
                max_points=max_points,
                submission_type=submission_type
            )

            # Normalize and update submission with AI results
            normalized = normalize_ai_grading(grading, max_points=max_points)
            submission.ai_processed = True
            submission.ai_score = normalized.get("ai_score")
            submission.ai_feedback = normalized.get("ai_feedback")
            submission.ai_strengths = normalized.get("ai_strengths")
            submission.ai_improvements = normalized.get("ai_improvements")
            submission.ai_corrections = normalized.get("ai_corrections")
            submission.processed_at = datetime.utcnow()
            db.commit()
            ai_results = normalized
        except Exception as ai_err:
            # Don't fail the whole request if AI grading has an issue
            print(f"AI grading error: {ai_err}")
            ai_results = {"error": str(ai_err)}
        
        # Update study session with latest score and feedback (only if grading succeeded)
        if isinstance(ai_results, dict) and "ai_score" in ai_results:
            session.ai_score = ai_results.get("ai_score")
            session.ai_feedback = ai_results.get("ai_feedback")
            session.ai_recommendations = ai_results.get("ai_improvements")
        # Always bump updated_at
        session.updated_at = datetime.utcnow()
        
        db.commit()
        
        # Return JSON summary instead of raw PDF content to better support mobile clients
        return JSONResponse({
            "success": True,
            "message": "PDF created and AI processed",
            "submission_id": submission.id,
            "pdf_filename": pdf_filename,
            "pdf_size": pdf_size,
            "content_hash": content_hash,
            "total_images": len(valid_files),
            "ai_processing_results": ai_results
        })
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating PDF: {str(e)}")

# ===============================
# SUBMISSION MANAGEMENT ENDPOINTS
# ===============================

@router.get("/sessions/{session_id}/submissions", response_model=List[AISubmissionOut])
async def get_session_submissions(
    session_id: int,
    db: db_dependency,
    current_user: dict = user_dependency,
    submission_type: Optional[str] = Query(None, description="Filter by submission type"),
    limit: int = Query(50, ge=1, le=100, description="Limit results")
):
    """
    Get all submissions for a study session with detailed information
    Compatible with both bulk PDF uploads and single file uploads
    """
    user_id = current_user["user_id"]
    
    # Verify session belongs to user
    session = db.query(StudySession).filter(
        StudySession.id == session_id,
        StudySession.user_id == user_id
    ).first()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Study session not found or doesn't belong to you"
        )
    
    query = db.query(AISubmission).filter(AISubmission.session_id == session_id)
    
    if submission_type:
        query = query.filter(AISubmission.submission_type == submission_type)
    
    submissions = query.order_by(AISubmission.submitted_at.desc()).limit(limit).all()
    
    return submissions

@router.get("/sessions/{session_id}/submissions-summary")
async def get_session_submissions_summary(
    session_id: int,
    db: db_dependency,
    current_user: dict = user_dependency
):
    """
    Get summary of submissions for a study session
    """
    user_id = current_user["user_id"]
    
    # Verify session belongs to user
    session = db.query(StudySession).options(
        joinedload(StudySession.course),
        joinedload(StudySession.lesson)
    ).filter(
        StudySession.id == session_id,
        StudySession.user_id == user_id
    ).first()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Study session not found or doesn't belong to you"
        )
    
    submissions = db.query(AISubmission).filter(
        AISubmission.session_id == session_id
    ).all()
    
    # Calculate summary stats
    total_submissions = len(submissions)
    processed_submissions = len([s for s in submissions if s.ai_processed])
    average_score = None
    if processed_submissions > 0:
        scores = [s.ai_score for s in submissions if s.ai_score is not None]
        if scores:
            average_score = sum(scores) / len(scores)
    
    # Determine anchor title depending on session type
    anchor_title = None
    if getattr(session, 'lesson', None) is not None:
        anchor_title = session.lesson.title
    elif getattr(session, 'block', None) is not None:
        anchor_title = session.block.title

    return {
        "session_id": session_id,
        "course_title": session.course.title,
        "lesson_title": anchor_title or "",
        "total_submissions": total_submissions,
        "processed_submissions": processed_submissions,
        "pending_submissions": total_submissions - processed_submissions,
        "average_score": average_score,
        "session_score": session.ai_score,
        "session_status": session.status
    }

@router.get("/submissions/{submission_id}", response_model=AISubmissionOut)
async def get_submission_details(
    submission_id: int,
    db: db_dependency,
    current_user: dict = user_dependency
):
    """
    Get detailed information about a specific AI submission
    """
    user_id = current_user["user_id"]
    
    # Get the submission and verify it belongs to the user
    submission = db.query(AISubmission).filter(
        AISubmission.id == submission_id,
        AISubmission.user_id == user_id
    ).first()
    
    if not submission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="AI submission not found or access denied"
        )
    
    return submission

@router.get("/submissions/{submission_id}/download")
async def download_submission_file(
    submission_id: int,
    db: db_dependency,
    current_user: dict = user_dependency
):
    """
    Download any submission file by ID (works for both PDF and single files)
    Compatible with all upload endpoints
    """
    user_id = current_user["user_id"]
    
    # Get submission and verify ownership
    submission = db.query(AISubmission).filter(
        AISubmission.id == submission_id,
        AISubmission.user_id == user_id
    ).first()
    
    if not submission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Submission not found"
        )
    
    # Check if file exists
    if not submission.file_path or not Path(submission.file_path).exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found"
        )
    
    # Read and return file
    try:
        async with aiofiles.open(submission.file_path, 'rb') as f:
            file_content = await f.read()
        
        # Determine media type based on file extension
        file_ext = Path(submission.file_path).suffix.lower()
        media_type_mapping = {
            ".pdf": "application/pdf",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".gif": "image/gif",
            ".bmp": "image/bmp",
            ".webp": "image/webp",
            ".txt": "text/plain",
            ".doc": "application/msword",
            ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        }
        media_type = media_type_mapping.get(file_ext, "application/octet-stream")
        
        return Response(
            content=file_content,
            media_type=media_type,
            headers={
                "Content-Disposition": f"attachment; filename={submission.original_filename}",
                "Content-Length": str(len(file_content)),
                "X-Submission-ID": str(submission.id),
                "X-Submission-Type": submission.submission_type,
                "X-AI-Score": str(submission.ai_score) if submission.ai_score else "N/A",
                "X-File-Type": submission.file_type
            }
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error reading file: {str(e)}"
        )

@router.delete("/submissions/{submission_id}", response_model=MessageResponse)
async def delete_submission_by_id(
    submission_id: int,
    db: db_dependency,
    current_user: dict = user_dependency
):
    """
    Delete any submission by ID (works for both PDF and single files)
    Compatible with all upload endpoints
    """
    user_id = current_user["user_id"]
    
    # Get submission and verify ownership
    submission = db.query(AISubmission).filter(
        AISubmission.id == submission_id,
        AISubmission.user_id == user_id
    ).first()
    
    if not submission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Submission not found"
        )
    
    # Delete physical file if it exists
    if submission.file_path and Path(submission.file_path).exists():
        try:
            Path(submission.file_path).unlink()
            print(f"🗑️ Deleted file: {submission.file_path}")
        except Exception as e:
            print(f"Warning: Could not delete file {submission.file_path}: {e}")
    
    # Store info before deletion
    deleted_filename = submission.original_filename
    session_id = submission.session_id
    
    # Delete database record
    db.delete(submission)
    db.commit()
    
    return MessageResponse(
        message=f"Submission '{deleted_filename}' deleted successfully"
    )

@router.post("/submissions/{submission_id}/reprocess", response_model=AIGradingResponse)
async def reprocess_submission_by_id(
    submission_id: int,
    db: db_dependency,
    current_user: dict = user_dependency
):
    """
    Reprocess any submission with AI (works for both PDF and single files)
    Compatible with all upload endpoints
    """
    user_id = current_user["user_id"]
    
    submission = db.query(AISubmission).filter(
        AISubmission.id == submission_id,
        AISubmission.user_id == user_id
    ).first()
    
    if not submission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Submission not found"
        )
    
    if not submission.file_path or not Path(submission.file_path).exists():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Original file no longer exists, cannot reprocess"
        )
    
    # Reprocess with AI (real grading via Gemini)
    try:
        # Read the file bytes
        with open(submission.file_path, 'rb') as f:
            pdf_bytes = f.read()

        # Assignment context if available
        assignment_title = f"{submission.submission_type.capitalize()} Submission"
        assignment_description = ""
        rubric = ""
        max_points = 100
        if submission.assignment_id:
            assignment: Optional[CourseAssignment] = db.query(CourseAssignment).filter(CourseAssignment.id == submission.assignment_id).first()
            if assignment:
                assignment_title = assignment.title or assignment_title
                assignment_description = assignment.description or ""
                rubric = getattr(assignment, 'rubric', '') or ''
                max_points = getattr(assignment, 'points', 100) or 100

        # Always use native file grading to avoid misinterpreting base64 as text
        grading = await gemini_service.grade_submission_from_file(
            file_bytes=pdf_bytes,
            filename=submission.original_filename or "submission.pdf",
            assignment_title=assignment_title,
            assignment_description=assignment_description,
            rubric=rubric,
            max_points=max_points,
            submission_type=submission.submission_type
        )

        # Normalize and update submission
        normalized = normalize_ai_grading(grading, max_points=max_points)
        submission.ai_score = normalized.get("ai_score")
        submission.ai_feedback = normalized.get("ai_feedback")
        submission.ai_strengths = normalized.get("ai_strengths")
        submission.ai_improvements = normalized.get("ai_improvements")
        submission.ai_corrections = normalized.get("ai_corrections")
        submission.processed_at = datetime.utcnow()
        submission.ai_processed = True
        db.commit()
        ai_results = normalized
    except Exception as ai_err:
        raise HTTPException(status_code=500, detail=f"AI grading error: {ai_err}")
    
    # Update associated study session
    session = db.query(StudySession).filter(StudySession.id == submission.session_id).first()
    if session:
        if isinstance(ai_results, dict) and "ai_score" in ai_results:
            session.ai_score = ai_results.get("ai_score")
            session.ai_feedback = ai_results.get("ai_feedback")
            session.ai_recommendations = ai_results.get("ai_improvements")
        session.updated_at = datetime.utcnow()
    
    db.commit()
    
    return AIGradingResponse(
        submission_id=submission.id,
        ai_score=submission.ai_score if submission.ai_score is not None else 0.0,
        ai_feedback=submission.ai_feedback or "",
        ai_corrections=submission.ai_corrections,
        ai_strengths=submission.ai_strengths,
        ai_improvements=submission.ai_improvements,
        processed_at=submission.processed_at
    )

# ===============================
# USER-LEVEL STATISTICS ENDPOINTS
# ===============================

@router.get("/user/recent-submissions", response_model=List[AISubmissionOut])
async def get_user_recent_submissions(
    db: db_dependency,
    current_user: dict = user_dependency,
    limit: int = Query(10, ge=1, le=50, description="Limit results"),
    submission_type: Optional[str] = Query(None, description="Filter by submission type")
):
    """
    Get user's recent submissions across all sessions and courses
    
    This endpoint provides a user-level view of recent AI submissions,
    aggregating submissions from all the user's study sessions.
    """
    user_id = current_user["user_id"]
    
    try:
        # Build query to get user's submissions across all sessions
        query = db.query(AISubmission).filter(AISubmission.user_id == user_id)
        
        # Apply optional filter by submission type
        if submission_type:
            query = query.filter(AISubmission.submission_type == submission_type)
        
        # Order by most recent and apply limit
        submissions = query.order_by(AISubmission.submitted_at.desc()).limit(limit).all()
        
        return submissions
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching user recent submissions: {str(e)}"
        )

@router.get("/user/statistics")
async def get_user_upload_statistics(
    db: db_dependency,
    current_user: dict = user_dependency
):
    """
    Get comprehensive upload statistics and analytics for the current user
    
    Returns aggregated statistics about the user's file uploads, AI processing,
    scores, and activity patterns across all their study sessions.
    """
    user_id = current_user["user_id"]
    
    try:
        # Get all user submissions for statistics
        all_submissions = db.query(AISubmission).filter(AISubmission.user_id == user_id).all()
        
        # Basic counts
        total_uploads = len(all_submissions)
        successful_uploads = len([s for s in all_submissions if s.ai_processed])
        pending_processing = total_uploads - successful_uploads
        
        # Calculate file sizes (if available from file paths)
        total_size_uploaded = 0
        for submission in all_submissions:
            if submission.file_path and Path(submission.file_path).exists():
                try:
                    file_size = Path(submission.file_path).stat().st_size
                    total_size_uploaded += file_size
                except (OSError, FileNotFoundError):
                    continue
        
        # Calculate average score from processed submissions
        processed_scores = [s.ai_score for s in all_submissions if s.ai_score is not None]
        average_score = sum(processed_scores) / len(processed_scores) if processed_scores else 0
        
        # Time-based analytics
        from datetime import datetime, timedelta
        
        now = datetime.utcnow()
        week_ago = now - timedelta(days=7)
        month_ago = now - timedelta(days=30)
        
        this_week_uploads = len([
            s for s in all_submissions 
            if s.submitted_at and s.submitted_at >= week_ago
        ])
        
        this_month_uploads = len([
            s for s in all_submissions 
            if s.submitted_at and s.submitted_at >= month_ago
        ])
        
        # Submission type breakdown
        submission_types = {}
        for submission in all_submissions:
            sub_type = submission.submission_type or "unknown"
            submission_types[sub_type] = submission_types.get(sub_type, 0) + 1
        
        # File type breakdown
        file_types = {}
        for submission in all_submissions:
            file_type = submission.file_type or "unknown"
            file_types[file_type] = file_types.get(file_type, 0) + 1
        
        # Recent activity trend (last 7 days)
        daily_uploads = {}
        for i in range(7):
            day = now - timedelta(days=i)
            day_str = day.strftime("%Y-%m-%d")
            day_uploads = len([
                s for s in all_submissions 
                if s.submitted_at and s.submitted_at.date() == day.date()
            ])
            daily_uploads[day_str] = day_uploads
        
        return {
            "user_id": user_id,
            "total_uploads": total_uploads,
            "total_size_uploaded": total_size_uploaded,
            "successful_uploads": successful_uploads,
            "pending_processing": pending_processing,
            "average_score": round(average_score, 2) if average_score else 0,
            "this_week_uploads": this_week_uploads,
            "this_month_uploads": this_month_uploads,
            "submission_types": submission_types,
            "file_types": file_types,
            "daily_activity": daily_uploads,
            "statistics_generated_at": now.isoformat()
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating user upload statistics: {str(e)}"
        )

@router.get("/health")
async def after_school_upload_health_check():
    """
    Simple health check endpoint for after-school upload service
    """
    return {
        "status": "healthy",
        "service": "After-School Learning File Upload & PDF Generator",
        "timestamp": datetime.now().isoformat(),
        "supported_formats": list(ALLOWED_EXTENSIONS),
        "storage_method": "file_system_with_database_records",
        "features": [
            "Image validation and resizing",
            "PDF generation from multiple images",
            "AI grading via Gemini (file-based with OCR)",
            "Study session integration",
            "Automatic grading and feedback"
        ]
    }