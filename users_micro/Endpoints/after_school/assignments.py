from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import and_

from db.connection import db_dependency
from Endpoints.auth import get_current_user
from Endpoints.after_school.grades import get_assignment_status_with_grade
from models.afterschool_models import CourseAssignment, StudentAssignment

router = APIRouter(prefix="/after-school/assignments", tags=["After-School Assignments (Public)"])

# Dependency for current user
user_dependency = Depends(get_current_user)

@router.get("/{assignment_id}")
async def get_single_assignment(
    assignment_id: int,
    db: db_dependency,
    current_user: dict = user_dependency
):
    """
    Get a single assignment with full details including student-specific status and attempts.
    
    This endpoint provides comprehensive assignment information:
    - Assignment definition (title, description, points, instructions, etc.)
    - Student's assignment record if they're assigned to it
    - Attempt tracking scoped to this specific assignment
    - Current grade and feedback
    
    Perfect for displaying detailed assignment views with accurate attempt counts.
    """
    user_id = current_user["user_id"]
    
    # Get the assignment definition
    assignment = db.query(CourseAssignment).filter(CourseAssignment.id == assignment_id).first()
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")
    
    # Get student's assignment record if exists
    student_assignment = db.query(StudentAssignment).filter(
        and_(
            StudentAssignment.assignment_id == assignment_id,
            StudentAssignment.user_id == user_id
        )
    ).first()
    
    # Get status with attempts (properly scoped per assignment)
    try:
        status = await get_assignment_status_with_grade(
            assignment_id=assignment_id,
            db=db,
            current_user=current_user
        )
    except HTTPException as e:
        if e.status_code == 404:
            # Not assigned yet - return basic assignment info without student data
            status = None
        else:
            raise
    
    return {
        "assignment": {
            "id": assignment.id,
            "course_id": assignment.course_id,
            "title": assignment.title,
            "description": assignment.description,
            "assignment_type": assignment.assignment_type,
            "instructions": assignment.instructions,
            "duration_minutes": assignment.duration_minutes,
            "points": assignment.points,
            "rubric": assignment.rubric,
            "week_assigned": assignment.week_assigned,
            "block_id": assignment.block_id,
            "due_days_after_assignment": assignment.due_days_after_assignment,
            "submission_format": assignment.submission_format,
            "learning_outcomes": assignment.learning_outcomes,
            "generated_by_ai": assignment.generated_by_ai,
            "is_active": assignment.is_active
        },
        "student_status": status,
        "is_assigned": student_assignment is not None
    }

@router.get("/{assignment_id}/status")
async def get_assignment_status_public(
    assignment_id: int,
    db: db_dependency,
    current_user: dict = user_dependency
):
    """
    Public assignment status endpoint expected by mobile app at
    GET /after-school/assignments/{assignment_id}/status

    Returns the richer status payload (grade + attempts) expected by the mobile app.
    Delegates to the shared implementation used by the sessions router so the
    data stays consistent regardless of which endpoint the client calls.
    
    Attempts are properly scoped per assignment, not shared across all assignments.
    """
    return await get_assignment_status_with_grade(
        assignment_id=assignment_id,
        db=db,
        current_user=current_user,
    )
