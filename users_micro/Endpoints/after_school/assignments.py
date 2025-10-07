from fastapi import APIRouter, HTTPException, Depends, status
from sqlalchemy import and_
from datetime import datetime, timedelta

from db.connection import db_dependency
from Endpoints.auth import get_current_user
from models.afterschool_models import CourseAssignment, StudentAssignment

router = APIRouter(prefix="/after-school/assignments", tags=["After-School Assignments (Public)"])

# Dependency for current user
user_dependency = Depends(get_current_user)

@router.get("/{assignment_id}/status")
async def get_assignment_status_public(
    assignment_id: int,
    db: db_dependency,
    current_user: dict = user_dependency
):
    """
    Public assignment status endpoint expected by mobile app at
    GET /after-school/assignments/{assignment_id}/status

    Returns a minimal payload compatible with frontend types. This mirrors
    the minimal status present in sessions router but at the correct path.
    """
    user_id = current_user["user_id"]

    assignment = db.query(CourseAssignment).filter(CourseAssignment.id == assignment_id).first()
    if not assignment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found")

    sa = db.query(StudentAssignment).filter(
        and_(
            StudentAssignment.assignment_id == assignment_id,
            StudentAssignment.user_id == user_id
        )
    ).first()

    # If no student assignment exists yet, seed a lightweight record so the app has something to track
    if not sa:
        # Due date fallback: from assignment config or 7 days from now
        due_days = getattr(assignment, 'due_days_after_assignment', None) or 7
        sa = StudentAssignment(
            user_id=user_id,
            assignment_id=assignment.id,
            course_id=assignment.course_id,
            due_date=datetime.utcnow() + timedelta(days=due_days),
            status='assigned'
        )
        try:
            db.add(sa)
            db.commit()
            db.refresh(sa)
        except Exception:
            db.rollback()
            # If unique constraint hit due to race, fetch again
            sa = db.query(StudentAssignment).filter(
                and_(
                    StudentAssignment.assignment_id == assignment_id,
                    StudentAssignment.user_id == user_id
                )
            ).first()

    required_pct = 80
    can_retry = False

    return {
        "assignment": {
            "id": assignment.id,
            "title": assignment.title,
            "description": assignment.description or assignment.title,
            "points": assignment.points or 100,
            "required_percentage": required_pct,
        },
        "student_assignment": {
            "id": sa.id,
            "status": sa.status,
            "grade": float(sa.grade) if sa.grade is not None else 0.0,
            "submitted_at": sa.submitted_at.isoformat() if sa.submitted_at else None,
            "feedback": sa.feedback or None,
        },
        "attempts_info": {
            "attempts_used": 0,
            "attempts_remaining": 0,
            "can_retry": can_retry,
        },
        "message": "OK",
        "passing_grade": (sa.grade or 0) >= required_pct,
    }
