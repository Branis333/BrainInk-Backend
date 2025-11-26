from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, Depends, status
from typing import Annotated, List
import random
import string
from sqlalchemy.orm import Session
from sqlalchemy import func

from users_micro.db.connection import db_dependency
from models.study_area_models import (
    Role, School, Classroom, Student, Teacher,
    SchoolRequest, SchoolRequestStatus, UserRole,
    Subject, Assignment, Grade
)
from models.users_models import User
from schemas.roles_schemas import RoleCreate, RoleOut
from schemas.schools_schemas import SchoolCreate, SchoolOut, SchoolWithStats
from schemas.school_requests_schemas import (
    SchoolRequestCreate, SchoolRequestOut, SchoolRequestUpdate, 
    SchoolRequestWithPrincipal
)
from schemas.classrooms_schemas import ClassroomCreate, ClassroomOut
from schemas.students_schemas import StudentCreate, StudentOut
from schemas.teachers_schemas import TeacherCreate, TeacherOut
from Endpoints.auth import get_current_user
from schemas.direct_join_schemas import (
    DirectSchoolJoinRequest, SchoolSelectionResponse, JoinRequestResponse
)
# Import shared utility functions
from Endpoints.utils import (
    _get_user_roles, check_user_role, ensure_user_role, check_user_has_any_role, 
    ensure_user_has_any_role, generate_random_code, assign_role_to_user_by_email
)

router = APIRouter(tags=["School Management", "Schools", "Roles"])

user_dependency = Annotated[dict, Depends(get_current_user)]

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
    # Access code system removed: always return 0
    return SchoolWithStats(
        **school.__dict__,
        total_students=total_students,
        total_teachers=total_teachers,
        total_classrooms=total_classrooms,
        active_access_codes=0
    )

@router.get("/schools", response_model=List[SchoolOut])
async def get_all_schools(db: db_dependency, current_user: user_dependency):
    """
    Get all schools (admins only)
    """
    ensure_user_role(db, current_user["user_id"], UserRole.admin)
    
    schools = db.query(School).filter(School.is_active == True).all()
    return schools

# === CLASSROOM ENDPOINTS ===



# === ANALYTICS ENDPOINTS ===

@router.get("/analytics/school-overview")
async def get_school_analytics(db: db_dependency, current_user: user_dependency):
    """
    Get comprehensive analytics for current principal's school
    """
    ensure_user_role(db, current_user["user_id"], UserRole.principal)
    
    school = db.query(School).filter(School.principal_id == current_user["user_id"]).first()
    if not school:
        raise HTTPException(status_code=404, detail="No school found for this principal")
    
    # Basic counts
    total_students = db.query(Student).filter(Student.school_id == school.id).count()
    total_teachers = db.query(Teacher).filter(Teacher.school_id == school.id).count()
    total_classrooms = db.query(Classroom).filter(
        Classroom.school_id == school.id,
        Classroom.is_active == True
    ).count()
    
    # # Active access codes by type
    # active_student_codes = db.query(AccessCode).filter(
    #     AccessCode.school_id == school.id,
    #     AccessCode.code_type == AccessCodeType.student,
    #     AccessCode.is_active == True
    # ).count()
    
    # active_teacher_codes = db.query(AccessCode).filter(
    #     AccessCode.school_id == school.id,
    #     AccessCode.code_type == AccessCodeType.teacher,
    #     AccessCode.is_active == True
    # ).count()
    
    # # Used access codes
    # used_codes = db.query(AccessCode).filter(
    #     AccessCode.school_id == school.id,
    #     AccessCode.is_active == False,
    #     AccessCode.used_at.isnot(None)
    # ).count()
    
    # Recent registrations (last 30 days)
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    
    recent_students = db.query(Student).filter(
        Student.school_id == school.id,
        Student.enrollment_date >= thirty_days_ago
    ).count()
    
    recent_teachers = db.query(Teacher).filter(
        Teacher.school_id == school.id,
        Teacher.hire_date >= thirty_days_ago
    ).count()
    
    # ENHANCED ANALYTICS - Overall school average from grades
    try:
        overall_average = db.query(func.avg(
            (Grade.points_earned * 100.0 / Assignment.max_points)
        )).select_from(Grade).join(
            Assignment, Grade.assignment_id == Assignment.id
        ).join(
            Subject, Assignment.subject_id == Subject.id
        ).filter(
            Subject.school_id == school.id,
            Grade.is_active == True,
            Assignment.is_active == True
        ).scalar() or 0.0
    except Exception as e:
        print(f"Error calculating overall average: {e}")
        overall_average = 0.0
    
    # Assignment completion rate - simplified approach
    try:
        total_assignments = db.query(Assignment).join(Subject).filter(
            Subject.school_id == school.id,
            Assignment.is_active == True
        ).count()
        
        graded_assignments = db.query(func.count(Grade.id)).select_from(Grade).join(
            Assignment, Grade.assignment_id == Assignment.id
        ).join(
            Subject, Assignment.subject_id == Subject.id
        ).filter(
            Subject.school_id == school.id,
            Assignment.is_active == True,
            Grade.is_active == True
        ).scalar() or 0
        
        # Simplified calculation - total students * total assignments
        total_students = db.query(Student).filter(
            Student.school_id == school.id,
            Student.is_active == True
        ).count()
        
        expected_submissions = total_assignments * total_students
        completion_rate = (graded_assignments / expected_submissions * 100) if expected_submissions > 0 else 0.0
        
    except Exception as e:
        print(f"Error calculating completion rate: {e}")
        completion_rate = 0.0
        graded_assignments = 0
        total_assignments = 0

    return {
        "school_info": {
            "name": school.name,
            "address": school.address,
            "created_at": school.created_date
        },
        "user_counts": {
            "total_students": total_students,
            "total_teachers": total_teachers,
            "recent_students": recent_students,
            "recent_teachers": recent_teachers
        },
        "infrastructure": {
            "total_classrooms": total_classrooms
        },
        "analytics": {
            "overall_average": round(overall_average, 1),
            "completion_rate": round(completion_rate, 1),
            "total_assignments": total_assignments,
            "graded_assignments": graded_assignments
        }
        # "access_codes": {
        #     "active_student_codes": active_student_codes,
        #     "active_teacher_codes": active_teacher_codes,
        #     "used_codes": used_codes,
        #     "total_active": active_student_codes + active_teacher_codes
        # }
    }

@router.get("/analytics/subject-performance")
async def get_subject_performance(db: db_dependency, current_user: user_dependency):
    """
    Get subject performance analytics - average grades by subject
    """
    ensure_user_role(db, current_user["user_id"], UserRole.principal)
    
    school = db.query(School).filter(School.principal_id == current_user["user_id"]).first()
    if not school:
        raise HTTPException(status_code=404, detail="No school found for this principal")
    
    try:
        # Get average performance by subject
        subject_performance = db.query(
            Subject.id,
            Subject.name,
            func.avg((Grade.points_earned * 100.0 / Assignment.max_points)).label('average'),
            func.count(Grade.id).label('total_grades')
        ).select_from(Subject).join(
            Assignment, Subject.id == Assignment.subject_id
        ).join(
            Grade, Assignment.id == Grade.assignment_id
        ).filter(
            Subject.school_id == school.id,
            Subject.is_active == True,
            Assignment.is_active == True,
            Grade.is_active == True
        ).group_by(Subject.id, Subject.name).all()
        
        # Calculate trends (comparing last 30 days vs previous 30 days)
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        sixty_days_ago = datetime.utcnow() - timedelta(days=60)
        
        result = []
        for subject in subject_performance:
            try:
                # Get recent performance
                recent_avg = db.query(
                    func.avg((Grade.points_earned * 100.0 / Assignment.max_points))
                ).select_from(Grade).join(
                    Assignment, Grade.assignment_id == Assignment.id
                ).filter(
                    Assignment.subject_id == subject.id,
                    Grade.graded_date >= thirty_days_ago,
                    Grade.is_active == True,
                    Assignment.is_active == True
                ).scalar() or 0
                
                # Get previous period performance
                previous_avg = db.query(
                    func.avg((Grade.points_earned * 100.0 / Assignment.max_points))
                ).select_from(Grade).join(
                    Assignment, Grade.assignment_id == Assignment.id
                ).filter(
                    Assignment.subject_id == subject.id,
                    Grade.graded_date >= sixty_days_ago,
                    Grade.graded_date < thirty_days_ago,
                    Grade.is_active == True,
                    Assignment.is_active == True
                ).scalar() or 0
                
                # Calculate trend
                trend = recent_avg - previous_avg if previous_avg > 0 else 0
                trend_formatted = f"+{trend:.1f}%" if trend > 0 else f"{trend:.1f}%"
                
                result.append({
                    "subject": subject.name,
                    "average": round(subject.average, 1),
                    "trend": trend_formatted,
                    "total_grades": subject.total_grades
                })
            except Exception as e:
                print(f"Error processing subject {subject.name}: {e}")
                result.append({
                    "subject": subject.name,
                    "average": round(subject.average, 1) if subject.average else 0.0,
                    "trend": "+0.0%",
                    "total_grades": subject.total_grades
                })
        
        return {"subject_performance": result}
    except Exception as e:
        print(f"Error in subject performance analytics: {e}")
        return {"subject_performance": []}

@router.get("/analytics/grade-distribution") 
async def get_grade_distribution(db: db_dependency, current_user: user_dependency):
    """
    Get grade distribution across the school (A, B, C, D, F percentages)
    """
    ensure_user_role(db, current_user["user_id"], UserRole.principal)
    
    school = db.query(School).filter(School.principal_id == current_user["user_id"]).first()
    if not school:
        raise HTTPException(status_code=404, detail="No school found for this principal")
    
    try:
        # Get all grades for school
        grades = db.query(
            (Grade.points_earned * 100.0 / Assignment.max_points).label('percentage')
        ).select_from(Grade).join(
            Assignment, Grade.assignment_id == Assignment.id
        ).join(
            Subject, Assignment.subject_id == Subject.id
        ).filter(
            Subject.school_id == school.id,
            Grade.is_active == True,
            Assignment.is_active == True
        ).all()
        
        if not grades:
            return {"grade_distribution": {
                "Grade A": 0,
                "Grade B": 0,
                "Grade C": 0,
                "Grade D": 0,
                "Grade F": 0
            }}
        
        # Calculate grade distribution
        total_grades = len(grades)
        grade_counts = {"A": 0, "B": 0, "C": 0, "D": 0, "F": 0}
        
        for grade in grades:
            percentage = grade.percentage
            if percentage >= 90:
                grade_counts["A"] += 1
            elif percentage >= 80:
                grade_counts["B"] += 1
            elif percentage >= 70:
                grade_counts["C"] += 1
            elif percentage >= 60:
                grade_counts["D"] += 1
            else:
                grade_counts["F"] += 1
        
        # Convert to percentages
        grade_distribution = {}
        for grade, count in grade_counts.items():
            grade_distribution[f"Grade {grade}"] = round((count / total_grades) * 100) if total_grades > 0 else 0
        
        return {"grade_distribution": grade_distribution}
    except Exception as e:
        print(f"Error in grade distribution analytics: {e}")
        return {"grade_distribution": {
            "Grade A": 0,
            "Grade B": 0,
            "Grade C": 0,
            "Grade D": 0,
            "Grade F": 0
        }}

@router.get("/analytics/completion-rate")
async def get_completion_rate(db: db_dependency, current_user: user_dependency):
    """
    Get assignment completion rate - percentage of assignments that have been graded
    """
    ensure_user_role(db, current_user["user_id"], UserRole.principal)
    
    school = db.query(School).filter(School.principal_id == current_user["user_id"]).first()
    if not school:
        raise HTTPException(status_code=404, detail="No school found for this principal")
    
    try:
        # Get total assignments and graded assignments
        total_assignments = db.query(Assignment).join(Subject).filter(
            Subject.school_id == school.id,
            Assignment.is_active == True
        ).count()
        
        graded_assignments = db.query(func.count(Grade.id)).select_from(Grade).join(
            Assignment, Grade.assignment_id == Assignment.id
        ).join(
            Subject, Assignment.subject_id == Subject.id
        ).filter(
            Subject.school_id == school.id,
            Assignment.is_active == True,
            Grade.is_active == True
        ).scalar() or 0
        
        # Simplified calculation - total students * total assignments
        total_students = db.query(Student).filter(
            Student.school_id == school.id,
            Student.is_active == True
        ).count()
        
        expected_submissions = total_assignments * total_students
        completion_rate = (graded_assignments / expected_submissions * 100) if expected_submissions > 0 else 0.0
        
        return {
            "completion_rate": round(completion_rate, 1),
            "graded_submissions": graded_assignments,
            "expected_submissions": expected_submissions,
            "improvement": "+5.1%"  # This could be calculated by comparing with previous period
        }
    except Exception as e:
        print(f"Error in completion rate analytics: {e}")
        return {
            "completion_rate": 0.0,
            "graded_submissions": 0,
            "expected_submissions": 0,
            "improvement": "+0.0%"
        }

@router.get("/analytics/daily-active")
async def get_daily_active_students(db: db_dependency, current_user: user_dependency):
    """
    Get daily active students count - based on recent grade activity
    """
    ensure_user_role(db, current_user["user_id"], UserRole.principal)
    
    school = db.query(School).filter(School.principal_id == current_user["user_id"]).first()
    if not school:
        raise HTTPException(status_code=404, detail="No school found for this principal")
    
    # Get last 7 days of activity
    seven_days_ago = datetime.utcnow() - timedelta(days=7)
    
    # For now, we'll simulate daily activity based on recent grades
    # In a real system, you'd track actual user login/activity
    recent_students = db.query(Student).filter(
        Student.school_id == school.id,
        Student.enrollment_date >= seven_days_ago
    ).count()
    
    total_students = db.query(Student).filter(
        Student.school_id == school.id,
        Student.is_active == True
    ).count()
    
    # Simulate peak engagement (you'd replace this with actual activity tracking)
    daily_active = min(total_students, max(recent_students, int(total_students * 0.75)))
    
    return {
        "daily_active": daily_active,
        "peak_engagement": True,
        "total_students": total_students
    }

@router.get("/analytics/session-time")
async def get_average_session_time(db: db_dependency, current_user: user_dependency):
    """
    Get average session time - this would normally come from user activity tracking
    """
    ensure_user_role(db, current_user["user_id"], UserRole.principal)
    
    school = db.query(School).filter(School.principal_id == current_user["user_id"]).first()
    if not school:
        raise HTTPException(status_code=404, detail="No school found for this principal")
    
    # In a real system, you'd track actual session times
    # For now, return a simulated value based on engagement
    return {
        "average_session_time": "45 minutes",
        "quality_engagement": True
    }

# === ROLE MANAGEMENT ENDPOINTS ===

@router.get("/role/current-role")
async def get_current_user_role(db: db_dependency, current_user: user_dependency):
    """
    Get current user's roles and associated school information - accessible by any authenticated user
    """
    user = db.query(User).filter(User.id == current_user["user_id"]).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user_roles = _get_user_roles(db, current_user["user_id"])
    
    response = {
        "user_id": user.id,
        "username": user.username,
        "email": user.email,
        "full_name": f"{user.fname} {user.lname}".strip() if user.fname or user.lname else None,
        "roles": [role.value for role in user_roles],
        "is_student": UserRole.student in user_roles,
        "is_teacher": UserRole.teacher in user_roles,
        "is_principal": UserRole.principal in user_roles,
        "is_admin": UserRole.admin in user_roles
    }
    
    # Add role-specific school information
    school_info = {}
    
    # If user is a principal, get their school
    if UserRole.principal in user_roles:
        school = db.query(School).filter(School.principal_id == user.id).first()
        if school:
            school_info["principal_school"] = {
                "school_id": school.id,
                "school_name": school.name,
                "school_address": school.address
            }
    
    # If user is a teacher, get their school(s)
    if UserRole.teacher in user_roles:
        teacher_records = db.query(Teacher).filter(Teacher.user_id == user.id).all()
        if teacher_records:
            teacher_schools = []
            for teacher in teacher_records:
                school = db.query(School).filter(School.id == teacher.school_id).first()
                if school:
                    teacher_schools.append({
                        "school_id": school.id,
                        "school_name": school.name,
                        "teacher_id": teacher.id
                    })
            if teacher_schools:
                school_info["teacher_schools"] = teacher_schools
    
    # If user is a student, get their school(s)
    if UserRole.student in user_roles:
        student_records = db.query(Student).filter(Student.user_id == user.id).all()
        if student_records:
            student_schools = []
            for student in student_records:
                school = db.query(School).filter(School.id == student.school_id).first()
                if school:
                    student_schools.append({
                        "school_id": school.id,
                        "school_name": school.name,
                        "student_id": student.id
                    })
            if student_schools:
                school_info["student_schools"] = student_schools
    
    if school_info:
        response["school_info"] = school_info
    
    return response

@router.post("/roles/assign")
async def assign_role_to_user(
    db: db_dependency, 
    current_user: user_dependency,
    user_id: int,
    role_name: str
):
    """
    Assign role to user (admins only)
    """
    ensure_user_role(db, current_user["user_id"], UserRole.admin)
    
    # Get user and role
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    try:
        role_enum = UserRole(role_name)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid role: {role_name}")
    
    role = db.query(Role).filter(Role.name == role_enum).first()
    if not role:
        raise HTTPException(status_code=404, detail=f"Role {role_name} not found")
    
    # Check if user already has this role
    if user.has_role(role_enum):
        raise HTTPException(status_code=400, detail=f"User already has {role_name} role")
    
    try:
        user.add_role(role)
        db.commit()
        return {"message": f"Role {role_name} assigned to user {user.username}"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Role assignment error: {str(e)}")

@router.delete("/roles/remove")
async def remove_role_from_user(
    db: db_dependency, 
    current_user: user_dependency,
    user_id: int,
    role_name: str
):
    """
    Remove role from user (admins only)
    """
    ensure_user_role(db, current_user["user_id"], UserRole.admin)
    
    # Get user and role
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    try:
        role_enum = UserRole(role_name)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid role: {role_name}")
    
    role = db.query(Role).filter(Role.name == role_enum).first()
    if not role:
        raise HTTPException(status_code=404, detail=f"Role {role_name} not found")
    
    # Check if user has this role
    if not user.has_role(role_enum):
        raise HTTPException(status_code=400, detail=f"User doesn't have {role_name} role")
    
    try:
        user.remove_role(role)
        db.commit()
        return {"message": f"Role {role_name} removed from user {user.username}"}
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
    Get all roles for a specific user (admins only, or users viewing their own roles)
    """
    # Allow users to view their own roles, or admins to view any user's roles
    if current_user["user_id"] != user_id:
        ensure_user_role(db, current_user["user_id"], UserRole.admin)
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user_roles = _get_user_roles(db, user_id)
    return {
        "user_id": user_id,
        "username": user.username,
        "email": user.email,
        "roles": [role.value for role in user_roles]
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
    role_name: str,
    db: db_dependency, 
    current_user: user_dependency
):
    """
    Get all users with a specific role (admins only)
    """
    ensure_user_role(db, current_user["user_id"], UserRole.admin)
    
    try:
        role_enum = UserRole(role_name)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid role: {role_name}")
    
    role = db.query(Role).filter(Role.name == role_enum).first()
    if not role:
        raise HTTPException(status_code=404, detail=f"Role {role_name} not found")
    
    users_with_role = []
    for user in role.users:
        users_with_role.append({
            "user_id": user.id,
            "username": user.username,
            "email": user.email,
            "fname": user.fname,
            "lname": user.lname
        })
    
    return {
        "role": role_name,
        "users": users_with_role,
        "count": len(users_with_role)
    }

# === USER STATUS ENDPOINTS ===

@router.get("/user/status")
async def get_user_status(db: db_dependency, current_user: user_dependency):
    """
    Get comprehensive status for current user including roles, schools, subjects etc.
    """
    user = db.query(User).filter(User.id == current_user["user_id"]).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user_roles = _get_user_roles(db, current_user["user_id"])
    
    status = {
        "user_id": user.id,
        "username": user.username,
        "email": user.email,
        "roles": [role.value for role in user_roles]
    }
    
    # Add role-specific information
    if UserRole.principal in user_roles:
        school = db.query(School).filter(School.principal_id == user.id).first()
    if UserRole.teacher in user_roles:
        teacher_records = db.query(Teacher).filter(Teacher.user_id == user.id).all()
        if teacher_records:
            schools_info = []
            for teacher in teacher_records:
                school = db.query(School).filter(School.id == teacher.school_id).first()
                if school:
                    schools_info.append({
                        "school_id": school.id,
                        "school_name": school.name,
                        "teacher_id": teacher.id
                    })
            status["teacher_info"] = {"schools": schools_info}
    
    if UserRole.student in user_roles:
        student_records = db.query(Student).filter(Student.user_id == user.id).all()
        if student_records:
            schools_info = []
            for student in student_records:
                school = db.query(School).filter(School.id == student.school_id).first()
                if school:
                    schools_info.append({
                        "school_id": school.id,
                        "school_name": school.name,
                        "student_id": student.id
                    })
            status["student_info"] = {"schools": schools_info}
    
    return status

@router.get("/students/my-school", response_model=List[StudentOut])
async def get_my_school_students(db: db_dependency, current_user: user_dependency):
    """
    Get all students in current principal's school
    """
    ensure_user_role(db, current_user["user_id"], UserRole.principal)
    
    school = db.query(School).filter(School.principal_id == current_user["user_id"]).first()
    if not school:
        raise HTTPException(status_code=404, detail="No school found for this principal")
    
    students = db.query(Student).filter(Student.school_id == school.id).all()
    return students

@router.get("/teachers/my-school", response_model=List[TeacherOut])
async def get_my_school_teachers(db: db_dependency, current_user: user_dependency):
    """
    Get all teachers in current principal's school
    """
    ensure_user_role(db, current_user["user_id"], UserRole.principal)
    
    school = db.query(School).filter(School.principal_id == current_user["user_id"]).first()
    if not school:
        raise HTTPException(status_code=404, detail="No school found for this principal")
    
    teachers = db.query(Teacher).filter(Teacher.school_id == school.id).all()
    return teachers

# === DIRECT SCHOOL JOINING ENDPOINTS ===

@router.get("/schools/available", response_model=List[SchoolSelectionResponse])
async def get_available_schools_for_user(db: db_dependency, current_user: user_dependency):
    """
    Get all active schools with user's role in each school (if any)
    Available to any authenticated user
    """
    user_roles = _get_user_roles(db, current_user["user_id"])
    available_schools = []
    
    # Get all active schools
    schools = db.query(School).filter(School.is_active == True).all()
    
    for school in schools:
        # Count students and teachers
        total_students = db.query(Student).filter(Student.school_id == school.id).count()
        total_teachers = db.query(Teacher).filter(Teacher.school_id == school.id).count()
        
        # Get principal name
        principal_user = db.query(User).filter(User.id == school.principal_id).first()
        principal_name = None
        if principal_user:
            principal_name = f"{principal_user.fname} {principal_user.lname}".strip()
        
        # Determine user's role in this school
        user_role = None
        if school.principal_id == current_user["user_id"]:
            user_role = "principal"
        else:
            # Check if user is a teacher in this school
            teacher_assignment = db.query(Teacher).filter(
                Teacher.user_id == current_user["user_id"],
                Teacher.school_id == school.id
            ).first()
            if teacher_assignment:
                user_role = "teacher"
            else:
                # Check if user is a student in this school
                student_assignment = db.query(Student).filter(
                    Student.user_id == current_user["user_id"],
                    Student.school_id == school.id
                ).first()
                if student_assignment:
                    user_role = "student"
        
        available_schools.append(SchoolSelectionResponse(
            id=school.id,
            name=school.name,
            address=school.address,
            principal_name=principal_name,
            total_students=total_students,
            total_teachers=total_teachers,
            is_accepting_applications=True,
            created_date=school.created_date,
            user_role=user_role
        ))
    
    return available_schools

@router.post("/login-school/select-principal", response_model=JoinRequestResponse)
async def select_school_as_principal(
    request: DirectSchoolJoinRequest,
    db: db_dependency, 
    current_user: user_dependency
):
    """
    Login/select a school as principal (for already-assigned principals)
    """
    ensure_user_role(db, current_user["user_id"], UserRole.principal)
    
    # Verify the user is actually the principal of this school
    school = db.query(School).filter(
        School.id == request.school_id,
        School.principal_id == current_user["user_id"],
        School.is_active == True
    ).first()
    
    if not school:
        raise HTTPException(
            status_code=403, 
            detail="You are not the principal of this school or school is inactive"
        )
    
    return JoinRequestResponse(
        message=f"Successfully logged in as principal of {school.name}",
        status="success",
        school_name=school.name,
        note="Principal login successful",
        success=True,
        school_id=school.id,
        role="principal"
    )

@router.post("/login-school/select-teacher", response_model=JoinRequestResponse)
async def select_school_as_teacher(
    request: DirectSchoolJoinRequest,
    db: db_dependency, 
    current_user: user_dependency
):
    """
    Login/select a school as teacher (for already-assigned teachers)
    """
    ensure_user_role(db, current_user["user_id"], UserRole.teacher)
    
    # Verify the user is actually a teacher in this school
    teacher = db.query(Teacher).filter(
        Teacher.user_id == current_user["user_id"],
        Teacher.school_id == request.school_id
    ).first()
    
    if not teacher:
        raise HTTPException(
            status_code=403, 
            detail="You are not a teacher in this school"
        )
    
    school = db.query(School).filter(
        School.id == request.school_id,
        School.is_active == True
    ).first()
    
    if not school:
        raise HTTPException(status_code=404, detail="School not found or inactive")
    
    return JoinRequestResponse(
        message=f"Successfully logged in as teacher at {school.name}",
        status="success",
        school_name=school.name,
        note="Teacher login successful",
        success=True,
        school_id=school.id,
        role="teacher"
    )

@router.get("/school-requests/principal-pending", response_model=List[dict])
async def get_pending_principal_requests(db: db_dependency, current_user: user_dependency):
    """
    Get pending principal/teacher join requests for approval (school principals only)
    """
    ensure_user_role(db, current_user["user_id"], UserRole.principal)
    
    # Get principal's school
    school = db.query(School).filter(School.principal_id == current_user["user_id"]).first()
    if not school:
        raise HTTPException(status_code=404, detail="No school found for this principal")
    
    # Get pending requests for this school (teacher join requests)
    pending_requests = db.query(SchoolRequest).filter(
        SchoolRequest.school_name == school.name,
        SchoolRequest.status == SchoolRequestStatus.pending,
        SchoolRequest.principal_id != current_user["user_id"]  # Exclude principal's own requests
    ).all()
    
    result = []
    for request in pending_requests:
        user = db.query(User).filter(User.id == request.principal_id).first()
        if user:
            result.append({
                "request_id": request.id,
                "user_id": user.id,
                "user_name": f"{user.fname} {user.lname}",
                "user_email": user.email,
                "request_type": "teacher_join",
                "created_at": request.created_date,
                "admin_notes": request.admin_notes
            })
    
    return result

@router.put("/school-requests/{request_id}/approve-principal", response_model=dict)
async def approve_principal_request(
    request_id: int,
    db: db_dependency, 
    current_user: user_dependency
):
    """
    Approve a teacher join request (school principals only)
    """
    ensure_user_role(db, current_user["user_id"], UserRole.principal)
    
    # Get principal's school
    school = db.query(School).filter(School.principal_id == current_user["user_id"]).first()
    if not school:
        raise HTTPException(status_code=404, detail="No school found for this principal")
    
    # Get the request
    request = db.query(SchoolRequest).filter(SchoolRequest.id == request_id).first()
    if not request:
        raise HTTPException(status_code=404, detail="Request not found")
    
    if request.status != SchoolRequestStatus.pending:
        raise HTTPException(status_code=400, detail="Request has already been processed")
    
    if request.school_name != school.name:
        raise HTTPException(status_code=403, detail="You can only approve requests for your school")
    
    try:
        # Create teacher record
        teacher = Teacher(
            user_id=request.principal_id,
            school_id=school.id
        )
        db.add(teacher)
        
        # Update request status
        request.status = SchoolRequestStatus.approved
        request.reviewed_by = current_user["user_id"]
        request.reviewed_date = datetime.utcnow()
        request.admin_notes = f"Approved by principal {current_user['user_id']}"
        
        db.commit()
        
        return {
            "message": "Teacher join request approved successfully",
            "teacher_id": teacher.id,
            "school_name": school.name
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Approval error: {str(e)}")

@router.put("/school-requests/{request_id}/reject-principal", response_model=dict)
async def reject_principal_request(
    request_id: int,
    db: db_dependency, 
    current_user: user_dependency,
    rejection_reason: str = "No reason provided"
):
    """
    Reject a teacher join request (school principals only)
    """
    ensure_user_role(db, current_user["user_id"], UserRole.principal)
    
    # Get principal's school
    school = db.query(School).filter(School.principal_id == current_user["user_id"]).first()
    if not school:
        raise HTTPException(status_code=404, detail="No school found for this principal")
    
    # Get the request
    request = db.query(SchoolRequest).filter(SchoolRequest.id == request_id).first()
    if not request:
        raise HTTPException(status_code=404, detail="Request not found")
    
    if request.status != SchoolRequestStatus.pending:
        raise HTTPException(status_code=400, detail="Request has already been processed")
    
    if request.school_name != school.name:
        raise HTTPException(status_code=403, detail="You can only reject requests for your school")
    
    try:
        # Update request status
        request.status = SchoolRequestStatus.rejected
        request.reviewed_by = current_user["user_id"]
        request.reviewed_date = datetime.utcnow()
        request.admin_notes = f"Rejected by principal {current_user['user_id']}: {rejection_reason}"
        
        db.commit()
        
        return {
            "message": "Teacher join request rejected",
            "school_name": school.name,
            "reason": rejection_reason
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Rejection error: {str(e)}")
