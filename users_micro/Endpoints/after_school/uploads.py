from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends, status, UploadFile, File, Form, Query
from fastapi.responses import Response
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
    Course, CourseLesson, StudySession, AISubmission
)
from schemas.afterschool_schema import (
    AISubmissionCreate, AISubmissionOut, AIGradingResponse, MessageResponse
)

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

def simulate_ai_processing(file_path: str, submission_type: str, lesson_content: str = "") -> dict:
    """
    Simulate AI processing of uploaded file
    In production, this would integrate with actual AI services for:
    - OCR for handwritten text
    - Content analysis
    - Automatic grading
    - Feedback generation
    """
    import random
    
    # Simulate processing based on file type
    file_ext = Path(file_path).suffix.lower()
    
    if file_ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp']:
        # Image processing simulation
        processing_results = {
            "content_extracted": "Sample handwritten math equations detected: 2+2=4, 5x3=15",
            "ai_score": random.randint(70, 95),
            "ai_feedback": "Good handwriting! Your calculations are correct.",
            "ai_strengths": "Clear presentation, accurate calculations",
            "ai_improvements": "Try to show more working steps",
            "ai_corrections": "None needed - excellent work!"
        }
    elif file_ext == '.pdf':
        # PDF processing simulation
        processing_results = {
            "content_extracted": "PDF document with multiple pages of science notes",
            "ai_score": random.randint(75, 90),
            "ai_feedback": "Comprehensive notes with good organization.",
            "ai_strengths": "Well-structured content, good use of diagrams",
            "ai_improvements": "Add more examples for complex concepts",
            "ai_corrections": "Check spelling on page 2"
        }
    else:
        # Text file processing simulation
        processing_results = {
            "content_extracted": "Text document with essay content",
            "ai_score": random.randint(65, 85),
            "ai_feedback": "Good effort in expressing ideas.",
            "ai_strengths": "Clear arguments, good vocabulary",
            "ai_improvements": "Work on paragraph structure",
            "ai_corrections": "Fix grammar in paragraph 3"
        }
    
    # Adjust score based on submission type
    if submission_type == "assessment":
        processing_results["ai_score"] = min(processing_results["ai_score"], 85)
    elif submission_type == "practice":
        processing_results["ai_score"] += 5  # Encourage practice
    
    return processing_results

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
        
        # Generate PDF filename
        course_title = session.course.title.replace(" ", "_").replace("/", "_")
        lesson_title = session.lesson.title.replace(" ", "_").replace("/", "_")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        pdf_filename = f"session_{session_id}_{course_title}_{lesson_title}_{timestamp}.pdf"
        
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
        submission = AISubmission(
            user_id=user_id,
            course_id=session.course_id,
            lesson_id=session.lesson_id,
            session_id=session_id,
            submission_type=submission_type,
            original_filename=pdf_filename,
            file_path=str(file_path),
            file_type="pdf",
            ai_processed=False
        )
        
        db.add(submission)
        db.commit()
        db.refresh(submission)
        
        # Process with AI (simulate)
        lesson_content = session.lesson.content or ""
        ai_results = simulate_ai_processing(str(file_path), submission_type, lesson_content)
        
        # Update submission with AI results
        submission.ai_processed = True
        submission.ai_score = ai_results["ai_score"]
        submission.ai_feedback = ai_results["ai_feedback"]
        submission.ai_strengths = ai_results["ai_strengths"]
        submission.ai_improvements = ai_results["ai_improvements"]
        submission.ai_corrections = ai_results["ai_corrections"]
        submission.processed_at = datetime.utcnow()
        
        # Update study session with latest score and feedback
        session.ai_score = ai_results["ai_score"]
        session.ai_feedback = ai_results["ai_feedback"]
        session.ai_recommendations = ai_results["ai_improvements"]
        session.updated_at = datetime.utcnow()
        
        db.commit()
        
        # Return the PDF file directly from memory
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename={pdf_filename}",
                "Content-Length": str(pdf_size),
                "X-Total-Images": str(len(valid_files)),
                "X-Course-Title": session.course.title,
                "X-Lesson-Title": session.lesson.title,
                "X-Submission-ID": str(submission.id),
                "X-Content-Hash": content_hash
            }
        )
        
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
    
    return {
        "session_id": session_id,
        "course_title": session.course.title,
        "lesson_title": session.lesson.title,
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
    
    # Reprocess with AI
    ai_results = simulate_ai_processing(
        submission.file_path, 
        submission.submission_type
    )
    
    # Update submission
    submission.ai_score = ai_results["ai_score"]
    submission.ai_feedback = ai_results["ai_feedback"]
    submission.ai_strengths = ai_results["ai_strengths"]
    submission.ai_improvements = ai_results["ai_improvements"]
    submission.ai_corrections = ai_results["ai_corrections"]
    submission.processed_at = datetime.utcnow()
    submission.ai_processed = True
    
    # Update associated study session
    session = db.query(StudySession).filter(StudySession.id == submission.session_id).first()
    if session:
        session.ai_score = ai_results["ai_score"]
        session.ai_feedback = ai_results["ai_feedback"]
        session.ai_recommendations = ai_results["ai_improvements"]
        session.updated_at = datetime.utcnow()
    
    db.commit()
    
    return AIGradingResponse(
        submission_id=submission.id,
        ai_score=submission.ai_score,
        ai_feedback=submission.ai_feedback,
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
            "AI processing simulation",
            "Study session integration",
            "Automatic grading and feedback"
        ]
    }