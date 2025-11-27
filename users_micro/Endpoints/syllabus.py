from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.orm import Session, joinedload
from db.connection import get_db, db_dependency
from models.users_models import User
from models.study_area_models import (
    Syllabus, WeeklyPlan, StudentSyllabusProgress, Subject, 
    Teacher, Student, SyllabusStatus, subject_students, UserRole
)
from schemas.syllabus_schemas import (
    SyllabusCreateRequest, SyllabusUpdateRequest, SyllabusResponse, SyllabusListResponse,
    WeeklyPlanCreateRequest, WeeklyPlanUpdateRequest, WeeklyPlanResponse,
    StudentProgressUpdateRequest, StudentSyllabusProgressResponse,
    SyllabusWithProgressResponse, TextbookAnalysisRequest, KanaProcessingResponse
)
from Endpoints.auth import get_current_user
from Endpoints.utils import ensure_user_role, ensure_user_has_any_role, _get_user_roles
from typing import List, Optional, Annotated
import json
import os
import aiofiles
import httpx
from datetime import datetime
import uuid

router = APIRouter(tags=["Syllabus"])

# Use the same pattern as school_management.py
user_dependency = Annotated[dict, Depends(get_current_user)]

# Configuration
UPLOAD_DIR = "uploads/textbooks"
KANA_BASE_URL = os.getenv("KANA_BASE_URL", "https://kana-backend-app.onrender.com")

# Ensure upload directory exists
os.makedirs(UPLOAD_DIR, exist_ok=True)

# --- HELPER FUNCTIONS ---

def get_user_permissions(current_user: dict, db: Session):
    """Get user's teaching/principal permissions"""
    permissions = {
        "can_create_syllabus": False,
        "can_edit_any_syllabus": False,
        "school_id": None,
        "teacher_id": None,
        "student_id": None
    }
    
    user_id = current_user["user_id"]
    user_roles = _get_user_roles(db, user_id)
    
    # Check if user is a principal
    if UserRole.principal in user_roles:
        from models.study_area_models import School
        school = db.query(School).filter(School.principal_id == user_id).first()
        if school:
            permissions["can_create_syllabus"] = True
            permissions["can_edit_any_syllabus"] = True
            permissions["school_id"] = school.id
    
    # Check if user is a teacher
    teacher = db.query(Teacher).filter(Teacher.user_id == user_id).first()
    if teacher:
        permissions["can_create_syllabus"] = True
        permissions["school_id"] = teacher.school_id
        permissions["teacher_id"] = teacher.id
    
    # Check if user is a student
    student = db.query(Student).filter(Student.user_id == user_id).first()
    if student:
        permissions["school_id"] = student.school_id
        permissions["student_id"] = student.id
    
    return permissions

def serialize_json_field(data):
    """Helper to serialize JSON fields"""
    if isinstance(data, str):
        try:
            return json.loads(data)
        except:
            return []
    return data or []

def format_syllabus_response(syllabus, include_weekly_plans=False):
    """Format syllabus for response"""
    response_data = {
        "id": syllabus.id,
        "title": syllabus.title,
        "description": syllabus.description,
        "subject_id": syllabus.subject_id,
        "subject_name": syllabus.subject.name if syllabus.subject else None,
        "created_by": syllabus.created_by,
        "creator_name": f"{syllabus.creator.fname} {syllabus.creator.lname}" if syllabus.creator else None,
        "term_length_weeks": syllabus.term_length_weeks,
        "textbook_filename": syllabus.textbook_filename,
        "textbook_path": syllabus.textbook_path,
        "ai_processing_status": syllabus.ai_processing_status,
        "ai_analysis_data": json.loads(syllabus.ai_analysis_data) if syllabus.ai_analysis_data else None,
        "status": syllabus.status,
        "created_date": syllabus.created_date,
        "updated_date": syllabus.updated_date,
        "is_active": syllabus.is_active,
    }
    
    if include_weekly_plans:
        weekly_plans = []
        for plan in sorted(syllabus.weekly_plans, key=lambda x: x.week_number):
            weekly_plans.append({
                "id": plan.id,
                "syllabus_id": plan.syllabus_id,
                "week_number": plan.week_number,
                "title": plan.title,
                "description": plan.description,
                "learning_objectives": serialize_json_field(plan.learning_objectives),
                "topics_covered": serialize_json_field(plan.topics_covered),
                "textbook_chapters": plan.textbook_chapters,
                "textbook_pages": plan.textbook_pages,
                "assignments": serialize_json_field(plan.assignments),
                "resources": serialize_json_field(plan.resources),
                "notes": plan.notes,
                "created_date": plan.created_date,
                "updated_date": plan.updated_date,
                "is_active": plan.is_active
            })
        response_data["weekly_plans"] = weekly_plans
    
    return response_data

# --- SYLLABUS ENDPOINTS ---

@router.post("/syllabuses", response_model=SyllabusResponse)
async def create_syllabus(
    syllabus_data: SyllabusCreateRequest,
    current_user: user_dependency,
    db: db_dependency
):
    """Create a new syllabus (Principal or Teacher only)"""
    permissions = get_user_permissions(current_user, db)
    
    if not permissions["can_create_syllabus"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only principals and teachers can create syllabuses"
        )
    
    # Verify subject exists and user has access
    subject = db.query(Subject).filter(
        Subject.id == syllabus_data.subject_id,
        Subject.school_id == permissions["school_id"],
        Subject.is_active == True
    ).first()
    
    if not subject:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subject not found or access denied"
        )
    
    # Check if syllabus already exists for this subject
    existing_syllabus = db.query(Syllabus).filter(
        Syllabus.subject_id == syllabus_data.subject_id,
        Syllabus.status != SyllabusStatus.archived,
        Syllabus.is_active == True
    ).first()
    
    if existing_syllabus:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An active syllabus already exists for this subject"
        )
    
    # Create syllabus
    new_syllabus = Syllabus(
        title=syllabus_data.title,
        description=syllabus_data.description,
        subject_id=syllabus_data.subject_id,
        created_by=current_user["user_id"],
        term_length_weeks=syllabus_data.term_length_weeks
    )
    
    db.add(new_syllabus)
    db.commit()
    db.refresh(new_syllabus)
    
    # Load relationships for response
    db.refresh(new_syllabus)
    syllabus_with_relations = db.query(Syllabus).options(
        joinedload(Syllabus.subject),
        joinedload(Syllabus.creator),
        joinedload(Syllabus.weekly_plans)
    ).filter(Syllabus.id == new_syllabus.id).first()
    
    return format_syllabus_response(syllabus_with_relations, include_weekly_plans=True)

@router.get("/syllabuses", response_model=List[SyllabusListResponse])
async def get_syllabuses(
    current_user: user_dependency,
    db: db_dependency,
    subject_id: Optional[int] = None,
    status: Optional[str] = None
):
    """Get all syllabuses accessible to the user"""
    permissions = get_user_permissions(current_user, db)
    
    if not permissions["school_id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User not associated with any school"
        )
    
    query = db.query(Syllabus).options(
        joinedload(Syllabus.subject),
        joinedload(Syllabus.creator),
        joinedload(Syllabus.weekly_plans)
    ).join(Subject).filter(
        Subject.school_id == permissions["school_id"],
        Syllabus.is_active == True
    )
    
    if subject_id:
        query = query.filter(Syllabus.subject_id == subject_id)
    
    if status:
        query = query.filter(Syllabus.status == status)
    
    syllabuses = query.all()
    
    result = []
    for syllabus in syllabuses:
        response_data = {
            "id": syllabus.id,
            "title": syllabus.title,
            "description": syllabus.description,
            "subject_id": syllabus.subject_id,
            "subject_name": syllabus.subject.name if syllabus.subject else None,
            "created_by": syllabus.created_by,
            "creator_name": f"{syllabus.creator.fname} {syllabus.creator.lname}" if syllabus.creator else None,
            "term_length_weeks": syllabus.term_length_weeks,
            "textbook_filename": syllabus.textbook_filename,
            "ai_processing_status": syllabus.ai_processing_status,
            "status": syllabus.status,
            "created_date": syllabus.created_date,
            "updated_date": syllabus.updated_date,
            "total_weeks": len(syllabus.weekly_plans),
        }
        
        # If user is a student, include their progress
        if permissions["student_id"]:
            progress = db.query(StudentSyllabusProgress).filter(
                StudentSyllabusProgress.student_id == permissions["student_id"],
                StudentSyllabusProgress.syllabus_id == syllabus.id
            ).first()
            response_data["completed_weeks"] = len(serialize_json_field(progress.completed_weeks)) if progress else 0
        
        result.append(response_data)
    
    return result

@router.get("/syllabuses/{syllabus_id}", response_model=SyllabusResponse)
async def get_syllabus(
    syllabus_id: int,
    current_user: user_dependency,
    db: db_dependency
):
    """Get a specific syllabus with weekly plans"""
    permissions = get_user_permissions(current_user, db)
    
    syllabus = db.query(Syllabus).options(
        joinedload(Syllabus.subject),
        joinedload(Syllabus.creator),
        joinedload(Syllabus.weekly_plans)
    ).join(Subject).filter(
        Syllabus.id == syllabus_id,
        Subject.school_id == permissions["school_id"],
        Syllabus.is_active == True
    ).first()
    
    if not syllabus:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Syllabus not found or access denied"
        )
    
    # Update last accessed if user is a student
    if permissions["student_id"]:
        progress = db.query(StudentSyllabusProgress).filter(
            StudentSyllabusProgress.student_id == permissions["student_id"],
            StudentSyllabusProgress.syllabus_id == syllabus_id
        ).first()
        
        if not progress:
            # Create progress record
            progress = StudentSyllabusProgress(
                student_id=permissions["student_id"],
                syllabus_id=syllabus_id,
                current_week=1,
                completed_weeks=json.dumps([]),
                progress_percentage=0
            )
            db.add(progress)
        else:
            progress.last_accessed = datetime.utcnow()
        
        db.commit()
    
    return format_syllabus_response(syllabus, include_weekly_plans=True)

@router.put("/syllabuses/{syllabus_id}", response_model=SyllabusResponse)
async def update_syllabus(
    syllabus_id: int,
    syllabus_data: SyllabusUpdateRequest,
    current_user: user_dependency,
    db: db_dependency
):
    """Update a syllabus"""
    permissions = get_user_permissions(current_user, db)
    
    syllabus = db.query(Syllabus).options(
        joinedload(Syllabus.subject),
        joinedload(Syllabus.creator),
        joinedload(Syllabus.weekly_plans)
    ).join(Subject).filter(
        Syllabus.id == syllabus_id,
        Subject.school_id == permissions["school_id"],
        Syllabus.is_active == True
    ).first()
    
    if not syllabus:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Syllabus not found or access denied"
        )
    
    # Check permissions
    can_edit = (
        permissions["can_edit_any_syllabus"] or  # Principal
        syllabus.created_by == current_user["user_id"]   # Creator
    )
    
    if not can_edit:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only edit syllabuses you created"
        )
    
    # Update fields
    if syllabus_data.title is not None:
        syllabus.title = syllabus_data.title
    if syllabus_data.description is not None:
        syllabus.description = syllabus_data.description
    if syllabus_data.term_length_weeks is not None:
        syllabus.term_length_weeks = syllabus_data.term_length_weeks
    if syllabus_data.status is not None:
        syllabus.status = syllabus_data.status
    
    syllabus.updated_date = datetime.utcnow()
    
    db.commit()
    db.refresh(syllabus)
    
    return format_syllabus_response(syllabus, include_weekly_plans=True)

@router.patch("/syllabuses/{syllabus_id}/status")
async def update_syllabus_status(
    syllabus_id: int,
    status_update: dict,
    current_user: user_dependency,
    db: db_dependency
):
    """Update syllabus status (Principal only)"""
    permissions = get_user_permissions(current_user, db)
    
    # Only principals can manually change status
    if not permissions["can_edit_any_syllabus"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only principals can manually update syllabus status"
        )
    
    syllabus = db.query(Syllabus).join(Subject).filter(
        Syllabus.id == syllabus_id,
        Subject.school_id == permissions["school_id"],
        Syllabus.is_active == True
    ).first()
    
    if not syllabus:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Syllabus not found or access denied"
        )
    
    new_status = status_update.get("status")
    if new_status not in ["draft", "active", "archived"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid status. Must be one of: draft, active, archived"
        )
    
    syllabus.status = new_status
    syllabus.updated_date = datetime.utcnow()
    
    db.commit()
    db.refresh(syllabus)
    
    return {
        "success": True,
        "message": f"Syllabus status updated to {new_status}",
        "syllabus_id": syllabus_id,
        "new_status": new_status
    }

# --- TEXTBOOK UPLOAD & K.A.N.A. INTEGRATION ---

@router.post("/syllabuses/{syllabus_id}/upload-textbook", response_model=KanaProcessingResponse)
async def upload_textbook(
    syllabus_id: int,
    current_user: user_dependency,
    db: db_dependency,
    textbook: UploadFile = File(...)
):
    """Upload textbook and trigger K.A.N.A. AI processing"""
    permissions = get_user_permissions(current_user, db)
    
    if not permissions["can_create_syllabus"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only principals and teachers can upload textbooks"
        )
    
    # Get syllabus
    syllabus = db.query(Syllabus).join(Subject).filter(
        Syllabus.id == syllabus_id,
        Subject.school_id == permissions["school_id"],
        Syllabus.is_active == True
    ).first()
    
    if not syllabus:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Syllabus not found or access denied"
        )
    
    # Check if user can edit this syllabus
    can_edit = (
        permissions["can_edit_any_syllabus"] or
        syllabus.created_by == current_user["user_id"]
    )
    
    if not can_edit:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only upload textbooks to syllabuses you created"
        )
    
    # Validate file type
    if not textbook.filename.lower().endswith('.pdf'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF files are supported"
        )
    
    # Save file
    file_id = str(uuid.uuid4())
    filename = f"{file_id}_{textbook.filename}"
    file_path = os.path.join(UPLOAD_DIR, filename)
    
    try:
        async with aiofiles.open(file_path, 'wb') as f:
            content = await textbook.read()
            await f.write(content)
        
        # Update syllabus with file info and auto-activate
        syllabus.textbook_filename = textbook.filename
        syllabus.textbook_path = file_path
        syllabus.ai_processing_status = "processing"
        
        # Auto-activate syllabus when textbook is successfully uploaded
        if syllabus.status == SyllabusStatus.draft:
            syllabus.status = SyllabusStatus.active
            print(f"📚 Syllabus {syllabus_id} auto-activated after textbook upload")
        
        syllabus.updated_date = datetime.utcnow()
        
        db.commit()
        
        # Call K.A.N.A. AI service
        try:
            async with httpx.AsyncClient(timeout=300.0) as client:
                with open(file_path, 'rb') as pdf_file:
                    files = {'textbook': (textbook.filename, pdf_file, 'application/pdf')}
                    data = {
                        'syllabus_id': syllabus_id,
                        'term_length_weeks': syllabus.term_length_weeks,
                        'subject_name': syllabus.subject.name
                    }
                    
                    response = await client.post(
                        f"{KANA_BASE_URL}/api/kana/process-syllabus-textbook",
                        files=files,
                        data=data
                    )
                    
                    if response.status_code == 200:
                        result = response.json()
                        
                        # Update syllabus with processing results
                        syllabus.ai_processing_status = "completed"
                        syllabus.ai_analysis_data = json.dumps(result.get('analysis_data', {}))
                        
                        # Auto-activate syllabus when textbook is successfully uploaded and processed
                        if syllabus.status == SyllabusStatus.draft:
                            syllabus.status = SyllabusStatus.active
                            print(f"📚 Syllabus {syllabus_id} auto-activated after textbook upload")
                        
                        # Create weekly plans if provided
                        if result.get('weekly_plans'):
                            for plan_data in result['weekly_plans']:
                                weekly_plan = WeeklyPlan(
                                    syllabus_id=syllabus_id,
                                    week_number=plan_data['week_number'],
                                    title=plan_data['title'],
                                    description=plan_data['description'],
                                    learning_objectives=json.dumps(plan_data.get('learning_objectives', [])),
                                    topics_covered=json.dumps(plan_data.get('topics_covered', [])),
                                    textbook_chapters=plan_data.get('textbook_chapters'),
                                    textbook_pages=plan_data.get('textbook_pages'),
                                    assignments=json.dumps(plan_data.get('assignments', [])),
                                    resources=json.dumps(plan_data.get('resources', []))
                                )
                                db.add(weekly_plan)
                        
                        db.commit()
                        
                        return KanaProcessingResponse(
                            success=True,
                            message="Textbook processed successfully",
                            processing_id=file_id,
                            weekly_plans=result.get('weekly_plans')
                        )
                    else:
                        raise HTTPException(
                            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail=f"K.A.N.A. processing failed: {response.text}"
                        )
        
        except httpx.RequestError as e:
            syllabus.ai_processing_status = "failed"
            
            # Auto-activate syllabus even if K.A.N.A. processing fails (fallback)
            if syllabus.status == SyllabusStatus.draft:
                syllabus.status = SyllabusStatus.active
                print(f"📚 Syllabus {syllabus_id} auto-activated after textbook upload (K.A.N.A. failed)")
            
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to connect to K.A.N.A. service: {str(e)}"
            )
    
    except Exception as e:
        # Clean up file on error
        if os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"File upload failed: {str(e)}"
        )

# --- WEEKLY PLANS ENDPOINTS ---

@router.post("/syllabuses/{syllabus_id}/weekly-plans", response_model=WeeklyPlanResponse)
async def create_weekly_plan(
    syllabus_id: int,
    plan_data: WeeklyPlanCreateRequest,
    current_user: user_dependency,
    db: db_dependency
):
    """Create a weekly plan"""
    permissions = get_user_permissions(current_user, db)
    
    # Get syllabus and verify access
    syllabus = db.query(Syllabus).join(Subject).filter(
        Syllabus.id == syllabus_id,
        Subject.school_id == permissions["school_id"],
        Syllabus.is_active == True
    ).first()
    
    if not syllabus:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Syllabus not found or access denied"
        )
    
    # Check permissions
    can_edit = (
        permissions["can_edit_any_syllabus"] or
        syllabus.created_by == current_user["user_id"]
    )
    
    if not can_edit:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only add plans to syllabuses you created"
        )
    
    # Check if week already exists
    existing_plan = db.query(WeeklyPlan).filter(
        WeeklyPlan.syllabus_id == syllabus_id,
        WeeklyPlan.week_number == plan_data.week_number,
        WeeklyPlan.is_active == True
    ).first()
    
    if existing_plan:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Week {plan_data.week_number} already exists"
        )
    
    # Create weekly plan
    weekly_plan = WeeklyPlan(
        syllabus_id=syllabus_id,
        week_number=plan_data.week_number,
        title=plan_data.title,
        description=plan_data.description,
        learning_objectives=json.dumps(plan_data.learning_objectives or []),
        topics_covered=json.dumps(plan_data.topics_covered or []),
        textbook_chapters=plan_data.textbook_chapters,
        textbook_pages=plan_data.textbook_pages,
        assignments=json.dumps(plan_data.assignments or []),
        resources=json.dumps(plan_data.resources or []),
        notes=plan_data.notes
    )
    
    db.add(weekly_plan)
    db.commit()
    db.refresh(weekly_plan)
    
    return {
        "id": weekly_plan.id,
        "syllabus_id": weekly_plan.syllabus_id,
        "week_number": weekly_plan.week_number,
        "title": weekly_plan.title,
        "description": weekly_plan.description,
        "learning_objectives": serialize_json_field(weekly_plan.learning_objectives),
        "topics_covered": serialize_json_field(weekly_plan.topics_covered),
        "textbook_chapters": weekly_plan.textbook_chapters,
        "textbook_pages": weekly_plan.textbook_pages,
        "assignments": serialize_json_field(weekly_plan.assignments),
        "resources": serialize_json_field(weekly_plan.resources),
        "notes": weekly_plan.notes,
        "created_date": weekly_plan.created_date,
        "updated_date": weekly_plan.updated_date,
        "is_active": weekly_plan.is_active
    }

# --- STUDENT PROGRESS ENDPOINTS ---

@router.get("/student/syllabuses", response_model=List[SyllabusWithProgressResponse])
async def get_student_syllabuses(
    current_user: user_dependency,
    db: db_dependency
):
    """Get all syllabuses for the current student with their progress"""
    permissions = get_user_permissions(current_user, db)
    
    if not permissions["student_id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only students can access this endpoint"
        )
    
    # Get student's subjects
    student = db.query(Student).options(joinedload(Student.subjects)).filter(
        Student.id == permissions["student_id"]
    ).first()
    
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student profile not found"
        )
    
    result = []
    for subject in student.subjects:
        # Get active syllabus for this subject
        syllabus = db.query(Syllabus).options(
            joinedload(Syllabus.subject),
            joinedload(Syllabus.creator),
            joinedload(Syllabus.weekly_plans)
        ).filter(
            Syllabus.subject_id == subject.id,
            Syllabus.status == SyllabusStatus.active,
            Syllabus.is_active == True
        ).first()
        
        if syllabus:
            # Get student's progress
            progress = db.query(StudentSyllabusProgress).filter(
                StudentSyllabusProgress.student_id == permissions["student_id"],
                StudentSyllabusProgress.syllabus_id == syllabus.id
            ).first()
            
            syllabus_response = format_syllabus_response(syllabus, include_weekly_plans=True)
            progress_response = None
            
            if progress:
                progress_response = {
                    "id": progress.id,
                    "student_id": progress.student_id,
                    "syllabus_id": progress.syllabus_id,
                    "current_week": progress.current_week,
                    "completed_weeks": serialize_json_field(progress.completed_weeks),
                    "progress_percentage": progress.progress_percentage,
                    "last_accessed": progress.last_accessed,
                    "created_date": progress.created_date,
                    "updated_date": progress.updated_date
                }
            
            result.append({
                "syllabus": syllabus_response,
                "progress": progress_response
            })
    
    return result

@router.put("/student/syllabuses/{syllabus_id}/progress", response_model=StudentSyllabusProgressResponse)
async def update_student_progress(
    syllabus_id: int,
    progress_data: StudentProgressUpdateRequest,
    current_user: user_dependency,
    db: db_dependency
):
    """Update student's progress on a syllabus"""
    permissions = get_user_permissions(current_user, db)
    
    if not permissions["student_id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only students can update their progress"
        )
    
    # Verify syllabus access
    syllabus = db.query(Syllabus).join(Subject).join(subject_students).filter(
        Syllabus.id == syllabus_id,
        subject_students.c.student_id == permissions["student_id"],
        Syllabus.is_active == True
    ).first()
    
    if not syllabus:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Syllabus not found or access denied"
        )
    
    # Get or create progress record
    progress = db.query(StudentSyllabusProgress).filter(
        StudentSyllabusProgress.student_id == permissions["student_id"],
        StudentSyllabusProgress.syllabus_id == syllabus_id
    ).first()
    
    if not progress:
        progress = StudentSyllabusProgress(
            student_id=permissions["student_id"],
            syllabus_id=syllabus_id,
            current_week=1,
            completed_weeks=json.dumps([]),
            progress_percentage=0
        )
        db.add(progress)
    
    # Update progress
    if progress_data.current_week is not None:
        progress.current_week = progress_data.current_week
    
    if progress_data.completed_weeks is not None:
        progress.completed_weeks = json.dumps(progress_data.completed_weeks)
        # Calculate progress percentage
        total_weeks = syllabus.term_length_weeks
        completed_count = len(progress_data.completed_weeks)
        progress.progress_percentage = min(100, (completed_count * 100) // total_weeks)
    
    progress.updated_date = datetime.utcnow()
    progress.last_accessed = datetime.utcnow()
    
    db.commit()
    db.refresh(progress)
    
    return {
        "id": progress.id,
        "student_id": progress.student_id,
        "syllabus_id": progress.syllabus_id,
        "current_week": progress.current_week,
        "completed_weeks": serialize_json_field(progress.completed_weeks),
        "progress_percentage": progress.progress_percentage,
        "last_accessed": progress.last_accessed,
        "created_date": progress.created_date,
        "updated_date": progress.updated_date
    }

@router.post("/student/syllabuses/{syllabus_id}/weeks/{week_number}/complete")
async def mark_week_complete(
    syllabus_id: int,
    week_number: int,
    current_user: user_dependency,
    db: db_dependency
):
    """Mark a specific week as complete for the student"""
    permissions = get_user_permissions(current_user, db)
    
    if not permissions["student_id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only students can mark weeks as complete"
        )
    
    # Verify syllabus access
    syllabus = db.query(Syllabus).join(Subject).join(subject_students).filter(
        Syllabus.id == syllabus_id,
        subject_students.c.student_id == permissions["student_id"],
        Syllabus.is_active == True
    ).first()
    
    if not syllabus:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Syllabus not found or access denied"
        )
    
    # Validate week number
    if week_number < 1 or week_number > syllabus.term_length_weeks:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid week number. Must be between 1 and {syllabus.term_length_weeks}"
        )
    
    # Get or create progress record
    progress = db.query(StudentSyllabusProgress).filter(
        StudentSyllabusProgress.student_id == permissions["student_id"],
        StudentSyllabusProgress.syllabus_id == syllabus_id
    ).first()
    
    if not progress:
        progress = StudentSyllabusProgress(
            student_id=permissions["student_id"],
            syllabus_id=syllabus_id,
            current_week=1,
            completed_weeks=json.dumps([]),
            progress_percentage=0
        )
        db.add(progress)
    
    # Parse current completed weeks
    completed_weeks = serialize_json_field(progress.completed_weeks)
    
    # Add week if not already completed
    if week_number not in completed_weeks:
        completed_weeks.append(week_number)
        completed_weeks.sort()  # Keep sorted
        
        # Update progress
        progress.completed_weeks = json.dumps(completed_weeks)
        progress.current_week = max(progress.current_week, week_number)
        
        # Calculate progress percentage
        total_weeks = syllabus.term_length_weeks
        completed_count = len(completed_weeks)
        progress.progress_percentage = min(100, (completed_count * 100) // total_weeks)
        
        progress.updated_date = datetime.utcnow()
        progress.last_accessed = datetime.utcnow()
        
        db.commit()
        db.refresh(progress)
        
        return {
            "success": True,
            "message": f"Week {week_number} marked as complete",
            "syllabus_id": syllabus_id,
            "week_number": week_number,
            "completed_weeks": completed_weeks,
            "progress_percentage": progress.progress_percentage,
            "total_weeks": total_weeks
        }
    else:
        return {
            "success": True,
            "message": f"Week {week_number} was already completed",
            "syllabus_id": syllabus_id,
            "week_number": week_number,
            "completed_weeks": completed_weeks,
            "progress_percentage": progress.progress_percentage,
            "total_weeks": syllabus.term_length_weeks
        }

@router.delete("/student/syllabuses/{syllabus_id}/weeks/{week_number}/complete")
async def unmark_week_complete(
    syllabus_id: int,
    week_number: int,
    current_user: user_dependency,
    db: db_dependency
):
    """Unmark a specific week as complete for the student"""
    permissions = get_user_permissions(current_user, db)
    
    if not permissions["student_id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only students can unmark weeks"
        )
    
    # Get progress record
    progress = db.query(StudentSyllabusProgress).filter(
        StudentSyllabusProgress.student_id == permissions["student_id"],
        StudentSyllabusProgress.syllabus_id == syllabus_id
    ).first()
    
    if not progress:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No progress record found"
        )
    
    # Parse current completed weeks
    completed_weeks = serialize_json_field(progress.completed_weeks)
    
    # Remove week if completed
    if week_number in completed_weeks:
        completed_weeks.remove(week_number)
        
        # Update progress
        progress.completed_weeks = json.dumps(completed_weeks)
        
        # Calculate new progress percentage
        syllabus = db.query(Syllabus).filter(Syllabus.id == syllabus_id).first()
        total_weeks = syllabus.term_length_weeks
        completed_count = len(completed_weeks)
        progress.progress_percentage = min(100, (completed_count * 100) // total_weeks)
        
        progress.updated_date = datetime.utcnow()
        
        db.commit()
        db.refresh(progress)
        
        return {
            "success": True,
            "message": f"Week {week_number} unmarked as complete",
            "syllabus_id": syllabus_id,
            "week_number": week_number,
            "completed_weeks": completed_weeks,
            "progress_percentage": progress.progress_percentage,
            "total_weeks": total_weeks
        }
    else:
        return {
            "success": True,
            "message": f"Week {week_number} was not completed",
            "syllabus_id": syllabus_id,
            "week_number": week_number,
            "completed_weeks": completed_weeks,
            "progress_percentage": progress.progress_percentage,
            "total_weeks": syllabus.term_length_weeks
        }
