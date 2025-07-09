from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, Depends, status
from typing import Annotated, List
from sqlalchemy.orm import Session
from sqlalchemy import func

from db.connection import db_dependency
from models.study_area_models import (
    Role, School, Subject, Student, Teacher, UserRole, Assignment, Grade
)
from models.users_models import User
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
from schemas.direct_join_schemas import SchoolSelectionResponse
# Import shared utility functions
from Endpoints.utils import (
    _get_user_roles, check_user_role, ensure_user_role, check_user_has_any_role, 
    ensure_user_has_any_role
)

router = APIRouter(tags=["Academic Management", "Subjects", "Assignments"])

user_dependency = Annotated[dict, Depends(get_current_user)]

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
    Get all subjects the current student is enrolled in
    """
    ensure_user_role(db, current_user["user_id"], UserRole.student)
    
    # Get student record
    student = db.query(Student).filter(
        Student.user_id == current_user["user_id"],
        Student.is_active == True
    ).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student profile not found")
    
    # Get subjects the student is enrolled in
    try:
        # Try many-to-many relationship first
        from models.study_area_models import subject_students
        subjects = db.query(Subject).join(
            subject_students, Subject.id == subject_students.c.subject_id
        ).filter(
            subject_students.c.student_id == student.id,
            Subject.is_active == True
        ).all()
    except Exception:
        # Fallback: get all subjects in the same school
        subjects = db.query(Subject).filter(
            Subject.school_id == student.school_id,
            Subject.is_active == True
        ).all()
    
    return subjects

@router.get("/academic/subjects/{subject_id}/classmates")
async def get_subject_classmates(
    subject_id: int,
    db: db_dependency, 
    current_user: user_dependency
):
    """
    Get list of other students in the same subject (students only)
    """
    ensure_user_role(db, current_user["user_id"], UserRole.student)
    
    # Get current student
    current_student = db.query(Student).filter(
        Student.user_id == current_user["user_id"],
        Student.is_active == True
    ).first()
    if not current_student:
        raise HTTPException(status_code=404, detail="Student profile not found")
    
    # Get subject and verify student is enrolled
    subject = db.query(Subject).filter(
        Subject.id == subject_id,
        Subject.is_active == True
    ).first()
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found")
    
    # Check if current student is enrolled in this subject
    try:
        from models.study_area_models import subject_students
        enrollment = db.query(subject_students).filter(
            subject_students.c.subject_id == subject_id,
            subject_students.c.student_id == current_student.id
        ).first()
        
        if not enrollment:
            raise HTTPException(status_code=403, detail="You are not enrolled in this subject")
    except Exception:
        # Fallback: check if subject is in same school
        if subject.school_id != current_student.school_id:
            raise HTTPException(status_code=403, detail="You are not enrolled in this subject")
    
    # Get all students in this subject (excluding current student)
    try:
        classmates = db.query(Student).join(
            subject_students, Student.id == subject_students.c.student_id
        ).filter(
            subject_students.c.subject_id == subject_id,
            Student.id != current_student.id,
            Student.is_active == True
        ).all()
    except Exception:
        # Fallback: get all students in the same school
        classmates = db.query(Student).filter(
            Student.school_id == current_student.school_id,
            Student.id != current_student.id,
            Student.is_active == True
        ).all()
    
    # Format response
    result = []
    for student in classmates:
        user = db.query(User).filter(User.id == student.user_id).first()
        if user:
            result.append({
                "id": student.id,
                "user_id": user.id,
                "name": f"{user.fname} {user.lname}",
                "email": user.email,
                "enrollment_date": student.enrollment_date
            })
    
    return result

# === ASSIGNMENT ENDPOINTS ===

@router.post("/assignments/create", response_model=AssignmentResponse)
async def create_assignment(
    assignment: AssignmentCreate,
    db: db_dependency,
    current_user: user_dependency
):
    """
    Create a new assignment (teachers only - for subjects they teach)
    """
    ensure_user_role(db, current_user["user_id"], UserRole.teacher)
    
    # Get teacher and verify they teach this subject
    teacher = db.query(Teacher).filter(Teacher.user_id == current_user["user_id"]).first()
    if not teacher:
        raise HTTPException(status_code=404, detail="Teacher profile not found")
    
    subject = db.query(Subject).filter(Subject.id == assignment.subject_id).first()
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found")
    
    if subject not in teacher.subjects:
        raise HTTPException(status_code=403, detail="You are not assigned to teach this subject")
    
    try:
        db_assignment = Assignment(
            title=assignment.title,
            description=assignment.description,
            subtopic=assignment.subtopic,
            subject_id=assignment.subject_id,
            teacher_id=teacher.id,
            due_date=assignment.due_date,
            max_points=assignment.max_points
        )
        db.add(db_assignment)
        db.commit()
        db.refresh(db_assignment)
        return db_assignment
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Assignment creation error: {str(e)}")

@router.get("/assignments/subject/{subject_id}", response_model=List[AssignmentResponse])
async def get_subject_assignments(
    subject_id: int,
    db: db_dependency,
    current_user: user_dependency
):
    """
    Get all assignments for a subject (teachers and students in the subject)
    """
    subject = db.query(Subject).filter(Subject.id == subject_id).first()
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found")
    
    # Check if user has access to this subject
    user_roles = _get_user_roles(db, current_user["user_id"])
    has_access = False
    
    if UserRole.teacher in user_roles:
        teacher = db.query(Teacher).filter(Teacher.user_id == current_user["user_id"]).first()
        if teacher and subject in teacher.subjects:
            has_access = True
    
    if UserRole.student in user_roles:
        student = db.query(Student).filter(Student.user_id == current_user["user_id"]).first()
        if student and subject in student.subjects:
            has_access = True
    
    if UserRole.principal in user_roles:
        school = db.query(School).filter(
            School.id == subject.school_id,
            School.principal_id == current_user["user_id"]
        ).first()
        if school:
            has_access = True
    
    if not has_access:
        raise HTTPException(status_code=403, detail="Access denied to this subject")
    
    assignments = db.query(Assignment).filter(
        Assignment.subject_id == subject_id,
        Assignment.is_active == True
    ).all()
    
    return assignments

@router.put("/assignments/{assignment_id}", response_model=AssignmentResponse)
async def update_assignment(
    assignment_id: int,
    assignment_update: AssignmentUpdate,
    db: db_dependency,
    current_user: user_dependency
):
    """
    Update an assignment (only the teacher who created it)
    """
    ensure_user_role(db, current_user["user_id"], UserRole.teacher)
    
    assignment = db.query(Assignment).filter(Assignment.id == assignment_id).first()
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")
    
    # Get teacher to verify ownership
    teacher = db.query(Teacher).filter(Teacher.user_id == current_user["user_id"]).first()
    if not teacher:
        raise HTTPException(status_code=404, detail="Teacher profile not found")
    
    if assignment.teacher_id != teacher.id:
        raise HTTPException(status_code=403, detail="You can only edit assignments you created")
    
    try:
        if assignment_update.title is not None:
            assignment.title = assignment_update.title
        if assignment_update.description is not None:
            assignment.description = assignment_update.description
        if assignment_update.due_date is not None:
            assignment.due_date = assignment_update.due_date
        if assignment_update.max_points is not None:
            assignment.max_points = assignment_update.max_points
        
        db.commit()
        db.refresh(assignment)
        return assignment
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Assignment update error: {str(e)}")

@router.delete("/assignments/{assignment_id}")
async def delete_assignment(
    assignment_id: int,
    db: db_dependency,
    current_user: user_dependency
):
    """
    Delete (deactivate) an assignment (only the teacher who created it)
    """
    ensure_user_role(db, current_user["user_id"], UserRole.teacher)
    
    assignment = db.query(Assignment).filter(Assignment.id == assignment_id).first()
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")
    
    # Get teacher to verify ownership
    teacher = db.query(Teacher).filter(Teacher.user_id == current_user["user_id"]).first()
    if not teacher:
        raise HTTPException(status_code=404, detail="Teacher profile not found")
    
    if assignment.teacher_id != teacher.id:
        raise HTTPException(status_code=403, detail="You can only delete assignments you created")
    
    try:
        assignment.is_active = False
        db.commit()
        return {"message": f"Assignment '{assignment.title}' has been deactivated"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Assignment deletion error: {str(e)}")

# === GRADE ENDPOINTS ===

@router.post("/grades/create", response_model=GradeResponse)
async def create_grade(
    grade: GradeCreate,
    db: db_dependency,
    current_user: user_dependency
):
    """
    Create or update a grade for a student's assignment (teachers only)
    """
    ensure_user_role(db, current_user["user_id"], UserRole.teacher)
    
    # Verify teacher teaches the subject of this assignment
    assignment = db.query(Assignment).join(Subject).filter(Assignment.id == grade.assignment_id).first()
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")
    
    teacher = db.query(Teacher).filter(Teacher.user_id == current_user["user_id"]).first()
    if not teacher or assignment.subject not in teacher.subjects:
        raise HTTPException(status_code=403, detail="You are not authorized to grade this assignment")
    
    # Verify student is enrolled in the subject
    student = db.query(Student).filter(Student.id == grade.student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    
    if assignment.subject not in student.subjects:
        raise HTTPException(status_code=400, detail="Student is not enrolled in this subject")
    
    # Check if grade already exists
    existing_grade = db.query(Grade).filter(
        Grade.assignment_id == grade.assignment_id,
        Grade.student_id == grade.student_id
    ).first()
    
    if existing_grade:
        # Update existing grade
        try:
            existing_grade.points_earned = grade.points_earned
            existing_grade.feedback = grade.comments
            existing_grade.teacher_id = teacher.id
            existing_grade.graded_date = datetime.utcnow()
            
            db.commit()
            db.refresh(existing_grade)
            return existing_grade
        except Exception as e:
            db.rollback()
            raise HTTPException(status_code=500, detail=f"Grade update error: {str(e)}")
    else:
        # Create new grade
        try:
            db_grade = Grade(
                assignment_id=grade.assignment_id,
                student_id=grade.student_id,
                teacher_id=teacher.id,
                points_earned=grade.points_earned,
                feedback=grade.feedback
            )
            db.add(db_grade)
            db.commit()
            db.refresh(db_grade)
            return db_grade
        except Exception as e:
            db.rollback()
            raise HTTPException(status_code=500, detail=f"Grade creation error: {str(e)}")

@router.get("/grades/assignment/{assignment_id}", response_model=List[GradeResponse])
async def get_assignment_grades(
    assignment_id: int,
    db: db_dependency,
    current_user: user_dependency
):
    """
    Get all grades for an assignment (teachers who teach the subject)
    """
    ensure_user_role(db, current_user["user_id"], UserRole.teacher)
    
    assignment = db.query(Assignment).join(Subject).filter(Assignment.id == assignment_id).first()
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")
    
    teacher = db.query(Teacher).filter(Teacher.user_id == current_user["user_id"]).first()
    if not teacher or assignment.subject not in teacher.subjects:
        raise HTTPException(status_code=403, detail="Access denied")
    
    grades = db.query(Grade).filter(Grade.assignment_id == assignment_id).all()
    return grades

@router.get("/grades/student/{student_id}/subject/{subject_id}", response_model=StudentGradeReport)
async def get_student_grades_in_subject(
    student_id: int,
    subject_id: int,
    db: db_dependency,
    current_user: user_dependency
):
    """
    Get all grades for a student in a specific subject (teachers and the student themselves)
    """
    # Verify access
    user_roles = _get_user_roles(db, current_user["user_id"])
    
    if UserRole.student in user_roles:
        # Students can only view their own grades
        student = db.query(Student).filter(
            Student.id == student_id,
            Student.user_id == current_user["user_id"]
        ).first()
        if not student:
            raise HTTPException(status_code=403, detail="You can only view your own grades")
    
    elif UserRole.teacher in user_roles:
        # Teachers can view grades for subjects they teach
        teacher = db.query(Teacher).filter(Teacher.user_id == current_user["user_id"]).first()
        subject = db.query(Subject).filter(Subject.id == subject_id).first()
        if not teacher or not subject or subject not in teacher.subjects:
            raise HTTPException(status_code=403, detail="Access denied")
    
    else:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Get student and subject
    student = db.query(Student).filter(Student.id == student_id).first()
    subject = db.query(Subject).filter(Subject.id == subject_id).first()
    
    if not student or not subject:
        raise HTTPException(status_code=404, detail="Student or subject not found")
    
    # Get all assignments and grades for this student in this subject
    assignments_with_grades = []
    assignments = db.query(Assignment).filter(
        Assignment.subject_id == subject_id,
        Assignment.is_active == True
    ).all()
    
    total_points_possible = 0
    total_points_earned = 0
    
    for assignment in assignments:
        grade = db.query(Grade).filter(
            Grade.assignment_id == assignment.id,
            Grade.student_id == student_id
        ).first()
        
        assignment_info = {
            "assignment": assignment,
            "grade": grade
        }
        assignments_with_grades.append(assignment_info)
        
        total_points_possible += assignment.max_points
        if grade:
            total_points_earned += grade.points_earned
    
    percentage = (total_points_earned / total_points_possible * 100) if total_points_possible > 0 else 0
    
    return StudentGradeReport(
        student_id=student_id,
        student_name=f"{student.user.fname} {student.user.lname}",
        subject_id=subject_id,
        subject_name=subject.name,
        assignments=assignments_with_grades,
        total_points_possible=total_points_possible,
        total_points_earned=total_points_earned,
        percentage=round(percentage, 2)
    )

@router.post("/grades/bulk", response_model=BulkGradeResponse)
async def create_bulk_grades(
    bulk_grades: BulkGradeCreate,
    db: db_dependency,
    current_user: user_dependency
):
    """
    Create or update multiple grades at once (teachers only)
    """
    ensure_user_role(db, current_user["user_id"], UserRole.teacher)
    
    # Verify teacher teaches the subject of this assignment
    assignment = db.query(Assignment).join(Subject).filter(Assignment.id == bulk_grades.assignment_id).first()
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")
    
    teacher = db.query(Teacher).filter(Teacher.user_id == current_user["user_id"]).first()
    if not teacher or assignment.subject not in teacher.subjects:
        raise HTTPException(status_code=403, detail="You are not authorized to grade this assignment")
    
    created_grades = []
    updated_grades = []
    errors = []
    
    try:
        for grade_data in bulk_grades.grades:
            # Verify student is enrolled in the subject
            student = db.query(Student).filter(Student.id == grade_data.student_id).first()
            if not student:
                errors.append(f"Student ID {grade_data.student_id} not found")
                continue
            
            if assignment.subject not in student.subjects:
                errors.append(f"Student ID {grade_data.student_id} is not enrolled in this subject")
                continue
            
            # Check if grade already exists
            existing_grade = db.query(Grade).filter(
                Grade.assignment_id == bulk_grades.assignment_id,
                Grade.student_id == grade_data.student_id
            ).first()
            
            if existing_grade:
                # Update existing grade
                existing_grade.points_earned = grade_data.points_earned
                existing_grade.feedback = grade_data.comments
                existing_grade.teacher_id = teacher.id
                existing_grade.graded_date = datetime.utcnow()
                updated_grades.append(existing_grade)
            else:
                # Create new grade
                new_grade = Grade(
                    assignment_id=bulk_grades.assignment_id,
                    student_id=grade_data.student_id,
                    teacher_id=teacher.id,
                    points_earned=grade_data.points_earned,
                    feedback=grade_data.comments
                )
                db.add(new_grade)
                created_grades.append(new_grade)
        
        db.commit()
        
        # Refresh all new grades
        for grade in created_grades:
            db.refresh(grade)
        
        return BulkGradeResponse(
            assignment_id=bulk_grades.assignment_id,
            created_count=len(created_grades),
            updated_count=len(updated_grades),
            error_count=len(errors),
            created_grades=created_grades,
            updated_grades=updated_grades,
            errors=errors
        )
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Bulk grade creation error: {str(e)}")

# === ACADEMIC STATUS ENDPOINTS ===

@router.get("/schools/available", response_model=List[SchoolSelectionResponse])
async def get_available_schools(
    db: db_dependency,
    current_user: user_dependency
):
    """
    Get list of all available schools for users to join (academic context)
    """
    schools = db.query(School).filter(School.is_active == True).all()
    
    school_list = []
    for school in schools:
        # Get principal info
        principal = db.query(User).filter(User.id == school.principal_id).first()
        
        # Get stats
        total_students = db.query(Student).filter(Student.school_id == school.id).count()
        total_teachers = db.query(Teacher).filter(Teacher.school_id == school.id).count()
        total_subjects = db.query(Subject).filter(
            Subject.school_id == school.id,
            Subject.is_active == True
        ).count()
        
        school_info = SchoolSelectionResponse(
            id=school.id,
            name=school.name,
            address=school.address or "Address not provided",
            principal_name=f"{principal.fname} {principal.lname}" if principal else "No Principal Assigned",
            total_students=total_students,
            total_teachers=total_teachers,
            total_subjects=total_subjects,
            is_accepting_applications=True,
            created_date=school.created_date
        )
        school_list.append(school_info)
    
    return school_list

@router.get("/user/academic-status")
async def get_user_academic_status(db: db_dependency, current_user: user_dependency):
    """
    Get comprehensive academic status for current user including subjects, assignments, grades
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
    
    # Add role-specific academic information
    if UserRole.student in user_roles:
        student_records = db.query(Student).filter(Student.user_id == user.id).all()
        if student_records:
            student_academic_info = []
            for student in student_records:
                school = db.query(School).filter(School.id == student.school_id).first()
                subjects = student.subjects
                
                subject_summaries = []
                for subject in subjects:
                    # Get assignment count and grade average
                    assignments = db.query(Assignment).filter(
                        Assignment.subject_id == subject.id,
                        Assignment.is_active == True
                    ).all()
                    
                    grades = db.query(Grade).join(Assignment).filter(
                        Assignment.subject_id == subject.id,
                        Grade.student_id == student.id
                    ).all()
                    
                    total_possible = sum(a.max_points for a in assignments)
                    total_earned = sum(g.points_earned for g in grades)
                    percentage = (total_earned / total_possible * 100) if total_possible > 0 else 0;
                    
                    subject_summaries.append({
                        "subject_id": subject.id,
                        "subject_name": subject.name,
                        "assignments_count": len(assignments),
                        "grades_count": len(grades),
                        "current_percentage": round(percentage, 2)
                    })
                
                student_academic_info.append({
                    "school_id": school.id,
                    "school_name": school.name,
                    "student_id": student.id,
                    "subjects": subject_summaries
                })
            
            status["student_academic_info"] = student_academic_info
    
    if UserRole.teacher in user_roles:
        teacher_records = db.query(Teacher).filter(Teacher.user_id == user.id).all()
        if teacher_records:
            teacher_academic_info = []
            for teacher in teacher_records:
                school = db.query(School).filter(School.id == teacher.school_id).first()
                subjects = teacher.subjects
                
                subject_summaries = []
                for subject in subjects:
                    # Get assignment and student counts
                    assignments_count = db.query(Assignment).filter(
                        Assignment.subject_id == subject.id,
                        Assignment.is_active == True
                    ).count()
                    
                    students_count = len(subject.students)
                    
                    subject_summaries.append({
                        "subject_id": subject.id,
                        "subject_name": subject.name,
                        "assignments_count": assignments_count,
                        "students_count": students_count
                    })
                
                teacher_academic_info.append({
                    "school_id": school.id,
                    "school_name": school.name,
                    "teacher_id": teacher.id,
                    "subjects": subject_summaries
                })
            
            status["teacher_academic_info"] = teacher_academic_info
    
    if UserRole.principal in user_roles:
        school = db.query(School).filter(School.principal_id == user.id).first()
        if school:
            # Get comprehensive school academic statistics
            total_subjects = db.query(Subject).filter(
                Subject.school_id == school.id,
                Subject.is_active == True
            ).count()
            
            total_assignments = db.query(Assignment).join(Subject).filter(
                Subject.school_id == school.id,
                Assignment.is_active == True
            ).count()
            
            total_grades = db.query(Grade).join(Assignment).join(Subject).filter(
                Subject.school_id == school.id
            ).count()
            
            status["principal_academic_info"] = {
                "school_id": school.id,
                "school_name": school.name,
                "total_subjects": total_subjects,
                "total_assignments": total_assignments,
                "total_grades": total_grades
            }
    
    return status

# === PRINCIPAL-SPECIFIC SUBJECT MANAGEMENT ENDPOINTS ===

@router.post("/subjects/principal/add-student")
async def principal_add_student_to_subject(
    assignment: SubjectStudentAssignment,
    db: db_dependency,
    current_user: user_dependency
):
    """
    Add a student to a subject (principals only for their school subjects)
    """
    ensure_user_role(db, current_user["user_id"], UserRole.principal)
    
    # Get subject and verify principal owns the school
    subject = db.query(Subject).join(School).filter(
        Subject.id == assignment.subject_id,
        School.principal_id == current_user["user_id"]
    ).first()
    
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found or not in your school")
    
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

@router.delete("/subjects/principal/remove-student")
async def principal_remove_student_from_subject(
    assignment: SubjectStudentAssignment,
    db: db_dependency,
    current_user: user_dependency
):
    """
    Remove a student from a subject (principals only for their school subjects)
    """
    ensure_user_role(db, current_user["user_id"], UserRole.principal)
    
    # Get subject and verify principal owns the school
    subject = db.query(Subject).join(School).filter(
        Subject.id == assignment.subject_id,
        School.principal_id == current_user["user_id"]
    ).first()
    
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found or not in your school")
    
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

# === STUDENT-SPECIFIC ENDPOINTS FOR STUDY CENTRE ===

@router.get("/students/my-assignments")
async def get_my_assignments(db: db_dependency, current_user: user_dependency):
    """
    Get all assignments for current student across all their subjects
    """
    ensure_user_role(db, current_user["user_id"], UserRole.student)
    
    # Get student record
    student = db.query(Student).filter(
        Student.user_id == current_user["user_id"],
        Student.is_active == True
    ).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student profile not found")
    
    # Get all subjects the student is enrolled in
    try:
        from models.study_area_models import subject_students
        subjects = db.query(Subject).join(
            subject_students, Subject.id == subject_students.c.subject_id
        ).filter(
            subject_students.c.student_id == student.id,
            Subject.is_active == True
        ).all()
    except Exception:
        # Fallback: get all subjects in the same school
        subjects = db.query(Subject).filter(
            Subject.school_id == student.school_id,
            Subject.is_active == True
        ).all()
    
    # Get assignments for each subject
    all_assignments = []
    for subject in subjects:
        assignments = db.query(Assignment).filter(
            Assignment.subject_id == subject.id,
            Assignment.is_active == True
        ).all()
        
        for assignment in assignments:
            # Check if student has a grade for this assignment
            grade = db.query(Grade).filter(
                Grade.assignment_id == assignment.id,
                Grade.student_id == student.id
            ).first()
            
            # Get teacher info
            teacher = db.query(Teacher).filter(Teacher.id == assignment.teacher_id).first()
            teacher_name = f"{teacher.user.fname} {teacher.user.lname}" if teacher else "Unknown Teacher"
            
            assignment_data = {
                "assignment_id": assignment.id,
                "title": assignment.title,
                "description": assignment.description,
                "subtopic": assignment.subtopic,
                "subject_id": subject.id,
                "subject_name": subject.name,
                "teacher_name": teacher_name,
                "due_date": assignment.due_date,
                "max_points": assignment.max_points,
                "created_date": assignment.created_date,
                "is_completed": grade is not None,
                "grade": {
                    "points_earned": grade.points_earned,
                    "feedback": grade.feedback,
                    "graded_date": grade.graded_date
                } if grade else None,
                "status": "completed" if grade else ("overdue" if assignment.due_date and assignment.due_date < datetime.utcnow() else "pending")
            }
            all_assignments.append(assignment_data)
    
    # Sort by due date (upcoming first, then by creation date)
    all_assignments.sort(key=lambda x: (
        x["due_date"] or datetime.max.replace(tzinfo=None),
        x["created_date"]
    ))
    
    return {
        "student_id": student.id,
        "total_assignments": len(all_assignments),
        "completed_assignments": len([a for a in all_assignments if a["is_completed"]]),
        "pending_assignments": len([a for a in all_assignments if not a["is_completed"]]),
        "assignments": all_assignments
    }

@router.get("/students/my-grades")
async def get_my_grades(db: db_dependency, current_user: user_dependency):
    """
    Get all grades for current student with detailed breakdown by subject
    """
    ensure_user_role(db, current_user["user_id"], UserRole.student)
    
    # Get student record
    student = db.query(Student).filter(
        Student.user_id == current_user["user_id"],
        Student.is_active == True
    ).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student profile not found")
    
    # Get all grades for this student
    grades = db.query(Grade).join(Assignment).join(Subject).filter(
        Grade.student_id == student.id
    ).all()
    
    # Group grades by subject
    subjects_grades = {}
    for grade in grades:
        subject_id = grade.assignment.subject_id
        subject_name = grade.assignment.subject.name
        
        if subject_id not in subjects_grades:
            subjects_grades[subject_id] = {
                "subject_id": subject_id,
                "subject_name": subject_name,
                "grades": [],
                "total_points_earned": 0,
                "total_points_possible": 0,
                "assignment_count": 0
            }
        
        grade_data = {
            "grade_id": grade.id,
            "assignment_id": grade.assignment.id,
            "assignment_title": grade.assignment.title,
            "points_earned": grade.points_earned,
            "max_points": grade.assignment.max_points,
            "percentage": round((grade.points_earned / grade.assignment.max_points) * 100, 2),
            "feedback": grade.feedback,
            "graded_date": grade.graded_date,
            "due_date": grade.assignment.due_date
        }
        
        subjects_grades[subject_id]["grades"].append(grade_data)
        subjects_grades[subject_id]["total_points_earned"] += grade.points_earned
        subjects_grades[subject_id]["total_points_possible"] += grade.assignment.max_points
        subjects_grades[subject_id]["assignment_count"] += 1
    
    # Calculate subject averages
    for subject_data in subjects_grades.values():
        if subject_data["total_points_possible"] > 0:
            subject_data["average_percentage"] = round(
                (subject_data["total_points_earned"] / subject_data["total_points_possible"]) * 100, 2
            )
        else:
            subject_data["average_percentage"] = 0
        
        # Sort grades by due date
        subject_data["grades"].sort(key=lambda g: g["due_date"] or datetime.min.replace(tzinfo=None))
    
    # Calculate overall GPA
    total_points_earned = sum(s["total_points_earned"] for s in subjects_grades.values())
    total_points_possible = sum(s["total_points_possible"] for s in subjects_grades.values())
    overall_percentage = round((total_points_earned / total_points_possible) * 100, 2) if total_points_possible > 0 else 0
    
    return {
        "student_id": student.id,
        "overall_percentage": overall_percentage,
        "total_grades": len(grades),
        "subjects_count": len(subjects_grades),
        "subjects": list(subjects_grades.values())
    }

@router.get("/students/my-dashboard")
async def get_student_dashboard(db: db_dependency, current_user: user_dependency):
    """
    Get comprehensive dashboard data for student including assignments, grades, and analytics
    """
    ensure_user_role(db, current_user["user_id"], UserRole.student)
    
    # Get student record
    student = db.query(Student).filter(
        Student.user_id == current_user["user_id"],
        Student.is_active == True
    ).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student profile not found")
    
    # Get student's subjects
    try:
        from models.study_area_models import subject_students
        subjects = db.query(Subject).join(
            subject_students, Subject.id == subject_students.c.subject_id
        ).filter(
            subject_students.c.student_id == student.id,
            Subject.is_active == True
        ).all()
    except Exception:
        subjects = db.query(Subject).filter(
            Subject.school_id == student.school_id,
            Subject.is_active == True
        ).all()
    
    # Get assignments and grades
    total_assignments = 0
    completed_assignments = 0
    pending_assignments = 0
    overdue_assignments = 0
    recent_grades = []
    upcoming_assignments = []
    
    for subject in subjects:
        assignments = db.query(Assignment).filter(
            Assignment.subject_id == subject.id,
            Assignment.is_active == True
        ).all()
        
        for assignment in assignments:
            total_assignments += 1
            
            # Check for grade
            grade = db.query(Grade).filter(
                Grade.assignment_id == assignment.id,
                Grade.student_id == student.id
            ).first()
            
            if grade:
                completed_assignments += 1
                recent_grades.append({
                    "assignment_title": assignment.title,
                    "subject_name": subject.name,
                    "points_earned": grade.points_earned,
                    "max_points": assignment.max_points,
                    "percentage": round((grade.points_earned / assignment.max_points) * 100, 2),
                    "graded_date": grade.graded_date
                })
            else:
                if assignment.due_date and assignment.due_date < datetime.utcnow():
                    overdue_assignments += 1
                else:
                    pending_assignments += 1
                    
                    if assignment.due_date:
                        upcoming_assignments.append({
                            "assignment_title": assignment.title,
                            "subject_name": subject.name,
                            "due_date": assignment.due_date,
                            "max_points": assignment.max_points
                        })
    
    # Sort recent grades by date (most recent first)
    recent_grades.sort(key=lambda g: g["graded_date"], reverse=True)
    recent_grades = recent_grades[:5]  # Latest 5 grades
    
    # Sort upcoming assignments by due date
    upcoming_assignments.sort(key=lambda a: a["due_date"])
    upcoming_assignments = upcoming_assignments[:5]  # Next 5 assignments
    
    # Calculate performance metrics
    all_grades = db.query(Grade).join(Assignment).join(Subject).filter(
        Grade.student_id == student.id
    ).all()
    
    if all_grades:
        total_points_earned = sum(g.points_earned for g in all_grades)
        total_points_possible = sum(g.assignment.max_points for g in all_grades)
        overall_percentage = round((total_points_earned / total_points_possible) * 100, 2)
        
        # Calculate trend (last 30 days vs previous 30 days)
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        sixty_days_ago = datetime.utcnow() - timedelta(days=60)
        
        recent_grades_data = [g for g in all_grades if g.graded_date and g.graded_date >= thirty_days_ago]
        previous_grades_data = [g for g in all_grades if g.graded_date and sixty_days_ago <= g.graded_date < thirty_days_ago]
        
        recent_avg = 0
        previous_avg = 0
        
        if recent_grades_data:
            recent_total_earned = sum(g.points_earned for g in recent_grades_data)
            recent_total_possible = sum(g.assignment.max_points for g in recent_grades_data)
            recent_avg = (recent_total_earned / recent_total_possible) * 100 if recent_total_possible > 0 else 0
        
        if previous_grades_data:
            previous_total_earned = sum(g.points_earned for g in previous_grades_data)
            previous_total_possible = sum(g.assignment.max_points for g in previous_grades_data)
            previous_avg = (previous_total_earned / previous_total_possible) * 100 if previous_total_possible > 0 else 0
        
        trend = "improving" if recent_avg > previous_avg else ("declining" if recent_avg < previous_avg else "stable")
    else:
        overall_percentage = 0
        trend = "no_data"
    
    # Get school info
    school = db.query(School).filter(School.id == student.school_id).first()
    
    return {
        "student_info": {
            "id": student.id,
            "name": f"{student.user.fname} {student.user.lname}",
            "email": student.user.email,
            "school_name": school.name if school else "Unknown School",
            "enrollment_date": student.enrollment_date
        },
        "academic_summary": {
            "subjects_count": len(subjects),
            "total_assignments": total_assignments,
            "completed_assignments": completed_assignments,
            "pending_assignments": pending_assignments,
            "overdue_assignments": overdue_assignments,
            "overall_percentage": overall_percentage,
            "performance_trend": trend
        },
        "recent_grades": recent_grades,
        "upcoming_assignments": upcoming_assignments,
        "subjects": [
            {
                "id": s.id,
                "name": s.name,
                "description": s.description
            } for s in subjects
        ]
    }

@router.get("/students/my-learning-path")
async def get_student_learning_path(db: db_dependency, current_user: user_dependency):
    """
    Generate personalized learning path based on student's performance and weak areas
    """
    ensure_user_role(db, current_user["user_id"], UserRole.student)
    
    # Get student record
    student = db.query(Student).filter(
        Student.user_id == current_user["user_id"],
        Student.is_active == True
    ).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student profile not found")
    
    # Get all grades to analyze performance
    grades = db.query(Grade).join(Assignment).join(Subject).filter(
        Grade.student_id == student.id
    ).all()
    
    if not grades:
        return {
            "student_id": student.id,
            "message": "No grades available yet. Complete some assignments to generate learning path.",
            "learning_path": []
        }
    
    # Analyze performance by subject and topic
    subject_performance = {}
    topic_performance = {}
    
    for grade in grades:
        subject_id = grade.assignment.subject_id
        subject_name = grade.assignment.subject.name
        topic = grade.assignment.subtopic or "General"
        
        percentage = (grade.points_earned / grade.assignment.max_points) * 100
        
        # Track subject performance
        if subject_id not in subject_performance:
            subject_performance[subject_id] = {
                "subject_name": subject_name,
                "grades": [],
                "average": 0
            }
        subject_performance[subject_id]["grades"].append(percentage)
        
        # Track topic performance
        topic_key = f"{subject_name}_{topic}"
        if topic_key not in topic_performance:
            topic_performance[topic_key] = {
                "subject_name": subject_name,
                "topic": topic,
                "grades": [],
                "average": 0
            }
        topic_performance[topic_key]["grades"].append(percentage)
    
    # Calculate averages
    for subject_data in subject_performance.values():
        subject_data["average"] = sum(subject_data["grades"]) / len(subject_data["grades"])
    
    for topic_data in topic_performance.values():
        topic_data["average"] = sum(topic_data["grades"]) / len(topic_data["grades"])
    
    # Generate learning recommendations
    learning_path = []
    
    # Find weak subjects (below 75%)
    weak_subjects = [s for s in subject_performance.values() if s["average"] < 75]
    weak_subjects.sort(key=lambda x: x["average"])  # Weakest first
    
    # Find weak topics (below 70%)
    weak_topics = [t for t in topic_performance.values() if t["average"] < 70]
    weak_topics.sort(key=lambda x: x["average"])  # Weakest first
    
    # Create recommendations
    for subject in weak_subjects[:3]:  # Top 3 weak subjects
        learning_path.append({
            "type": "subject_improvement",
            "title": f"Improve {subject['subject_name']} Performance",
            "description": f"Your average in {subject['subject_name']} is {subject['average']:.1f}%. Focus on completing practice exercises.",
            "priority": "high" if subject["average"] < 60 else "medium",
            "current_score": round(subject["average"], 1),
            "target_score": 80,
            "estimated_time": "2-3 weeks"
        })
    
    for topic in weak_topics[:5]:  # Top 5 weak topics
        learning_path.append({
            "type": "topic_mastery",
            "title": f"Master {topic['topic']} in {topic['subject_name']}",
            "description": f"Focus on {topic['topic']} concepts. Current average: {topic['average']:.1f}%",
            "priority": "high" if topic["average"] < 50 else "medium",
            "current_score": round(topic["average"], 1),
            "target_score": 75,
            "estimated_time": "1-2 weeks"
        })
    
    # Add general recommendations
    if not weak_subjects and not weak_topics:
        learning_path.append({
            "type": "advanced_challenge",
            "title": "Advanced Challenges",
            "description": "Great job! You're performing well. Try some advanced practice problems to push your limits.",
            "priority": "low",
            "current_score": max(s["average"] for s in subject_performance.values()),
            "target_score": 95,
            "estimated_time": "Ongoing"
        })
    
    return {
        "student_id": student.id,
        "analysis_date": datetime.utcnow(),
        "performance_summary": {
            "total_subjects": len(subject_performance),
            "strong_subjects": len([s for s in subject_performance.values() if s["average"] >= 80]),
            "weak_subjects": len(weak_subjects),
            "overall_average": round(sum(s["average"] for s in subject_performance.values()) / len(subject_performance), 2)
        },
        "learning_path": learning_path
    }

@router.get("/students/subject/{subject_id}/progress")
async def get_subject_progress(
    subject_id: int,
    db: db_dependency, 
    current_user: user_dependency
):
    """
    Get detailed progress for a specific subject
    """
    ensure_user_role(db, current_user["user_id"], UserRole.student)
    
    # Get student record
    student = db.query(Student).filter(
        Student.user_id == current_user["user_id"],
        Student.is_active == True
    ).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student profile not found")
    
    # Get subject and verify student is enrolled
    subject = db.query(Subject).filter(
        Subject.id == subject_id,
        Subject.is_active == True
    ).first()
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found")
    
    # Verify enrollment
    try:
        from models.study_area_models import subject_students
        enrollment = db.query(subject_students).filter(
            subject_students.c.subject_id == subject_id,
            subject_students.c.student_id == student.id
        ).first()
        if not enrollment:
            raise HTTPException(status_code=403, detail="You are not enrolled in this subject")
    except Exception:
        # Fallback check
        if subject.school_id != student.school_id:
            raise HTTPException(status_code=403, detail="You are not enrolled in this subject")
    
    # Get all assignments for this subject
    assignments = db.query(Assignment).filter(
        Assignment.subject_id == subject_id,
        Assignment.is_active == True
    ).all()
    
    # Get grades for this student in this subject
    grades = db.query(Grade).join(Assignment).filter(
        Assignment.subject_id == subject_id,
        Grade.student_id == student.id
    ).all()
    
    # Build progress data
    assignment_progress = []
    total_points_possible = 0
    total_points_earned = 0
    completed_count = 0
    
    for assignment in assignments:
        grade = next((g for g in grades if g.assignment_id == assignment.id), None)
        
        assignment_data = {
            "assignment_id": assignment.id,
            "title": assignment.title,
            "description": assignment.description,
            "subtopic": assignment.subtopic,
            "due_date": assignment.due_date,
            "max_points": assignment.max_points,
            "is_completed": grade is not None,
            "grade": {
                "points_earned": grade.points_earned,
                "percentage": round((grade.points_earned / assignment.max_points) * 100, 2),
                "feedback": grade.feedback,
                "graded_date": grade.graded_date
            } if grade else None
        }
        
        assignment_progress.append(assignment_data)
        total_points_possible += assignment.max_points
        
        if grade:
            total_points_earned += grade.points_earned
            completed_count += 1
    
    # Calculate statistics
    completion_rate = (completed_count / len(assignments)) * 100 if assignments else 0
    current_grade = (total_points_earned / total_points_possible) * 100 if total_points_possible > 0 else 0
    
    # Sort assignments by due date
    assignment_progress.sort(key=lambda a: a["due_date"] or datetime.max.replace(tzinfo=None))
    
    # Get teacher info
    teachers = subject.teachers
    teacher_info = []
    for teacher in teachers:
        teacher_info.append({
            "name": f"{teacher.user.fname} {teacher.user.lname}",
            "email": teacher.user.email
        })
    
    return {
        "subject_info": {
            "id": subject.id,
            "name": subject.name,
            "description": subject.description,
            "teachers": teacher_info
        },
        "progress_summary": {
            "total_assignments": len(assignments),
            "completed_assignments": completed_count,
            "completion_rate": round(completion_rate, 2),
            "current_grade": round(current_grade, 2),
            "total_points_earned": total_points_earned,
            "total_points_possible": total_points_possible
        },
        "assignments": assignment_progress
    }

@router.get("/students/my-study-analytics")
async def get_study_analytics(db: db_dependency, current_user: user_dependency):
    """
    Get detailed study analytics for the student including time trends, performance patterns
    """
    ensure_user_role(db, current_user["user_id"], UserRole.student)
    
    # Get student record
    student = db.query(Student).filter(
        Student.user_id == current_user["user_id"],
        Student.is_active == True
    ).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student profile not found")
    
    # Get all grades with dates
    grades = db.query(Grade).join(Assignment).join(Subject).filter(
        Grade.student_id == student.id,
        Grade.graded_date.isnot(None)
    ).order_by(Grade.graded_date).all()
    
    if not grades:
        return {
            "student_id": student.id,
            "message": "No graded assignments yet",
            "analytics": {}
        }
    
    # Performance over time (monthly averages)
    monthly_performance = {}
    for grade in grades:
        month_key = grade.graded_date.strftime("%Y-%m")
        percentage = (grade.points_earned / grade.assignment.max_points) * 100
        
        if month_key not in monthly_performance:
            monthly_performance[month_key] = []
        monthly_performance[month_key].append(percentage)
    
    # Calculate monthly averages
    monthly_averages = {}
    for month, percentages in monthly_performance.items():
        monthly_averages[month] = round(sum(percentages) / len(percentages), 2)
    
    # Subject performance breakdown
    subject_breakdown = {}
    for grade in grades:
        subject_name = grade.assignment.subject.name
        percentage = (grade.points_earned / grade.assignment.max_points) * 100
        
        if subject_name not in subject_breakdown:
            subject_breakdown[subject_name] = []
        subject_breakdown[subject_name].append(percentage)
    
    subject_averages = {}
    for subject, percentages in subject_breakdown.items():
        subject_averages[subject] = round(sum(percentages) / len(percentages), 2)
    
    # Performance distribution
    grade_ranges = {
        "A (90-100%)": 0,
        "B (80-89%)": 0,
        "C (70-79%)": 0,
        "D (60-69%)": 0,
        "F (0-59%)": 0
    }
    
    for grade in grades:
        percentage = (grade.points_earned / grade.assignment.max_points) * 100
        if percentage >= 90:
            grade_ranges["A (90-100%)"] += 1
        elif percentage >= 80:
            grade_ranges["B (80-89%)"] += 1
        elif percentage >= 70:
            grade_ranges["C (70-79%)"] += 1
        elif percentage >= 60:
            grade_ranges["D (60-69%)"] += 1
        else:
            grade_ranges["F (0-59%)"] += 1
    
    # Recent performance trend (last 10 grades)
    recent_grades = grades[-10:] if len(grades) >= 10 else grades
    recent_percentages = [(g.points_earned / g.assignment.max_points) * 100 for g in recent_grades]
    
    # Calculate trend
    if len(recent_percentages) >= 3:
        first_half = recent_percentages[:len(recent_percentages)//2]
        second_half = recent_percentages[len(recent_percentages)//2:]
        
        first_avg = sum(first_half) / len(first_half)
        second_avg = sum(second_half) / len(second_half)
        
        if second_avg > first_avg + 5:
            trend = "improving"
        elif second_avg < first_avg - 5:
            trend = "declining"
        else:
            trend = "stable"
    else:
        trend = "insufficient_data"
    
    return {
        "student_id": student.id,
        "analytics_date": datetime.utcnow(),
        "overall_stats": {
            "total_grades": len(grades),
            "overall_average": round(sum((g.points_earned / g.assignment.max_points) * 100 for g in grades) / len(grades), 2),
            "highest_grade": round(max((g.points_earned / g.assignment.max_points) * 100 for g in grades), 2),
            "lowest_grade": round(min((g.points_earned / g.assignment.max_points) * 100 for g in grades), 2),
            "recent_trend": trend
        },
        "monthly_performance": monthly_averages,
        "subject_performance": subject_averages,
        "grade_distribution": grade_ranges,
        "recent_performance": [
            {
                "assignment_title": g.assignment.title,
                "subject_name": g.assignment.subject.name,
                "percentage": round((g.points_earned / g.assignment.max_points) * 100, 2),
                "graded_date": g.graded_date
            } for g in recent_grades
        ]
    }
