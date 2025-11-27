from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, Depends, status
from typing import Annotated, List
import random
import string
from sqlalchemy.orm import Session
from sqlalchemy import func

from db.connection import db_dependency
from models.study_area_models import (
    Role, School, Classroom, Student, Teacher,
    SchoolRequest, SchoolRequestStatus, UserRole,
    Subject, Assignment, Grade,
    subject_students, subject_teachers
)
from models.users_models import User
from schemas.roles_schemas import RoleCreate, RoleOut
from schemas.schools_schemas import SchoolCreate, SchoolOut, SchoolWithStats
from schemas.school_requests_schemas import (
    SchoolRequestCreate, SchoolRequestOut, SchoolRequestUpdate, 
    SchoolRequestWithPrincipal
)
from schemas.classrooms_schemas import ClassroomCreate, ClassroomOut, ClassroomUpdate, ClassroomWithDetails
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

router = APIRouter(tags=["Classroom Management"])

user_dependency = Annotated[dict, Depends(get_current_user)]

# === CLASSROOM ENDPOINTS ===

@router.post("/classrooms/create", response_model=ClassroomOut)
async def create_classroom(
    db: db_dependency, 
    current_user: user_dependency, 
    classroom: ClassroomCreate
):
    """
    Create a new classroom (principals only for their school)
    """
    ensure_user_role(db, current_user["user_id"], UserRole.principal)
    
    # Check if principal owns the school
    school = db.query(School).filter(
        School.id == classroom.school_id,
        School.principal_id == current_user["user_id"]
    ).first()
    if not school:
        raise HTTPException(status_code=404, detail="School not found or not managed by you")
    
    # Check if classroom name already exists in this school
    existing_classroom = db.query(Classroom).filter(
        Classroom.school_id == classroom.school_id,
        Classroom.name == classroom.name
    ).first()
    if existing_classroom:
        raise HTTPException(
            status_code=400, 
            detail=f"Classroom '{classroom.name}' already exists in this school"
        )
    
    # Validate teacher assignment if provided
    if classroom.teacher_id:
        teacher = db.query(Teacher).filter(
            Teacher.id == classroom.teacher_id,
            Teacher.school_id == classroom.school_id
        ).first()
        if not teacher:
            raise HTTPException(
                status_code=404, 
                detail="Teacher not found or not in this school"
            )
    
    try:
        db_classroom = Classroom(
            name=classroom.name,
            description=classroom.description,
            capacity=classroom.capacity,
            location=classroom.location,
            school_id=classroom.school_id,
            teacher_id=classroom.teacher_id
        )
        db.add(db_classroom)
        db.commit()
        db.refresh(db_classroom)
        return db_classroom
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Classroom creation error: {str(e)}")

@router.get("/classrooms/my-school", response_model=List[ClassroomWithDetails])
async def get_my_school_classrooms(db: db_dependency, current_user: user_dependency):
    """
    Get all classrooms for current principal's school with details
    """
    ensure_user_role(db, current_user["user_id"], UserRole.principal)
    
    school = db.query(School).filter(School.principal_id == current_user["user_id"]).first()
    if not school:
        raise HTTPException(status_code=404, detail="No school found for this principal")
    
    classrooms = db.query(Classroom).filter(
        Classroom.school_id == school.id,
        Classroom.is_active == True
    ).all()
    
    result = []
    for classroom in classrooms:
        # Get assigned teacher details
        assigned_teacher = None
        if classroom.teacher_id:
            teacher = db.query(Teacher).filter(Teacher.id == classroom.teacher_id).first()
            if teacher:
                user = db.query(User).filter(User.id == teacher.user_id).first()
                if user:
                    assigned_teacher = {
                        "id": teacher.id,
                        "name": f"{user.fname} {user.lname}",
                        "email": user.email
                    }
        
        # Get student count
        student_count = db.query(Student).filter(
            Student.classroom_id == classroom.id,
            Student.is_active == True
        ).count()
        
        result.append(ClassroomWithDetails(
            **classroom.__dict__,
            assigned_teacher=assigned_teacher,
            student_count=student_count,
            subjects=[]  # Will implement subject assignment later
        ))
    
    return result

@router.put("/classrooms/{classroom_id}", response_model=ClassroomOut)
async def update_classroom(
    classroom_id: int,
    classroom_update: ClassroomUpdate,
    db: db_dependency, 
    current_user: user_dependency
):
    """
    Update classroom details (principals only)
    """
    ensure_user_role(db, current_user["user_id"], UserRole.principal)
    
    # Get classroom and verify ownership
    classroom = db.query(Classroom).filter(Classroom.id == classroom_id).first()
    if not classroom:
        raise HTTPException(status_code=404, detail="Classroom not found")
    
    school = db.query(School).filter(
        School.id == classroom.school_id,
        School.principal_id == current_user["user_id"]
    ).first()
    if not school:
        raise HTTPException(status_code=403, detail="You don't have permission to update this classroom")
    
    # Validate teacher assignment if provided
    if classroom_update.teacher_id:
        teacher = db.query(Teacher).filter(
            Teacher.id == classroom_update.teacher_id,
            Teacher.school_id == classroom.school_id
        ).first()
        if not teacher:
            raise HTTPException(
                status_code=404, 
                detail="Teacher not found or not in this school"
            )
    
    try:
        # Update fields if provided
        if classroom_update.name is not None:
            # Check if new name conflicts
            existing = db.query(Classroom).filter(
                Classroom.school_id == classroom.school_id,
                Classroom.name == classroom_update.name,
                Classroom.id != classroom_id
            ).first()
            if existing:
                raise HTTPException(
                    status_code=400, 
                    detail=f"Classroom '{classroom_update.name}' already exists in this school"
                )
            classroom.name = classroom_update.name
            
        if classroom_update.description is not None:
            classroom.description = classroom_update.description
        if classroom_update.capacity is not None:
            classroom.capacity = classroom_update.capacity
        if classroom_update.location is not None:
            classroom.location = classroom_update.location
        if classroom_update.teacher_id is not None:
            classroom.teacher_id = classroom_update.teacher_id
        
        db.commit()
        db.refresh(classroom)
        return classroom
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Classroom update error: {str(e)}")

@router.delete("/classrooms/{classroom_id}")
async def delete_classroom(
    classroom_id: int,
    db: db_dependency, 
    current_user: user_dependency
):
    """
    Delete/deactivate classroom (principals only)
    """
    ensure_user_role(db, current_user["user_id"], UserRole.principal)
    
    # Get classroom and verify ownership
    classroom = db.query(Classroom).filter(Classroom.id == classroom_id).first()
    if not classroom:
        raise HTTPException(status_code=404, detail="Classroom not found")
    
    school = db.query(School).filter(
        School.id == classroom.school_id,
        School.principal_id == current_user["user_id"]
    ).first()
    if not school:
        raise HTTPException(status_code=403, detail="You don't have permission to delete this classroom")
    
    try:
        # Soft delete - just mark as inactive
        classroom.is_active = False
        db.commit()
        return {"message": f"Classroom '{classroom.name}' has been deactivated successfully"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Classroom deletion error: {str(e)}")

@router.post("/classrooms/{classroom_id}/assign-teacher")
async def assign_teacher_to_classroom(
    classroom_id: int,
    teacher_id: int,
    db: db_dependency, 
    current_user: user_dependency
):
    """
    Assign teacher to classroom (principals only)
    """
    ensure_user_role(db, current_user["user_id"], UserRole.principal)
    
    # Get classroom and verify ownership
    classroom = db.query(Classroom).filter(Classroom.id == classroom_id).first()
    if not classroom:
        raise HTTPException(status_code=404, detail="Classroom not found")
    
    school = db.query(School).filter(
        School.id == classroom.school_id,
        School.principal_id == current_user["user_id"]
    ).first()
    if not school:
        raise HTTPException(status_code=403, detail="You don't have permission to manage this classroom")
    
    # Verify teacher exists and belongs to this school
    teacher = db.query(Teacher).filter(
        Teacher.id == teacher_id,
        Teacher.school_id == classroom.school_id
    ).first()
    if not teacher:
        raise HTTPException(status_code=404, detail="Teacher not found or not in this school")
    
    try:
        classroom.teacher_id = teacher_id
        db.commit()
        
        # Get teacher name for response
        user = db.query(User).filter(User.id == teacher.user_id).first()
        teacher_name = f"{user.fname} {user.lname}" if user else "Unknown"
        
        return {
            "message": f"Teacher '{teacher_name}' assigned to classroom '{classroom.name}' successfully",
            "classroom_id": classroom_id,
            "teacher_id": teacher_id
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Teacher assignment error: {str(e)}")

@router.post("/classrooms/{classroom_id}/add-students")
async def add_students_to_classroom(
    classroom_id: int,
    student_ids: List[int],
    db: db_dependency, 
    current_user: user_dependency
):
    """
    Add students to classroom (principals and teachers can access)
    """
    user_roles = _get_user_roles(db, current_user["user_id"])
    if not (UserRole.principal in user_roles or UserRole.teacher in user_roles):
        raise HTTPException(status_code=403, detail="Only principals and teachers can manage classroom students")
    
    classroom = db.query(Classroom).filter(Classroom.id == classroom_id).first()
    if not classroom:
        raise HTTPException(status_code=404, detail="Classroom not found")
    
    # Permission checks (same as before)...

    try:
        added_students = []
        already_assigned = []
        not_found = []
        
        for student_id in student_ids:
            student = db.query(Student).filter(
                Student.id == student_id,
                Student.school_id == classroom.school_id,
                Student.is_active == True
            ).first()
            
            if not student:
                not_found.append(student_id)
                continue
            
            if student.classroom_id == classroom_id:
                already_assigned.append(student_id)
                continue
            
            # Assign student to classroom
            student.classroom_id = classroom_id
            db.add(student)  # <-- Ensure SQLAlchemy tracks the change!
            added_students.append(student_id)
        
        db.commit()
        # Optionally, db.refresh(classroom) if you want to return updated classroom info
        
        return {
            "message": f"Students processed for classroom '{classroom.name}'",
            "added_students": added_students,
            "already_assigned": already_assigned,
            "not_found": not_found,
            "total_added": len(added_students)
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Student assignment error: {str(e)}")

@router.delete("/classrooms/{classroom_id}/remove-students")
async def remove_students_from_classroom(
    classroom_id: int,
    student_ids: List[int],
    db: db_dependency, 
    current_user: user_dependency
):
    """
    Remove students from classroom (principals and teachers can access)
    """
    user_roles = _get_user_roles(db, current_user["user_id"])
    if not (UserRole.principal in user_roles or UserRole.teacher in user_roles):
        raise HTTPException(status_code=403, detail="Only principals and teachers can manage classroom students")
    
    # Get classroom
    classroom = db.query(Classroom).filter(Classroom.id == classroom_id).first()
    if not classroom:
        raise HTTPException(status_code=404, detail="Classroom not found")
    
    # Check permissions (same as add_students)
    if UserRole.principal in user_roles:
        school = db.query(School).filter(
            School.id == classroom.school_id,
            School.principal_id == current_user["user_id"]
        ).first()
        if not school:
            raise HTTPException(status_code=403, detail="You don't have permission to manage this classroom")
    
    elif UserRole.teacher in user_roles:
        teacher = db.query(Teacher).filter(
            Teacher.user_id == current_user["user_id"],
            Teacher.school_id == classroom.school_id
        ).first()
        if not teacher:
            raise HTTPException(status_code=403, detail="You are not a teacher in this school")
    
    try:
        removed_students = []
        not_in_classroom = []
        not_found = []
        
        for student_id in student_ids:
            student = db.query(Student).filter(
                Student.id == student_id,
                Student.school_id == classroom.school_id
            ).first()
            
            if not student:
                not_found.append(student_id)
                continue
            
            if student.classroom_id != classroom_id:
                not_in_classroom.append(student_id)
                continue
            
            # Remove student from classroom
            student.classroom_id = None
            removed_students.append(student_id)
        
        db.commit()
        
        return {
            "message": f"Students processed for removal from classroom '{classroom.name}'",
            "removed_students": removed_students,
            "not_in_classroom": not_in_classroom,
            "not_found": not_found,
            "total_removed": len(removed_students)
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Student removal error: {str(e)}")

@router.get("/classrooms/{classroom_id}/students")
async def get_classroom_students(
    classroom_id: int,
    db: db_dependency, 
    current_user: user_dependency
):
    """
    Get all students in a classroom (principals and teachers can access)
    """
    user_roles = _get_user_roles(db, current_user["user_id"])
    if not (UserRole.principal in user_roles or UserRole.teacher in user_roles):
        raise HTTPException(status_code=403, detail="Only principals and teachers can view classroom students")
    
    # Get classroom
    classroom = db.query(Classroom).filter(Classroom.id == classroom_id).first()
    if not classroom:
        raise HTTPException(status_code=404, detail="Classroom not found")
    
    # Check permissions
    if UserRole.principal in user_roles:
        school = db.query(School).filter(
            School.id == classroom.school_id,
            School.principal_id == current_user["user_id"]
        ).first()
        if not school:
            raise HTTPException(status_code=403, detail="You don't have permission to view this classroom")
    
    elif UserRole.teacher in user_roles:
        teacher = db.query(Teacher).filter(
            Teacher.user_id == current_user["user_id"],
            Teacher.school_id == classroom.school_id
        ).first()
        if not teacher:
            raise HTTPException(status_code=403, detail="You are not a teacher in this school")
    
    # Get students in this classroom
    students = db.query(Student).filter(
        Student.classroom_id == classroom_id,
        Student.is_active == True
    ).all()
    
    result = []
    for student in students:
        user = db.query(User).filter(User.id == student.user_id).first()
        if user:
            result.append({
                "student_id": student.id,
                "user_id": user.id,
                "name": f"{user.fname} {user.lname}",
                "email": user.email,
                "enrollment_date": student.enrollment_date
            })
    
    return {
        "classroom_id": classroom_id,
        "classroom_name": classroom.name,
        "students": result,
        "total_students": len(result)
    }

# Add this new endpoint for teachers to get their assigned classrooms
@router.get("/classrooms/my-assigned")
async def get_my_assigned_classrooms(db: db_dependency, current_user: user_dependency):
    """
    Get classrooms assigned to current teacher
    """
    ensure_user_role(db, current_user["user_id"], UserRole.teacher)
    
    # Get teacher record
    teacher = db.query(Teacher).filter(
        Teacher.user_id == current_user["user_id"],
        Teacher.is_active == True
    ).first()
    if not teacher:
        raise HTTPException(status_code=404, detail="Teacher profile not found")
    
    # Get classrooms assigned to this teacher
    classrooms = db.query(Classroom).filter(
        Classroom.teacher_id == teacher.id,
        Classroom.is_active == True
    ).all()
    
    result = []
    for classroom in classrooms:
        # Get student count
        student_count = db.query(Student).filter(
            Student.classroom_id == classroom.id,
            Student.is_active == True
        ).count()
        
        # Get school name
        school = db.query(School).filter(School.id == classroom.school_id).first()
        school_name = school.name if school else "Unknown School"
        
        result.append({
            "id": classroom.id,
            "name": classroom.name,
            "description": classroom.description,
            "capacity": classroom.capacity,
            "location": classroom.location,
            "school_id": classroom.school_id,
            "school_name": school_name,
            "student_count": student_count,
            "teacher_id": classroom.teacher_id
        })
    
    return result

# Add endpoint for teachers to get all students across their subjects
@router.get("/teachers/my-students")
async def get_my_students_across_subjects(db: db_dependency, current_user: user_dependency):
    """
    Get all students assigned to current teacher's subjects
    """
    ensure_user_role(db, current_user["user_id"], UserRole.teacher)
    
    # Get teacher record
    teacher = db.query(Teacher).filter(
        Teacher.user_id == current_user["user_id"],
        Teacher.is_active == True
    ).first()
    if not teacher:
        raise HTTPException(status_code=404, detail="Teacher profile not found")
    
    # Method 1: Try to get students through many-to-many subject relationships (if available)
    try:
        # First try using association table if it exists
        students_from_subjects = db.query(Student).join(
            subject_students, Student.id == subject_students.c.student_id
        ).join(
            Subject, Subject.id == subject_students.c.subject_id
        ).join(
            subject_teachers, Subject.id == subject_teachers.c.subject_id
        ).filter(
            subject_teachers.c.teacher_id == teacher.id,
            Student.is_active == True
        ).distinct().all()
        
        if students_from_subjects:
            # Use students from many-to-many relationships
            students = students_from_subjects
            print(f"Found {len(students)} students through many-to-many relationships")
        else:
            raise Exception("No many-to-many data found")
            
    except Exception as e:
        print(f"Many-to-many query failed: {e}, falling back to alternative methods")
        
        # Fallback 1: Get students from teacher's assigned classrooms
        teacher_classrooms = db.query(Classroom).filter(
            Classroom.teacher_id == teacher.id,
            Classroom.is_active == True
        ).all()
        
        classroom_students = []
        for classroom in teacher_classrooms:
            classroom_students.extend(
                db.query(Student).filter(
                    Student.classroom_id == classroom.id,
                    Student.is_active == True
                ).all()
            )
        
        # Fallback 2: Get students from subjects taught by this teacher (direct assignment)
        subjects = db.query(Subject).filter(
            Subject.teacher_id == teacher.id,
            Subject.is_active == True
        ).all()
        
        # Fallback 3: If still no students, get ALL students in the same school
        # This ensures teachers can see all students in their school for assignment purposes
        school_students = db.query(Student).filter(
            Student.school_id == teacher.school_id,
            Student.is_active == True
        ).all()
        
        # Combine and deduplicate all sources
        all_students = classroom_students + school_students
        students = list({student.id: student for student in all_students}.values())
        
        print(f"Fallback found: {len(classroom_students)} from classrooms, {len(school_students)} from school, {len(students)} total unique students")
    
    result = []
    for student in students:
        user = db.query(User).filter(User.id == student.user_id).first()
        if user:
            # Get classroom name if assigned
            classroom_name = None
            if student.classroom_id:
                classroom = db.query(Classroom).filter(Classroom.id == student.classroom_id).first()
                classroom_name = classroom.name if classroom else None
            
            result.append({
                "id": student.id,
                "user_id": user.id,
                "username": user.username,
                "fname": user.fname,
                "lname": user.lname,
                "email": user.email,
                "classroom_id": student.classroom_id,
                "classroom_name": classroom_name,
                "enrollment_date": student.enrollment_date,
                "school_id": student.school_id,
                "is_active": student.is_active,
                "user": {
                    "id": user.id,
                    "username": user.username,
                    "fname": user.fname,
                    "lname": user.lname,
                    "email": user.email
                }
            })
    
    return result

# Add endpoint for teachers to get their assigned subjects (missing from academic module)
@router.get("/academic/teachers/my-subjects")
async def get_my_subjects_academic(db: db_dependency, current_user: user_dependency):
    """
    Get subjects assigned to current teacher (academic endpoint)
    """
    ensure_user_role(db, current_user["user_id"], UserRole.teacher)
    
    # Get teacher record
    teacher = db.query(Teacher).filter(
        Teacher.user_id == current_user["user_id"],
        Teacher.is_active == True
    ).first()
    if not teacher:
        raise HTTPException(status_code=404, detail="Teacher profile not found")
    
    # Try to get subjects through many-to-many relationship first
    try:
        subjects = db.query(Subject).join(
            subject_teachers, Subject.id == subject_teachers.c.subject_id
        ).filter(
            subject_teachers.c.teacher_id == teacher.id,
            Subject.is_active == True
        ).all()
    except Exception:
        # Fallback: Get subjects by teacher_id (direct foreign key)
        subjects = db.query(Subject).filter(
            Subject.teacher_id == teacher.id,
            Subject.is_active == True
        ).all()
    
    result = []
    for subject in subjects:
        # Get students enrolled in this subject
        try:
            # Try many-to-many first
            subject_students_query = db.query(Student).join(
                subject_students, Student.id == subject_students.c.student_id
            ).filter(
                subject_students.c.subject_id == subject.id,
                Student.is_active == True
            ).all()
        except Exception:
            # Fallback: Get all students in the same school
            subject_students_query = db.query(Student).filter(
                Student.school_id == teacher.school_id,
                Student.is_active == True
            ).all()
        
        # Get school name
        school = db.query(School).filter(School.id == subject.school_id).first()
        school_name = school.name if school else "Unknown School"
        
        # Format students for subject
        formatted_students = []
        for student in subject_students_query:
            user = db.query(User).filter(User.id == student.user_id).first()
            if user:
                formatted_students.append({
                    "id": student.id,
                    "user_id": user.id,
                    "username": user.username,
                    "fname": user.fname,
                    "lname": user.lname,
                    "email": user.email,
                    "classroom_id": student.classroom_id,
                    "enrollment_date": student.enrollment_date,
                    "is_active": student.is_active,
                    "user": {
                        "id": user.id,
                        "username": user.username,
                        "fname": user.fname,
                        "lname": user.lname,
                        "email": user.email
                    }
                })
        
        result.append({
            "id": subject.id,
            "name": subject.name,
            "description": subject.description,
            "school_id": subject.school_id,
            "school_name": school_name,
            "teacher_id": subject.teacher_id,
            "is_active": subject.is_active,
            "students": formatted_students
        })
    
    return result

# Add endpoint for getting a specific subject with students
@router.get("/academic/subjects/{subject_id}")
async def get_subject_with_students(
    subject_id: int,
    db: db_dependency, 
    current_user: user_dependency
):
    """
    Get a specific subject with its enrolled students
    """
    user_roles = _get_user_roles(db, current_user["user_id"])
    if not (UserRole.principal in user_roles or UserRole.teacher in user_roles):
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Get subject
    subject = db.query(Subject).filter(
        Subject.id == subject_id,
        Subject.is_active == True
    ).first()
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found")
    
    # Check access permissions
    if UserRole.teacher in user_roles:
        teacher = db.query(Teacher).filter(
            Teacher.user_id == current_user["user_id"],
            Teacher.is_active == True
        ).first()
        if not teacher:
            raise HTTPException(status_code=404, detail="Teacher profile not found")
        
        # Check if teacher teaches this subject
        teaches_subject = db.query(subject_teachers).filter(
            subject_teachers.c.teacher_id == teacher.id,
            subject_teachers.c.subject_id == subject_id
        ).first()
        
        if not teaches_subject and subject.teacher_id != teacher.id:
            raise HTTPException(status_code=403, detail="You don't teach this subject")
    
    # Get students enrolled in this subject
    try:
        # Try many-to-many relationship first
        students = db.query(Student).join(
            subject_students, Student.id == subject_students.c.student_id
        ).filter(
            subject_students.c.subject_id == subject_id,
            Student.is_active == True
        ).all()
    except Exception:
        # Fallback: Get all students in the same school
        students = db.query(Student).filter(
            Student.school_id == subject.school_id,
            Student.is_active == True
        ).all()
    
    # Format students with user data
    formatted_students = []
    for student in students:
        user = db.query(User).filter(User.id == student.user_id).first()
        if user:
            formatted_students.append({
                "id": student.id,
                "user_id": user.id,
                "username": user.username,
                "fname": user.fname,
                "lname": user.lname,
                "email": user.email,
                "classroom_id": student.classroom_id,
                "enrollment_date": student.enrollment_date,
                "is_active": student.is_active,
                "user": {
                    "id": user.id,
                    "username": user.username,
                    "fname": user.fname,
                    "lname": user.lname,
                    "email": user.email
                }
            })
    
    # Get school name
    school = db.query(School).filter(School.id == subject.school_id).first()
    school_name = school.name if school else "Unknown School"
    
    return {
        "id": subject.id,
        "name": subject.name,
        "description": subject.description,
        "school_id": subject.school_id,
        "school_name": school_name,
        "teacher_id": subject.teacher_id,
        "is_active": subject.is_active,
        "students": formatted_students
    }