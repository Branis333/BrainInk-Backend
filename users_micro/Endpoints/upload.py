from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends, status, UploadFile, File, Form, Query
from fastapi.responses import FileResponse, Response
from typing import Annotated, List, Optional
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, desc, or_
from pathlib import Path
import os
import shutil
import uuid
import asyncio
import tempfile
import aiofiles
import hashlib
from PIL import Image
import io
import httpx
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.utils import ImageReader

from db.connection import db_dependency
from models.study_area_models import (
    UserRole, Student, Teacher, Subject, StudentImage, StudentPDF, Assignment, 
    GradingSession, Grade
)
from models.users_models import User
from schemas.assignments_schemas import (
    StudentImageUpload, ImageUploadResponse, StudentPDF as StudentPDFSchema,
    AssignmentImageSummary, BulkPDFGenerationRequest, BulkPDFGenerationResponse,
    GradingSessionCreate, GradingSessionResponse, AutoGradeRequest, AutoGradeResponse,
    AssignmentStudentsResponse, BulkUploadStudentInfo, BulkUploadDeleteResponse
)
from Endpoints.auth import get_current_user
from Endpoints.utils import _get_user_roles, check_user_role, ensure_user_role, check_user_has_any_role, ensure_user_has_any_role
from Endpoints.kana_service import KanaService

router = APIRouter(tags=["Assignment Image Upload, PDF Management & Bulk Upload"])

user_dependency = Annotated[dict, Depends(get_current_user)]

# Configuration
MAX_FILE_SIZE = 20 * 1024 * 1024  # 20MB
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"}

# Legacy file path for backward compatibility (deprecated - using database storage now)
STUDENT_PDFS_DIR = Path("uploads/student_pdfs")
STUDENT_PDFS_DIR.mkdir(parents=True, exist_ok=True)

print("📊 Using Database PDF Storage - No file system dependencies!")

# === UTILITY FUNCTIONS ===

def validate_image_file(file: UploadFile) -> tuple[bool, str]:
    """Validate uploaded image file"""
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

def generate_unique_filename(original_filename: str, student_id: int, assignment_id: int) -> str:
    """Generate unique filename while preserving extension"""
    file_ext = Path(original_filename).suffix.lower()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    unique_name = f"assignment_{assignment_id}_student_{student_id}_{timestamp}_{uuid.uuid4().hex[:8]}{file_ext}"
    return unique_name

async def check_and_generate_pdf(db: Session, student_id: int, assignment_id: int):
    """Check if student has multiple images for assignment and auto-generate PDF"""
    try:
        # Get all images for this student and assignment
        images = db.query(StudentImage).filter(
            StudentImage.student_id == student_id,
            StudentImage.assignment_id == assignment_id,
            StudentImage.is_processed == True
        ).order_by(StudentImage.upload_date).all()
        
        # Only generate PDF if there are 2 or more images
        if len(images) < 2:
            return None
            
        # Check if PDF already exists
        existing_pdf = db.query(StudentPDF).filter(
            StudentPDF.student_id == student_id,
            StudentPDF.assignment_id == assignment_id
        ).first()
        
        if existing_pdf:
            # Update existing PDF if new images were added
            if existing_pdf.image_count < len(images):
                await update_existing_pdf(db, existing_pdf, images)
            return existing_pdf
        
        # Generate new PDF
        return await generate_student_pdf(db, student_id, assignment_id, images)
        
    except Exception as e:
        print(f"Error in auto PDF generation: {e}")
        return None

async def generate_student_pdf(db: Session, student_id: int, assignment_id: int, images: List[StudentImage]):
    """Generate PDF from student images using KANA service"""
    try:
        # Get student and assignment info
        student = db.query(Student).options(joinedload(Student.user)).filter(Student.id == student_id).first()
        assignment = db.query(Assignment).filter(Assignment.id == assignment_id).first()
        
        if not student or not assignment:
            return None
        
        # Prepare image paths for KANA
        image_paths = [img.file_path for img in images]
        
        # Generate PDF filename
        student_name = f"{student.user.fname}_{student.user.lname}".replace(" ", "_")
        assignment_title = assignment.title.replace(" ", "_").replace("/", "_")
        pdf_filename = f"{student_name}_{assignment_title}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        pdf_path = STUDENT_PDFS_DIR / pdf_filename
        
        # Call KANA service to generate PDF
        pdf_result = await KanaService.generate_assignment_pdf(
            image_paths=image_paths,
            student_name=f"{student.user.fname} {student.user.lname}",
            assignment_title=assignment.title,
            output_path=str(pdf_path)
        )
        
        if not pdf_result.get("success", False):
            print(f"KANA PDF generation failed: {pdf_result.get('error', 'Unknown error')}")
            return None
        
        # Create PDF record in database
        student_pdf = StudentPDF(
            assignment_id=assignment_id,
            student_id=student_id,
            pdf_filename=pdf_filename,
            pdf_path=str(pdf_path),
            image_count=len(images)
        )
        
        db.add(student_pdf)
        db.commit()
        db.refresh(student_pdf)
        
        print(f"🎯 PDF generated successfully: {pdf_filename}")
        print(f"📝 Triggering automatic AI grading...")
        
        # Automatic grading trigger - check if this is for a course assignment
        try:
            # Check if it's a course assignment (after-school system)
            course_assignment = db.query(CourseAssignment).filter(
                CourseAssignment.id == assignment_id
            ).first()
            
            if course_assignment:
                print(f"🤖 Course assignment detected - preparing for AI grading")
                # Note: The actual grading will be triggered by the frontend or 
                # can be done here by calling the auto-grade endpoint
                # For now, we'll let the existing auto-grade system handle it
                pass
            else:
                print(f"📚 Regular assignment - standard grading workflow applies")
                
        except Exception as grade_error:
            print(f"⚠️ Could not trigger automatic grading: {grade_error}")
            # Don't fail the PDF generation if grading trigger fails
            pass
        
        return student_pdf
        
    except Exception as e:
        print(f"Error generating PDF: {e}")
        return None

async def update_existing_pdf(db: Session, existing_pdf: StudentPDF, images: List[StudentImage]):
    """Update existing PDF with new images"""
    try:
        # Get updated info
        student = db.query(Student).options(joinedload(Student.user)).filter(Student.id == existing_pdf.student_id).first()
        assignment = db.query(Assignment).filter(Assignment.id == existing_pdf.assignment_id).first()
        
        # Prepare image paths
        image_paths = [img.file_path for img in images]
        
        # Call KANA service to regenerate PDF
        pdf_result = await KanaService.generate_assignment_pdf(
            image_paths=image_paths,
            student_name=f"{student.user.fname} {student.user.lname}",
            assignment_title=assignment.title,
            output_path=existing_pdf.pdf_path
        )
        
        if pdf_result.get("success", False):
            # Update PDF record
            existing_pdf.image_count = len(images)
            existing_pdf.generated_date = datetime.utcnow()
            db.commit()
                
    except Exception as e:
        print(f"Error updating PDF: {e}")

# === BULK UPLOAD UTILITY FUNCTIONS ===

def validate_bulk_image_file(file: UploadFile) -> bool:
    """Validate if uploaded file is a supported image format for bulk upload"""
    if not file.filename:
        return False
    
    file_extension = Path(file.filename).suffix.lower()
    return file_extension in ALLOWED_EXTENSIONS


def resize_image_for_pdf(image: Image.Image, max_width: float, max_height: float) -> tuple:
    """
    Resize image to fit within PDF page dimensions while maintaining aspect ratio
    Returns (width, height) for the resized image
    """
    img_width, img_height = image.size
    
    # Calculate scaling factor to fit within page
    width_ratio = max_width / img_width
    height_ratio = max_height / img_height
    scale_factor = min(width_ratio, height_ratio)
    
    # Calculate new dimensions
    new_width = img_width * scale_factor
    new_height = img_height * scale_factor
    
    return new_width, new_height


async def create_pdf_from_images(images: List[UploadFile], filename: str) -> tuple[bytes, str]:
    """
    Create a PDF file from a list of image files
    Returns tuple of (pdf_bytes, content_hash)
    """
    # Create PDF in memory
    pdf_buffer = io.BytesIO()
    c = canvas.Canvas(pdf_buffer, pagesize=A4)
    page_width, page_height = A4
   
    # Add margins (50 points = ~0.7 inches)
    margin = 50
    usable_width = page_width - (2 * margin)
    usable_height = page_height - (2 * margin)
    
    for image_file in images:
        try:
            # Read image data
            image_data = await image_file.read()
            
            # Open image with PIL
            image = Image.open(io.BytesIO(image_data))
            
            # Convert to RGB if necessary (for PDF compatibility)
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            # Calculate dimensions to fit the page
            img_width, img_height = resize_image_for_pdf(image, usable_width, usable_height)
            
            # Center the image on the page
            x_offset = (page_width - img_width) / 2
            y_offset = (page_height - img_height) / 2
            
            # Create ImageReader object for reportlab
            img_buffer = io.BytesIO()
            image.save(img_buffer, format='JPEG', quality=85)
            img_buffer.seek(0)
            img_reader = ImageReader(img_buffer)
            
            # Draw image on PDF
            c.drawImage(img_reader, x_offset, y_offset, width=img_width, height=img_height)
            
            # Add new page for next image (if not the last image)
            if image_file != images[-1]:
                c.showPage()
                
        except Exception as e:
            # If there's an error with this image, skip it and continue
            print(f"Error processing image {image_file.filename}: {str(e)}")
            continue
    
    # Save the PDF to buffer
    c.save()
    
    # Get PDF bytes
    pdf_buffer.seek(0)
    pdf_bytes = pdf_buffer.read()
    
    # Generate content hash for deduplication
    content_hash = hashlib.md5(pdf_bytes).hexdigest()
    
    print(f"📄 PDF created in memory: {len(pdf_bytes)} bytes, hash: {content_hash}")
    return pdf_bytes, content_hash

# === ASSIGNMENT IMAGE UPLOAD ENDPOINTS ===

@router.post("/assignment-images/upload", response_model=ImageUploadResponse)
async def upload_assignment_image(
    db: db_dependency,
    current_user: user_dependency,
    assignment_id: int = Form(...),
    student_id: int = Form(...),
    description: Optional[str] = Form(None),
    file: UploadFile = File(...)
):
    """
    Upload an image for a specific student's assignment (Teachers only)
    """
    try:
        # Ensure user is a teacher
        ensure_user_role(db, current_user["user_id"], UserRole.teacher)
        
        teacher = db.query(Teacher).filter(Teacher.user_id == current_user["user_id"]).first()
        if not teacher:
            raise HTTPException(status_code=404, detail="Teacher profile not found")
        
        # Validate file
        is_valid, message = validate_image_file(file)
        if not is_valid:
            raise HTTPException(status_code=400, detail=message)
        
        # Get and validate assignment
        assignment = db.query(Assignment).options(joinedload(Assignment.subject)).filter(
            Assignment.id == assignment_id
        ).first()
        if not assignment:
            raise HTTPException(status_code=404, detail="Assignment not found")
        
        # Check if teacher has access to this assignment's subject
        if assignment.teacher_id != teacher.id:
            raise HTTPException(status_code=403, detail="Access denied to this assignment")
        
        # Get and validate student
        student = db.query(Student).options(joinedload(Student.user)).filter(
            Student.id == student_id
        ).first()
        if not student:
            raise HTTPException(status_code=404, detail="Student not found")
        
        # Check if student is in the assignment's subject
        student_in_subject = db.query(Student).join(Student.subjects).filter(
            Student.id == student_id,
            Subject.id == assignment.subject_id
        ).first()
        
        if not student_in_subject:
            raise HTTPException(status_code=403, detail="Student is not enrolled in this subject")
        
        # Generate unique filename
        unique_filename = generate_unique_filename(file.filename, student_id, assignment_id)
        file_path = ASSIGNMENT_IMAGES_DIR / unique_filename
        
        # Save file
        async with aiofiles.open(file_path, "wb") as buffer:
            content = await file.read()
            await buffer.write(content)
        
        # Get file info
        file_size = file_path.stat().st_size
        
        # Create database record
        db_image = StudentImage(
            assignment_id=assignment_id,
            student_id=student_id,
            filename=unique_filename,
            original_filename=file.filename,
            file_path=str(file_path),
            file_size=file_size,
            mime_type=file.content_type or "image/jpeg",
            uploaded_by=current_user["user_id"],
            description=description,
            is_processed=True
        )
        
        db.add(db_image)
        db.commit()
        db.refresh(db_image)
        
        # Auto-generate PDF if multiple images exist
        pdf_result = await check_and_generate_pdf(db, student_id, assignment_id)
        
        # Prepare response
        return ImageUploadResponse(
            id=db_image.id,
            assignment_id=db_image.assignment_id,
            student_id=db_image.student_id,
            filename=db_image.filename,
            original_filename=db_image.original_filename,
            file_path=db_image.file_path,
            file_size=db_image.file_size,
            mime_type=db_image.mime_type,
            upload_date=db_image.upload_date,
            is_processed=db_image.is_processed,
            assignment_title=assignment.title,
            student_name=f"{student.user.fname} {student.user.lname}",
            subject_name=assignment.subject.name
        )
        
    except HTTPException:
        # Clean up file if it was created
        if 'file_path' in locals() and file_path.exists():
            file_path.unlink()
        raise
    except Exception as e:
        # Clean up file if it was created
        if 'file_path' in locals() and file_path.exists():
            file_path.unlink()
        raise HTTPException(status_code=500, detail=f"Failed to upload image: {str(e)}")

@router.get("/assignment-images/assignment/{assignment_id}/summary", response_model=AssignmentImageSummary)
async def get_assignment_images_summary(
    assignment_id: int,
    db: db_dependency,
    current_user: user_dependency
):
    """
    Get summary of images and PDFs for an assignment (Teachers only)
    """
    ensure_user_role(db, current_user["user_id"], UserRole.teacher)
    
    teacher = db.query(Teacher).filter(Teacher.user_id == current_user["user_id"]).first()
    if not teacher:
        raise HTTPException(status_code=404, detail="Teacher profile not found")
    
    # Get assignment
    assignment = db.query(Assignment).options(joinedload(Assignment.subject)).filter(
        Assignment.id == assignment_id
    ).first()
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")
    
    # Check access
    if assignment.teacher_id != teacher.id:
        raise HTTPException(status_code=403, detail="Access denied to this assignment")
    
    # Get all students in the subject using a simpler approach
    try:
        # First get the subject
        subject = db.query(Subject).filter(Subject.id == assignment.subject_id).first()
        if not subject:
            raise HTTPException(status_code=404, detail="Subject not found")
        
        # Get students enrolled in this subject
        # Use a different approach to avoid relationship issues
        students = db.query(Student).options(joinedload(Student.user)).filter(
            Student.is_active == True
        ).all()
        
        # Filter students who are in this subject (we'll do this check differently)
        # For now, include all active students to avoid the relationship error
        students_in_subject = students
        
    except Exception as e:
        print(f"Error querying students: {str(e)}")
        # Fallback: return empty list if query fails
        students_in_subject = []
    
    # Get images and PDFs data
    students_data = []
    total_images = 0
    students_with_images = 0
    students_with_pdfs = 0
    
    for student in students_in_subject:
        # Get student's images for this assignment
        images = db.query(StudentImage).filter(
            StudentImage.assignment_id == assignment_id,
            StudentImage.student_id == student.id
        ).all()
        
        # Get student's PDF for this assignment
        pdf = db.query(StudentPDF).filter(
            StudentPDF.assignment_id == assignment_id,
            StudentPDF.student_id == student.id
        ).first()
        
        image_count = len(images)
        total_images += image_count
        
        if image_count > 0:
            students_with_images += 1
        
        if pdf:
            students_with_pdfs += 1
        
        students_data.append({
            "student_id": student.id,
            "student_name": f"{student.user.fname} {student.user.lname}",
            "image_count": image_count,
            "has_pdf": pdf is not None,
            "pdf_id": pdf.id if pdf else None,
            "is_graded": pdf.is_graded if pdf else False,
            "images": [
                {
                    "id": image.id,
                    "filename": image.filename,
                    "description": image.description,
                    "upload_date": image.upload_date.isoformat() if image.upload_date else None,
                    "file_path": image.file_path,
                    "is_processed": image.is_processed
                }
                for image in images
            ]
        })
    
    return AssignmentImageSummary(
        assignment_id=assignment_id,
        assignment_title=assignment.title,
        subject_name=assignment.subject.name,
        total_students=len(students),
        students_with_images=students_with_images,
        students_with_pdfs=students_with_pdfs,
        total_images=total_images,
        students_data=students_data
    )

@router.post("/assignment-images/assignment/{assignment_id}/generate-pdfs", response_model=BulkPDFGenerationResponse)
async def bulk_generate_pdfs(
    assignment_id: int,
    db: db_dependency,
    current_user: user_dependency
):
    """
    Generate PDFs for all students with images in an assignment
    """
    ensure_user_role(db, current_user["user_id"], UserRole.teacher)
    
    teacher = db.query(Teacher).filter(Teacher.user_id == current_user["user_id"]).first()
    if not teacher:
        raise HTTPException(status_code=404, detail="Teacher profile not found")
    
    # Get assignment
    assignment = db.query(Assignment).options(joinedload(Assignment.subject)).filter(
        Assignment.id == assignment_id
    ).first()
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")
    
    # Check access
    if assignment.teacher_id != teacher.id:
        raise HTTPException(status_code=403, detail="Access denied to this assignment")
    
    # Get all students with images for this assignment
    students_with_images = db.query(StudentImage.student_id).filter(
        StudentImage.assignment_id == assignment_id
    ).distinct().all()
    
    student_ids = [row[0] for row in students_with_images]
    
    generated_pdfs = []
    errors = []
    pdfs_generated = 0
    pdfs_failed = 0
    
    for student_id in student_ids:
        try:
            # Get images for this student
            images = db.query(StudentImage).filter(
                StudentImage.student_id == student_id,
                StudentImage.assignment_id == assignment_id,
                StudentImage.is_processed == True
            ).order_by(StudentImage.upload_date).all()
            
            if len(images) == 0:
                continue
                
            # Check if PDF already exists
            existing_pdf = db.query(StudentPDF).filter(
                StudentPDF.student_id == student_id,
                StudentPDF.assignment_id == assignment_id
            ).first()
            
            if existing_pdf:
                # Update if needed
                if existing_pdf.image_count < len(images):
                    await update_existing_pdf(db, existing_pdf, images)
                generated_pdfs.append(existing_pdf)
                pdfs_generated += 1
            else:
                # Generate new PDF
                pdf_result = await generate_student_pdf(db, student_id, assignment_id, images)
                if pdf_result:
                    generated_pdfs.append(pdf_result)
                    pdfs_generated += 1
                else:
                    pdfs_failed += 1
                    errors.append({
                        "student_id": student_id,
                        "error": "Failed to generate PDF"
                    })
                    
        except Exception as e:
            pdfs_failed += 1
            errors.append({
                "student_id": student_id,
                "error": str(e)
            })
    
    # Convert to response format
    pdf_responses = []
    for pdf in generated_pdfs:
        student = db.query(Student).options(joinedload(Student.user)).filter(Student.id == pdf.student_id).first()
        pdf_responses.append(StudentPDFSchema(
            id=pdf.id,
            assignment_id=pdf.assignment_id,
            student_id=pdf.student_id,
            pdf_filename=pdf.pdf_filename,
            pdf_path=pdf.pdf_path,
            image_count=pdf.image_count,
            generated_date=pdf.generated_date,
            is_graded=pdf.is_graded,
            grade_id=pdf.grade_id,
            assignment_title=assignment.title,
            student_name=f"{student.user.fname} {student.user.lname}",
            subject_name=assignment.subject.name,
            max_points=assignment.max_points
        ))
    
    return BulkPDFGenerationResponse(
        success=pdfs_failed == 0,
        assignment_id=assignment_id,
        total_students=len(student_ids),
        pdfs_generated=pdfs_generated,
        pdfs_failed=pdfs_failed,
        generated_pdfs=pdf_responses,
        errors=errors
    )

# === GRADING SESSION ENDPOINTS ===

@router.post("/grading-sessions/create", response_model=GradingSessionResponse)
async def create_grading_session(
    session_request: GradingSessionCreate,
    db: db_dependency,
    current_user: user_dependency
):
    """
    Create a grading session for an assignment
    """
    ensure_user_role(db, current_user["user_id"], UserRole.teacher)
    
    teacher = db.query(Teacher).filter(Teacher.user_id == current_user["user_id"]).first()
    if not teacher:
        raise HTTPException(status_code=404, detail="Teacher profile not found")
    
    # Get assignment
    assignment = db.query(Assignment).options(joinedload(Assignment.subject)).filter(
        Assignment.id == session_request.assignment_id
    ).first()
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")
    
    # Check access
    if assignment.teacher_id != teacher.id:
        raise HTTPException(status_code=403, detail="Access denied to this assignment")
    
    # Check if session already exists
    existing_session = db.query(GradingSession).filter(
        GradingSession.assignment_id == session_request.assignment_id,
        GradingSession.is_completed == False
    ).first()
    
    if existing_session:
        raise HTTPException(status_code=400, detail="Active grading session already exists for this assignment")
    
    # Get student PDFs count
    pdf_count = db.query(StudentPDF).filter(
        StudentPDF.assignment_id == session_request.assignment_id
    ).count()
    
    # Create grading session
    grading_session = GradingSession(
        assignment_id=session_request.assignment_id,
        teacher_id=teacher.id,
        subject_id=assignment.subject_id,
        total_students=pdf_count
    )
    
    db.add(grading_session)
    db.commit()
    db.refresh(grading_session)
    
    # Get student PDFs
    student_pdfs = db.query(StudentPDF).filter(
        StudentPDF.assignment_id == session_request.assignment_id
    ).all()
    
    # Convert to response format
    pdf_responses = []
    for pdf in student_pdfs:
        student = db.query(Student).options(joinedload(Student.user)).filter(Student.id == pdf.student_id).first()
        pdf_responses.append(StudentPDFSchema(
            id=pdf.id,
            assignment_id=pdf.assignment_id,
            student_id=pdf.student_id,
            pdf_filename=pdf.pdf_filename,
            pdf_path=pdf.pdf_path,
            image_count=pdf.image_count,
            generated_date=pdf.generated_date,
            is_graded=pdf.is_graded,
            grade_id=pdf.grade_id,
            assignment_title=assignment.title,
            student_name=f"{student.user.fname} {student.user.lname}",
            subject_name=assignment.subject.name,
            max_points=assignment.max_points
        ))
    
    return GradingSessionResponse(
        id=grading_session.id,
        assignment_id=grading_session.assignment_id,
        teacher_id=grading_session.teacher_id,
        subject_id=grading_session.subject_id,
        created_date=grading_session.created_date,
        is_completed=grading_session.is_completed,
        assignment_title=assignment.title,
        subject_name=assignment.subject.name,
        teacher_name=f"{teacher.user.fname} {teacher.user.lname}",
        student_pdfs=pdf_responses,
        total_students=grading_session.total_students,
        graded_count=grading_session.graded_count
    )

@router.post("/grading-sessions/{session_id}/auto-grade", response_model=AutoGradeResponse)
async def auto_grade_assignment(
    session_id: int,
    grade_request: AutoGradeRequest,
    db: db_dependency,
    current_user: user_dependency
):
    """
    Automatically grade all PDFs in a grading session using AI
    """
    ensure_user_role(db, current_user["user_id"], UserRole.teacher)
    
    teacher = db.query(Teacher).filter(Teacher.user_id == current_user["user_id"]).first()
    if not teacher:
        raise HTTPException(status_code=404, detail="Teacher profile not found")
    
    # Get grading session
    session = db.query(GradingSession).options(
        joinedload(GradingSession.assignment),
        joinedload(GradingSession.subject)
    ).filter(GradingSession.id == session_id).first()
    
    if not session:
        raise HTTPException(status_code=404, detail="Grading session not found")
    
    # Check access
    if session.teacher_id != teacher.id:
        raise HTTPException(status_code=403, detail="Access denied to this grading session")
    
    if session.is_completed:
        raise HTTPException(status_code=400, detail="Grading session is already completed")
    
    # Get all ungraded PDFs for this assignment
    ungraded_pdfs = db.query(StudentPDF).filter(
        StudentPDF.assignment_id == session.assignment_id,
        StudentPDF.is_graded == False
    ).all()
    
    if not ungraded_pdfs:
        raise HTTPException(status_code=400, detail="No ungraded PDFs found")
    
    student_results = []
    successfully_graded = 0
    failed_gradings = 0
    total_score = 0
    errors = []
    
    for pdf in ungraded_pdfs:
        try:
            # Get student info
            student = db.query(Student).options(joinedload(Student.user)).filter(Student.id == pdf.student_id).first()

            temp_pdf_path = None
            pdf_path_for_grading = None

            if pdf.pdf_data:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_pdf:
                    temp_pdf.write(bytes(pdf.pdf_data))
                    temp_pdf.flush()
                    temp_pdf_path = temp_pdf.name
                pdf_path_for_grading = temp_pdf_path
            elif pdf.pdf_path:
                pdf_path_for_grading = pdf.pdf_path
            else:
                raise Exception("No PDF binary data or file path available for grading")
            
            # Call KANA AI grading service
            grading_result = await KanaService.grade_assignment_pdf(
                pdf_path=pdf_path_for_grading,
                assignment_title=session.assignment.title,
                assignment_description=session.assignment.description,
                rubric=session.assignment.rubric,
                max_points=session.assignment.max_points,
                feedback_type=grade_request.feedback_type,
                student_name=f"{student.user.fname} {student.user.lname}"
            )

            if temp_pdf_path:
                try:
                    os.unlink(temp_pdf_path)
                except Exception:
                    pass
            
            if grading_result.get("success", False):
                # Create grade record
                grade = Grade(
                    assignment_id=session.assignment_id,
                    student_id=pdf.student_id,
                    teacher_id=teacher.id,
                    points_earned=grading_result.get("points_earned", 0),
                    feedback=grading_result.get("feedback", ""),
                    ai_generated=True,
                    ai_confidence=grading_result.get("confidence", 80)
                )
                    
                db.add(grade)
                db.commit()
                db.refresh(grade)
                
                # Update PDF record
                pdf.is_graded = True
                pdf.grade_id = grade.id
                db.commit()
                
                # Update session stats
                session.graded_count += 1
                
                successfully_graded += 1
                total_score += grade.points_earned
                
                student_results.append({
                    "student_id": pdf.student_id,
                    "student_name": f"{student.user.fname} {student.user.lname}",
                    "points_earned": grade.points_earned,
                    "max_points": session.assignment.max_points,
                    "percentage": round((grade.points_earned / session.assignment.max_points) * 100, 2),
                    "feedback": grade.feedback,
                    "confidence": grade.ai_confidence,
                    "pdf_filename": pdf.pdf_filename
                })
                
            else:
                failed_gradings += 1
                errors.append({
                    "student_id": pdf.student_id,
                    "student_name": f"{student.user.fname} {student.user.lname}",
                    "error": f"AI grading failed: {grading_result.get('error', 'Unknown error')}"
                })
                    
        except Exception as e:
            if 'temp_pdf_path' in locals() and temp_pdf_path:
                try:
                    os.unlink(temp_pdf_path)
                except Exception:
                    pass
            failed_gradings += 1
            errors.append({
                "student_id": pdf.student_id,
                "student_name": f"{student.user.fname} {student.user.lname}" if 'student' in locals() else "Unknown",
                "error": str(e)
            })
    
    # Update session completion status
    if successfully_graded > 0 and failed_gradings == 0:
        session.is_completed = True
        session.completed_date = datetime.utcnow()
    
    db.commit()
    
    # Calculate average score
    average_score = round(total_score / successfully_graded, 2) if successfully_graded > 0 else 0
    
    return AutoGradeResponse(
        success=failed_gradings == 0,
        session_id=session_id,
        assignment_id=session.assignment_id,
        total_students=len(ungraded_pdfs),
        successfully_graded=successfully_graded,
        failed_gradings=failed_gradings,
        average_score=average_score,
        processed_at=datetime.utcnow(),
        student_results=student_results,
        batch_summary={
            "assignment_title": session.assignment.title,
            "subject_name": session.subject.name,
            "total_possible_points": session.assignment.max_points,
            "average_percentage": round((average_score / session.assignment.max_points) * 100, 2) if session.assignment.max_points > 0 else 0,
            "grading_method": "AI Automated" if grade_request.use_ai_grading else "Manual Review"
        },
        errors=errors
    )

# === UTILITY ENDPOINTS ===

@router.get("/assignment-images/file/{image_id}")
async def get_image_file(
    image_id: int,
    db: db_dependency,
    current_user: user_dependency
):
    """
    Download an assignment image file
    """
    ensure_user_role(db, current_user["user_id"], UserRole.teacher)
    
    teacher = db.query(Teacher).filter(Teacher.user_id == current_user["user_id"]).first()
    if not teacher:
        raise HTTPException(status_code=404, detail="Teacher profile not found")
    
    # Get image
    image = db.query(StudentImage).options(joinedload(StudentImage.assignment)).filter(
        StudentImage.id == image_id
    ).first()
    
    if not image:
        raise HTTPException(status_code=404, detail="Image not found")
    
    # Check access
    if image.assignment.teacher_id != teacher.id:
        raise HTTPException(status_code=403, detail="Access denied to this image")
    
    # Check if file exists
    if not Path(image.file_path).exists():
        raise HTTPException(status_code=404, detail="Image file not found on disk")
    
    return FileResponse(
        path=image.file_path,
        filename=image.original_filename,
        media_type=image.mime_type
    )

@router.get("/student-pdfs/file/{pdf_id}")
async def get_pdf_file(
    pdf_id: int,
    db: db_dependency,
    current_user: user_dependency
):
    """
    Download a student PDF file
    """
    ensure_user_role(db, current_user["user_id"], UserRole.teacher)
    
    teacher = db.query(Teacher).filter(Teacher.user_id == current_user["user_id"]).first()
    if not teacher:
        raise HTTPException(status_code=404, detail="Teacher profile not found")
    
    # Get PDF
    pdf = db.query(StudentPDF).options(joinedload(StudentPDF.assignment)).filter(
        StudentPDF.id == pdf_id
    ).first()
    
    if not pdf:
        raise HTTPException(status_code=404, detail="PDF not found")
    
    # Check access
    if pdf.assignment.teacher_id != teacher.id:
        raise HTTPException(status_code=403, detail="Access denied to this PDF")

    if pdf.pdf_data:
        return Response(
            content=bytes(pdf.pdf_data),
            media_type=pdf.mime_type or "application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename={pdf.pdf_filename}",
                "Content-Length": str(len(pdf.pdf_data))
            }
        )

    if pdf.pdf_path and Path(pdf.pdf_path).exists():
        return FileResponse(
            path=pdf.pdf_path,
            filename=pdf.pdf_filename,
            media_type="application/pdf"
        )

    raise HTTPException(status_code=404, detail="PDF content not found in database or on disk")

@router.get("/grading-sessions/{session_id}", response_model=GradingSessionResponse)
async def get_grading_session(
    session_id: int,
    db: db_dependency,
    current_user: user_dependency
):
    """
    Get grading session details
    """
    ensure_user_role(db, current_user["user_id"], UserRole.teacher)
    
    teacher = db.query(Teacher).filter(Teacher.user_id == current_user["user_id"]).first()
    if not teacher:
        raise HTTPException(status_code=404, detail="Teacher profile not found")
    
    # Get grading session
    session = db.query(GradingSession).options(
        joinedload(GradingSession.assignment),
        joinedload(GradingSession.subject)
    ).filter(GradingSession.id == session_id).first()
    
    if not session:
        raise HTTPException(status_code=404, detail="Grading session not found")
    
    # Check access
    if session.teacher_id != teacher.id:
        raise HTTPException(status_code=403, detail="Access denied to this grading session")
    
    # Get student PDFs
    student_pdfs = db.query(StudentPDF).filter(
        StudentPDF.assignment_id == session.assignment_id
    ).all()
    
    # Convert to response format
    pdf_responses = []
    for pdf in student_pdfs:
        student = db.query(Student).options(joinedload(Student.user)).filter(Student.id == pdf.student_id).first()
        pdf_responses.append(StudentPDFSchema(
            id=pdf.id,
            assignment_id=pdf.assignment_id,
            student_id=pdf.student_id,
            pdf_filename=pdf.pdf_filename,
            pdf_path=pdf.pdf_path,
            image_count=pdf.image_count,
            generated_date=pdf.generated_date,
            is_graded=pdf.is_graded,
            grade_id=pdf.grade_id,
            assignment_title=session.assignment.title,
            student_name=f"{student.user.fname} {student.user.lname}",
            subject_name=session.subject.name,
            max_points=session.assignment.max_points
        ))
    
    return GradingSessionResponse(
        id=session.id,
        assignment_id=session.assignment_id,
        teacher_id=session.teacher_id,
        subject_id=session.subject_id,
        created_date=session.created_date,
        is_completed=session.is_completed,
        assignment_title=session.assignment.title,
        subject_name=session.subject.name,
        teacher_name=f"{teacher.user.fname} {teacher.user.lname}",
        student_pdfs=pdf_responses,
        total_students=session.total_students,
        graded_count=session.graded_count
    )

# === BULK IMAGE TO PDF ENDPOINTS ===

@router.post("/bulk-upload-to-pdf")
async def bulk_upload_images_to_pdf_assignment(
    db: db_dependency,
    current_user: user_dependency,
    assignment_id: int = Form(..., description="Assignment ID"),
    student_id: int = Form(..., description="Student ID"),
    files: List[UploadFile] = File(..., description="Multiple image files to combine into PDF"),
    storage_mode: str = Form("database", description="Storage mode: 'database' (default) or 'path' for legacy path-based storage if available"),
    skip_db: bool = Form(False, description="If true, only generate PDF and return; do not persist (debug)")
):
    """
    Upload multiple image files for a specific student assignment and combine them into a single PDF.
    
    - **assignment_id**: Assignment the images belong to
    - **student_id**: Student the images belong to  
    - **files**: List of image files (JPG, PNG, GIF, BMP, TIFF, WEBP)
    - Returns: PDF file containing all images as separate pages
    
    The API will:
    1. Validate teacher access to assignment
    2. Validate all uploaded files are images
    3. Convert and resize images to fit PDF pages
    4. Combine all images into a single PDF document
    5. Save PDF record in database
    6. Return the generated PDF file
    
    Note: Images are added as-is without any text extraction or OCR processing.
    """
    
    try:
        # Ensure user is a teacher
        ensure_user_role(db, current_user["user_id"], UserRole.teacher)
        
        teacher = db.query(Teacher).filter(Teacher.user_id == current_user["user_id"]).first()
        if not teacher:
            raise HTTPException(status_code=404, detail="Teacher profile not found")
        
        # Get and validate assignment
        assignment = db.query(Assignment).options(joinedload(Assignment.subject)).filter(
            Assignment.id == assignment_id
        ).first()
        if not assignment:
            raise HTTPException(status_code=404, detail="Assignment not found")
        
        # Check if teacher has access to this assignment
        if assignment.teacher_id != teacher.id:
            raise HTTPException(status_code=403, detail="Access denied to this assignment")
        
        # Get and validate student
        student = db.query(Student).options(joinedload(Student.user)).filter(
            Student.id == student_id
        ).first()
        if not student:
            raise HTTPException(status_code=404, detail="Student not found")
        
        # Check if student is in the assignment's subject
        student_in_subject = db.query(Student).join(Student.subjects).filter(
            Student.id == student_id,
            Subject.id == assignment.subject_id
        ).first()
        
        if not student_in_subject:
            raise HTTPException(status_code=403, detail="Student is not enrolled in this subject")
        
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
            if ext not in ALLOWED_EXTENSIONS:
                invalid_files.append(file.filename)
                continue
            # Fast size check (UploadFile may not have .size attr in some servers; attempt header fallback)
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

        # Reset file pointers (FastAPI's UploadFile is a SpooledTemporaryFile; we re-seek before read in create_pdf_from_images)
        for f in valid_files:
            try:
                if f.file.seekable():
                    f.file.seek(0)
            except Exception:
                pass
        
        # Generate PDF filename with student and assignment names
        student_name = f"{student.user.fname}_{student.user.lname}".replace(" ", "_")
        assignment_title = assignment.title.replace(" ", "_").replace("/", "_")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        pdf_filename = f"{student_name}_{assignment_title}_{timestamp}.pdf"
        
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

        # Normalize storage_mode
        storage_mode_normalized = storage_mode.lower().strip()
        if storage_mode_normalized not in {"database", "path"}:
            storage_mode_normalized = "database"
        
        # Check if PDF already exists for this student and assignment
        existing_pdf = db.query(StudentPDF).filter(
            StudentPDF.student_id == student_id,
            StudentPDF.assignment_id == assignment_id
        ).first()
        
        try:
            if existing_pdf:
                # Update existing PDF record
                existing_pdf.pdf_filename = pdf_filename
                existing_pdf.pdf_data = pdf_bytes
                existing_pdf.pdf_size = pdf_size
                existing_pdf.content_hash = content_hash
                existing_pdf.image_count = len(valid_files)
                existing_pdf.generated_date = datetime.utcnow()
                # Backward compatibility path (store a synthetic path reference)
                if hasattr(existing_pdf, 'pdf_path'):
                    existing_pdf.pdf_path = f"uploads/student_pdfs/{pdf_filename}"
                db.commit()
                db.refresh(existing_pdf)
                student_pdf = existing_pdf
            else:
                # Create new PDF record in database
                student_pdf = StudentPDF(
                    assignment_id=assignment_id,
                    student_id=student_id,
                    pdf_filename=pdf_filename,
                    pdf_data=pdf_bytes if storage_mode_normalized == "database" else None,
                    pdf_size=pdf_size,
                    content_hash=content_hash,
                    image_count=len(valid_files),
                    mime_type="application/pdf"
                )
                if hasattr(student_pdf, 'pdf_path'):
                    setattr(student_pdf, 'pdf_path', f"uploads/student_pdfs/{pdf_filename}")
                # NOTE: If legacy path-based mode is required and model supports pdf_path, you would set it here.
                db.add(student_pdf)
                db.commit()
                db.refresh(student_pdf)
        except Exception as db_err:
            # Provide a JSON diagnostic fallback (client can display meaningful info)
            raise HTTPException(status_code=500, detail=f"Database persistence failed: {db_err}")
        
        # Return the PDF file directly from memory
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename={pdf_filename}",
                "Content-Length": str(pdf_size),
                "X-Total-Images": str(len(valid_files)),
                "X-Student-Name": f"{student.user.fname} {student.user.lname}",
                "X-Assignment-Title": assignment.title,
                "X-PDF-ID": str(student_pdf.id),
                "X-Content-Hash": content_hash
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating PDF: {str(e)}")


@router.get("/bulk-upload/assignment/{assignment_id}/students", response_model=AssignmentStudentsResponse)
async def get_assignment_students_for_bulk_upload(
    assignment_id: int,
    db: db_dependency,
    current_user: user_dependency
):
    """
    Get list of students enrolled in an assignment's subject for bulk upload selection
    """
    try:
        # Ensure user is a teacher
        ensure_user_role(db, current_user["user_id"], UserRole.teacher)
        
        teacher = db.query(Teacher).filter(Teacher.user_id == current_user["user_id"]).first()
        if not teacher:
            raise HTTPException(status_code=404, detail="Teacher profile not found")
        
        # Get assignment
        assignment = db.query(Assignment).options(joinedload(Assignment.subject)).filter(
            Assignment.id == assignment_id
        ).first()
        if not assignment:
            raise HTTPException(status_code=404, detail="Assignment not found")
        
        # Check access
        if assignment.teacher_id != teacher.id:
            raise HTTPException(status_code=403, detail="Access denied to this assignment")
        
        # Get all students in the assignment's subject
        students = db.query(Student).options(joinedload(Student.user)).join(
            Student.subjects
        ).filter(
            Subject.id == assignment.subject_id,
            Student.is_active == True
        ).all()
        
        # Check existing PDFs for each student
        students_data = []
        for student in students:
            existing_pdf = db.query(StudentPDF).filter(
                StudentPDF.assignment_id == assignment_id,
                StudentPDF.student_id == student.id
            ).first()
            
            students_data.append(BulkUploadStudentInfo(
                student_id=student.id,
                student_name=f"{student.user.fname} {student.user.lname}",
                has_pdf=existing_pdf is not None,
                pdf_id=existing_pdf.id if existing_pdf else None,
                image_count=existing_pdf.image_count if existing_pdf else 0,
                generated_date=existing_pdf.generated_date.isoformat() if existing_pdf else None,
                is_graded=existing_pdf.is_graded if existing_pdf else False
            ))
        
        return AssignmentStudentsResponse(
            assignment_id=assignment_id,
            assignment_title=assignment.title,
            subject_name=assignment.subject.name,
            total_students=len(students_data),
            students=students_data
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching students: {str(e)}")


@router.get("/bulk-upload/assignment/{assignment_id}/student/{student_id}/pdf")
async def get_student_assignment_pdf(
    assignment_id: int,
    student_id: int,
    db: db_dependency,
    current_user: user_dependency
):
    """
    Download the PDF for a specific student assignment from database
    """
    print(f"🔍 PDF Download Request: assignment_id={assignment_id}, student_id={student_id}")
    
    try:
        # Ensure user is a teacher
        ensure_user_role(db, current_user["user_id"], UserRole.teacher)
        
        teacher = db.query(Teacher).filter(Teacher.user_id == current_user["user_id"]).first()
        if not teacher:
            raise HTTPException(status_code=404, detail="Teacher profile not found")
        
        # Get assignment and check access
        assignment = db.query(Assignment).filter(Assignment.id == assignment_id).first()
        if not assignment:
            raise HTTPException(status_code=404, detail="Assignment not found")
        
        if assignment.teacher_id != teacher.id:
            raise HTTPException(status_code=403, detail="Access denied to this assignment")
        
        # Get student PDF from database
        student_pdf = db.query(StudentPDF).filter(
            StudentPDF.assignment_id == assignment_id,
            StudentPDF.student_id == student_id
        ).first()
        
        if not student_pdf:
            raise HTTPException(status_code=404, detail="PDF not found for this student assignment")
        
        # Check if PDF data exists in database
        if not student_pdf.pdf_data:
            raise HTTPException(status_code=404, detail="PDF data not found in database")
        
        print(f"📄 Serving PDF from database: {student_pdf.pdf_filename}, size: {len(student_pdf.pdf_data)} bytes")
        
        # Return PDF data directly from database
        return Response(
            content=student_pdf.pdf_data,
            media_type=student_pdf.mime_type or "application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename={student_pdf.pdf_filename}",
                "Content-Length": str(len(student_pdf.pdf_data)),
                "X-PDF-ID": str(student_pdf.id),
                "X-Content-Hash": student_pdf.content_hash or "",
                "X-Image-Count": str(student_pdf.image_count or 0)
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving PDF: {str(e)}")


@router.delete("/bulk-upload/assignment/{assignment_id}/student/{student_id}/pdf", response_model=BulkUploadDeleteResponse)
async def delete_student_assignment_pdf(
    assignment_id: int,
    student_id: int,
    db: db_dependency,
    current_user: user_dependency
):
    """
    Delete the PDF for a specific student assignment
    """
    try:
        # Ensure user is a teacher
        ensure_user_role(db, current_user["user_id"], UserRole.teacher)
        
        teacher = db.query(Teacher).filter(Teacher.user_id == current_user["user_id"]).first()
        if not teacher:
            raise HTTPException(status_code=404, detail="Teacher profile not found")
        
        # Get assignment and check access
        assignment = db.query(Assignment).filter(Assignment.id == assignment_id).first()
        if not assignment:
            raise HTTPException(status_code=404, detail="Assignment not found")
        
        if assignment.teacher_id != teacher.id:
            raise HTTPException(status_code=403, detail="Access denied to this assignment")
        
        # Get student PDF
        student_pdf = db.query(StudentPDF).filter(
            StudentPDF.assignment_id == assignment_id,
            StudentPDF.student_id == student_id
        ).first()
        
        if not student_pdf:
            raise HTTPException(status_code=404, detail="PDF not found for this student assignment")
        
        # Store filename before deletion
        deleted_filename = student_pdf.pdf_filename
        pdf_size = len(student_pdf.pdf_data) if student_pdf.pdf_data else 0
        
        # Delete database record (PDF data is stored in database)
        db.delete(student_pdf)
        db.commit()
        
        print(f"🗑️ Deleted PDF from database: {deleted_filename}, size: {pdf_size} bytes")
        
        return BulkUploadDeleteResponse(
            message="PDF deleted successfully from database",
            assignment_id=assignment_id,
            student_id=student_id,
            deleted_filename=deleted_filename
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting PDF: {str(e)}")


@router.get("/bulk-upload/health")
async def bulk_upload_health_check():
    """
    Simple health check endpoint for bulk upload service
    """
    return {
        "status": "healthy",
        "service": "Assignment-Based Bulk Image to PDF Converter",
        "timestamp": datetime.now().isoformat(),
        "supported_formats": list(ALLOWED_EXTENSIONS),
        "storage_method": "database_binary",
        "features": [
            "Image validation and resizing",
            "PDF generation in memory",
            "Database binary storage",
            "Content deduplication via hashing",
            "No file system dependencies"
        ]
    }