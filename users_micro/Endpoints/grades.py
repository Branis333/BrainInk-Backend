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
# Import shared utility functions
from Endpoints.utils import _get_user_roles, check_user_role, ensure_user_role, check_user_has_any_role, ensure_user_has_any_role

router = APIRouter(tags=["Assignments and Grades Management"])

user_dependency = Annotated[dict, Depends(get_current_user)]

@router.post("/assignments-management/create", response_model=AssignmentResponse, tags=["Assignments"])
async def create_assignment(
    assignment: AssignmentCreate,
    db: db_dependency,
    current_user: user_dependency
):
    """
    Create a new assignment (Teachers only, for their assigned subjects)
    """
    ensure_user_role(db, current_user["user_id"], UserRole.teacher)
    
    # Get teacher profile
    teacher = db.query(Teacher).filter(Teacher.user_id == current_user["user_id"]).first()
    if not teacher:
        raise HTTPException(status_code=404, detail="Teacher profile not found")
    
    # Get subject and verify teacher is assigned to it
    subject = db.query(Subject).filter(Subject.id == assignment.subject_id).first()
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found")
    
    if subject not in teacher.subjects:
        raise HTTPException(status_code=403, detail="You are not assigned to this subject")
    
    # Validate max_points vs points_earned constraint
    if assignment.max_points <= 0:
        raise HTTPException(status_code=400, detail="Max points must be greater than 0")
    
    try:
        new_assignment = Assignment(
            title=assignment.title,
            description=assignment.description,
            rubric=assignment.rubric,
            subtopic=assignment.subtopic,
            subject_id=assignment.subject_id,
            teacher_id=teacher.id,
            max_points=assignment.max_points,
            due_date=assignment.due_date
        )
        
        db.add(new_assignment)
        db.commit()
        db.refresh(new_assignment)
        
        # Create response with additional info
        response = AssignmentResponse(
            id=new_assignment.id,
            title=new_assignment.title,
            description=new_assignment.description,
            rubric=new_assignment.rubric,
            subtopic=new_assignment.subtopic,
            subject_id=new_assignment.subject_id,
            teacher_id=new_assignment.teacher_id,
            max_points=new_assignment.max_points,
            due_date=new_assignment.due_date,
            created_date=new_assignment.created_date,
            is_active=new_assignment.is_active,
            subject_name=subject.name,
            teacher_name=f"{teacher.user.fname} {teacher.user.lname}"
        )
        
        return response
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Assignment creation error: {str(e)}")

@router.get("/assignments-management/my-assignments", response_model=List[AssignmentWithGrades], tags=["Assignments"])
async def get_teacher_assignments(db: db_dependency, current_user: user_dependency):
    """
    Get all assignments created by the current teacher with grade statistics
    """
    try:
        ensure_user_role(db, current_user["user_id"], UserRole.teacher)
        
        teacher = db.query(Teacher).filter(Teacher.user_id == current_user["user_id"]).first()
        if not teacher:
            raise HTTPException(status_code=404, detail="Teacher profile not found")
        
        result = []
        for assignment in teacher.assignments:
            if not assignment.is_active:
                continue
                
            # Get grade statistics
            grades = [g for g in assignment.grades if g.is_active]
            total_students = len(assignment.subject.students)
            graded_count = len(grades)
            average_score = None
            
            if grades:
                avg_points = sum(grade.points_earned for grade in grades) / len(grades)
                average_score = (avg_points / assignment.max_points) * 100 if assignment.max_points > 0 else 0
            
            # Convert grades to response format
            grade_responses = []
            for grade in grades:
                percentage = (grade.points_earned / assignment.max_points) * 100 if assignment.max_points > 0 else 0
                grade_responses.append(GradeResponse(
                    id=grade.id,
                    assignment_id=grade.assignment_id,
                    student_id=grade.student_id,
                    teacher_id=grade.teacher_id,
                    points_earned=grade.points_earned,
                    feedback=grade.feedback,
                    graded_date=grade.graded_date,
                    is_active=grade.is_active,
                    assignment_title=assignment.title,
                    assignment_max_points=assignment.max_points,
                    student_name=f"{grade.student.user.fname} {grade.student.user.lname}",
                    teacher_name=f"{teacher.user.fname} {teacher.user.lname}",
                    percentage=percentage
                ))
            
            # Ensure rubric has a value (required by schema)
            rubric = assignment.rubric or "Grading rubric not provided - please update this assignment with detailed grading criteria."
            
            # Ensure description has minimum length and maximum length (required by schema)
            description = assignment.description or "Assignment description not provided - please update this assignment with detailed instructions."
            if len(description.strip()) < 10:
                description = "Assignment description not provided - please update this assignment with detailed instructions and requirements."
            elif len(description) > 1000:
                description = description[:997] + "..."
            
            assignment_response = AssignmentWithGrades(
                id=assignment.id,
                title=assignment.title,
                description=description,
                rubric=rubric,
                subtopic=assignment.subtopic,
                subject_id=assignment.subject_id,
                teacher_id=assignment.teacher_id,
                max_points=assignment.max_points,
                due_date=assignment.due_date,
                created_date=assignment.created_date,
                is_active=assignment.is_active,
                subject_name=assignment.subject.name,
                teacher_name=f"{teacher.user.fname} {teacher.user.lname}",
                grades=grade_responses,
                total_students=total_students,
                graded_count=graded_count,
                average_score=average_score
            )
            
            result.append(assignment_response)
        
        return result
    
    except Exception as e:
        # Handle database connection errors
        if "server closed the connection unexpectedly" in str(e) or "Can't reconnect until invalid transaction is rolled back" in str(e):
            try:
                db.rollback()
            except:
                pass
            raise HTTPException(status_code=503, detail="Database connection error. Please try again.")
        else:
            raise HTTPException(status_code=500, detail=f"Error retrieving assignments: {str(e)}")

@router.get("/assignments-management/subject/{subject_id}", response_model=List[AssignmentResponse])
async def get_subject_assignments(
    subject_id: int,
    db: db_dependency,
    current_user: user_dependency
):
    """
    Get all assignments for a subject (accessible by teachers and students in the subject)
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
    
    if UserRole.student in user_roles:
        student = db.query(Student).filter(Student.user_id == current_user["user_id"]).first()
        if student and subject in student.subjects:
            has_access = True
    
    if UserRole.principal in user_roles:
        # Principal can view assignments in their school
        user = db.query(User).filter(User.id == current_user["user_id"]).first()
        if user and any(school.id == subject.school_id for school in user.schools_managed):
            has_access = True
    
    if not has_access:
        raise HTTPException(status_code=403, detail="You don't have access to this subject")
    
    # Get assignments
    assignments = db.query(Assignment).filter(
        Assignment.subject_id == subject_id,
        Assignment.is_active == True
    ).all()
    
    result = []
    for assignment in assignments:
        # Ensure rubric has a value (required by schema)
        rubric = assignment.rubric or "Grading rubric not provided - please update this assignment with detailed grading criteria."
        
        # Ensure description has minimum length (required by schema)
        description = assignment.description or "Assignment description not provided - please update this assignment with detailed instructions."
        if len(description.strip()) < 10:
            description = "Assignment description not provided - please update this assignment with detailed instructions and requirements."
        
        result.append(AssignmentResponse(
            id=assignment.id,
            title=assignment.title,
            description=description,
            rubric=rubric,
            subtopic=assignment.subtopic,
            subject_id=assignment.subject_id,
            teacher_id=assignment.teacher_id,
            max_points=assignment.max_points,
            due_date=assignment.due_date,
            created_date=assignment.created_date,
            is_active=assignment.is_active,
            subject_name=subject.name,
            teacher_name=f"{assignment.teacher.user.fname} {assignment.teacher.user.lname}"
        ))
    
    return result

@router.put("/assignments-management/{assignment_id}", response_model=AssignmentResponse)
async def update_assignment(
    assignment_id: int,
    assignment_update: AssignmentUpdate,
    db: db_dependency,
    current_user: user_dependency
):
    """
    Update an assignment (only by the teacher who created it)
    """
    ensure_user_role(db, current_user["user_id"], UserRole.teacher)
    
    teacher = db.query(Teacher).filter(Teacher.user_id == current_user["user_id"]).first()
    if not teacher:
        raise HTTPException(status_code=404, detail="Teacher profile not found")
    
    # Get assignment
    assignment = db.query(Assignment).filter(Assignment.id == assignment_id).first()
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")
    
    # Check if teacher owns this assignment
    if assignment.teacher_id != teacher.id:
        raise HTTPException(status_code=403, detail="You can only update your own assignments")
    
    try:
        # Update fields if provided
        if assignment_update.title is not None:
            assignment.title = assignment_update.title
        if assignment_update.description is not None:
            assignment.description = assignment_update.description
        if assignment_update.subtopic is not None:
            assignment.subtopic = assignment_update.subtopic
        if assignment_update.max_points is not None:
            # Validate that existing grades don't exceed new max_points
            existing_grades = db.query(Grade).filter(
                Grade.assignment_id == assignment_id,
                Grade.is_active == True
            ).all()
            
            if any(grade.points_earned > assignment_update.max_points for grade in existing_grades):
                raise HTTPException(
                    status_code=400,
                    detail="Cannot set max_points lower than existing grades"
                )
            assignment.max_points = assignment_update.max_points
        if assignment_update.due_date is not None:
            assignment.due_date = assignment_update.due_date
        if assignment_update.is_active is not None:
            assignment.is_active = assignment_update.is_active
        
        db.commit()
        db.refresh(assignment)
        
        # Ensure rubric has a value (required by schema)
        rubric = assignment.rubric or "Grading rubric not provided - please update this assignment with detailed grading criteria."
        
        # Ensure description has minimum length (required by schema)
        description = assignment.description or "Assignment description not provided - please update this assignment with detailed instructions."
        if len(description.strip()) < 10:
            description = "Assignment description not provided - please update this assignment with detailed instructions and requirements."
        
        return AssignmentResponse(
            id=assignment.id,
            title=assignment.title,
            description=description,
            rubric=rubric,
            subtopic=assignment.subtopic,
            subject_id=assignment.subject_id,
            teacher_id=assignment.teacher_id,
            max_points=assignment.max_points,
            due_date=assignment.due_date,
            created_date=assignment.created_date,
            is_active=assignment.is_active,
            subject_name=assignment.subject.name,
            teacher_name=f"{teacher.user.fname} {teacher.user.lname}"
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Assignment update error: {str(e)}")

@router.delete("/assignments-management/{assignment_id}")
async def delete_assignment(
    assignment_id: int,
    db: db_dependency,
    current_user: user_dependency
):
    """
    Soft delete an assignment (only by the teacher who created it)
    """
    ensure_user_role(db, current_user["user_id"], UserRole.teacher)
    
    teacher = db.query(Teacher).filter(Teacher.user_id == current_user["user_id"]).first()
    if not teacher:
        raise HTTPException(status_code=404, detail="Teacher profile not found")
    
    # Get assignment
    assignment = db.query(Assignment).filter(Assignment.id == assignment_id).first()
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")
    
    # Check if teacher owns this assignment
    if assignment.teacher_id != teacher.id:
        raise HTTPException(status_code=403, detail="You can only delete your own assignments")
    
    try:
        assignment.is_active = False
        # Also soft delete associated grades
        grades = db.query(Grade).filter(Grade.assignment_id == assignment_id).all()
        for grade in grades:
            grade.is_active = False
        
        db.commit()
        return {"message": f"Assignment '{assignment.title}' deleted successfully"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Assignment deletion error: {str(e)}")

# =============================================================================
# GRADE ENDPOINTS
# =============================================================================

@router.post("/grades-management/create", response_model=GradeResponse, tags=["Grades"])
async def create_grade(
    grade: GradeCreate,
    db: db_dependency,
    current_user: user_dependency
):
    """
    Create a grade for a student's assignment (Teachers only, for their assignments)
    """
    ensure_user_role(db, current_user["user_id"], UserRole.teacher)
    
    teacher = db.query(Teacher).filter(Teacher.user_id == current_user["user_id"]).first()
    if not teacher:
        raise HTTPException(status_code=404, detail="Teacher profile not found")
    
    # Get assignment and verify teacher owns it
    assignment = db.query(Assignment).filter(Assignment.id == grade.assignment_id).first()
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")
    
    if assignment.teacher_id != teacher.id:
        raise HTTPException(status_code=403, detail="You can only grade your own assignments")
    
    # Get student and verify they're in the subject
    student = db.query(Student).filter(Student.id == grade.student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    
    if assignment.subject not in student.subjects:
        raise HTTPException(status_code=400, detail="Student is not enrolled in this subject")
    
    # Validate points_earned doesn't exceed max_points
    if grade.points_earned > assignment.max_points:
        raise HTTPException(
            status_code=400,
            detail=f"Points earned ({grade.points_earned}) cannot exceed max points ({assignment.max_points})"
        )
    
    # Check if grade already exists
    existing_grade = db.query(Grade).filter(
        Grade.assignment_id == grade.assignment_id,
        Grade.student_id == grade.student_id,
        Grade.is_active == True
    ).first()
    
    if existing_grade:
        raise HTTPException(status_code=400, detail="Grade already exists for this student and assignment")
    
    try:
        new_grade = Grade(
            assignment_id=grade.assignment_id,
            student_id=grade.student_id,
            teacher_id=teacher.id,
            points_earned=grade.points_earned,
            feedback=grade.feedback
        )
        
        db.add(new_grade)
        db.commit()
        db.refresh(new_grade)
        
        # Calculate percentage
        percentage = (new_grade.points_earned / assignment.max_points) * 100 if assignment.max_points > 0 else 0
        
        return GradeResponse(
            id=new_grade.id,
            assignment_id=new_grade.assignment_id,
            student_id=new_grade.student_id,
            teacher_id=new_grade.teacher_id,
            points_earned=new_grade.points_earned,
            feedback=new_grade.feedback,
            graded_date=new_grade.graded_date,
            is_active=new_grade.is_active,
            assignment_title=assignment.title,
            assignment_max_points=assignment.max_points,
            student_name=f"{student.user.fname} {student.user.lname}",
            teacher_name=f"{teacher.user.fname} {teacher.user.lname}",
            percentage=percentage
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Grade creation error: {str(e)}")

@router.post("/grades-management/bulk-create", response_model=BulkGradeResponse)
async def create_bulk_grades(
    bulk_grade: BulkGradeCreate,
    db: db_dependency,
    current_user: user_dependency
):
    """
    Create multiple grades for an assignment at once (Teachers only)
    """
    ensure_user_role(db, current_user["user_id"], UserRole.teacher)
    
    teacher = db.query(Teacher).filter(Teacher.user_id == current_user["user_id"]).first()
    if not teacher:
        raise HTTPException(status_code=404, detail="Teacher profile not found")
    
    # Get assignment and verify teacher owns it
    assignment = db.query(Assignment).filter(Assignment.id == bulk_grade.assignment_id).first()
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")
    
    if assignment.teacher_id != teacher.id:
        raise HTTPException(status_code=403, detail="You can only grade your own assignments")
    
    successful_grades = []
    failed_grades = []
    
    for grade_item in bulk_grade.grades:
        try:
            # Get student and verify they're in the subject
            student = db.query(Student).filter(Student.id == grade_item.student_id).first()
            if not student:
                failed_grades.append({
                    "student_id": grade_item.student_id,
                    "error": "Student not found"
                })
                continue
            
            if assignment.subject not in student.subjects:
                failed_grades.append({
                    "student_id": grade_item.student_id,
                    "error": "Student is not enrolled in this subject"
                })
                continue
            
            # Validate points_earned doesn't exceed max_points
            if grade_item.points_earned > assignment.max_points:
                failed_grades.append({
                    "student_id": grade_item.student_id,
                    "error": f"Points earned ({grade_item.points_earned}) cannot exceed max points ({assignment.max_points})"
                })
                continue
            
            # Check if grade already exists
            existing_grade = db.query(Grade).filter(
                Grade.assignment_id == bulk_grade.assignment_id,
                Grade.student_id == grade_item.student_id,
                Grade.is_active == True
            ).first()
            
            if existing_grade:
                failed_grades.append({
                    "student_id": grade_item.student_id,
                    "error": "Grade already exists for this student and assignment"
                })
                continue
            
            # Create grade
            new_grade = Grade(
                assignment_id=bulk_grade.assignment_id,
                student_id=grade_item.student_id,
                teacher_id=teacher.id,
                points_earned=grade_item.points_earned,
                feedback=grade_item.feedback
            )
            
            db.add(new_grade)
            db.flush()  # Flush to get the ID without committing
            
            # Calculate percentage
            percentage = (new_grade.points_earned / assignment.max_points) * 100 if assignment.max_points > 0 else 0
            
            successful_grades.append(GradeResponse(
                id=new_grade.id,
                assignment_id=new_grade.assignment_id,
                student_id=new_grade.student_id,
                teacher_id=new_grade.teacher_id,
                points_earned=new_grade.points_earned,
                feedback=new_grade.feedback,
                graded_date=new_grade.graded_date,
                is_active=new_grade.is_active,
                assignment_title=assignment.title,
                assignment_max_points=assignment.max_points,
                student_name=f"{student.user.fname} {student.user.lname}",
                teacher_name=f"{teacher.user.fname} {teacher.user.lname}",
                percentage=percentage
            ))
            
        except Exception as e:
            failed_grades.append({
                "student_id": grade_item.student_id,
                "error": str(e)
            })
    
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Bulk grade creation error: {str(e)}")
    
    return BulkGradeResponse(
        successful_grades=successful_grades,
        failed_grades=failed_grades,
        total_processed=len(bulk_grade.grades),
        total_successful=len(successful_grades),
        total_failed=len(failed_grades)
    )

@router.get("/grades-management/student/{student_id}/subject/{subject_id}", response_model=StudentGradeReport)
async def get_student_grades_by_subject(
    student_id: int,
    subject_id: int,
    db: db_dependency,
    current_user: user_dependency
):
    """
    Get all grades for a specific student in a specific subject
    (Accessible by: the student themselves, teachers assigned to the subject, principal)
    """
    user_roles = _get_user_roles(db, current_user["user_id"])
    
    # Get student and subject
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    
    subject = db.query(Subject).filter(Subject.id == subject_id).first()
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found")
    
    # Check access permissions
    has_access = False
    
    # Student can view their own grades
    if UserRole.student in user_roles:
        current_student = db.query(Student).filter(Student.user_id == current_user["user_id"]).first()
        if current_student and current_student.id == student_id:
            has_access = True
    
    # Teacher can view grades for their subjects
    if UserRole.teacher in user_roles:
        teacher = db.query(Teacher).filter(Teacher.user_id == current_user["user_id"]).first()
        if teacher and subject in teacher.subjects:
            has_access = True
    
    # Principal can view grades in their school
    if UserRole.principal in user_roles:
        user = db.query(User).filter(User.id == current_user["user_id"]).first()
        if user and any(school.id == subject.school_id for school in user.schools_managed):
            has_access = True
    
    if not has_access:
        raise HTTPException(status_code=403, detail="You don't have access to these grades")
    
    # Verify student is in the subject
    if subject not in student.subjects:
        raise HTTPException(status_code=400, detail="Student is not enrolled in this subject")
    
    # Get all assignments and grades for this subject
    assignments = db.query(Assignment).filter(
        Assignment.subject_id == subject_id,
        Assignment.is_active == True
    ).all()
    
    grades = db.query(Grade).filter(
        Grade.student_id == student_id,
        Grade.is_active == True
    ).join(Assignment).filter(
        Assignment.subject_id == subject_id,
        Assignment.is_active == True
    ).all()
    
    # Convert grades to response format
    grade_responses = []
    for grade in grades:
        percentage = (grade.points_earned / grade.assignment.max_points) * 100 if grade.assignment.max_points > 0 else 0
        grade_responses.append(GradeResponse(
            id=grade.id,
            assignment_id=grade.assignment_id,
            student_id=grade.student_id,
            teacher_id=grade.teacher_id,
            points_earned=grade.points_earned,
            feedback=grade.feedback,
            graded_date=grade.graded_date,
            is_active=grade.is_active,
            assignment_title=grade.assignment.title,
            assignment_max_points=grade.assignment.max_points,
            student_name=f"{student.user.fname} {student.user.lname}",
            teacher_name=f"{grade.teacher.user.fname} {grade.teacher.user.lname}",
            percentage=percentage
        ))
    
    # Calculate average percentage
    average_percentage = None
    if grade_responses:
        total_percentage = sum(grade.percentage for grade in grade_responses if grade.percentage is not None)
        average_percentage = total_percentage / len(grade_responses)
    
    return StudentGradeReport(
        student_id=student_id,
        student_name=f"{student.user.fname} {student.user.lname}",
        subject_id=subject_id,
        subject_name=subject.name,
        grades=grade_responses,
        total_assignments=len(assignments),
        completed_assignments=len(grade_responses),
        average_percentage=average_percentage
    )

@router.get("/grades-management/my-grades", response_model=List[StudentGradeReport], tags=["Grades"])
async def get_my_grades(db: db_dependency, current_user: user_dependency):
    """
    Get all grades for the current student across all subjects
    """
    ensure_user_role(db, current_user["user_id"], UserRole.student)
    
    student = db.query(Student).filter(Student.user_id == current_user["user_id"]).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student profile not found")
    
    result = []
    for subject in student.subjects:
        # Get grades for this subject
        grades = db.query(Grade).filter(
            Grade.student_id == student.id,
            Grade.is_active == True
        ).join(Assignment).filter(
            Assignment.subject_id == subject.id,
            Assignment.is_active == True
        ).all()
        
        # Get total assignments for this subject
        total_assignments = db.query(Assignment).filter(
            Assignment.subject_id == subject.id,
            Assignment.is_active == True
        ).count()
        
        # Convert grades to response format
        grade_responses = []
        for grade in grades:
            percentage = (grade.points_earned / grade.assignment.max_points) * 100 if grade.assignment.max_points > 0 else 0
            grade_responses.append(GradeResponse(
                id=grade.id,
                assignment_id=grade.assignment_id,
                student_id=grade.student_id,
                teacher_id=grade.teacher_id,
                points_earned=grade.points_earned,
                feedback=grade.feedback,
                graded_date=grade.graded_date,
                is_active=grade.is_active,
                assignment_title=grade.assignment.title,
                assignment_max_points=grade.assignment.max_points,
                student_name=f"{student.user.fname} {student.user.lname}",
                teacher_name=f"{grade.teacher.user.fname} {grade.teacher.user.lname}",
                percentage=percentage
            ))
        
        # Calculate average percentage
        average_percentage = None
        if grade_responses:
            total_percentage = sum(grade.percentage for grade in grade_responses if grade.percentage is not None)
            average_percentage = total_percentage / len(grade_responses)
        
        result.append(StudentGradeReport(
            student_id=student.id,
            student_name=f"{student.user.fname} {student.user.lname}",
            subject_id=subject.id,
            subject_name=subject.name,
            grades=grade_responses,
            total_assignments=total_assignments,
            completed_assignments=len(grade_responses),
            average_percentage=average_percentage
        ))
    
    return result

@router.get("/grades-management/subject/{subject_id}/summary", response_model=SubjectGradesSummary)
async def get_subject_grades_summary(
    subject_id: int,
    db: db_dependency,
    current_user: user_dependency
):
    """
    Get grades summary for a subject (Teachers assigned to subject, Principal)
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
        user = db.query(User).filter(User.id == current_user["user_id"]).first()
        if user and any(school.id == subject.school_id for school in user.schools_managed):
            has_access = True
    
    if not has_access:
        raise HTTPException(status_code=403, detail="You don't have access to this subject")
    
    # Get assignments and their grades
    assignments = db.query(Assignment).filter(
        Assignment.subject_id == subject_id,
        Assignment.is_active == True
    ).all()
    
    total_students = len(subject.students)
    total_assignments = len(assignments)
    
    # Calculate overall statistics
    all_grades = db.query(Grade).filter(
        Grade.is_active == True
    ).join(Assignment).filter(
        Assignment.subject_id == subject_id,
        Assignment.is_active == True
    ).all()
    
    grades_given = len(all_grades)
    average_class_score = None
    
    if all_grades:
        total_percentage = sum((grade.points_earned / grade.assignment.max_points) * 100 
                             for grade in all_grades if grade.assignment.max_points > 0)
        average_class_score = total_percentage / len(all_grades) if all_grades else None
    
    # Process each assignment
    assignment_details = []
    for assignment in assignments:
        grades = [g for g in assignment.grades if g.is_active]
        graded_count = len(grades)
        assignment_average = None
        
        if grades:
            avg_points = sum(grade.points_earned for grade in grades) / len(grades)
            assignment_average = (avg_points / assignment.max_points) * 100 if assignment.max_points > 0 else 0
        
        # Convert grades to response format
        grade_responses = []
        for grade in grades:
            percentage = (grade.points_earned / assignment.max_points) * 100 if assignment.max_points > 0 else 0
            grade_responses.append(GradeResponse(
                id=grade.id,
                assignment_id=grade.assignment_id,
                student_id=grade.student_id,
                teacher_id=grade.teacher_id,
                points_earned=grade.points_earned,
                feedback=grade.feedback,
                graded_date=grade.graded_date,
                is_active=grade.is_active,
                assignment_title=assignment.title,
                assignment_max_points=assignment.max_points,
                student_name=f"{grade.student.user.fname} {grade.student.user.lname}",
                teacher_name=f"{grade.teacher.user.fname} {grade.teacher.user.lname}",
                percentage=percentage
            ))
        
        assignment_details.append(AssignmentWithGrades(
            id=assignment.id,
            title=assignment.title,
            description=assignment.description,
            subtopic=assignment.subtopic,
            subject_id=assignment.subject_id,
            teacher_id=assignment.teacher_id,
            max_points=assignment.max_points,
            due_date=assignment.due_date,
            created_date=assignment.created_date,
            is_active=assignment.is_active,
            subject_name=subject.name,
            teacher_name=f"{assignment.teacher.user.fname} {assignment.teacher.user.lname}",
            grades=grade_responses,
            total_students=total_students,
            graded_count=graded_count,
            average_score=assignment_average
        ))
    
    return SubjectGradesSummary(
        subject_id=subject_id,
        subject_name=subject.name,
        total_assignments=total_assignments,
        total_students=total_students,
        grades_given=grades_given,
        average_class_score=average_class_score,
        assignments=assignment_details
    )

@router.put("/grades-management/{grade_id}", response_model=GradeResponse)
async def update_grade(
    grade_id: int,
    grade_update: GradeUpdate,
    db: db_dependency,
    current_user: user_dependency
):
    """
    Update a grade (only by the teacher who created it)
    """
    ensure_user_role(db, current_user["user_id"], UserRole.teacher)
    
    teacher = db.query(Teacher).filter(Teacher.user_id == current_user["user_id"]).first()
    if not teacher:
        raise HTTPException(status_code=404, detail="Teacher profile not found")
    
    # Get grade
    grade = db.query(Grade).filter(Grade.id == grade_id).first()
    if not grade:
        raise HTTPException(status_code=404, detail="Grade not found")
    
    # Check if teacher owns this grade
    if grade.teacher_id != teacher.id:
        raise HTTPException(status_code=403, detail="You can only update your own grades")
    
    try:
        # Update fields if provided
        if grade_update.points_earned is not None:
            # Validate points_earned doesn't exceed max_points
            if grade_update.points_earned > grade.assignment.max_points:
                raise HTTPException(
                    status_code=400,
                    detail=f"Points earned ({grade_update.points_earned}) cannot exceed max points ({grade.assignment.max_points})"
                )
            grade.points_earned = grade_update.points_earned
        if grade_update.feedback is not None:
            grade.feedback = grade_update.feedback
        
        # Update graded_date to reflect the modification
        grade.graded_date = datetime.utcnow()
        
        db.commit()
        db.refresh(grade)
        
        # Calculate percentage
        percentage = (grade.points_earned / grade.assignment.max_points) * 100 if grade.assignment.max_points > 0 else 0
        
        return GradeResponse(
            id=grade.id,
            assignment_id=grade.assignment_id,
            student_id=grade.student_id,
            teacher_id=grade.teacher_id,
            points_earned=grade.points_earned,
            feedback=grade.feedback,
            graded_date=grade.graded_date,
            is_active=grade.is_active,
            assignment_title=grade.assignment.title,
            assignment_max_points=grade.assignment.max_points,
            student_name=f"{grade.student.user.fname} {grade.student.user.lname}",
            teacher_name=f"{teacher.user.fname} {teacher.user.lname}",
            percentage=percentage
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Grade update error: {str(e)}")

@router.delete("/grades-management/{grade_id}")
async def delete_grade(
    grade_id: int,
    db: db_dependency,
    current_user: user_dependency
):
    """
    Soft delete a grade (only by the teacher who created it)
    """

@router.get("/grades-management/subject/{subject_id}/average")
async def get_subject_average(
    subject_id: int,
    db: db_dependency,
    current_user: user_dependency
):
    """
    Get the average grade for a subject (Teachers assigned to subject, Principal)
    Returns: {subject_id, subject_name, average_percentage, total_grades, student_count, assignment_count}
    """
    user_roles = _get_user_roles(db, current_user["user_id"])
    
    # Get subject
    subject = db.query(Subject).filter(Subject.id == subject_id).first()
    if not subject:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subject not found"
        )
    
    # Check access permissions
    has_access = False
    
    if UserRole.teacher in user_roles:
        teacher = db.query(Teacher).filter(Teacher.user_id == current_user["user_id"]).first()
        if teacher and subject in teacher.subjects:
            has_access = True
    
    if UserRole.principal in user_roles:
        if subject.school.principal_id == current_user["user_id"]:
            has_access = True
    
    if not has_access:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. You can only view averages for subjects you teach or manage."
        )
    
    try:
        # Get all active assignments for this subject
        assignments = db.query(Assignment).filter(
            Assignment.subject_id == subject_id,
            Assignment.is_active == True
        ).all()
        
        # Get all grades for these assignments
        all_grades = db.query(Grade).filter(
            Grade.is_active == True
        ).join(Assignment).filter(
            Assignment.subject_id == subject_id,
            Assignment.is_active == True
        ).all()
        
        # Calculate average percentage
        average_percentage = 0
        if all_grades:
            total_percentage = 0
            valid_grades = 0
            
            for grade in all_grades:
                if grade.assignment.max_points > 0:
                    percentage = (grade.points_earned / grade.assignment.max_points) * 100
                    total_percentage += percentage
                    valid_grades += 1
            
            if valid_grades > 0:
                average_percentage = round(total_percentage / valid_grades, 1)
        
        # Get student count for this subject
        student_count = len(subject.students)
        assignment_count = len(assignments)
        
        # Calculate completion rate
        total_possible_submissions = student_count * assignment_count
        completion_rate = 0
        if total_possible_submissions > 0:
            completion_rate = round((len(all_grades) / total_possible_submissions) * 100, 1)
        
        return {
            "subject_id": subject_id,
            "subject_name": subject.name,
            "average_percentage": average_percentage,
            "total_grades": len(all_grades),
            "student_count": student_count,
            "assignment_count": assignment_count,
            "completion_rate": completion_rate
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error calculating subject average: {str(e)}"
        )

@router.get("/grades-management/teacher/overall-completion-rate")
async def get_teacher_overall_completion_rate(
    db: db_dependency,
    current_user: user_dependency
):
    """
    Get the overall completion rate across all subjects for the current teacher
    Returns: {overall_completion_rate, total_students, total_assignments, total_submissions}
    """
    ensure_user_role(db, current_user["user_id"], UserRole.teacher)
    
    teacher = db.query(Teacher).filter(Teacher.user_id == current_user["user_id"]).first()
    if not teacher:
        raise HTTPException(status_code=404, detail="Teacher profile not found")
    
    try:
        total_possible_submissions = 0
        total_actual_submissions = 0
        total_students = 0
        total_assignments = 0
        
        # Process each subject assigned to the teacher
        for subject in teacher.subjects:
            # Get assignments for this subject
            subject_assignments = db.query(Assignment).filter(
                Assignment.subject_id == subject.id,
                Assignment.is_active == True
            ).all()
            
            # Get grades for this subject
            subject_grades = db.query(Grade).filter(
                Grade.is_active == True
            ).join(Assignment).filter(
                Assignment.subject_id == subject.id,
                Assignment.is_active == True
            ).all()
            
            subject_students = len(subject.students)
            subject_assignment_count = len(subject_assignments)
            
            # Add to totals
            total_students += subject_students
            total_assignments += subject_assignment_count
            total_possible_submissions += subject_students * subject_assignment_count
            total_actual_submissions += len(subject_grades)
        
        # Calculate overall completion rate
        overall_completion_rate = 0
        if total_possible_submissions > 0:
            overall_completion_rate = round((total_actual_submissions / total_possible_submissions) * 100, 1)
        
        return {
            "overall_completion_rate": overall_completion_rate,
            "total_students": total_students,
            "total_assignments": total_assignments,
            "total_possible_submissions": total_possible_submissions,
            "total_actual_submissions": total_actual_submissions
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error calculating overall completion rate: {str(e)}")
    ensure_user_role(db, current_user["user_id"], UserRole.teacher)
    
    teacher = db.query(Teacher).filter(Teacher.user_id == current_user["user_id"]).first()
    if not teacher:
        raise HTTPException(status_code=404, detail="Teacher profile not found")
    
    # Get grade
    grade = db.query(Grade).filter(Grade.id == grade_id).first()
    if not grade:
        raise HTTPException(status_code=404, detail="Grade not found")
    
    # Check if teacher owns this grade
    if grade.teacher_id != teacher.id:
        raise HTTPException(status_code=403, detail="You can only delete your own grades")
    
    try:
        grade.is_active = False
        db.commit()
        return {"message": "Grade deleted successfully"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Grade deletion error: {str(e)}")
