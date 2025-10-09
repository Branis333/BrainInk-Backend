from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, Depends, status, UploadFile, File, Form, Query
from fastapi.responses import Response, JSONResponse
from typing import List, Optional
from sqlalchemy.orm import Session, joinedload
from pathlib import Path
import re
import os
import shutil
import uuid
import asyncio
import logging
import aiofiles
from PIL import Image
import io
import hashlib

from db.connection import db_dependency
from Endpoints.auth import get_current_user
from models.afterschool_models import (
    Course, CourseLesson, CourseBlock, StudySession, AISubmission, CourseAssignment, StudentAssignment
)
from schemas.afterschool_schema import (
    AISubmissionCreate, AISubmissionOut, AIGradingResponse, MessageResponse
)
from services.gemini_service import gemini_service
import base64
router = APIRouter(prefix="/after-school/uploads", tags=["After-School File Uploads"])
logger = logging.getLogger(__name__)

# Dependency for current user
user_dependency = Depends(get_current_user)
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
def _clean_malformed_json(grading: dict) -> dict:
    """Clean malformed JSON from Gemini where keys/values have extra quotes and trailing commas."""
    if not isinstance(grading, dict):
        return grading
    
    cleaned = {}
    for key, value in grading.items():
        # Remove extra quotes from keys
        clean_key = key.strip('"').strip("'")
        
        # Clean values
        if isinstance(value, str):
            # Remove trailing commas and extra quotes
            clean_value = value.rstrip(',').strip().strip('"').strip("'")
            
            # Try to convert to appropriate type
            if clean_value.lower() in ('null', 'none', ''):
                clean_value = None
            elif clean_value.replace('.', '', 1).replace('-', '', 1).isdigit():
                # It's a number
                try:
                    clean_value = float(clean_value) if '.' in clean_value else int(clean_value)
                except:
                    pass
            elif clean_value in ('[', '{'):
                # Incomplete array/object
                clean_value = [] if clean_value == '[' else {}
            
            cleaned[clean_key] = clean_value
        else:
            cleaned[clean_key] = value
    
    return cleaned


def _extract_numeric_percentage(value) -> Optional[float]:
    """Attempt to coerce various representations into a float percentage."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        text = value.strip().replace('%', '').replace(',', '')
        if text.replace('.', '', 1).isdigit():
            try:
                return float(text)
            except Exception:
                return None
        match = re.search(r"-?\d+(?:\.\d+)?", text)
        if match:
            try:
                return float(match.group())
            except Exception:
                return None
    return None


# ==============================================================================
# DEPRECATED: normalize_ai_grading() function removed (2025-01-09)
# 
# This function was previously used to normalize Gemini AI grading responses
# into a structured format with ai_score, ai_feedback, ai_strengths, etc.
# 
# REMOVED BECAUSE: Gemini returns malformed JSON with escaped quotes and 
# trailing commas, making normalization unreliable and causing 0% scores.
# 
# NEW APPROACH: All endpoints now return RAW Gemini data only. Frontend 
# handles parsing with robust error handling. Database fields (ai_score, 
# ai_feedback) are populated via best-effort extraction for legacy compatibility.
# 
# If you need this function, use raw data extraction instead:
#   score_val = raw.get('score') or raw.get('"score"')
#   if isinstance(score_val, str):
#       score_val = score_val.rstrip(',').strip()
# ==============================================================================


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
    course_id: int = Form(..., description="Course ID"),
    submission_type: str = Form("homework", description="Type of submission"),
    files: List[UploadFile] = File(..., description="Multiple image files to combine into PDF"),
    # Contextual metadata
    lesson_id: Optional[str] = Form(None, description="Lesson ID (for legacy courses) - leave empty if using block_id"),
    block_id: Optional[str] = Form(None, description="Block ID (for AI-generated courses) - leave empty if using lesson_id"),
    assignment_id: Optional[str] = Form(None, description="Assignment ID (optional) - leave empty if not needed"),
    storage_mode: str = Form("database", description="Storage mode: 'database' (default)"),
    skip_db: bool = Form(False, description="If true, only generate PDF and return; do not persist (debug)")
):
    """
    Upload multiple image files for a course block and combine them into a single PDF.
    
    - **course_id**: Course ID (required)
    - **block_id**: Block ID (for AI-generated courses)
    - **lesson_id**: Lesson ID (for legacy courses)
    - **submission_type**: Type of submission (homework, quiz, practice, assessment)
    - **files**: List of image files (JPG, PNG, GIF, BMP, WEBP)
    - Returns: PDF file containing all images as separate pages
    
    The API will:
    1. Validate user access to course and block/lesson
    2. Validate all uploaded files are images
    3. Convert and resize images to fit PDF pages
    4. Combine all images into a single PDF document
    5. Save submission record in database with AI processing
    6. Return the generated PDF file
    """
    
    try:
        user_id = current_user["user_id"]
        
        # Convert string parameters to integers, handling empty strings and "null"
        def parse_optional_int(value: Optional[str]) -> Optional[int]:
            if value is None or value == "" or value.lower() == "null":
                return None
            try:
                return int(value)
            except (ValueError, AttributeError):
                return None
        
        lesson_id_int = parse_optional_int(lesson_id)
        block_id_int = parse_optional_int(block_id)
        assignment_id_int = parse_optional_int(assignment_id)
        
        # Validate that either lesson_id or block_id is provided
        if not lesson_id_int and not block_id_int:
            raise HTTPException(status_code=400, detail="Either lesson_id or block_id must be provided")
        
        # Get and validate course
        course = db.query(Course).filter(Course.id == course_id).first()
        if not course:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Course not found"
            )
        
        # Validate block or lesson exists and belongs to the course
        block = None
        lesson = None
        
        if block_id_int:
            block = db.query(CourseBlock).filter(
                CourseBlock.id == block_id_int,
                CourseBlock.course_id == course_id,
                CourseBlock.is_active == True
            ).first()
            if not block:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Course block not found or inactive"
                )
        
        if lesson_id_int:
            lesson = db.query(CourseLesson).filter(
                CourseLesson.id == lesson_id_int,
                CourseLesson.course_id == course_id,
                CourseLesson.is_active == True
            ).first()
            if not lesson:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Course lesson not found or inactive"
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
        
        # Generate PDF filename (support lesson- or block-anchored uploads)
        course_title = course.title.replace(" ", "_").replace("/", "_")
        if lesson is not None:
            anchor_title = lesson.title.replace(" ", "_").replace("/", "_")
            upload_id = f"lesson_{lesson_id_int}"
        elif block is not None:
            anchor_title = f"week{block.week}_block{block.block_number}_" + block.title.replace(" ", "_").replace("/", "_")
            upload_id = f"block_{block_id_int}"
        else:
            anchor_title = "upload"
            upload_id = "unknown"
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        pdf_filename = f"{upload_id}_{course_title}_{anchor_title}_{timestamp}.pdf"
        
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
        unique_filename = generate_unique_filename(pdf_filename, user_id, block_id_int or lesson_id_int or 0)
        file_path = UPLOAD_DIR / unique_filename
        
        try:
            async with aiofiles.open(file_path, 'wb') as f:
                await f.write(pdf_bytes)
        except Exception as save_err:
            raise HTTPException(status_code=500, detail=f"Failed to save PDF file: {save_err}")
        
        # Create AI submission record without session dependency
        submission = AISubmission(
            user_id=user_id,
            course_id=course_id,
            lesson_id=lesson_id_int,
            block_id=block_id_int,
            session_id=None,  # Not using sessions for this workflow
            assignment_id=assignment_id_int,
            submission_type=submission_type,
            original_filename=pdf_filename,
            file_path=str(file_path),
            file_type="pdf",
            ai_processed=False,
            submitted_at=datetime.utcnow()
        )
        
        db.add(submission)
        db.commit()
        db.refresh(submission)
        
        # Process with AI (real grading via Gemini)
        # Returns RAW Gemini response only - frontend handles parsing
        try:
            # Prepare assignment context if available
            assignment_title = f"{submission_type.capitalize()} Submission"
            assignment_description = ""
            rubric = ""
            max_points = 100
            if assignment_id_int:
                assignment: Optional[CourseAssignment] = db.query(CourseAssignment).filter(CourseAssignment.id == assignment_id_int).first()
                if assignment:
                    assignment_title = assignment.title or assignment_title
                    assignment_description = assignment.description or ""
                    rubric = getattr(assignment, 'rubric', '') or ''
                    max_points = getattr(assignment, 'points', 100) or 100

            # Grade using Gemini's native file processing (handles OCR for scanned/image PDFs)
            raw_grading = await gemini_service.grade_submission_from_file(
                file_bytes=pdf_bytes,
                filename=pdf_filename,
                assignment_title=assignment_title,
                assignment_description=assignment_description,
                rubric=rubric,
                max_points=max_points,
                submission_type=submission_type
            )
            
            # DEBUG: Print raw response for troubleshooting
            print(f"\n{'='*80}")
            print(f"🔍 RAW GEMINI RESPONSE AFTER PARSING")
            print(f"{'='*80}")
            print(f"Type: {type(raw_grading)}")
            print(f"Keys: {list(raw_grading.keys()) if isinstance(raw_grading, dict) else 'N/A'}")
            if isinstance(raw_grading, dict):
                print(f"📊 Score value: {raw_grading.get('score')} (type: {type(raw_grading.get('score'))})")
                print(f"📊 Percentage value: {raw_grading.get('percentage')} (type: {type(raw_grading.get('percentage'))})")
                print(f"📊 Feedback value: {raw_grading.get('overall_feedback', 'N/A')[:100]}...")
                print(f"❌ Error key present: {'error' in raw_grading}")
                if 'error' in raw_grading:
                    print(f"❌ Error value: {raw_grading.get('error')}")
                # CRITICAL DEBUG: Check if keys are actually clean or have quotes
                print(f"🔑 First key (raw): {repr(list(raw_grading.keys())[0]) if raw_grading.keys() else 'N/A'}")
                print(f"🔑 Is 'score' a key?: {'score' in raw_grading}")
                print(f"🔑 Is '\"score\"' a key?: {'\"score\"' in raw_grading}")
            print(f"{'='*80}\n")

            # Extract score for database (best effort, but raw is source of truth)
            # Frontend will parse the raw data directly
            extracted_score = None
            extracted_feedback = None
            
            if isinstance(raw_grading, dict):
                # Try to get score from raw data (handle both clean and malformed keys)
                score_val = raw_grading.get('score') or raw_grading.get('"score"') or raw_grading.get('percentage') or raw_grading.get('"percentage"')
                if isinstance(score_val, (int, float)):
                    extracted_score = float(score_val)
                elif isinstance(score_val, str):
                    # Remove trailing commas and convert
                    cleaned = score_val.rstrip(',').strip()
                    try:
                        extracted_score = float(cleaned)
                    except:
                        pass
                
                # Try to get feedback
                feedback_val = raw_grading.get('overall_feedback') or raw_grading.get('"overall_feedback"') or raw_grading.get('detailed_feedback') or raw_grading.get('"detailed_feedback"')
                if isinstance(feedback_val, str):
                    # Remove trailing quotes and commas
                    extracted_feedback = feedback_val.strip('"').strip(',').strip()
            
            # Update database with extracted values (for legacy compatibility and search)
            submission.ai_processed = True
            submission.ai_score = extracted_score
            submission.ai_feedback = extracted_feedback
            submission.processed_at = datetime.utcnow()
            db.commit()
            
            # Return ONLY raw data - frontend handles all parsing
            ai_results = {"raw": raw_grading}
            
        except Exception as ai_err:
            # Don't fail the whole request if AI grading has an issue
            print(f"AI grading error: {ai_err}")
            ai_results = {"raw": {"error": str(ai_err)}}
        
        # If this upload is for an assignment, propagate status/grade to StudentAssignment
        try:
            if assignment_id_int and extracted_score is not None:
                student_assignment = db.query(StudentAssignment).filter(
                    StudentAssignment.assignment_id == assignment_id_int,
                    StudentAssignment.user_id == user_id
                ).first()

                # Create a StudentAssignment record if missing so status shows up immediately
                if not student_assignment:
                    due_days = getattr(assignment, 'due_days_after_assignment', 7) if 'assignment' in locals() and assignment else 7
                    student_assignment = StudentAssignment(
                        user_id=user_id,
                        assignment_id=assignment_id_int,
                        course_id=course_id,
                        due_date=datetime.utcnow() + timedelta(days=due_days),
                        status='assigned'
                    )
                    db.add(student_assignment)
                    db.flush()

                # Always mark submitted and attach file path
                student_assignment.submission_file_path = str(file_path)
                student_assignment.submission_content = f"PDF submission with {len(valid_files)} page(s)"
                student_assignment.submitted_at = datetime.utcnow()

                # Set grade from extracted score
                student_assignment.ai_grade = float(extracted_score)
                student_assignment.grade = float(extracted_score)
                student_assignment.status = "graded"

                # Feedback if available
                if extracted_feedback:
                    student_assignment.feedback = extracted_feedback

                student_assignment.updated_at = datetime.utcnow()
                db.commit()
        except Exception as assign_err:
            # Non-fatal: log and continue response
            print(f"⚠️ Could not update StudentAssignment for assignment_id={assignment_id_int}: {assign_err}")

        # Final commit to ensure all changes persisted
        db.commit()
        
        # Return JSON summary with ONLY raw Gemini data
        return JSONResponse({
            "success": True,
            "message": "PDF created and AI processed",
            "submission_id": submission.id,
            "pdf_filename": pdf_filename,
            "pdf_size": pdf_size,
            "content_hash": content_hash,
            "total_images": len(valid_files),
            "ai_processing_results": ai_results  # Only contains {"raw": {...}}
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
        raw_grading = await gemini_service.grade_submission_from_file(
            file_bytes=pdf_bytes,
            filename=submission.original_filename or "submission.pdf",
            assignment_title=assignment_title,
            assignment_description=assignment_description,
            rubric=rubric,
            max_points=max_points,
            submission_type=submission.submission_type
        )

        # Extract score and feedback for database (best effort)
        extracted_score = None
        extracted_feedback = None
        
        if isinstance(raw_grading, dict):
            # Try to get score from raw data (handle both clean and malformed keys)
            score_val = raw_grading.get('score') or raw_grading.get('"score"') or raw_grading.get('percentage') or raw_grading.get('"percentage"')
            if isinstance(score_val, (int, float)):
                extracted_score = float(score_val)
            elif isinstance(score_val, str):
                cleaned = score_val.rstrip(',').strip()
                try:
                    extracted_score = float(cleaned)
                except:
                    pass
            
            # Try to get feedback
            feedback_val = raw_grading.get('overall_feedback') or raw_grading.get('"overall_feedback"') or raw_grading.get('detailed_feedback') or raw_grading.get('"detailed_feedback"')
            if isinstance(feedback_val, str):
                extracted_feedback = feedback_val.strip('"').strip(',').strip()

        # Update submission with extracted values
        submission.ai_score = extracted_score
        submission.ai_feedback = extracted_feedback
        submission.processed_at = datetime.utcnow()
        submission.ai_processed = True
        db.commit()
        
    except Exception as ai_err:
        raise HTTPException(status_code=500, detail=f"AI grading error: {ai_err}")
    
    # Update associated study session if exists
    if submission.session_id:
        session = db.query(StudySession).filter(StudySession.id == submission.session_id).first()
        if session and extracted_score is not None:
            session.ai_score = extracted_score
            session.ai_feedback = extracted_feedback
            session.updated_at = datetime.utcnow()
            db.commit()
    
    return AIGradingResponse(
        submission_id=submission.id,
        ai_score=extracted_score if extracted_score is not None else 0.0,
        ai_feedback=extracted_feedback or "",
        ai_corrections=None,
        ai_strengths=None,
        ai_improvements=None,
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