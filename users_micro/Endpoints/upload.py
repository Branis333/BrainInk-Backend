from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends, status, UploadFile, File, Form, Query
from fastapi.responses import FileResponse
from typing import Annotated, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, or_
from pathlib import Path
import os
import shutil
import uuid

from db.connection import db_dependency
from models.study_area_models import (
    UserRole, Student, Teacher, Subject, StudentImage
)
from models.users_models import User
from Endpoints.auth import get_current_user
from Endpoints.utils import _get_user_roles, check_user_role, ensure_user_role, check_user_has_any_role, ensure_user_has_any_role

router = APIRouter(tags=["Image Upload and Management"])

user_dependency = Annotated[dict, Depends(get_current_user)]

# Configuration
UPLOAD_DIR = Path("uploads/student_images")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"}

# === IMAGE SCHEMAS (defined inline) ===

from pydantic import BaseModel, Field

class ImageBase(BaseModel):
    description: Optional[str] = None
    tags: Optional[str] = None
    subject_id: Optional[int] = None

class ImageResponse(ImageBase):
    id: int
    filename: str
    original_filename: str
    file_path: str
    file_size: int
    mime_type: str
    uploaded_by: int
    upload_date: datetime
    is_active: bool
    extracted_text: Optional[str] = None
    ai_analysis: Optional[str] = None
    analysis_date: Optional[datetime] = None
    
    # Include uploader and subject info
    uploader_name: Optional[str] = None
    subject_name: Optional[str] = None
    
    class Config:
        from_attributes = True

class ImageListResponse(BaseModel):
    images: List[ImageResponse] = []
    total_count: int = 0
    page: int = 1
    per_page: int = 20
    total_pages: int = 0

class ImageUploadResponse(BaseModel):
    success: bool
    message: str
    image: Optional[ImageResponse] = None
    error: Optional[str] = None

class ImageAnalysisUpdate(BaseModel):
    extracted_text: Optional[str] = None
    ai_analysis: Optional[str] = None

# === UTILITY FUNCTIONS ===

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

def generate_unique_filename(original_filename: str) -> str:
    """Generate unique filename while preserving extension"""
    file_ext = Path(original_filename).suffix.lower()
    unique_name = f"{uuid.uuid4()}{file_ext}"
    return unique_name

# === IMAGE UPLOAD ENDPOINTS ===

@router.post("/images-management/upload", response_model=ImageUploadResponse, tags=["Images"])
async def upload_image(
    db: db_dependency,
    current_user: user_dependency,
    file: UploadFile = File(...),
    description: Optional[str] = Form(None),
    tags: Optional[str] = Form(None),
    subject_id: Optional[int] = Form(None)
):
    """
    Upload a new image (Teachers only)
    """
    try:
        # Ensure user is a teacher
        ensure_user_role(db, current_user["user_id"], UserRole.teacher)
        
        teacher = db.query(Teacher).filter(Teacher.user_id == current_user["user_id"]).first()
        if not teacher:
            raise HTTPException(status_code=404, detail="Teacher profile not found")
        
        # Validate file
        is_valid, message = validate_file(file)
        if not is_valid:
            return ImageUploadResponse(
                success=False,
                message=message,
                error=message
            )
        
        # Validate subject if provided
        if subject_id:
            subject = db.query(Subject).filter(Subject.id == subject_id).first()
            if not subject:
                return ImageUploadResponse(
                    success=False,
                    message="Subject not found",
                    error="Subject not found"
                )
            
            # Check if teacher has access to this subject
            if subject not in teacher.subjects:
                return ImageUploadResponse(
                    success=False,
                    message="Access denied to this subject",
                    error="Access denied to this subject"
                )
        
        # Generate unique filename
        unique_filename = generate_unique_filename(file.filename)
        file_path = UPLOAD_DIR / unique_filename
        
        # Save file
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Get file info
        file_size = file_path.stat().st_size
        
        # Create database record
        db_image = StudentImage(
            filename=unique_filename,
            original_filename=file.filename,
            file_path=str(file_path),
            file_size=file_size,
            mime_type=file.content_type or "application/octet-stream",
            uploaded_by=current_user["user_id"],
            subject_id=subject_id,
            description=description,
            tags=tags
        )
        
        db.add(db_image)
        db.commit()
        db.refresh(db_image)
        
        # Prepare response
        uploader_name = f"{teacher.user.fname} {teacher.user.lname}" if teacher.user else "Unknown"
        subject_name = subject.name if subject_id and subject else None
        
        image_response = ImageResponse(
            id=db_image.id,
            filename=db_image.filename,
            original_filename=db_image.original_filename,
            file_path=db_image.file_path,
            file_size=db_image.file_size,
            mime_type=db_image.mime_type,
            uploaded_by=db_image.uploaded_by,
            upload_date=db_image.upload_date,
            is_active=db_image.is_active,
            extracted_text=db_image.extracted_text,
            ai_analysis=db_image.ai_analysis,
            analysis_date=db_image.analysis_date,
            description=db_image.description,
            tags=db_image.tags,
            subject_id=db_image.subject_id,
            uploader_name=uploader_name,
            subject_name=subject_name
        )
        
        return ImageUploadResponse(
            success=True,
            message="Image uploaded successfully",
            image=image_response
        )
        
    except Exception as e:
        # Clean up file if it was created
        if 'file_path' in locals() and file_path.exists():
            file_path.unlink()
        
        return ImageUploadResponse(
            success=False,
            message="Failed to upload image",
            error=str(e)
        )

@router.get("/images-management/my-images", response_model=ImageListResponse, tags=["Images"])
async def get_my_images(
    db: db_dependency,
    current_user: user_dependency,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    subject_id: Optional[int] = Query(None),
    search: Optional[str] = Query(None)
):
    """
    Get all images uploaded by the current teacher
    """
    ensure_user_role(db, current_user["user_id"], UserRole.teacher)
    
    teacher = db.query(Teacher).filter(Teacher.user_id == current_user["user_id"]).first()
    if not teacher:
        raise HTTPException(status_code=404, detail="Teacher profile not found")
    
    # Build query
    query = db.query(StudentImage).filter(
        StudentImage.uploaded_by == current_user["user_id"],
        StudentImage.is_active == True
    )
    
    # Filter by subject if provided
    if subject_id:
        query = query.filter(StudentImage.subject_id == subject_id)
    
    # Search in filename, description, or tags
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            or_(
                StudentImage.original_filename.ilike(search_term),
                StudentImage.description.ilike(search_term),
                StudentImage.tags.ilike(search_term)
            )
        )
    
    # Get total count
    total_count = query.count()
    
    # Apply pagination
    offset = (page - 1) * per_page
    images = query.order_by(desc(StudentImage.upload_date)).offset(offset).limit(per_page).all()
    
    # Prepare response
    image_responses = []
    for image in images:
        uploader_name = f"{teacher.user.fname} {teacher.user.lname}" if teacher.user else "Unknown"
        subject_name = image.subject.name if image.subject else None
        
        image_responses.append(ImageResponse(
            id=image.id,
            filename=image.filename,
            original_filename=image.original_filename,
            file_path=image.file_path,
            file_size=image.file_size,
            mime_type=image.mime_type,
            uploaded_by=image.uploaded_by,
            upload_date=image.upload_date,
            is_active=image.is_active,
            extracted_text=image.extracted_text,
            ai_analysis=image.ai_analysis,
            analysis_date=image.analysis_date,
            description=image.description,
            tags=image.tags,
            subject_id=image.subject_id,
            uploader_name=uploader_name,
            subject_name=subject_name
        ))
    
    total_pages = (total_count + per_page - 1) // per_page
    
    return ImageListResponse(
        images=image_responses,
        total_count=total_count,
        page=page,
        per_page=per_page,
        total_pages=total_pages
    )

@router.get("/images-management/{image_id}", response_model=ImageResponse, tags=["Images"])
async def get_image(
    image_id: int,
    db: db_dependency,
    current_user: user_dependency
):
    """
    Get a specific image (only by the teacher who uploaded it)
    """
    ensure_user_role(db, current_user["user_id"], UserRole.teacher)
    
    image = db.query(StudentImage).filter(
        StudentImage.id == image_id,
        StudentImage.uploaded_by == current_user["user_id"],
        StudentImage.is_active == True
    ).first()
    
    if not image:
        raise HTTPException(status_code=404, detail="Image not found")
    
    # Get uploader and subject info
    teacher = db.query(Teacher).filter(Teacher.user_id == current_user["user_id"]).first()
    uploader_name = f"{teacher.user.fname} {teacher.user.lname}" if teacher and teacher.user else "Unknown"
    subject_name = image.subject.name if image.subject else None
    
    return ImageResponse(
        id=image.id,
        filename=image.filename,
        original_filename=image.original_filename,
        file_path=image.file_path,
        file_size=image.file_size,
        mime_type=image.mime_type,
        uploaded_by=image.uploaded_by,
        upload_date=image.upload_date,
        is_active=image.is_active,
        extracted_text=image.extracted_text,
        ai_analysis=image.ai_analysis,
        analysis_date=image.analysis_date,
        description=image.description,
        tags=image.tags,
        subject_id=image.subject_id,
        uploader_name=uploader_name,
        subject_name=subject_name
    )

@router.put("/images-management/{image_id}", response_model=ImageResponse, tags=["Images"])
async def update_image(
    image_id: int,
    db: db_dependency,
    current_user: user_dependency,
    description: Optional[str] = Form(None),
    tags: Optional[str] = Form(None),
    subject_id: Optional[int] = Form(None)
):
    """
    Update image metadata (only by the teacher who uploaded it)
    """
    ensure_user_role(db, current_user["user_id"], UserRole.teacher)
    
    teacher = db.query(Teacher).filter(Teacher.user_id == current_user["user_id"]).first()
    if not teacher:
        raise HTTPException(status_code=404, detail="Teacher profile not found")
    
    image = db.query(StudentImage).filter(
        StudentImage.id == image_id,
        StudentImage.uploaded_by == current_user["user_id"],
        StudentImage.is_active == True
    ).first()
    
    if not image:
        raise HTTPException(status_code=404, detail="Image not found")
    
    # Validate subject if provided
    if subject_id:
        subject = db.query(Subject).filter(Subject.id == subject_id).first()
        if not subject:
            raise HTTPException(status_code=404, detail="Subject not found")
        
        if subject not in teacher.subjects:
            raise HTTPException(status_code=403, detail="Access denied to this subject")
    
    # Update fields
    if description is not None:
        image.description = description
    if tags is not None:
        image.tags = tags
    if subject_id is not None:
        image.subject_id = subject_id
    
    db.commit()
    db.refresh(image)
    
    # Prepare response
    uploader_name = f"{teacher.user.fname} {teacher.user.lname}" if teacher.user else "Unknown"
    subject_name = image.subject.name if image.subject else None
    
    return ImageResponse(
        id=image.id,
        filename=image.filename,
        original_filename=image.original_filename,
        file_path=image.file_path,
        file_size=image.file_size,
        mime_type=image.mime_type,
        uploaded_by=image.uploaded_by,
        upload_date=image.upload_date,
        is_active=image.is_active,
        extracted_text=image.extracted_text,
        ai_analysis=image.ai_analysis,
        analysis_date=image.analysis_date,
        description=image.description,
        tags=image.tags,
        subject_id=image.subject_id,
        uploader_name=uploader_name,
        subject_name=subject_name
    )

@router.put("/images-management/{image_id}/analysis", response_model=ImageResponse, tags=["Images"])
async def update_image_analysis(
    image_id: int,
    analysis_update: ImageAnalysisUpdate,
    db: db_dependency,
    current_user: user_dependency
):
    """
    Update image analysis results (only by the teacher who uploaded it)
    """
    ensure_user_role(db, current_user["user_id"], UserRole.teacher)
    
    image = db.query(StudentImage).filter(
        StudentImage.id == image_id,
        StudentImage.uploaded_by == current_user["user_id"],
        StudentImage.is_active == True
    ).first()
    
    if not image:
        raise HTTPException(status_code=404, detail="Image not found")
    
    # Update analysis fields
    if analysis_update.extracted_text is not None:
        image.extracted_text = analysis_update.extracted_text
    if analysis_update.ai_analysis is not None:
        image.ai_analysis = analysis_update.ai_analysis
    
    # Update analysis date
    image.analysis_date = datetime.utcnow()
    
    db.commit()
    db.refresh(image)
    
    # Get teacher and subject info
    teacher = db.query(Teacher).filter(Teacher.user_id == current_user["user_id"]).first()
    uploader_name = f"{teacher.user.fname} {teacher.user.lname}" if teacher and teacher.user else "Unknown"
    subject_name = image.subject.name if image.subject else None
    
    return ImageResponse(
        id=image.id,
        filename=image.filename,
        original_filename=image.original_filename,
        file_path=image.file_path,
        file_size=image.file_size,
        mime_type=image.mime_type,
        uploaded_by=image.uploaded_by,
        upload_date=image.upload_date,
        is_active=image.is_active,
        extracted_text=image.extracted_text,
        ai_analysis=image.ai_analysis,
        analysis_date=image.analysis_date,
        description=image.description,
        tags=image.tags,
        subject_id=image.subject_id,
        uploader_name=uploader_name,
        subject_name=subject_name
    )

@router.delete("/images-management/{image_id}", tags=["Images"])
async def delete_image(
    image_id: int,
    db: db_dependency,
    current_user: user_dependency
):
    """
    Soft delete an image (only by the teacher who uploaded it)
    """
    ensure_user_role(db, current_user["user_id"], UserRole.teacher)
    
    image = db.query(StudentImage).filter(
        StudentImage.id == image_id,
        StudentImage.uploaded_by == current_user["user_id"],
        StudentImage.is_active == True
    ).first()
    
    if not image:
        raise HTTPException(status_code=404, detail="Image not found")
    
    # Soft delete
    image.is_active = False
    db.commit()
    
    return {"message": "Image deleted successfully"}

@router.get("/images-management/subject/{subject_id}/images", response_model=ImageListResponse, tags=["Images"])
async def get_subject_images(
    subject_id: int,
    db: db_dependency,
    current_user: user_dependency,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100)
):
    """
    Get all images for a specific subject (accessible by teachers in the subject)
    """
    user_roles = _get_user_roles(db, current_user["user_id"])
    
    # Get subject
    subject = db.query(Subject).filter(Subject.id == subject_id).first()
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found")
    
    # Check access permissions
    has_access = False
    if UserRole.teacher in user_roles:
        teacher = db.query(Teacher).filter(Teacher.user_id == current_user["user_id"]).first()
        if teacher and subject in teacher.subjects:
            has_access = True
    
    if UserRole.principal in user_roles:
        # Principal can access all subjects in their school
        has_access = True
    
    if not has_access:
        raise HTTPException(status_code=403, detail="Access denied to this subject")
    
    # Build query
    query = db.query(StudentImage).filter(
        StudentImage.subject_id == subject_id,
        StudentImage.is_active == True
    )
    
    # Get total count
    total_count = query.count()
    
    # Apply pagination
    offset = (page - 1) * per_page
    images = query.order_by(desc(StudentImage.upload_date)).offset(offset).limit(per_page).all()
    
    # Prepare response
    image_responses = []
    for image in images:
        uploader = db.query(User).filter(User.id == image.uploaded_by).first()
        uploader_name = f"{uploader.fname} {uploader.lname}" if uploader else "Unknown"
        
        image_responses.append(ImageResponse(
            id=image.id,
            filename=image.filename,
            original_filename=image.original_filename,
            file_path=image.file_path,
            file_size=image.file_size,
            mime_type=image.mime_type,
            uploaded_by=image.uploaded_by,
            upload_date=image.upload_date,
            is_active=image.is_active,
            extracted_text=image.extracted_text,
            ai_analysis=image.ai_analysis,
            analysis_date=image.analysis_date,
            description=image.description,
            tags=image.tags,
            subject_id=image.subject_id,
            uploader_name=uploader_name,
            subject_name=subject.name
        ))
    
    total_pages = (total_count + per_page - 1) // per_page
    
    return ImageListResponse(
        images=image_responses,
        total_count=total_count,
        page=page,
        per_page=per_page,
        total_pages=total_pages
    )

@router.get("/images-management/{image_id}/file", tags=["Images"])
async def get_image_file(
    image_id: int,
    db: db_dependency,
    current_user: user_dependency
):
    """
    Get the actual image file (only by the teacher who uploaded it)
    """
    ensure_user_role(db, current_user["user_id"], UserRole.teacher)
    
    image = db.query(StudentImage).filter(
        StudentImage.id == image_id,
        StudentImage.uploaded_by == current_user["user_id"],
        StudentImage.is_active == True
    ).first()
    
    if not image:
        raise HTTPException(status_code=404, detail="Image not found")
    
    # Check if file exists
    file_path = Path(image.file_path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Image file not found on disk")
    
    # Return the file
    return FileResponse(
        path=str(file_path),
        media_type=image.mime_type,
        filename=image.original_filename
    )
