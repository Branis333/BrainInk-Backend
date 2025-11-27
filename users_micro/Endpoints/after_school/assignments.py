from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, asc, desc
from typing import Optional

from db.connection import db_dependency
from Endpoints.auth import get_current_user
from Endpoints.after_school.grades import get_assignment_status_with_grade
from models.afterschool_models import CourseAssignment, StudentAssignment, StudySession

router = APIRouter(prefix="/after-school/assignments", tags=["After-School Assignments (Public)"])

# Dependency for current user
user_dependency = Depends(get_current_user)

PASS_THRESHOLD = 80  # minimum percentage required to consider an assignment completed

async def _extract_numeric_score(status_payload: dict) -> Optional[float]:
    if not isinstance(status_payload, dict):
        return None
    for key in [
        "score", "final_score", "percentage", "grade", "ai_score",
        "overall", "overall_score", "overall_percentage",
    ]:
        val = status_payload.get(key)
        try:
            if isinstance(val, (int, float)):
                return float(val)
        except Exception:
            continue
    return None

async def _previous_assignment(db, assignment: CourseAssignment) -> Optional[CourseAssignment]:
    return (
        db.query(CourseAssignment)
        .filter(
            CourseAssignment.course_id == assignment.course_id,
            CourseAssignment.is_active == True,
            CourseAssignment.id < assignment.id,
        )
        .order_by(desc(CourseAssignment.id))
        .first()
    )

async def _has_passed_assignment(assignment_id: int, db, current_user: dict) -> bool:
    try:
        status_payload = await get_assignment_status_with_grade(
            assignment_id=assignment_id, db=db, current_user=current_user
        )
    except HTTPException as e:
        if e.status_code == 404:
            return False
        raise

    if not isinstance(status_payload, dict):
        return False

    s = (status_payload.get("status") or status_payload.get("state") or "").lower()
    if s == "passed":
        return True

    score = await _extract_numeric_score(status_payload)
    if score is not None and score >= PASS_THRESHOLD:
        return True
    return False

async def _has_completed_block(db, current_user: dict, block_id: Optional[int]) -> bool:
    """Return True if the user has completed the correlating block (module)."""
    if not block_id:
        return True
    user_id = current_user["user_id"]
    completed = (
        db.query(StudySession)
        .filter(
            StudySession.user_id == user_id,
            StudySession.block_id == block_id,
            StudySession.status == 'completed'
        )
        .first()
    )
    return completed is not None

async def _lock_info_for_assignment(db, current_user: dict, assignment: CourseAssignment):
    """
    Lock rule: an assignment is locked if its correlating block (module) has not
    been marked as completed by the student. If the assignment has no block linkage,
    it is considered unlocked.
    """
    # Gate by block completion
    if await _has_completed_block(db, current_user, getattr(assignment, 'block_id', None)):
        return {"locked": False, "required_assignment_id": None}
    # When locked by module gating, we don't force a specific prior assignment; keep field for compatibility
    return {"locked": True, "required_assignment_id": None}

@router.get("/one")
async def get_one_assignment(
    db: db_dependency,
    current_user: dict = user_dependency,
    course_id: int = Query(..., description="Course to pick an assignment from"),
    block_id: Optional[int] = Query(None, description="Filter by course block"),
    lesson_id: Optional[int] = Query(None, description="Filter by lesson"),
    prefer_status: str = Query("assigned", description="Preferred student status to pick first (e.g., 'assigned')")
):
    """
    Return a single best assignment for quick navigation.

    Rules:
    - If the user already has assignments in this course that match the filters, pick the earliest-due with the
      preferred status (default: 'assigned').
    - Otherwise, return the first active assignment definition in the scope (course + optional block/lesson).
    - Always return detailed status for the selected assignment id.

    Response shape mirrors get_single_assignment: { assignment, student_status, is_assigned }.
    """
    user_id = current_user["user_id"]

    # First try: student's own assignments in this scope with preferred status
    student_q = db.query(StudentAssignment).join(CourseAssignment, CourseAssignment.id == StudentAssignment.assignment_id)
    student_q = student_q.filter(
        and_(
            StudentAssignment.user_id == user_id,
            StudentAssignment.course_id == course_id,
        )
    )

    if block_id is not None:
        student_q = student_q.filter(CourseAssignment.block_id == block_id)
    if lesson_id is not None:
        lesson_attr = getattr(CourseAssignment, 'lesson_id', None)
        if lesson_attr is not None:
            student_q = student_q.filter(lesson_attr == lesson_id)

    if prefer_status:
        student_q = student_q.filter(StudentAssignment.status == prefer_status)

    student_q = student_q.order_by(asc(StudentAssignment.due_date))
    student_pick = student_q.first()

    if student_pick:
        # Enforce sequential unlock: ensure previous assignment is passed
        current_def = db.query(CourseAssignment).filter(CourseAssignment.id == student_pick.assignment_id).first()
        if current_def:
            prev_def = await _previous_assignment(db, current_def)
            if prev_def is not None and not await _has_passed_assignment(prev_def.id, db, current_user):
                # Return the previous (actionable) assignment with lock meta
                prev_payload = await get_single_assignment(assignment_id=prev_def.id, db=db, current_user=current_user)
                lock_info = {"locked": True, "required_assignment_id": prev_def.id}
                if isinstance(prev_payload, dict):
                    prev_payload.setdefault("locked", lock_info["locked"])  # previous itself isn't locked
                    prev_payload.setdefault("required_assignment_id", None)
                return prev_payload

        payload = await get_single_assignment(assignment_id=student_pick.assignment_id, db=db, current_user=current_user)
        # Add lock info to payload (first assignment remains unlocked)
        if isinstance(payload, dict) and current_def is not None:
            lock_info = await _lock_info_for_assignment(db, current_user, current_def)
            payload["locked"] = lock_info["locked"]
            payload["required_assignment_id"] = lock_info["required_assignment_id"]
        return payload

    # Second try: any student assignment in the scope regardless of status (earliest due)
    fallback_student_q = db.query(StudentAssignment).join(CourseAssignment, CourseAssignment.id == StudentAssignment.assignment_id)
    fallback_student_q = fallback_student_q.filter(
        and_(
            StudentAssignment.user_id == user_id,
            StudentAssignment.course_id == course_id,
        )
    )
    if block_id is not None:
        fallback_student_q = fallback_student_q.filter(CourseAssignment.block_id == block_id)
    if lesson_id is not None:
        lesson_attr = getattr(CourseAssignment, 'lesson_id', None)
        if lesson_attr is not None:
            fallback_student_q = fallback_student_q.filter(lesson_attr == lesson_id)
    fallback_student_q = fallback_student_q.order_by(asc(StudentAssignment.due_date))
    fallback_student = fallback_student_q.first()
    if fallback_student:
        current_def = db.query(CourseAssignment).filter(CourseAssignment.id == fallback_student.assignment_id).first()
        if current_def:
            prev_def = await _previous_assignment(db, current_def)
            if prev_def is not None and not await _has_passed_assignment(prev_def.id, db, current_user):
                prev_payload = await get_single_assignment(assignment_id=prev_def.id, db=db, current_user=current_user)
                if isinstance(prev_payload, dict):
                    prev_payload.setdefault("locked", False)
                    prev_payload.setdefault("required_assignment_id", None)
                return prev_payload
        payload = await get_single_assignment(assignment_id=fallback_student.assignment_id, db=db, current_user=current_user)
        if isinstance(payload, dict) and current_def is not None:
            lock_info = await _lock_info_for_assignment(db, current_user, current_def)
            payload["locked"] = lock_info["locked"]
            payload["required_assignment_id"] = lock_info["required_assignment_id"]
        return payload

    # Final try: any course assignment definition in scope (not yet assigned to user)
    definition_q = db.query(CourseAssignment).filter(CourseAssignment.course_id == course_id, CourseAssignment.is_active == True)
    if block_id is not None:
        definition_q = definition_q.filter(CourseAssignment.block_id == block_id)
    if lesson_id is not None:
        lesson_attr = getattr(CourseAssignment, 'lesson_id', None)
        if lesson_attr is not None:
            definition_q = definition_q.filter(lesson_attr == lesson_id)

    definition_q = definition_q.order_by(asc(CourseAssignment.id))
    definition_pick = definition_q.first()
    if not definition_pick:
        # Progressive relaxation: if nothing found within block/lesson scope,
        # fall back to course-wide search to always return something useful
        # for quick-start flows.
        # 1) Student assignments with preferred status (course-wide)
        wide_student_q = db.query(StudentAssignment).filter(
            and_(
                StudentAssignment.user_id == user_id,
                StudentAssignment.course_id == course_id,
            )
        )
        if prefer_status:
            wide_student_q = wide_student_q.filter(StudentAssignment.status == prefer_status)
        wide_student_q = wide_student_q.order_by(asc(StudentAssignment.due_date))
        wide_student_pick = wide_student_q.first()
        if wide_student_pick:
            return await get_single_assignment(assignment_id=wide_student_pick.assignment_id, db=db, current_user=current_user)

        # 2) Any student assignment regardless of status (course-wide)
        wide_fallback_q = db.query(StudentAssignment).filter(
            and_(
                StudentAssignment.user_id == user_id,
                StudentAssignment.course_id == course_id,
            )
        ).order_by(asc(StudentAssignment.due_date))
        wide_fallback = wide_fallback_q.first()
        if wide_fallback:
            return await get_single_assignment(assignment_id=wide_fallback.assignment_id, db=db, current_user=current_user)

        # 3) Any active course assignment definition (course-wide)
        wide_definition_q = db.query(CourseAssignment).filter(
            and_(
                CourseAssignment.course_id == course_id,
                CourseAssignment.is_active == True,
            )
        ).order_by(asc(CourseAssignment.id))
        wide_definition_pick = wide_definition_q.first()
        if not wide_definition_pick:
            raise HTTPException(status_code=404, detail="No assignment found for the given criteria")

        try:
            status = await get_assignment_status_with_grade(
                assignment_id=wide_definition_pick.id,
                db=db,
                current_user=current_user
            )
        except HTTPException as e:
            if e.status_code == 404:
                status = None
            else:
                raise

        return {
            "assignment": {
                "id": wide_definition_pick.id,
                "course_id": wide_definition_pick.course_id,
                "title": wide_definition_pick.title,
                "description": wide_definition_pick.description,
                "assignment_type": wide_definition_pick.assignment_type,
                "instructions": wide_definition_pick.instructions,
                "duration_minutes": wide_definition_pick.duration_minutes,
                "points": wide_definition_pick.points,
                "rubric": wide_definition_pick.rubric,
                "week_assigned": wide_definition_pick.week_assigned,
                "block_id": wide_definition_pick.block_id,
                "due_days_after_assignment": wide_definition_pick.due_days_after_assignment,
                "submission_format": wide_definition_pick.submission_format,
                "learning_outcomes": wide_definition_pick.learning_outcomes,
                "generated_by_ai": wide_definition_pick.generated_by_ai,
                "is_active": wide_definition_pick.is_active
            },
            "student_status": status,
            "is_assigned": False
        }

    # Enforce sequential unlock for definition pick as well
    prev_def = await _previous_assignment(db, definition_pick)
    if prev_def is not None and not await _has_passed_assignment(prev_def.id, db, current_user):
        prev_payload = await get_single_assignment(assignment_id=prev_def.id, db=db, current_user=current_user)
        if isinstance(prev_payload, dict):
            prev_payload.setdefault("locked", False)
            prev_payload.setdefault("required_assignment_id", None)
        return prev_payload

    # Build response similar to get_single_assignment but without a student record
    try:
        status = await get_assignment_status_with_grade(
            assignment_id=definition_pick.id,
            db=db,
            current_user=current_user
        )
    except HTTPException as e:
        # If user doesn't have a student assignment yet, surface None for student_status
        if e.status_code == 404:
            status = None
        else:
            raise

    lock_info = await _lock_info_for_assignment(db, current_user, definition_pick)
    return {
        "assignment": {
            "id": definition_pick.id,
            "course_id": definition_pick.course_id,
            "title": definition_pick.title,
            "description": definition_pick.description,
            "assignment_type": definition_pick.assignment_type,
            "instructions": definition_pick.instructions,
            "duration_minutes": definition_pick.duration_minutes,
            "points": definition_pick.points,
            "rubric": definition_pick.rubric,
            "week_assigned": definition_pick.week_assigned,
            "block_id": definition_pick.block_id,
            "due_days_after_assignment": definition_pick.due_days_after_assignment,
            "submission_format": definition_pick.submission_format,
            "learning_outcomes": definition_pick.learning_outcomes,
            "generated_by_ai": definition_pick.generated_by_ai,
            "is_active": definition_pick.is_active
        },
        "student_status": status,
        "is_assigned": False,
        "locked": lock_info["locked"],
        "required_assignment_id": lock_info["required_assignment_id"],
    }

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
    
    # Compute lock info for UI (do not hard-error; expose lock state)
    lock_info = await _lock_info_for_assignment(db, current_user, assignment)
    
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
        "is_assigned": student_assignment is not None,
        "locked": lock_info["locked"],
        "required_assignment_id": lock_info["required_assignment_id"],
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
