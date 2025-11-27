from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, Depends, status
from typing import Annotated, List
import random
import string
from sqlalchemy.orm import Session
from sqlalchemy import func

from db.connection import db_dependency
from models.study_area_models import (
    Role, School, Classroom, AccessCode, AccessCodeType, Student, Teacher,
    SchoolRequest, SchoolRequestStatus, UserRole, Subject, Assignment, Grade
)
from models.users_models import User
from schemas.roles_schemas import RoleCreate, RoleOut
from schemas.schools_schemas import SchoolCreate, SchoolOut, SchoolWithStats
from schemas.school_requests_schemas import (
    SchoolRequestCreate, SchoolRequestOut, SchoolRequestUpdate, 
    SchoolRequestWithPrincipal
)
from schemas.classrooms_schemas import ClassroomCreate, ClassroomOut
from schemas.access_codes_schemas import (
    AccessCodeCreate, AccessCodeOut, JoinSchoolRequest,
    AccessCodeType as AccessCodeTypeSchema
)
from schemas.students_schemas import StudentCreate, StudentOut
from schemas.teachers_schemas import TeacherCreate, TeacherOut
from schemas.subjects_schemas import (
    SubjectCreate, SubjectOut, SubjectWithDetails, SubjectWithMembers,
    SubjectTeacherAssignment, SubjectStudentAssignment, TeacherInfo, StudentInfo
)
from schemas.assignments_schemas import (
    AssignmentCreate, AssignmentUpdate, AssignmentResponse, AssignmentWithGrades,
    GradeCreate, GradeUpdate, GradeResponse, StudentGradeReport, SubjectGradesSummary,
    BulkGradeCreate, BulkGradeResponse
)
from Endpoints.auth import get_current_user
from schemas.direct_join_schemas import (
    DirectSchoolJoinRequest, SchoolSelectionResponse, JoinRequestResponse
)

router = APIRouter(tags=["Study Area", "Schools", "Subjects", "Roles"])

user_dependency = Annotated[dict, Depends(get_current_user)]

def generate_random_code(length=8):
    """Generate a unique random access code"""
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

def assign_role_to_user_by_email(db: Session, email: str, role: UserRole) -> bool:
    """
    Assign a role to a user by email if they exist in the system
    Returns True if role was assigned, False if user doesn't exist
    """
    try:
        user = db.query(User).filter(User.email == email.lower()).first()
        if user:
            target_role = db.query(Role).filter(Role.name == role).first()
            if target_role and not user.has_role(role):
                user.add_role(target_role)
                print(f"✅ Automatically assigned {role.value} role to user {user.username} ({email})")
                return True
            elif user.has_role(role):
                print(f"ℹ️  User {user.username} ({email}) already has {role.value} role")
                return True
        else:
            print(f"ℹ️  User with email {email} not found in system - role will be assigned when they join")
        return False
    except Exception as e:
        print(f"❌ Error assigning role to {email}: {str(e)}")
        return False

# Utility functions for role checking
def _get_user_roles(db: Session, user_id: int) -> List[UserRole]:
    """Get all user roles, return [normal_user] if no roles assigned"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user or not user.roles:
        return [UserRole.normal_user]
    return [role.name for role in user.roles]

def check_user_role(db: Session, user_id: int, required_role: UserRole) -> bool:
    """Check if user has required role"""
    user_roles = _get_user_roles(db, user_id)
    return required_role in user_roles

def ensure_user_role(db: Session, user_id: int, required_role: UserRole):
    """Raise HTTPException if user doesn't have required role"""
    if not check_user_role(db, user_id, required_role):
        raise HTTPException(
            status_code=403, 
            detail=f"Only users with {required_role.value} role can access this endpoint"
        )

def check_user_has_any_role(db: Session, user_id: int, required_roles: List[UserRole]) -> bool:
    """Check if user has any of the required roles"""
    user_roles = _get_user_roles(db, user_id)
    return any(role in user_roles for role in required_roles)

def ensure_user_has_any_role(db: Session, user_id: int, required_roles: List[UserRole]):
    """Raise HTTPException if user doesn't have any of the required roles"""
    if not check_user_has_any_role(db, user_id, required_roles):
        role_names = [role.value for role in required_roles]
        raise HTTPException(
            status_code=403, 
            detail=f"Only users with one of these roles can access this endpoint: {', '.join(role_names)}"
        )

# === SCHOOL REQUEST ENDPOINTS ===

@router.post("/school-requests/create", response_model=SchoolRequestOut)
async def create_school_request(
    db: db_dependency, 
    current_user: user_dependency, 
    school_request: SchoolRequestCreate
):
    """
    Create a school registration request (any authenticated user can request to become a principal)
    """
    # Any authenticated user can create a school request - they don't need principal role yet
    
    # Check if principal already has a pending or approved request
    existing_request = db.query(SchoolRequest).filter(
        SchoolRequest.principal_id == current_user["user_id"],
        SchoolRequest.status.in_([SchoolRequestStatus.pending, SchoolRequestStatus.approved])
    ).first()
    
    if existing_request:
        raise HTTPException(
            status_code=400, 
            detail="You already have a pending or approved school request"
        )
    
    # Check if school name already exists
    if db.query(School).filter(School.name == school_request.school_name).first():
        raise HTTPException(
            status_code=400, 
            detail="School with this name already exists"
        )
    
    try:
        db_request = SchoolRequest(
            school_name=school_request.school_name,
            school_address=school_request.school_address,
            principal_id=current_user["user_id"]
        )
        db.add(db_request)
        db.commit()
        db.refresh(db_request)
        return db_request
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"School request creation error: {str(e)}")

@router.get("/school-requests/pending", response_model=List[SchoolRequestWithPrincipal])
async def get_pending_school_requests(db: db_dependency, current_user: user_dependency):
    """
    Get all pending school requests (admins only)
    """
    ensure_user_role(db, current_user["user_id"], UserRole.admin)
    
    requests = db.query(SchoolRequest).filter(
        SchoolRequest.status == SchoolRequestStatus.pending
    ).join(User, SchoolRequest.principal_id == User.id).all()
    
    result = []
    for request in requests:
        result.append(SchoolRequestWithPrincipal(
            **request.__dict__,
            principal_name=f"{request.principal.fname} {request.principal.lname}",
            principal_email=request.principal.email
        ))
    
    return result

@router.put("/school-requests/{request_id}/review", response_model=SchoolRequestOut)
async def review_school_request(
    request_id: int,
    db: db_dependency, 
    current_user: user_dependency,
    review: SchoolRequestUpdate
):
    """
    Approve or reject a school request (admins only)
    """
    ensure_user_role(db, current_user["user_id"], UserRole.admin)
    
    request = db.query(SchoolRequest).filter(SchoolRequest.id == request_id).first()
    if not request:
        raise HTTPException(status_code=404, detail="School request not found")
    
    if request.status != SchoolRequestStatus.pending:
        raise HTTPException(status_code=400, detail="Request has already been reviewed")
    
    try:
        request.status = review.status
        request.admin_notes = review.admin_notes
        request.reviewed_by = current_user["user_id"]
        request.reviewed_date = datetime.utcnow()
        
        # If approved, create the school and assign principal role
        if review.status == SchoolRequestStatus.approved:
            # Create the school
            school = School(
                name=request.school_name,
                address=request.school_address,
                principal_id=request.principal_id
            )
            db.add(school)
            
            # Automatically assign principal role to the user
            principal_user = db.query(User).filter(User.id == request.principal_id).first()
            if principal_user:
                principal_role = db.query(Role).filter(Role.name == UserRole.principal).first()
                if principal_role and not principal_user.has_role(UserRole.principal):
                    principal_user.add_role(principal_role)
                    print(f"✅ Automatically assigned principal role to user {principal_user.username}")
        
        db.commit()
        db.refresh(request)
        return request
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Request review error: {str(e)}")

# === SCHOOL ENDPOINTS ===

@router.get("/schools/my-school", response_model=SchoolWithStats)
async def get_my_school(db: db_dependency, current_user: user_dependency):
    """
    Get school managed by current principal with statistics
    """
    ensure_user_role(db, current_user["user_id"], UserRole.principal)
    
    school = db.query(School).filter(School.principal_id == current_user["user_id"]).first()
    if not school:
        raise HTTPException(status_code=404, detail="No school found for this principal")
    
    # Get statistics
    total_students = db.query(Student).filter(Student.school_id == school.id).count()
    total_teachers = db.query(Teacher).filter(Teacher.school_id == school.id).count()
    total_classrooms = db.query(Classroom).filter(Classroom.school_id == school.id).count()
    active_access_codes = db.query(AccessCode).filter(
        AccessCode.school_id == school.id,
        AccessCode.is_active == True
    ).count()
    
    return SchoolWithStats(
        **school.__dict__,
        total_students=total_students,
        total_teachers=total_teachers,
        total_classrooms=total_classrooms,
        active_access_codes=active_access_codes
    )

@router.get("/schools", response_model=List[SchoolOut])
async def get_all_schools(db: db_dependency, current_user: user_dependency):
    """
    Get all schools (admins only)
    """
    ensure_user_role(db, current_user["user_id"], UserRole.admin)
    
    schools = db.query(School).filter(School.is_active == True).all()
    return schools

# === ACCESS CODE ENDPOINTS ===

@router.post("/access-codes/generate", response_model=AccessCodeOut)
async def generate_access_code(
    db: db_dependency, 
    current_user: user_dependency, 
    access_code: AccessCodeCreate
):
    """
    Generate unique access code for a specific student or teacher email (principals only)
    """
    ensure_user_role(db, current_user["user_id"], UserRole.principal)
    
    # Check if principal owns the school
    school = db.query(School).filter(
        School.id == access_code.school_id,
        School.principal_id == current_user["user_id"]
    ).first()
    if not school:
        raise HTTPException(status_code=404, detail="School not found or not managed by you")
    
    # Convert schema AccessCodeType to model AccessCodeType for database queries
    from models.study_area_models import AccessCodeType as ModelAccessCodeType
    from schemas.access_codes_schemas import AccessCodeType as SchemaAccessCodeType
    
    # Handle both string and enum values for code_type
    code_type_str = str(access_code.code_type.value) if hasattr(access_code.code_type, 'value') else str(access_code.code_type)
    
    if code_type_str == "student":
        model_code_type = ModelAccessCodeType.student
    elif code_type_str == "teacher":
        model_code_type = ModelAccessCodeType.teacher
    else:
        raise HTTPException(status_code=400, detail=f"Invalid access code type: {code_type_str}. Must be 'student' or 'teacher'")

    # Check if access code for this email and type already exists in this school
    existing_code = db.query(AccessCode).filter(
        AccessCode.school_id == access_code.school_id,
        AccessCode.email == access_code.email.lower(),
        AccessCode.code_type == model_code_type
    ).first()
    
    if existing_code:
        if existing_code.is_active:
            raise HTTPException(
                status_code=400, 
                detail=f"Active access code for {access_code.email} as {access_code.code_type.value} already exists"
            )
        else:
            # Reactivate existing code and assign role if user exists
            existing_code.is_active = True
            
            # Automatically assign role to user if they exist based on access code type
            # Use the converted code_type_str for consistent handling
            if code_type_str == "student":
                target_role = UserRole.student
                print(f"🎓 Assigning STUDENT role for access code: {access_code.email}")
            elif code_type_str == "teacher":
                target_role = UserRole.teacher
                print(f"👨‍🏫 Assigning TEACHER role for access code: {access_code.email}")
            else:
                print(f"❌ Received code_type: {code_type_str} (original: {access_code.code_type})")
                raise HTTPException(status_code=400, detail=f"Invalid access code type: {code_type_str}. Must be 'student' or 'teacher'")
            
            assign_role_to_user_by_email(db, access_code.email, target_role)
            
            db.commit()
            db.refresh(existing_code)
            return existing_code
    
    # Generate unique code
    code = generate_random_code()
    while db.query(AccessCode).filter(AccessCode.code == code).first():
        code = generate_random_code(10)
    
    try:
        db_code = AccessCode(
            code=code,
            code_type=model_code_type,
            school_id=access_code.school_id,
            email=access_code.email.lower()
        )
        db.add(db_code)
        
        # Automatically assign role to user if they exist based on access code type
        # Use the converted code_type_str for consistent handling
        if code_type_str == "student":
            target_role = UserRole.student
            print(f"🎓 Generating STUDENT access code for: {access_code.email}")
        elif code_type_str == "teacher":
            target_role = UserRole.teacher
            print(f"👨‍🏫 Generating TEACHER access code for: {access_code.email}")
        else:
            print(f"❌ Received code_type: {code_type_str} (original: {access_code.code_type})")
            raise HTTPException(status_code=400, detail=f"Invalid access code type: {code_type_str}. Must be 'student' or 'teacher'")
        
        assign_role_to_user_by_email(db, access_code.email, target_role)
        
        db.commit()
        db.refresh(db_code)
        return db_code
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Access code generation error: {str(e)}")

@router.get("/access-codes/my-school", response_model=List[AccessCodeOut])
async def get_school_access_codes(db: db_dependency, current_user: user_dependency):
    """
    Get all access codes for principal's school
    """
    ensure_user_role(db, current_user["user_id"], UserRole.principal)
    
    school = db.query(School).filter(School.principal_id == current_user["user_id"]).first()
    if not school:
        raise HTTPException(status_code=404, detail="No school found for this principal")
    
    access_codes = db.query(AccessCode).filter(AccessCode.school_id == school.id).all()
    return access_codes

@router.get("/access-codes/by-email/{email}", response_model=List[AccessCodeOut])
async def get_access_codes_by_email(
    email: str,
    db: db_dependency, 
    current_user: user_dependency
):
    """
    Get access codes for a specific email in principal's school
    """
    ensure_user_role(db, current_user["user_id"], UserRole.principal)
    
    school = db.query(School).filter(School.principal_id == current_user["user_id"]).first()
    if not school:
        raise HTTPException(status_code=404, detail="No school found for this principal")
    
    access_codes = db.query(AccessCode).filter(
        AccessCode.school_id == school.id,
        AccessCode.email == email.lower()
    ).all()
    
    return access_codes

@router.delete("/access-codes/{code_id}")
async def deactivate_access_code(
    code_id: int,
    db: db_dependency, 
    current_user: user_dependency
):
    """
    Deactivate an access code (principals only)
    """
    ensure_user_role(db, current_user["user_id"], UserRole.principal)
    
    # Check if code belongs to principal's school
    code = db.query(AccessCode).join(School).filter(
        AccessCode.id == code_id,
        School.principal_id == current_user["user_id"]
    ).first()
    
    if not code:
        raise HTTPException(status_code=404, detail="Access code not found")
    
    try:
        code.is_active = False
        db.commit()
        return {"message": "Access code deactivated successfully"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Deactivation error: {str(e)}")

@router.put("/access-codes/{code_id}/reactivate", response_model=AccessCodeOut)
async def reactivate_access_code(
    code_id: int,
    db: db_dependency, 
    current_user: user_dependency
):
    """
    Reactivate a deactivated access code (principals only)
    """
    ensure_user_role(db, current_user["user_id"], UserRole.principal)
    
    # Check if code belongs to principal's school
    code = db.query(AccessCode).join(School).filter(
        AccessCode.id == code_id,
        School.principal_id == current_user["user_id"]
    ).first()
    
    if not code:
        raise HTTPException(status_code=404, detail="Access code not found")
    
    if code.is_active:
        raise HTTPException(status_code=400, detail="Access code is already active")
    
    try:
        code.is_active = True
        db.commit()
        db.refresh(code)
        return code
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Reactivation error: {str(e)}")

# === JOIN SCHOOL ENDPOINTS ===

@router.post("/join-school/student", response_model=StudentOut)
async def join_school_as_student(
    db: db_dependency,
    current_user: user_dependency,
    join_request: JoinSchoolRequest
):
    """
    Join a school as a student using access code (code remains active for reuse)
    """
    # Verify user exists and email matches
    user = db.query(User).filter(
        User.id == current_user["user_id"],
        User.email == join_request.email
    ).first()
    
    if not user:
        raise HTTPException(status_code=400, detail="User not found or email mismatch")
    
    # Find school by name
    school = db.query(School).filter(School.name == join_request.school_name).first()
    if not school:
        raise HTTPException(status_code=404, detail="School not found")
    
    # Verify access code - must match email, school, and be for students
    print(f"🔍 Looking for access code:")
    print(f"   Code: {join_request.access_code}")
    print(f"   School ID: {school.id}")
    print(f"   Email: {join_request.email.lower()}")
    print(f"   Looking for code_type: {AccessCodeType.student}")
    
    access_code = db.query(AccessCode).filter(
        AccessCode.code == join_request.access_code,
        AccessCode.school_id == school.id,
        AccessCode.code_type == AccessCodeType.student,
        AccessCode.email == join_request.email.lower(),
        AccessCode.is_active == True
    ).first()
    
    # Debug: Let's see what access codes exist for this email
    all_codes_for_email = db.query(AccessCode).filter(
        AccessCode.email == join_request.email.lower(),
        AccessCode.school_id == school.id
    ).all()
    
    print(f"🔍 Found {len(all_codes_for_email)} access code(s) for this email:")
    for code in all_codes_for_email:
        print(f"   Code: {code.code}, Type: {code.code_type}, Active: {code.is_active}")
    
    if not access_code:
        raise HTTPException(
            status_code=400, 
            detail="Invalid access code or code not assigned to your email"
        )
    
    # Check if user is already a student in this school
    existing_student = db.query(Student).filter(
        Student.user_id == user.id,
        Student.school_id == school.id
    ).first()
    
    if existing_student:
        raise HTTPException(status_code=400, detail="User is already a student in this school")
    
    try:
        # Ensure user has student role (assign if not already assigned)
        student_role = db.query(Role).filter(Role.name == UserRole.student).first()
        if student_role and not user.has_role(UserRole.student):
            user.add_role(student_role)
            print(f"✅ Assigned student role to user {user.username}")
        
        # Create student record
        student = Student(
            user_id=user.id,
            school_id=school.id
        )
        db.add(student)
        
        # Keep the access code active for future use
        # access_code remains active and can be used again
        
        db.commit()
        db.refresh(student)
        return student
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Student registration error: {str(e)}")

@router.post("/join-school/teacher", response_model=TeacherOut)
async def join_school_as_teacher(
    db: db_dependency,
    current_user: user_dependency,
    join_request: JoinSchoolRequest
):
    """
    Join a school as a teacher using access code (code remains active for reuse)
    """
    # Verify user exists and email matches
    user = db.query(User).filter(
        User.id == current_user["user_id"],
        User.email == join_request.email
    ).first()
    
    if not user:
        raise HTTPException(status_code=400, detail="User not found or email mismatch")
    
    # Find school by name
    school = db.query(School).filter(School.name == join_request.school_name).first()
    if not school:
        raise HTTPException(status_code=404, detail="School not found")
    
    # Verify access code - must match email, school, and be for teachers
    print(f"🔍 Looking for teacher access code:")
    print(f"   Code: {join_request.access_code}")
    print(f"   School ID: {school.id}")
    print(f"   Email: {join_request.email.lower()}")
    print(f"   Looking for code_type: {AccessCodeType.teacher}")
    
    access_code = db.query(AccessCode).filter(
        AccessCode.code == join_request.access_code,
        AccessCode.school_id == school.id,
        AccessCode.code_type == AccessCodeType.teacher,
        AccessCode.email == join_request.email.lower(),
        AccessCode.is_active == True
    ).first()
    
    # Debug: Let's see what access codes exist for this email
    all_codes_for_email = db.query(AccessCode).filter(
        AccessCode.email == join_request.email.lower(),
        AccessCode.school_id == school.id
    ).all()
    
    print(f"🔍 Found {len(all_codes_for_email)} access code(s) for this email:")
    for code in all_codes_for_email:
        print(f"   Code: {code.code}, Type: {code.code_type}, Active: {code.is_active}")
    
    if not access_code:
        raise HTTPException(
            status_code=400, 
            detail="Invalid access code or code not assigned to your email"
        )
    
    # Check if user is already a teacher in this school
    existing_teacher = db.query(Teacher).filter(
        Teacher.user_id == user.id,
        Teacher.school_id == school.id
    ).first()
    
    if existing_teacher:
        raise HTTPException(status_code=400, detail="User is already a teacher in this school")
    
    try:
        # Ensure user has teacher role (assign if not already assigned)
        teacher_role = db.query(Role).filter(Role.name == UserRole.teacher).first()
        if teacher_role and not user.has_role(UserRole.teacher):
            user.add_role(teacher_role)
            print(f"✅ Assigned teacher role to user {user.username}")
        
        # Create teacher record
        teacher = Teacher(
            user_id=user.id,
            school_id=school.id
        )
        db.add(teacher)
        
        # Keep the access code active for future use
        # access_code remains active and can be used again
        
        db.commit()
        db.refresh(teacher)
        return teacher
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Teacher registration error: {str(e)}")

# === CLASSROOM ENDPOINTS ===

@router.post("/classrooms/create", response_model=ClassroomOut)
async def create_classroom(
    db: db_dependency, 
    current_user: user_dependency, 
    classroom: ClassroomCreate
):
    """
    Create a new classroom (principals only)
    """
    ensure_user_role(db, current_user["user_id"], UserRole.principal)
    
    # Check if principal owns the school
    school = db.query(School).filter(
        School.id == classroom.school_id,
        School.principal_id == current_user["user_id"]
    ).first()
    if not school:
        raise HTTPException(status_code=404, detail="School not found or not managed by you")
    
    # Check if classroom name already exists in school
    existing_classroom = db.query(Classroom).filter(
        Classroom.name == classroom.name,
        Classroom.school_id == classroom.school_id
    ).first()
    if existing_classroom:
        raise HTTPException(
            status_code=400, 
            detail="Classroom with this name already exists in this school"
        )
    
    try:
        db_classroom = Classroom(
            name=classroom.name,
            school_id=classroom.school_id
        )
        db.add(db_classroom)
        db.commit()
        db.refresh(db_classroom)
        return db_classroom
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Classroom creation error: {str(e)}")

@router.get("/classrooms/my-school", response_model=List[ClassroomOut])
async def get_school_classrooms(db: db_dependency, current_user: user_dependency):
    """
    Get all classrooms for principal's school
    """
    ensure_user_role(db, current_user["user_id"], UserRole.principal)
    
    school = db.query(School).filter(School.principal_id == current_user["user_id"]).first()
    if not school:
        raise HTTPException(status_code=404, detail="No school found for this principal")
    
    classrooms = db.query(Classroom).filter(
        Classroom.school_id == school.id,
        Classroom.is_active == True
    ).all()
    return classrooms

# === ANALYTICS ENDPOINTS ===

@router.get("/analytics/school-overview")
async def get_school_analytics(db: db_dependency, current_user: user_dependency):
    """
    Get comprehensive school analytics for principals
    """
    ensure_user_role(db, current_user["user_id"], UserRole.principal)
    
    school = db.query(School).filter(School.principal_id == current_user["user_id"]).first()
    if not school:
        raise HTTPException(status_code=404, detail="No school found for this principal")
    
    # Get detailed analytics
    total_students = db.query(Student).filter(
        Student.school_id == school.id,
        Student.is_active == True
    ).count()
    
    total_teachers = db.query(Teacher).filter(
        Teacher.school_id == school.id,
        Teacher.is_active == True
    ).count()
    
    total_classrooms = db.query(Classroom).filter(
        Classroom.school_id == school.id,
        Classroom.is_active == True
    ).count()
    
    total_subjects = db.query(Subject).filter(
        Subject.school_id == school.id,
        Subject.is_active == True
    ).count()
    
    active_student_codes = db.query(AccessCode).filter(
        AccessCode.school_id == school.id,
        AccessCode.code_type == AccessCodeType.student,
        AccessCode.is_active == True
    ).count()
    
    active_teacher_codes = db.query(AccessCode).filter(
        AccessCode.school_id == school.id,
        AccessCode.code_type == AccessCodeType.teacher,
        AccessCode.is_active == True
    ).count()
    
    # Recent enrollments (last 30 days)
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    recent_student_enrollments = db.query(Student).filter(
        Student.school_id == school.id,
        Student.enrollment_date >= thirty_days_ago
    ).count()
    
    recent_teacher_enrollments = db.query(Teacher).filter(
        Teacher.school_id == school.id,
        Teacher.hire_date >= thirty_days_ago
    ).count()
    
    return {
        "school_info": {
            "id": school.id,
            "name": school.name,
            "address": school.address,
            "created_date": school.created_date
        },
        "totals": {
            "students": total_students,
            "teachers": total_teachers,
            "classrooms": total_classrooms,
            "subjects": total_subjects
        },
        "access_codes": {
            "active_student_codes": active_student_codes,
            "active_teacher_codes": active_teacher_codes
        },
        "recent_activity": {
            "new_students_30_days": recent_student_enrollments,
            "new_teachers_30_days": recent_teacher_enrollments
        }
    }

# === ROLE MANAGEMENT ENDPOINTS ===

@router.post("/roles/assign")
async def assign_role_to_user(
    user_id: int,
    role_name: UserRole,
    db: db_dependency,
    current_user: user_dependency
):
    """
    Assign a role to a user (admins only) - adds to existing roles
    """
    # Check if current user is admin
    ensure_user_role(db, current_user["user_id"], UserRole.admin)
    
    # Find target user
    target_user = db.query(User).filter(User.id == user_id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Find role
    role = db.query(Role).filter(Role.name == role_name).first()
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    
    # Check if user already has this role
    if target_user.has_role(role_name):
        return {"message": f"User {target_user.username} already has role {role_name.value}"}
    
    try:
        target_user.add_role(role)
        db.commit()
        return {"message": f"Role {role_name.value} assigned to user {target_user.username} successfully"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Role assignment error: {str(e)}")

@router.delete("/roles/remove")
async def remove_role_from_user(
    user_id: int,
    role_name: UserRole,
    db: db_dependency,
    current_user: user_dependency
):
    """
    Remove a role from a user (admins only)
    """
    # Check if current user is admin
    ensure_user_role(db, current_user["user_id"], UserRole.admin)
    
    # Find target user
    target_user = db.query(User).filter(User.id == user_id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Find role
    role = db.query(Role).filter(Role.name == role_name).first()
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    
    # Check if user has this role
    if not target_user.has_role(role_name):
        return {"message": f"User {target_user.username} doesn't have role {role_name.value}"}
    
    try:
        target_user.remove_role(role)
        db.commit()
        return {"message": f"Role {role_name.value} removed from user {target_user.username} successfully"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Role removal error: {str(e)}")

@router.get("/users/{user_id}/roles")
async def get_user_roles(
    user_id: int,
    db: db_dependency,
    current_user: user_dependency
):
    """
    Get all roles for a specific user (admins only)
    """
    ensure_user_role(db, current_user["user_id"], UserRole.admin)
    
    target_user = db.query(User).filter(User.id == user_id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return {
        "user_id": user_id,
        "username": target_user.username,
        "roles": target_user.get_role_names()
    }

@router.get("/roles/all", response_model=List[RoleOut])
async def get_all_roles(db: db_dependency, current_user: user_dependency):
    """
    Get all available roles (admins only)
    """
    ensure_user_role(db, current_user["user_id"], UserRole.admin)
    
    roles = db.query(Role).all()
    return roles

@router.get("/users/by-role/{role_name}")
async def get_users_by_role(
    role_name: UserRole,
    db: db_dependency,
    current_user: user_dependency
):
    """
    Get all users with a specific role (admins only)
    """
    ensure_user_role(db, current_user["user_id"], UserRole.admin)
    
    # Query users who have the specific role through the many-to-many relationship
    role = db.query(Role).filter(Role.name == role_name).first()
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    
    users = role.users  # Get users through the relationship
    
    result = []
    for user in users:
        result.append({
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "fname": user.fname,
            "lname": user.lname,
            "roles": user.get_role_names(),
            "created_at": user.created_at,
            "is_active": user.is_active
        })
    
    return result

# === SUBJECT ENDPOINTS ===

@router.post("/subjects/create", response_model=SubjectOut)
async def create_subject(
    db: db_dependency, 
    current_user: user_dependency, 
    subject: SubjectCreate
):
    """
    Create a new subject (principals only)
    """
    ensure_user_role(db, current_user["user_id"], UserRole.principal)
    
    # Check if principal owns the school
    school = db.query(School).filter(
        School.id == subject.school_id,
        School.principal_id == current_user["user_id"]
    ).first()
    if not school:
        raise HTTPException(status_code=404, detail="School not found or not managed by you")
    
    # Check if subject name already exists in school
    existing_subject = db.query(Subject).filter(
        Subject.name == subject.name,
        Subject.school_id == subject.school_id
    ).first()
    if existing_subject:
        raise HTTPException(
            status_code=400, 
            detail="Subject with this name already exists in this school"
        )
    
    try:
        db_subject = Subject(
            name=subject.name,
            description=subject.description,
            school_id=subject.school_id,
            created_by=current_user["user_id"]
        )
        db.add(db_subject)
        db.commit()
        db.refresh(db_subject)
        return db_subject
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Subject creation error: {str(e)}")

@router.get("/subjects/my-school", response_model=List[SubjectWithDetails])
async def get_school_subjects(db: db_dependency, current_user: user_dependency):
    """
    Get all subjects for principal's school with teacher and student counts
    """
    ensure_user_role(db, current_user["user_id"], UserRole.principal)
    
    school = db.query(School).filter(School.principal_id == current_user["user_id"]).first()
    if not school:
        raise HTTPException(status_code=404, detail="No school found for this principal")
    
    subjects = db.query(Subject).filter(
        Subject.school_id == school.id,
        Subject.is_active == True
    ).all()
    
    result = []
    for subject in subjects:
        teacher_count = len(subject.teachers)
        student_count = len(subject.students)
        
        result.append(SubjectWithDetails(
            id=subject.id,
            name=subject.name,
            description=subject.description,
            school_id=subject.school_id,
            created_by=subject.created_by,
            created_date=subject.created_date,
            is_active=subject.is_active,
            teacher_count=teacher_count,
            student_count=student_count
        ))
    
    return result

@router.get("/subjects/{subject_id}", response_model=SubjectWithMembers)
async def get_subject_details(
    subject_id: int,
    db: db_dependency, 
    current_user: user_dependency
):
    """
    Get subject details with teachers and students (principals and teachers)
    """
    ensure_user_has_any_role(
        db, 
        current_user["user_id"], 
        [UserRole.principal, UserRole.teacher]
    )
    
    subject = db.query(Subject).filter(Subject.id == subject_id).first()
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found")
    
    # Check access permissions
    user_roles = _get_user_roles(db, current_user["user_id"])
    
    if UserRole.principal in user_roles:
        # Principal can access subjects in their school
        school = db.query(School).filter(
            School.id == subject.school_id,
            School.principal_id == current_user["user_id"]
        ).first()
        if not school:
            raise HTTPException(status_code=403, detail="Access denied")
    
    elif UserRole.teacher in user_roles:
        # Teacher can access subjects they are assigned to
        teacher = db.query(Teacher).filter(Teacher.user_id == current_user["user_id"]).first()
        if not teacher or subject not in teacher.subjects:
            raise HTTPException(status_code=403, detail="Access denied")
    
    # Build teacher info
    teachers_info = []
    for teacher in subject.teachers:
        teachers_info.append(TeacherInfo(
            id=teacher.id,
            user_id=teacher.user_id,
            name=f"{teacher.user.fname} {teacher.user.lname}",
            email=teacher.user.email
        ))
    
    # Build student info
    students_info = []
    for student in subject.students:
        students_info.append(StudentInfo(
            id=student.id,
            user_id=student.user_id,
            name=f"{student.user.fname} {student.user.lname}",
            email=student.user.email
        ))
    
    return SubjectWithMembers(
        id=subject.id,
        name=subject.name,
        description=subject.description,
        school_id=subject.school_id,
        created_by=subject.created_by,
        created_date=subject.created_date,
        is_active=subject.is_active,
        teachers=teachers_info,
        students=students_info
    )

@router.post("/subjects/assign-teacher")
async def assign_teacher_to_subject(
    assignment: SubjectTeacherAssignment,
    db: db_dependency,
    current_user: user_dependency
):
    """
    Assign a teacher to a subject (principals only)
    """
    ensure_user_role(db, current_user["user_id"], UserRole.principal)
    
    # Get subject and verify principal owns the school
    subject = db.query(Subject).join(School).filter(
        Subject.id == assignment.subject_id,
        School.principal_id == current_user["user_id"]
    ).first()
    
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found or access denied")
    
    # Get teacher and verify they belong to the same school
    teacher = db.query(Teacher).filter(
        Teacher.id == assignment.teacher_id,
        Teacher.school_id == subject.school_id
    ).first()
    
    if not teacher:
        raise HTTPException(status_code=404, detail="Teacher not found in this school")
    
    # Check if teacher is already assigned to this subject
    if subject in teacher.subjects:
        raise HTTPException(status_code=400, detail="Teacher is already assigned to this subject")
    
    try:
        # Add teacher to subject
        teacher.subjects.append(subject)
        db.commit()
        return {"message": f"Teacher {teacher.user.fname} {teacher.user.lname} assigned to {subject.name}"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Assignment error: {str(e)}")

@router.delete("/subjects/remove-teacher")
async def remove_teacher_from_subject(
    assignment: SubjectTeacherAssignment,
    db: db_dependency,
    current_user: user_dependency
):
    """
    Remove a teacher from a subject (principals only)
    """
    ensure_user_role(db, current_user["user_id"], UserRole.principal)
    
    # Get subject and verify principal owns the school
    subject = db.query(Subject).join(School).filter(
        Subject.id == assignment.subject_id,
        School.principal_id == current_user["user_id"]
    ).first()
    
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found or access denied")
    
    # Get teacher
    teacher = db.query(Teacher).filter(Teacher.id == assignment.teacher_id).first()
    if not teacher:
        raise HTTPException(status_code=404, detail="Teacher not found")
    
    # Check if teacher is assigned to this subject
    if subject not in teacher.subjects:
        raise HTTPException(status_code=400, detail="Teacher is not assigned to this subject")
    
    try:
        # Remove teacher from subject
        teacher.subjects.remove(subject)
        db.commit()
        return {"message": f"Teacher {teacher.user.fname} {teacher.user.lname} removed from {subject.name}"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Removal error: {str(e)}")

@router.post("/subjects/add-student")
async def add_student_to_subject(
    assignment: SubjectStudentAssignment,
    db: db_dependency,
    current_user: user_dependency
):
    """
    Add a student to a subject (teachers assigned to the subject can do this)
    """
    ensure_user_role(db, current_user["user_id"], UserRole.teacher)
    
    # Get teacher and verify they are assigned to this subject
    teacher = db.query(Teacher).filter(Teacher.user_id == current_user["user_id"]).first()
    if not teacher:
        raise HTTPException(status_code=404, detail="Teacher profile not found")
    
    subject = db.query(Subject).filter(Subject.id == assignment.subject_id).first()
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found")
    
    if subject not in teacher.subjects:
        raise HTTPException(status_code=403, detail="You are not assigned to this subject")
    
    # Get student and verify they belong to the same school
    student = db.query(Student).filter(
        Student.id == assignment.student_id,
        Student.school_id == subject.school_id
    ).first()
    
    if not student:
        raise HTTPException(status_code=404, detail="Student not found in this school")
    
    # Check if student is already in this subject
    if subject in student.subjects:
        raise HTTPException(status_code=400, detail="Student is already enrolled in this subject")
    
    try:
        # Add student to subject
        student.subjects.append(subject)
        db.commit()
        return {"message": f"Student {student.user.fname} {student.user.lname} added to {subject.name}"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Enrollment error: {str(e)}")

@router.delete("/subjects/remove-student")
async def remove_student_from_subject(
    assignment: SubjectStudentAssignment,
    db: db_dependency,
    current_user: user_dependency
):
    """
    Remove a student from a subject (teachers assigned to the subject can do this)
    """
    ensure_user_role(db, current_user["user_id"], UserRole.teacher)
    
    # Get teacher and verify they are assigned to this subject
    teacher = db.query(Teacher).filter(Teacher.user_id == current_user["user_id"]).first()
    if not teacher:
        raise HTTPException(status_code=404, detail="Teacher profile not found")
    
    subject = db.query(Subject).filter(Subject.id == assignment.subject_id).first()
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found")
    
    if subject not in teacher.subjects:
        raise HTTPException(status_code=403, detail="You are not assigned to this subject")
    
    # Get student
    student = db.query(Student).filter(Student.id == assignment.student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    
    # Check if student is in this subject
    if subject not in student.subjects:
        raise HTTPException(status_code=400, detail="Student is not enrolled in this subject")
    
    try:
        # Remove student from subject
        student.subjects.remove(subject)
        db.commit()
        return {"message": f"Student {student.user.fname} {student.user.lname} removed from {subject.name}"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Removal error: {str(e)}")

@router.get("/teachers/my-subjects", response_model=List[SubjectWithDetails])
async def get_teacher_subjects(db: db_dependency, current_user: user_dependency):
    """
    Get subjects assigned to the current teacher
    """
    ensure_user_role(db, current_user["user_id"], UserRole.teacher)
    
    teacher = db.query(Teacher).filter(Teacher.user_id == current_user["user_id"]).first()
    if not teacher:
        raise HTTPException(status_code=404, detail="Teacher profile not found")
    
    result = []
    for subject in teacher.subjects:
        teacher_count = len(subject.teachers)
        student_count = len(subject.students)
        
        result.append(SubjectWithDetails(
            id=subject.id,
            name=subject.name,
            description=subject.description,
            school_id=subject.school_id,
            created_by=subject.created_by,
            created_date=subject.created_date,
            is_active=subject.is_active,
            teacher_count=teacher_count,
            student_count=student_count
        ))
    
    return result

@router.get("/students/my-subjects", response_model=List[SubjectOut])
async def get_student_subjects(db: db_dependency, current_user: user_dependency):
    """
    Get subjects the current student is enrolled in
    """
    ensure_user_role(db, current_user["user_id"], UserRole.student)
    
    student = db.query(Student).filter(Student.user_id == current_user["user_id"]).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student profile not found")
    
    return student.subjects

# === USER STATUS ENDPOINTS ===

@router.get("/user/status")
async def get_user_status(db: db_dependency, current_user: user_dependency):
    """
    Get current user's status, roles, and available actions
    """
    user = db.query(User).filter(User.id == current_user["user_id"]).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user_roles = _get_user_roles(db, current_user["user_id"])
    
    # Check for existing school request
    school_request = db.query(SchoolRequest).filter(
        SchoolRequest.principal_id == current_user["user_id"]
    ).order_by(SchoolRequest.created_date.desc()).first()
    
    # Check if user is a student or teacher in any school
    student_records = db.query(Student).filter(Student.user_id == current_user["user_id"]).all()
    teacher_records = db.query(Teacher).filter(Teacher.user_id == current_user["user_id"]).all()
    
    # Check if user manages any school
    managed_school = db.query(School).filter(School.principal_id == current_user["user_id"]).first()
    
    # Determine available actions
    available_actions = []
    
    # All users can create school requests if they don't have one pending/approved
    if not school_request or school_request.status == SchoolRequestStatus.rejected:
        available_actions.append({
            "action": "create_school_request",
            "description": "Request to become a principal and create a school",
            "endpoint": "/school-requests/create"
        })
    
    # Users can join schools as students or teachers if they have access codes
    if not student_records:
        available_actions.append({
            "action": "join_as_student",
            "description": "Join a school as a student using an access code",
            "endpoint": "/join-school/student"
        })
    
    if not teacher_records:
        available_actions.append({
            "action": "join_as_teacher", 
            "description": "Join a school as a teacher using an access code",
            "endpoint": "/join-school/teacher"
        })
        available_actions.append({
            "action": "request_teacher_direct",
            "description": "Request to join a school as a teacher by selecting from available schools",
            "endpoint": "/join-school/request-teacher"
        })
    
    # Users can request to become principal of existing schools without principals
    if not managed_school:
        available_actions.append({
            "action": "request_principal_direct",
            "description": "Request to become principal of an existing school",
            "endpoint": "/join-school/request-principal"
        })
    
    return {
        "user_info": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "full_name": f"{user.fname} {user.lname}",
            "roles": [role.value for role in user_roles]
        },
        "school_request_status": {
            "has_request": school_request is not None,
            "status": school_request.status.value if school_request else None,
            "school_name": school_request.school_name if school_request else None,
            "created_date": school_request.created_date if school_request else None,
            "admin_notes": school_request.admin_notes if school_request else None
        },
        "schools": {
            "as_principal": {
                "school_id": managed_school.id if managed_school else None,
                "school_name": managed_school.name if managed_school else None
            },
            "as_student": [
                {
                    "student_id": s.id,
                    "school_id": s.school_id,
                    "school_name": s.school.name,
                    "enrollment_date": s.enrollment_date
                } for s in student_records
            ],
            "as_teacher": [
                {
                    "teacher_id": t.id,
                    "school_id": t.school_id,
                    "school_name": t.school.name,
                    "hire_date": t.hire_date
                } for t in teacher_records
            ]
        },
        "available_actions": available_actions
    }

@router.get("/students/my-school", response_model=List[StudentOut])
async def get_school_students(db: db_dependency, current_user: user_dependency):
    """
    Get all students in principal's school
    """
    ensure_user_role(db, current_user["user_id"], UserRole.principal)
    
    school = db.query(School).filter(School.principal_id == current_user["user_id"]).first()
    if not school:
        raise HTTPException(status_code=404, detail="No school found for this principal")
    
    students = db.query(Student).filter(
        Student.school_id == school.id,
        Student.is_active == True
    ).all()
    return students

@router.get("/teachers/my-school", response_model=List[TeacherOut])
async def get_school_teachers(db: db_dependency, current_user: user_dependency):
    """
    Get all teachers in principal's school
    """
    ensure_user_role(db, current_user["user_id"], UserRole.principal)
    
    school = db.query(School).filter(School.principal_id == current_user["user_id"]).first()
    if not school:
        raise HTTPException(status_code=404, detail="No school found for this principal")
    
    teachers = db.query(Teacher).filter(
        Teacher.school_id == school.id,
        Teacher.is_active == True
    ).all()
    return teachers

# === DIRECT SCHOOL JOINING ENDPOINTS ===

@router.get("/schools/available", response_model=List[SchoolSelectionResponse])
async def get_available_schools(
    db: db_dependency,
    current_user: user_dependency
):
    """
    Get list of all available schools for users to join
    """
    schools = db.query(School).filter(School.is_active == True).all()
    
    school_list = []
    for school in schools:
        # Get principal info
        principal = db.query(User).filter(User.id == school.principal_id).first()
        
        # Get stats
        total_students = db.query(Student).filter(Student.school_id == school.id).count()
        total_teachers = db.query(Teacher).filter(Teacher.school_id == school.id).count()
        
        school_info = SchoolSelectionResponse(
            id=school.id,
            name=school.name,
            address=school.address or "Address not provided",
            principal_name=f"{principal.fname} {principal.lname}" if principal else "No Principal Assigned",
            total_students=total_students,
            total_teachers=total_teachers,
            is_accepting_applications=True,
            created_date=school.created_date
        )
        school_list.append(school_info)
    
    return school_list

@router.post("/login-school/select-principal", response_model=JoinRequestResponse)
async def select_school_as_principal(
    db: db_dependency,
    current_user: user_dependency,
    join_request: DirectSchoolJoinRequest
):
    """
    Select a school where user is already assigned as principal (login to assigned school)
    User must be logged in and already be the principal of the selected school
    """
    # Get current user
    user = db.query(User).filter(User.id == current_user["user_id"]).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Verify email matches current user
    if user.email.lower() != join_request.email.lower():
        raise HTTPException(
            status_code=400, 
            detail="Email must match your registered email address"
        )
    
    # Check if school exists
    school = db.query(School).filter(School.id == join_request.school_id).first()
    if not school:
        raise HTTPException(status_code=404, detail="School not found")
    
    # Verify user is the principal of this school
    if school.principal_id != current_user["user_id"]:
        raise HTTPException(
            status_code=403, 
            detail="You are not assigned as principal of this school"
        )
    
    # Ensure user has principal role
    if not check_user_role(db, current_user["user_id"], UserRole.principal):
        raise HTTPException(
            status_code=403, 
            detail="You do not have principal role permissions"
        )
    
    try:
        print(f"🏫 Principal {user.username} logged into school {school.name}")
        
        return JoinRequestResponse(
            message=f"Successfully logged into {school.name} as principal",
            status="active",
            school_name=school.name,
            request_id=None,
            note="You are now active as principal of this school"
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error selecting school: {str(e)}")

@router.post("/join-school/request-teacher", response_model=JoinRequestResponse)
async def request_to_join_as_teacher(
    db: db_dependency,
    current_user: user_dependency,
    join_request: DirectSchoolJoinRequest
):
    """
    Request to join a school as a teacher (auto-approved if school has principal)
    User must be logged in and provide their email
    """
    # Get current user
    user = db.query(User).filter(User.id == current_user["user_id"]).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Verify email matches current user
    if user.email.lower() != join_request.email.lower():
        raise HTTPException(
            status_code=400, 
            detail="Email must match your registered email address"
        )
    
    # Check if school exists
    school = db.query(School).filter(School.id == join_request.school_id).first()
    if not school:
        raise HTTPException(status_code=404, detail="School not found")
    
    # Check if school has a principal
    if not school.principal_id:
        raise HTTPException(
            status_code=400, 
            detail="This school doesn't have a principal yet. Cannot join as teacher."
        )
    
    # Check if user is already a teacher at this school
    existing_teacher = db.query(Teacher).filter(
        Teacher.user_id == current_user["user_id"],
        Teacher.school_id == join_request.school_id
    ).first()
    
    if existing_teacher:
        raise HTTPException(
            status_code=400, 
            detail="You are already a teacher at this school"
        )
    
    try:
        # Assign teacher role if user doesn't have it
        if not check_user_role(db, current_user["user_id"], UserRole.teacher):
            teacher_role = db.query(Role).filter(Role.name == UserRole.teacher).first()
            if teacher_role:
                user.add_role(teacher_role)
                print(f"✅ Assigned teacher role to user {user.username}")
        
        # Create teacher record directly (auto-approved for teachers)
        teacher = Teacher(
            user_id=current_user["user_id"],
            school_id=join_request.school_id
        )
        
        db.add(teacher)
        db.commit()
        db.refresh(teacher)
        
        print(f"👨‍🏫 User {user.username} successfully joined {school.name} as teacher")
        
        return JoinRequestResponse(
            message=f"Successfully joined {school.name} as teacher",
            status="approved",
            school_name=school.name,
            request_id=None,
            note="You can now be assigned to subjects by the principal"
        )
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error joining as teacher: {str(e)}")

@router.get("/school-requests/principal-pending", response_model=List[dict])
async def get_pending_principal_requests(
    db: db_dependency,
    current_user: user_dependency
):
    """
    Get pending principal join requests (admin only)
    """
    ensure_user_role(db, current_user["user_id"], UserRole.admin)
    
    # Get pending principal join requests
    requests = db.query(SchoolRequest).filter(
        SchoolRequest.status == SchoolRequestStatus.pending,
        SchoolRequest.request_type == "principal_join"
    ).all()
    
    request_list = []
    for req in requests:
        user = db.query(User).filter(User.id == req.principal_id).first()
        school = db.query(School).filter(School.id == req.target_school_id).first()
        
        request_info = {
            "id": req.id,
            "user_id": req.principal_id,
            "username": user.username if user else "Unknown",
            "user_email": user.email if user else "Unknown",
            "user_name": f"{user.fname} {user.lname}" if user else "Unknown",
            "school_id": req.target_school_id,
            "school_name": req.school_name,
            "current_principal": school.principal_id is not None if school else False,
            "request_date": req.created_date,
            "request_type": "principal_join"
        }
        request_list.append(request_info)
    
    return request_list

@router.put("/school-requests/{request_id}/approve-principal", response_model=dict)
async def approve_principal_request(
    request_id: int,
    db: db_dependency,
    current_user: user_dependency
):
    """
    Approve a principal join request (admin only)
    """
    ensure_user_role(db, current_user["user_id"], UserRole.admin)
    
    # Get the request
    request = db.query(SchoolRequest).filter(
        SchoolRequest.id == request_id,
        SchoolRequest.status == SchoolRequestStatus.pending,
        SchoolRequest.request_type == "principal_join"
    ).first()
    
    if not request:
        raise HTTPException(status_code=404, detail="Principal request not found or already processed")
    
    # Get the school
    school = db.query(School).filter(School.id == request.target_school_id).first()
    if not school:
        raise HTTPException(status_code=404, detail="Target school not found")
    
    # Check if school still doesn't have a principal
    if school.principal_id:
        raise HTTPException(status_code=400, detail="School already has a principal assigned")
    
    # Get the user
    user = db.query(User).filter(User.id == request.principal_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Requested user not found")
    
    try:
        # Assign principal role to user
        principal_role = db.query(Role).filter(Role.name == UserRole.principal).first()
        if principal_role and not user.has_role(UserRole.principal):
            user.add_role(principal_role)
            print(f"✅ Assigned principal role to user {user.username}")
        
        # Update school to assign this user as principal
        school.principal_id = request.principal_id
        
        # Update request status
        request.status = SchoolRequestStatus.approved
        request.reviewed_by = current_user["user_id"]
        request.reviewed_date = datetime.utcnow()
        request.admin_notes = "Principal join request approved"
        
        db.commit()
        
        print(f"🏫 User {user.username} approved as principal for {school.name}")
        
        return {
            "message": f"Successfully approved {user.fname} {user.lname} as principal of {school.name}",
            "school_name": school.name,
            "principal_name": f"{user.fname} {user.lname}",
            "approved_by": current_user["user_id"]
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error approving principal request: {str(e)}")

@router.put("/school-requests/{request_id}/reject-principal", response_model=dict)
async def reject_principal_request(
    request_id: int,
    rejection_reason: str,
    db: db_dependency,
    current_user: user_dependency
):
    """
    Reject a principal join request (admin only)
    """
    ensure_user_role(db, current_user["user_id"], UserRole.admin)
    
    # Get the request
    request = db.query(SchoolRequest).filter(
        SchoolRequest.id == request_id,
        SchoolRequest.status == SchoolRequestStatus.pending,
        SchoolRequest.request_type == "principal_join"
    ).first()
    
    if not request:
        raise HTTPException(status_code=404, detail="Principal request not found or already processed")
    
    try:
        # Update request status
        request.status = SchoolRequestStatus.rejected
        request.reviewed_by = current_user["user_id"]
        request.reviewed_date = datetime.utcnow()
        request.admin_notes = rejection_reason
        
        db.commit()
        
        user = db.query(User).filter(User.id == request.principal_id).first()
        print(f"❌ Principal request rejected for user {user.username if user else 'Unknown'}")
        
        return {
            "message": "Principal request rejected",
            "school_name": request.school_name,
            "reason": rejection_reason,
            "rejected_by": current_user["user_id"]
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error rejecting principal request: {str(e)}")

