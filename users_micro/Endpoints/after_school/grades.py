from fastapi import APIRouter, HTTPException, Depends, status, Query, Body
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_, desc, func, inspect, text
from typing import List, Optional
from datetime import datetime, timedelta
import os
import logging
from pathlib import Path

from db.connection import db_dependency
from Endpoints.auth import get_current_user
from models.afterschool_models import (
    Course, CourseLesson, CourseBlock, CourseAssignment, StudentAssignment,
    StudySession, AISubmission, StudentProgress
)
from schemas.afterschool_schema import (
    StudySessionStart, StudySessionEnd, StudySessionOut, StudySessionMarkDone,
    AISubmissionUpdate, AIGradingResponse, StudentProgressOut, MessageResponse,
    CourseBlockOut, CourseAssignmentOut, StudentAssignmentOut
)
from services.gemini_service import gemini_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/after-school/sessions", tags=["After-School Sessions & KANA Grading"])

# Dependency for current user
user_dependency = Depends(get_current_user)

# ===============================
# STUDY SESSION MANAGEMENT
# ===============================

@router.post("/mark-done", response_model=StudySessionOut)
async def mark_block_done(
    session_data: StudySessionMarkDone,
    db: db_dependency,
    current_user: dict = user_dependency
):
    """
    Mark a block or lesson as completed - simple and user-friendly
    
    This simplified endpoint allows users to mark content as done:
    - No time tracking complexity
    - Simple mark done functionality
    - Automatic progress tracking
    - Sequential completion enforcement (previous blocks must be done first)
    """
    user_id = current_user["user_id"]
    
    try:
        # Verify course exists
        course = db.query(Course).filter(Course.id == session_data.course_id).first()
        if not course:
            raise HTTPException(status_code=404, detail="Course not found")

        # Determine if working with lesson or block
        lesson = None
        block = None
        
        if session_data.lesson_id:
            lesson = db.query(CourseLesson).filter(
                and_(
                    CourseLesson.id == session_data.lesson_id,
                    CourseLesson.course_id == session_data.course_id,
                    CourseLesson.is_active == True
                )
            ).first()
            if not lesson:
                raise HTTPException(status_code=404, detail="Lesson not found or inactive")
                
        elif session_data.block_id:
            block = db.query(CourseBlock).filter(
                and_(
                    CourseBlock.id == session_data.block_id,
                    CourseBlock.course_id == session_data.course_id,
                    CourseBlock.is_active == True
                )
            ).first()
            if not block:
                raise HTTPException(status_code=404, detail="Course block not found or inactive")
                
            # Check if this is the very first block in the course (always accessible)
            is_first_block = block.week == 1 and block.block_number == 1
            
            if not is_first_block:
                # For any block that is NOT the very first one, check prerequisites
                previous_completed = True
                
                if block.block_number > 1:
                    # Check previous block in same week
                    prev_block = db.query(CourseBlock).filter(
                        and_(
                            CourseBlock.course_id == session_data.course_id,
                            CourseBlock.week == block.week,
                            CourseBlock.block_number == block.block_number - 1,
                            CourseBlock.is_active == True
                        )
                    ).first()
                    if prev_block:
                        prev_session = db.query(StudySession).filter(
                            and_(
                                StudySession.user_id == user_id,
                                StudySession.block_id == prev_block.id,
                                StudySession.status == "completed"
                            )
                        ).first()
                        if not prev_session:
                            previous_completed = False
                            
                elif block.week > 1:
                    # Check last block of previous week
                    prev_week_blocks = db.query(CourseBlock).filter(
                        and_(
                            CourseBlock.course_id == session_data.course_id,
                            CourseBlock.week == block.week - 1,
                            CourseBlock.is_active == True
                        )
                    ).order_by(CourseBlock.block_number.desc()).first()
                    
                    if prev_week_blocks:
                        prev_session = db.query(StudySession).filter(
                            and_(
                                StudySession.user_id == user_id,
                                StudySession.block_id == prev_week_blocks.id,
                                StudySession.status == "completed"
                            )
                        ).first()
                        if not prev_session:
                            previous_completed = False
                
                if not previous_completed:
                    raise HTTPException(
                        status_code=400, 
                        detail="You must complete the previous blocks first before accessing this one"
                    )
        else:
            raise HTTPException(status_code=400, detail="Either lesson_id or block_id must be provided")

        # Check if already completed
        existing_session = db.query(StudySession).filter(
            and_(
                StudySession.user_id == user_id,
                or_(
                    and_(StudySession.lesson_id == session_data.lesson_id) if session_data.lesson_id else False,
                    and_(StudySession.block_id == session_data.block_id) if session_data.block_id else False
                ),
                StudySession.status == "completed"
            )
        ).first()
        
        if existing_session:
            return existing_session  # Already completed

        # Create completed session - simple mark done
        completed_session = StudySession(
            user_id=user_id,
            course_id=session_data.course_id,
            lesson_id=session_data.lesson_id,
            block_id=session_data.block_id,
            status="completed",
            completion_percentage=100.0,
            started_at=datetime.utcnow(),
            ended_at=datetime.utcnow(),
            marked_done_at=datetime.utcnow()
        )
        db.add(completed_session)
        db.flush()  # Get session ID

        # Update or create student progress
        progress = db.query(StudentProgress).filter(
            and_(
                StudentProgress.user_id == user_id,
                StudentProgress.course_id == session_data.course_id
            )
        ).first()

        if not progress:
            # Count total content items for this course
            total_lessons = db.query(CourseLesson).filter(
                and_(CourseLesson.course_id == session_data.course_id, CourseLesson.is_active == True)
            ).count()
            total_blocks = db.query(CourseBlock).filter(
                and_(CourseBlock.course_id == session_data.course_id, CourseBlock.is_active == True)
            ).count()
            
            progress = StudentProgress(
                user_id=user_id,
                course_id=session_data.course_id,
                total_lessons=total_blocks if total_blocks > 0 else total_lessons,
                blocks_completed=1 if session_data.block_id else 0,
                lessons_completed=1 if session_data.lesson_id else 0,
                completion_percentage=0.0,
                sessions_count=1,
                total_study_time=0,
                started_at=datetime.utcnow(),
                last_activity=datetime.utcnow()
            )
            db.add(progress)
        else:
            # Update progress - increment completed count
            if session_data.block_id:
                progress.blocks_completed += 1
            else:
                progress.lessons_completed += 1
                
            progress.sessions_count += 1
            progress.last_activity = datetime.utcnow()
            
        # Recalculate completion percentage
        if progress.total_lessons > 0:
            completed_count = progress.blocks_completed if session_data.block_id else progress.lessons_completed
            progress.completion_percentage = (completed_count / progress.total_lessons) * 100
            
        # Check if course is complete
        if progress.completion_percentage >= 100:
            progress.completed_at = datetime.utcnow()

        db.commit()
        db.refresh(completed_session)

        target_info = lesson.title if lesson else (f"Block {block.week}.{block.block_number}: {block.title}" if block else "Unknown")
        logger.info("Marked content done", extra={
            "user_id": user_id,
            "course_id": session_data.course_id,
            "lesson_id": session_data.lesson_id,
            "block_id": session_data.block_id,
            "target": target_info
        })
        return completed_session
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to mark content as done: {str(e)}")

# ===============================
# ASSIGNMENT STATUS (minimal, avoid 404 for client UX)
# ===============================

@router.get("/../assignments/{assignment_id}/status")
async def get_assignment_status_minimal(
    assignment_id: int,
    db: db_dependency,
    current_user: dict = user_dependency
):
    """
    Minimal assignment status for current user.
    Returns student's assignment record if exists, else 404 with message.

    Frontend expects this route under /after-school/assignments/{id}/status.
    This shim lives here by using a relative path (..) from sessions prefix.
    """
    user_id = current_user["user_id"]
    try:
        assignment = db.query(CourseAssignment).filter(CourseAssignment.id == assignment_id).first()
        if not assignment:
            raise HTTPException(status_code=404, detail="Assignment not found")

        sa = db.query(StudentAssignment).filter(
            StudentAssignment.assignment_id == assignment_id,
            StudentAssignment.user_id == user_id
        ).first()

        if not sa:
            # Not assigned (treat as not found to keep noise low)
            raise HTTPException(status_code=404, detail="Not assigned")

        # Build a minimal status payload compatible with frontend types
        required_pct = 80
        can_retry = False  # Retry policy not implemented here

        return {
            "assignment": {
                "id": assignment.id,
                "title": assignment.title,
                "description": assignment.description or assignment.title,
                "points": assignment.points or 100,
                "required_percentage": required_pct
            },
            "student_assignment": {
                "id": sa.id,
                "status": sa.status,
                "grade": float(sa.grade) if sa.grade is not None else 0.0,
                "submitted_at": sa.submitted_at.isoformat() if sa.submitted_at else None,
                "feedback": sa.feedback or None
            },
            "attempts_info": {
                "attempts_used": 0,
                "attempts_remaining": 0,
                "can_retry": can_retry
            },
            "message": "OK",
            "passing_grade": (sa.grade or 0) >= required_pct
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get assignment status: {str(e)}")

@router.get("/blocks/{block_id}/availability")
async def check_block_availability(
    block_id: int,
    db: db_dependency,
    current_user: dict = user_dependency
):
    """
    Check if a block is available for the current user.
    Returns availability status and reason if not available.
    """
    user_id = current_user["user_id"]
    
    # Get the block
    block = db.query(CourseBlock).filter(CourseBlock.id == block_id).first()
    if not block:
        raise HTTPException(status_code=404, detail="Block not found")
    
    # Check if already completed
    existing_session = db.query(StudySession).filter(
        and_(
            StudySession.user_id == user_id,
            StudySession.block_id == block_id,
            StudySession.status == "completed"
        )
    ).first()
    
    if existing_session:
        return {
            "available": True,
            "completed": True,
            "reason": "Block already completed"
        }
    
    # Very first block in course is always available
    is_first_block = block.week == 1 and block.block_number == 1
    if is_first_block:
        return {
            "available": True,
            "completed": False,
            "reason": "First block in course - always available"
        }
    
    # For any other block, check prerequisites
    previous_completed = True
    missing_prerequisite = None
    
    if block.block_number > 1:
        # Check previous block in same week
        prev_block = db.query(CourseBlock).filter(
            and_(
                CourseBlock.course_id == block.course_id,
                CourseBlock.week == block.week,
                CourseBlock.block_number == block.block_number - 1,
                CourseBlock.is_active == True
            )
        ).first()
        
        if prev_block:
            prev_session = db.query(StudySession).filter(
                and_(
                    StudySession.user_id == user_id,
                    StudySession.block_id == prev_block.id,
                    StudySession.status == "completed"
                )
            ).first()
            
            if not prev_session:
                previous_completed = False
                missing_prerequisite = f"Block {prev_block.week}.{prev_block.block_number}: {prev_block.title}"
                
    elif block.week > 1:
        # Check last block of previous week
        prev_week_blocks = db.query(CourseBlock).filter(
            and_(
                CourseBlock.course_id == block.course_id,
                CourseBlock.week == block.week - 1,
                CourseBlock.is_active == True
            )
        ).order_by(CourseBlock.block_number.desc()).first()
        
        if prev_week_blocks:
            prev_session = db.query(StudySession).filter(
                and_(
                    StudySession.user_id == user_id,
                    StudySession.block_id == prev_week_blocks.id,
                    StudySession.status == "completed"
                )
            ).first()
            
            if not prev_session:
                previous_completed = False
                missing_prerequisite = f"Block {prev_week_blocks.week}.{prev_week_blocks.block_number}: {prev_week_blocks.title}"
    
    return {
        "available": previous_completed,
        "completed": False,
        "reason": f"Must complete {missing_prerequisite} first" if not previous_completed else "Available"
    }

@router.get("/", response_model=List[StudySessionOut])
async def get_user_sessions(
    db: db_dependency,
    current_user: dict = user_dependency,
    course_id: Optional[int] = Query(None, description="Filter by course"),
    block_id: Optional[int] = Query(None, description="Filter by block"),
    lesson_id: Optional[int] = Query(None, description="Filter by lesson"),
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(50, ge=1, le=100, description="Limit results")
):
    """Get user's study sessions with richer filtering (course / block / lesson / status)."""
    user_id = current_user["user_id"]
    query = db.query(StudySession).filter(StudySession.user_id == user_id)
    if course_id:
        query = query.filter(StudySession.course_id == course_id)
    if block_id:
        query = query.filter(StudySession.block_id == block_id)
    if lesson_id:
        query = query.filter(StudySession.lesson_id == lesson_id)
    if status:
        query = query.filter(StudySession.status == status)
    sessions = query.order_by(desc(StudySession.started_at)).limit(limit).all()
    return sessions

# ===============================
# PROGRESS TRACKING ENDPOINTS (must be before /{session_id} route)
# ===============================

@router.get("/course/{course_id}/blocks-progress")
async def get_course_blocks_progress(
    course_id: int,
    db: db_dependency,
    current_user: dict = user_dependency
):
    """
    Get user's progress through all blocks in a course with completion status
    """
    user_id = current_user["user_id"]
    
    # Get all blocks for this course, ordered by week and block number
    blocks = db.query(CourseBlock).filter(
        and_(
            CourseBlock.course_id == course_id,
            CourseBlock.is_active == True
        )
    ).order_by(CourseBlock.week, CourseBlock.block_number).all()
    
    if not blocks:
        raise HTTPException(status_code=404, detail="No blocks found for this course")
    
    # Get all completed sessions for this user and course
    completed_sessions = db.query(StudySession).filter(
        and_(
            StudySession.user_id == user_id,
            StudySession.course_id == course_id,
            StudySession.status == "completed"
        )
    ).all()
    
    # Create a set of completed block IDs for quick lookup
    completed_block_ids = {session.block_id for session in completed_sessions if session.block_id}
    
    # Build response with availability logic
    blocks_progress = []
    for i, block in enumerate(blocks):
        is_completed = block.id in completed_block_ids
        
        # Determine availability
        is_available = False
        if i == 0:  # First block is always available
            is_available = True
        elif is_completed:  # Already completed blocks are available
            is_available = True
        else:  # Check if previous block is completed
            prev_block = blocks[i-1]
            if prev_block.id in completed_block_ids:
                is_available = True
        
        blocks_progress.append({
            "block_id": block.id,
            "week": block.week,
            "block_number": block.block_number,
            "title": block.title,
            "description": block.description,
            "duration_minutes": block.duration_minutes,
            "is_completed": is_completed,
            "is_available": is_available,
            "completed_at": next(
                (session.marked_done_at or session.ended_at for session in completed_sessions 
                 if session.block_id == block.id), None
            )
        })
    
    # Calculate overall progress
    total_blocks = len(blocks)
    completed_count = len(completed_block_ids)
    completion_percentage = (completed_count / total_blocks * 100) if total_blocks > 0 else 0
    
    return {
        "course_id": course_id,
        "total_blocks": total_blocks,
        "completed_blocks": completed_count,
        "completion_percentage": completion_percentage,
        "blocks": blocks_progress
    }

@router.get("/progress", response_model=List[StudentProgressOut])
async def get_student_progress(
    db: db_dependency,
    current_user: dict = user_dependency,
    course_id: Optional[int] = Query(None, description="Filter by course")
):
    """
    Get student's progress across courses
    """
    user_id = current_user["user_id"]
    
    query = db.query(StudentProgress).filter(StudentProgress.user_id == user_id)
    
    if course_id:
        query = query.filter(StudentProgress.course_id == course_id)
    
    progress_records = query.all()
    
    return progress_records

@router.get("/progress/{course_id}", response_model=StudentProgressOut)
async def get_course_progress(
    course_id: int,
    db: db_dependency,
    current_user: dict = user_dependency
):
    """Return (or create if absent) the user's progress for a course.

    If progress does not exist yet we seed a minimal record so frontend never
    has to treat 404 specially.
    """
    user_id = current_user["user_id"]
    progress = db.query(StudentProgress).filter(
        and_(StudentProgress.user_id == user_id, StudentProgress.course_id == course_id)
    ).first()
    if not progress:
        # Ensure course exists to avoid orphan progress
        if not db.query(Course.id).filter(Course.id == course_id).first():
            raise HTTPException(status_code=404, detail="Course not found")
        # Compute total lessons/blocks for initial denominator
        total_lessons = db.query(CourseLesson).filter(
            and_(CourseLesson.course_id == course_id, CourseLesson.is_active == True)
        ).count()
        total_blocks = db.query(CourseBlock).filter(
            and_(CourseBlock.course_id == course_id, CourseBlock.is_active == True)
        ).count()
        total_content = total_blocks if total_blocks > 0 else total_lessons
        progress = StudentProgress(
            user_id=user_id,
            course_id=course_id,
            total_lessons=total_content,
            lessons_completed=0,
            completion_percentage=0.0,
            sessions_count=0,
            total_study_time=0,
            last_activity=datetime.utcnow()
        )
        db.add(progress)
        db.commit()
        db.refresh(progress)
    return progress

@router.get("/{session_id}", response_model=StudySessionOut)
async def get_session_details(
    session_id: int,
    db: db_dependency,
    current_user: dict = user_dependency
):
    """
    Get specific study session details
    """
    user_id = current_user["user_id"]
    
    session = db.query(StudySession).filter(
        and_(
            StudySession.id == session_id,
            StudySession.user_id == user_id
        )
    ).first()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Study session not found"
        )
    
    return session

# ===============================
# BULK AI GRADING ENDPOINTS (KANA INTEGRATION)
# ===============================



# ===============================
# ANALYTICS ENDPOINTS
# ===============================

@router.get("/analytics/summary")
async def get_learning_analytics(
    db: db_dependency,
    current_user: dict = user_dependency,
    days: int = Query(30, description="Number of days to analyze")
):
    """Learning analytics summary (sessions, time, completion, streak)."""
    if days < 1:
        raise HTTPException(status_code=400, detail="days must be >= 1")
    user_id = current_user["user_id"]
    since_date = datetime.utcnow() - timedelta(days=days)
    sessions = db.query(StudySession).filter(
        and_(StudySession.user_id == user_id, StudySession.started_at >= since_date)
    ).all()
    total_sessions = len(sessions)
    total_study_time = sum(s.duration_minutes or 0 for s in sessions)
    completed_sessions = len([s for s in sessions if s.status == "completed"])
    scored = [s for s in sessions if s.ai_score is not None]
    average_score = round(sum(s.ai_score for s in scored) / len(scored), 2) if scored else None
    study_dates = {s.started_at.date() for s in sessions}
    streak = 0
    cursor = datetime.utcnow().date()
    while cursor in study_dates:
        streak += 1
        cursor = cursor - timedelta(days=1)
    return {
        "period_days": days,
        "total_sessions": total_sessions,
        "completed_sessions": completed_sessions,
        "total_study_time_minutes": total_study_time,
        "average_score": average_score,
        "study_streak_days": streak,
        "sessions_per_day": round(total_sessions / days, 2) if days else 0
    }

# ===============================
# KANA AI GRADING ENDPOINTS  
# ===============================

@router.post("/grade-course-submissions")
async def grade_course_submissions(
    request: dict,
    db: db_dependency,
    current_user: dict = user_dependency
):
    """
    Grade submissions for multiple students using Gemini AI
    
    Comprehensive AI-powered grading system that provides:
    - Detailed feedback and scoring using Gemini AI
    - Support for lessons, blocks, and assignments from AI-generated courses
    - Automatic grade distribution to StudentAssignment records
    - Intelligent rubric-based assessment
    - Personalized feedback for each student
    
    No manual grading required - fully AI-driven assessment process
    """
    try:

        # Extract data from request with enhanced support
        course_id = request.get("course_id")
        lesson_id = request.get("lesson_id", None)  # Legacy lesson support
        block_id = request.get("block_id", None)  # AI-generated course blocks
        assignment_id = request.get("assignment_id", None)  # Specific assignments
        student_ids = request.get("student_ids", [])
        grade_all_students = request.get("grade_all_students", False)

        logger.info(
            "Bulk grading request received",
            extra={
                "course_id": course_id,
                "lesson_id": lesson_id,
                "block_id": block_id,
                "assignment_id": assignment_id,
                "grade_all_students": grade_all_students,
                "student_ids": student_ids,
            },
        )

        if not course_id:
            raise HTTPException(status_code=400, detail="Course ID is required")

        # Get course details
        course = db.query(Course).filter(Course.id == course_id).first()
        if not course:
            raise HTTPException(status_code=404, detail="Course not found")

        lesson = None
        block = None
        assignment = None
        grading_context = ""

        # Get lesson context (legacy)
        if lesson_id:
            lesson = db.query(CourseLesson).filter(
                and_(CourseLesson.id == lesson_id, CourseLesson.course_id == course_id)
            ).first()
            if not lesson:
                raise HTTPException(status_code=404, detail="Lesson not found in this course")
            grading_context = f"Lesson: {lesson.title}"

        # Get block context (AI-generated courses)
        if block_id:
            block = db.query(CourseBlock).filter(
                and_(CourseBlock.id == block_id, CourseBlock.course_id == course_id)
            ).first()
            if not block:
                raise HTTPException(status_code=404, detail="Course block not found")
            grading_context = f"Block {block.week}.{block.block_number}: {block.title}"

        # Get assignment context (comprehensive grading)
        if assignment_id:
            assignment = db.query(CourseAssignment).filter(
                and_(CourseAssignment.id == assignment_id, CourseAssignment.course_id == course_id)
            ).first()
            if not assignment:
                raise HTTPException(status_code=404, detail="Assignment not found in this course")
            grading_context = f"Assignment: {assignment.title}"

        if not grading_context:
            grading_context = f"Course: {course.title} (All content)"

        logger.info(
            "Resolved grading context",
            extra={
                "course_id": course_id,
                "grading_context": grading_context,
                "course_title": course.title,
            },
        )

    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed preparing bulk grading request")
        raise HTTPException(status_code=500, detail="Internal server error preparing grading request")
    
    # Get submissions to grade with enhanced filtering
    submissions_query = db.query(AISubmission).options(
        joinedload(AISubmission.session),
        joinedload(AISubmission.course),
        joinedload(AISubmission.lesson),
        joinedload(AISubmission.block)
    ).filter(AISubmission.course_id == course_id)
    
    # Filter by content type if specified
    if lesson_id:
        submissions_query = submissions_query.filter(AISubmission.lesson_id == lesson_id)
    
    if block_id:
        submissions_query = submissions_query.filter(AISubmission.block_id == block_id)
    
    if assignment_id:
        submissions_query = submissions_query.filter(AISubmission.assignment_id == assignment_id)
    
    # Filter by students if specified
    if not grade_all_students and student_ids:
        submissions_query = submissions_query.filter(AISubmission.user_id.in_(student_ids))
    
    # Only get PDF submissions for KANA grading
    submissions = submissions_query.filter(AISubmission.file_type == "pdf").all()
    
    if not submissions:
        raise HTTPException(status_code=404, detail="No PDF submissions found for grading")
    
    # Collect submission data for K.A.N.A. processing with enhanced context
    grading_data = []
    for submission in submissions:
        try:
            # Get student name from user table
            from models.users_models import User
            user = db.query(User).filter(User.id == submission.user_id).first()
            student_name = f"{user.fname or ''} {user.lname or ''}".strip() if user else f"User {submission.user_id}"
            if not student_name:
                student_name = f"User {submission.user_id}"
            
            # Determine content title based on what's available
            content_title = "General Submission"
            if assignment:
                content_title = assignment.title
            elif lesson:
                content_title = lesson.title
            elif submission.lesson:
                content_title = submission.lesson.title
            elif block:
                content_title = f"Block {block.week}.{block.block_number}: {block.title}"
            elif submission.block:
                content_title = f"Block {submission.block.week}.{submission.block.block_number}: {submission.block.title}"
            
            submission_data = {
                "submission_id": submission.id,
                "user_id": submission.user_id,
                "student_name": student_name,
                "course_title": course.title,
                "content_title": content_title,
                "assignment_id": submission.assignment_id,
                "lesson_id": submission.lesson_id,
                "block_id": submission.block_id,
                "file_path": submission.file_path,
                "filename": submission.original_filename,
                "submission_type": submission.submission_type,
                "has_work": True
            }
            grading_data.append(submission_data)
            logger.debug(
                "Queued submission for grading",
                extra={
                    "submission_id": submission.id,
                    "user_id": submission.user_id,
                    "student_name": student_name,
                    "content_title": content_title,
                },
            )
                
        except Exception as e:
            logger.exception(
                "Failed preparing submission for grading",
                extra={"submission_id": submission.id, "user_id": submission.user_id},
            )
            continue
    
    if not grading_data:
        raise HTTPException(status_code=404, detail="No valid submissions found for grading")
    
    # Process submissions using Gemini AI grading
    try:
        logger.info(
            "Starting Gemini AI grading",
            extra={"submission_count": len(grading_data), "course_id": course_id},
        )
        
        # Prepare grading context and rubric
        assignment_title = ""
        assignment_description = ""
        rubric = ""
        
        if assignment:
            assignment_title = assignment.title
            assignment_description = assignment.description
            rubric = assignment.rubric or assignment.description
        elif lesson:
            assignment_title = f"Lesson: {lesson.title}"
            assignment_description = lesson.learning_objectives or lesson.content or ""
            rubric = lesson.learning_objectives or f"Assessment based on lesson: {lesson.title}"
        elif block:
            assignment_title = f"Block {block.week}.{block.block_number}: {block.title}"
            assignment_description = block.description or ""
            objectives_text = ", ".join(block.learning_objectives) if block.learning_objectives else ""
            rubric = objectives_text or f"Assessment based on learning block: {block.title}"
        else:
            assignment_title = f"Course Assessment: {course.title}"
            assignment_description = course.description or f"General assessment for {course.title}"
            rubric = course.description or "General course assessment criteria"
        
        logger.info(
            "Prepared grading context",
            extra={
                "assignment_title": assignment_title,
                "rubric_preview": rubric[:80] if rubric else None,
                "assignment_id": assignment_id,
                "lesson_id": lesson_id,
                "block_id": block_id,
            },
        )

        max_points = assignment.points if assignment and assignment.points else 100

        submissions_for_ai = []
        for submission_data in grading_data:
            pdf_path = submission_data.get("file_path", "")
            if not pdf_path:
                logger.warning(
                    "Submission missing file path",
                    extra={"submission_id": submission_data["submission_id"]},
                )
                continue

            pdf_full_path = Path(pdf_path)
            if not pdf_full_path.is_absolute():
                pdf_full_path = Path(os.getcwd()) / pdf_full_path

            try:
                pdf_bytes = pdf_full_path.read_bytes()
            except FileNotFoundError:
                logger.warning(
                    "Submission file not found",
                    extra={
                        "submission_id": submission_data["submission_id"],
                        "file_path": str(pdf_full_path),
                    },
                )
                continue
            except Exception:
                logger.exception(
                    "Failed reading submission file",
                    extra={
                        "submission_id": submission_data["submission_id"],
                        "file_path": str(pdf_full_path),
                    },
                )
                continue

            submissions_for_ai.append(
                {
                    "submission_id": submission_data["submission_id"],
                    "user_id": submission_data["user_id"],
                    "student_name": submission_data["student_name"],
                    "file_bytes": pdf_bytes,
                    "filename": submission_data.get("filename") or f"submission_{submission_data['submission_id']}.pdf",
                    "submission_type": submission_data["submission_type"],
                }
            )

        if not submissions_for_ai:
            raise HTTPException(status_code=404, detail="No valid submissions found for processing")

        gemini_results = {"status": "completed", "student_results": [], "batch_summary": {}}
        graded_results = []

        for item in submissions_for_ai:
            try:
                grade_result = await gemini_service.grade_submission_from_file(
                    file_bytes=item["file_bytes"],
                    filename=item["filename"],
                    assignment_title=assignment_title,
                    assignment_description=assignment_description,
                    rubric=rubric,
                    max_points=max_points,
                    submission_type=item.get("submission_type", "homework"),
                )

                # Extract score from raw data (best effort, handle malformed keys)
                extracted_score = None
                if isinstance(grade_result, dict):
                    score_val = grade_result.get('score') or grade_result.get('"score"') or grade_result.get('percentage') or grade_result.get('"percentage"')
                    if isinstance(score_val, (int, float)):
                        extracted_score = float(score_val)
                    elif isinstance(score_val, str):
                        cleaned = score_val.rstrip(',').strip()
                        try:
                            extracted_score = float(cleaned)
                        except:
                            pass
                
                # If no score extracted, try strict grading
                if extracted_score is None:
                    try:
                        strict = await gemini_service.grade_submission_from_file_strict(
                            file_bytes=item["file_bytes"],
                            filename=item["filename"],
                            assignment_title=assignment_title,
                            assignment_description=assignment_description,
                            max_points=max_points,
                            submission_type=item.get("submission_type", "homework"),
                        )
                        # Extract score from strict result
                        if isinstance(strict, dict):
                            strict_score_val = strict.get('score') or strict.get('"score"') or strict.get('percentage') or strict.get('"percentage"')
                            if isinstance(strict_score_val, (int, float)):
                                extracted_score = float(strict_score_val)
                                grade_result["percentage"] = extracted_score
                            elif isinstance(strict_score_val, str):
                                cleaned = strict_score_val.rstrip(',').strip()
                                try:
                                    extracted_score = float(cleaned)
                                    grade_result["percentage"] = extracted_score
                                except:
                                    pass
                            
                            # Copy feedback if missing
                            if not grade_result.get("overall_feedback"):
                                feedback_val = strict.get('overall_feedback') or strict.get('"overall_feedback"') or strict.get('detailed_feedback') or strict.get('"detailed_feedback"')
                                if isinstance(feedback_val, str):
                                    grade_result["overall_feedback"] = feedback_val.strip('"').strip(',').strip()
                            
                            grade_result["strict_fallback"] = True
                    except Exception as strict_error:
                        logger.warning(
                            "Strict Gemini grading fallback failed",
                            extra={
                                "submission_id": item["submission_id"],
                                "user_id": item["user_id"],
                                "error": str(strict_error),
                            },
                        )

                grade_result.update(
                    {
                        "submission_id": item["submission_id"],
                        "user_id": item["user_id"],
                        "student_name": item.get("student_name", "Unknown"),
                        "success": True,
                    }
                )
                graded_results.append(grade_result)
            except Exception as grading_error:
                logger.exception(
                    "Gemini grading failed for submission",
                    extra={"submission_id": item["submission_id"], "user_id": item["user_id"]},
                )
                graded_results.append(
                    {
                        "submission_id": item["submission_id"],
                        "user_id": item["user_id"],
                        "student_name": item.get("student_name", "Unknown"),
                        "success": False,
                        "error": str(grading_error),
                        "percentage": 0.0,
                        "overall_feedback": "Gemini grading failed",
                    }
                )

        gemini_results["student_results"] = graded_results
        successes = [r for r in graded_results if r.get("success")]
        gemini_results["batch_summary"] = {
            "total_submissions": len(graded_results),
            "successfully_graded": len(successes),
            "failed_grades": len(graded_results) - len(successes),
            "success_rate": (len(successes) / len(graded_results) * 100) if graded_results else 0,
        }

        logger.info(
            "Gemini AI grading completed",
            extra={
                "course_id": course_id,
                "graded_count": len(successes),
                "failed_count": gemini_results["batch_summary"].get("failed_grades", 0),
            },
        )
            
        # Store Gemini AI grades in database
        grading_results = []
        
        for result in gemini_results.get("student_results", []):
            if result.get("success", False):
                submission_id = result.get("submission_id")
                student_name = result.get("student_name", "")
                
                # Extract score and feedback from raw data (best effort)
                extracted_score = None
                extracted_feedback = None
                
                if isinstance(result, dict):
                    # Extract score (handle malformed keys)
                    score_val = result.get('score') or result.get('"score"') or result.get('percentage') or result.get('"percentage"')
                    if isinstance(score_val, (int, float)):
                        extracted_score = float(score_val)
                    elif isinstance(score_val, str):
                        cleaned = score_val.rstrip(',').strip()
                        try:
                            extracted_score = float(cleaned)
                        except:
                            pass
                    
                    # Extract feedback (handle malformed keys)
                    feedback_val = result.get('overall_feedback') or result.get('"overall_feedback"') or result.get('detailed_feedback') or result.get('"detailed_feedback"')
                    if isinstance(feedback_val, str):
                        extracted_feedback = feedback_val.strip('"').strip(',').strip()
                
                try:
                    # Update the AI submission with Gemini results
                    submission = db.query(AISubmission).filter(AISubmission.id == submission_id).first()
                    if submission:
                        submission.ai_processed = True
                        submission.ai_score = extracted_score
                        submission.ai_feedback = extracted_feedback
                        submission.ai_corrections = None  # Not using normalized fields
                        submission.ai_strengths = None  # Not using normalized fields
                        submission.ai_improvements = None  # Not using normalized fields
                        submission.processed_at = datetime.utcnow()
                        
                        # Update the associated study session
                        if submission.session_id:
                            session = db.query(StudySession).filter(StudySession.id == submission.session_id).first()
                            if session:
                                session.ai_score = extracted_score
                                session.ai_feedback = extracted_feedback
                                session.ai_recommendations = None  # Not using normalized fields
                                session.updated_at = datetime.utcnow()
                        
                        # Update StudentAssignment record if this is assignment-based
                        if submission.assignment_id:
                            student_assignment = db.query(StudentAssignment).filter(
                                and_(
                                    StudentAssignment.user_id == submission.user_id,
                                    StudentAssignment.assignment_id == submission.assignment_id
                                )
                            ).first()
                            
                            if student_assignment:
                                student_assignment.ai_grade = extracted_score
                                student_assignment.grade = extracted_score  # AI grade is the final grade
                                student_assignment.feedback = extracted_feedback
                                student_assignment.status = "graded"
                                student_assignment.updated_at = datetime.utcnow()
                                logger.info(
                                    "Student assignment updated with AI grade",
                                    extra={
                                        "student_assignment_id": student_assignment.id,
                                        "submission_id": submission_id,
                                        "percentage": extracted_score,
                                    },
                                )
                            else:
                                logger.warning(
                                    "Student assignment not found for AI update",
                                    extra={
                                        "submission_id": submission_id,
                                        "user_id": submission.user_id,
                                        "assignment_id": submission.assignment_id,
                                    },
                                )
                        
                        grading_results.append({
                            "submission_id": submission_id,
                            "user_id": submission.user_id,
                            "student_name": student_name,
                            "score": result.get("score", 0),
                            "percentage": extracted_score,
                            "grade_letter": result.get("grade_letter", ""),
                            "feedback": extracted_feedback,
                            "overall_feedback": result.get("overall_feedback") or extracted_feedback,
                            "strengths": result.get("strengths", []),
                            "improvements": result.get("improvements", []),
                            "recommendations": result.get("recommendations", []),
                            "graded_by": result.get("graded_by", "Gemini AI"),
                            "raw": result,  # Include raw data instead of normalized
                            "success": True
                        })
                    
                except Exception as grade_error:
                    logger.exception(
                        "Failed persisting AI grade",
                        extra={"submission_id": submission_id, "user_id": submission.user_id},
                    )
                    grading_results.append({
                        "student_name": student_name,
                        "error": str(grade_error),
                        "success": False
                    })
            else:
                # Handle failed grading
                grading_results.append({
                    "student_name": result.get("student_name", "Unknown"),
                    "error": result.get("error", "Grading failed"),
                    "success": False
                })
        
        # Commit all updates to database
        try:
            db.commit()
            successful_grades = len([r for r in grading_results if r.get("success")])
            logger.info(
                "Successfully persisted AI grades",
                extra={
                    "course_id": course_id,
                    "successful_grades": successful_grades,
                    "failed_grades": len(grading_results) - successful_grades,
                },
            )
        except Exception as commit_error:
            db.rollback()
            logger.exception(
                "Failed committing AI grades",
                extra={"course_id": course_id},
            )
            raise HTTPException(status_code=500, detail=f"Failed to save Gemini grades: {str(commit_error)}")
        
        # Return comprehensive response with Gemini grading results
        return {
            "status": "success",
            "message": f"Successfully graded {len([r for r in grading_results if r.get('success')])} submissions using Gemini AI",
            "grading_service": "Gemini AI",
            "course": {
                "id": course.id,
                "title": course.title,
                "description": course.description,
                "subject": course.subject
            },
            "content_context": {
                "assignment": {
                    "id": assignment.id,
                    "title": assignment.title,
                    "description": assignment.description
                } if assignment else None,
                "lesson": {
                    "id": lesson.id,
                    "title": lesson.title,
                    "learning_objectives": lesson.learning_objectives
                } if lesson else None,
                "block": {
                    "id": block.id,
                    "title": block.title,
                    "week": block.week,
                    "block_number": block.block_number
                } if block else None
            },
            "grading_results": grading_results,
            "batch_summary": gemini_results.get("batch_summary", {}),
            "total_submissions": len(grading_data),
            "submissions_graded": len([r for r in grading_results if r.get("success")]),
            "submissions_failed": len([r for r in grading_results if not r.get("success")]),
            "processed_at": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as gemini_error:
        if gemini_service.config.is_quota_error(gemini_error) if hasattr(gemini_service, "config") else False:
            logger.warning(
                "Gemini quota or rate limit encountered during bulk grading",
                extra={"course_id": course_id},
            )
        else:
            logger.exception(
                "Unexpected Gemini AI grading error",
                extra={"course_id": course_id},
            )
        raise HTTPException(status_code=500, detail="Gemini AI grading service error")

@router.get("/submissions/pending-grade")
async def get_pending_submissions_for_grading(
    db: db_dependency,
    current_user: dict = user_dependency,
    course_id: Optional[int] = Query(None, description="Filter by course"),
    lesson_id: Optional[int] = Query(None, description="Filter by lesson")
):
    """
    Get all pending submissions that need grading
    Accessible to all authenticated users
    """
    
    query = db.query(AISubmission).options(
        joinedload(AISubmission.course),
        joinedload(AISubmission.lesson)
    ).filter(
        or_(
            AISubmission.ai_processed == False,
            AISubmission.ai_score.is_(None)
        ),
        AISubmission.file_type == "pdf"  # Only PDF submissions for KANA grading
    )
    
    if course_id:
        query = query.filter(AISubmission.course_id == course_id)
    
    if lesson_id:
        query = query.filter(AISubmission.lesson_id == lesson_id)
    
    pending_submissions = query.all()
    
    # Group by course and lesson for easier bulk grading
    grouped_submissions = {}
    for submission in pending_submissions:
        course_key = f"course_{submission.course_id}"
        if course_key not in grouped_submissions:
            grouped_submissions[course_key] = {
                "course": {
                    "id": submission.course.id,
                    "title": submission.course.title,
                    "subject": submission.course.subject
                },
                "lessons": {}
            }
        
        lesson_key = f"lesson_{submission.lesson_id}"
        if lesson_key not in grouped_submissions[course_key]["lessons"]:
            grouped_submissions[course_key]["lessons"][lesson_key] = {
                "lesson": {
                    "id": submission.lesson.id,
                    "title": submission.lesson.title
                },
                "submissions": []
            }
        
        # Get student name
        from models.users_models import User
        user = db.query(User).filter(User.id == submission.user_id).first()
        student_name = f"{user.fname or ''} {user.lname or ''}".strip() if user else f"User {submission.user_id}"
        
        grouped_submissions[course_key]["lessons"][lesson_key]["submissions"].append({
            "id": submission.id,
            "user_id": submission.user_id,
            "student_name": student_name,
            "filename": submission.original_filename,
            "submission_type": submission.submission_type,
            "submitted_at": submission.submitted_at.isoformat() if submission.submitted_at else None
        })
    
    return {
        "total_pending": len(pending_submissions),
        "grouped_submissions": grouped_submissions
    }

# ===============================
# STUDENT ASSIGNMENT MANAGEMENT ENDPOINTS
# ===============================

@router.get("/assignments/student/{user_id}", response_model=List[StudentAssignmentOut])
async def get_student_assignments(
    user_id: int,
    db: db_dependency,
    current_user: dict = user_dependency,
    course_id: Optional[int] = Query(None, description="Filter by course"),
    status: Optional[str] = Query(None, description="Filter by status: assigned, submitted, graded, overdue"),
    limit: int = Query(50, ge=1, le=100, description="Limit results")
):
    """
    Get all assignments for a specific student with comprehensive filtering
    
    This endpoint provides detailed assignment tracking for AI-generated course assignments:
    - Shows all student assignments with current status
    - Filters by course, assignment status, and date ranges
    - Includes grade information and feedback when available
    - Supports both graded and pending assignments
    
    Perfect for student dashboards and progress tracking
    """
    try:
        # Verify user access (students can only see their own assignments unless admin)
        current_user_id = current_user["user_id"]
        if user_id != current_user_id:
            # Add role-based access control here if needed
            logger.warning(
                "User attempting to access another student's assignments",
                extra={"requester_id": current_user_id, "target_user_id": user_id},
            )
        
        query = db.query(StudentAssignment).options(
            joinedload(StudentAssignment.assignment)
        ).filter(StudentAssignment.user_id == user_id)
        
        if course_id:
            query = query.filter(StudentAssignment.course_id == course_id)
        
        if status:
            query = query.filter(StudentAssignment.status == status)
        
        # Handle overdue status dynamically
        if status == "overdue":
            query = query.filter(
                and_(
                    StudentAssignment.due_date < datetime.utcnow(),
                    StudentAssignment.status.in_(["assigned", "submitted"])
                )
            )
        
        assignments = query.order_by(StudentAssignment.due_date.asc()).limit(limit).all()

        logger.info(
            "Retrieved student assignments",
            extra={
                "user_id": user_id,
                "assignment_count": len(assignments),
                "filters": {"course_id": course_id, "status": status, "limit": limit},
            },
        )
        return assignments

    except Exception as e:
        logger.exception(
            "Failed retrieving student assignments",
            extra={"user_id": user_id},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve assignments: {str(e)}"
        )

@router.get("/assignments/course/{course_id}", response_model=List[StudentAssignmentOut])
async def get_course_assignments_overview(
    course_id: int,
    db: db_dependency,
    current_user: dict = user_dependency,
    assignment_id: Optional[int] = Query(None, description="Filter by specific assignment"),
    student_ids: Optional[List[int]] = Query(None, description="Filter by specific students"),
    include_stats: bool = Query(True, description="Include assignment completion statistics")
):
    """
    Get assignment overview for a course with comprehensive analytics
    
    This endpoint provides course-level assignment management and analytics:
    - Shows all student assignments within a course
    - Filters by specific assignments or students
    - Provides completion statistics and grade distributions
    - Helps teachers track overall course progress
    
    Useful for course dashboards and progress monitoring
    """
    try:
        # Verify course exists and user has access
        course = db.query(Course).filter(Course.id == course_id).first()
        if not course:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Course not found"
            )
        
        query = db.query(StudentAssignment).options(
            joinedload(StudentAssignment.assignment)
        ).filter(StudentAssignment.course_id == course_id)
        
        if assignment_id:
            query = query.filter(StudentAssignment.assignment_id == assignment_id)
        
        if student_ids:
            query = query.filter(StudentAssignment.user_id.in_(student_ids))
        
        assignments = query.order_by(
            StudentAssignment.assignment_id, 
            StudentAssignment.due_date
        ).all()
        
        # Calculate statistics if requested
        stats = {}
        if include_stats:
            total_assignments = len(assignments)
            submitted_count = len([a for a in assignments if a.submitted_at is not None])
            graded_count = len([a for a in assignments if a.grade is not None])
            overdue_count = len([
                a for a in assignments 
                if a.due_date < datetime.utcnow() and a.status in ["assigned", "submitted"]
            ])
            
            grades = [a.grade for a in assignments if a.grade is not None]
            avg_grade = sum(grades) / len(grades) if grades else None
            
            stats = {
                "total_assignments": total_assignments,
                "submitted_count": submitted_count,
                "graded_count": graded_count,
                "overdue_count": overdue_count,
                "submission_rate": (submitted_count / total_assignments * 100) if total_assignments > 0 else 0,
                "grading_completion": (graded_count / total_assignments * 100) if total_assignments > 0 else 0,
                "average_grade": round(avg_grade, 2) if avg_grade is not None else None
            }
        
        logger.info(
            "Course assignments overview",
            extra={
                "course_id": course_id,
                "assignments_total": len(assignments),
                "filters": {
                    "assignment_id": assignment_id,
                    "student_ids": student_ids,
                    "include_stats": include_stats
                },
                "stats": stats if include_stats else None
            }
        )
        
        return assignments
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(
            "Failed retrieving course assignments overview",
            extra={"course_id": course_id},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve course assignments: {str(e)}"
        )

@router.post("/assignments/{assignment_id}/auto-grade")
async def auto_grade_assignment_submission(
    assignment_id: int,
    submission_data: dict,
    db: db_dependency,
    current_user: dict = user_dependency
):
    """
    Automatically grade a single assignment submission using Gemini AI
    
    This endpoint provides instant AI grading when students submit assignments:
    - Processes submission immediately upon upload
    - Uses Gemini AI for comprehensive assessment
    - Updates StudentAssignment records automatically
    - Provides detailed feedback and scoring
    - No manual intervention required
    
    Called automatically when students submit assignment work
    """
    user_id = current_user["user_id"]

    try:
        assignment = db.query(CourseAssignment).filter(CourseAssignment.id == assignment_id).first()
        if not assignment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Assignment not found"
            )

        student_assignment = db.query(StudentAssignment).options(
            joinedload(StudentAssignment.assignment)
        ).filter(
            and_(
                StudentAssignment.assignment_id == assignment_id,
                StudentAssignment.user_id == user_id
            )
        ).first()

        if not student_assignment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Student assignment record not found"
            )

        submission_content = submission_data.get("content") or ""
        submission_file_path = submission_data.get("file_path")
        file_bytes: Optional[bytes] = None
        filename: Optional[str] = None
        raw_path: Optional[Path] = None

        current_time = datetime.utcnow()

        # Enforce per-assignment attempt limits before processing a new submission
        twenty_four_hours_ago = current_time - timedelta(hours=24)
        recent_attempts_before = db.query(func.count(AISubmission.id)).filter(
            and_(
                AISubmission.user_id == user_id,
                AISubmission.assignment_id == assignment_id,
                AISubmission.submitted_at >= twenty_four_hours_ago
            )
        ).scalar() or 0

        existing_grade = float(student_assignment.grade) if student_assignment.grade is not None else 0.0
        if recent_attempts_before >= 3 and existing_grade < 80.0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Maximum attempts (3) reached in 24 hours. Try again tomorrow."
            )

        if submission_file_path:
            raw_path = Path(submission_file_path)
            if not raw_path.is_absolute():
                raw_path = Path(os.getcwd()) / raw_path
            try:
                file_bytes = raw_path.read_bytes()
                filename = raw_path.name
            except FileNotFoundError:
                logger.warning(
                    "Submission file not found for auto grading",
                    extra={"assignment_id": assignment_id, "user_id": user_id, "file_path": str(raw_path)},
                )
            except Exception:
                logger.exception(
                    "Error reading submission file for auto grading",
                    extra={"assignment_id": assignment_id, "user_id": user_id, "file_path": str(raw_path)},
                )

        # Attempt text fallback if no content yet and file is readable text
        if not submission_content and file_bytes is None and submission_file_path:
            try:
                with open(raw_path, "r", encoding="utf-8") as f:
                    submission_content = f.read()
            except Exception:
                submission_content = ""

        max_points = assignment.points or 100
        grade_result: dict

        logger.info(
            "Auto grading assignment submission",
            extra={"assignment_id": assignment_id, "user_id": user_id, "has_file": file_bytes is not None},
        )

        if file_bytes is not None:
            grade_result = await gemini_service.grade_submission_from_file(
                file_bytes=file_bytes,
                filename=filename or f"assignment_{assignment_id}.pdf",
                assignment_title=assignment.title,
                assignment_description=assignment.description or "",
                rubric=assignment.rubric or assignment.description or "",
                max_points=max_points,
                submission_type=assignment.assignment_type,
            )
        else:
            if not submission_content:
                raise HTTPException(status_code=400, detail="No submission content provided")

            grade_result = await gemini_service.grade_submission(
                submission_content=submission_content,
                assignment_title=assignment.title,
                assignment_description=assignment.description or "",
                rubric=assignment.rubric or assignment.description or "",
                max_points=max_points,
                submission_type=assignment.assignment_type,
            )

        # Extract score and feedback from raw data (best effort, handle malformed keys)
        extracted_score = None
        extracted_feedback = None
        
        if isinstance(grade_result, dict):
            # Extract score
            score_val = grade_result.get('score') or grade_result.get('"score"') or grade_result.get('percentage') or grade_result.get('"percentage"')
            if isinstance(score_val, (int, float)):
                extracted_score = float(score_val)
            elif isinstance(score_val, str):
                cleaned = score_val.rstrip(',').strip()
                try:
                    extracted_score = float(cleaned)
                except:
                    pass
            
            # Extract feedback
            feedback_val = grade_result.get('overall_feedback') or grade_result.get('"overall_feedback"') or grade_result.get('detailed_feedback') or grade_result.get('"detailed_feedback"')
            if isinstance(feedback_val, str):
                extracted_feedback = feedback_val.strip('"').strip(',').strip()

        # If no score extracted and we have file, try strict grading
        if file_bytes is not None and extracted_score is None:
            strict = await gemini_service.grade_submission_from_file_strict(
                file_bytes=file_bytes,
                filename=filename or f"assignment_{assignment_id}.pdf",
                assignment_title=assignment.title,
                assignment_description=assignment.description or "",
                max_points=max_points,
                submission_type=assignment.assignment_type,
            )
            # Extract from strict result
            if isinstance(strict, dict):
                strict_score_val = strict.get('score') or strict.get('"score"') or strict.get('percentage') or strict.get('"percentage"')
                if isinstance(strict_score_val, (int, float)):
                    extracted_score = float(strict_score_val)
                elif isinstance(strict_score_val, str):
                    cleaned = strict_score_val.rstrip(',').strip()
                    try:
                        extracted_score = float(cleaned)
                    except:
                        pass
                
                # Use strict feedback if main feedback is missing
                if not extracted_feedback:
                    strict_feedback_val = strict.get('overall_feedback') or strict.get('"overall_feedback"') or strict.get('detailed_feedback') or strict.get('"detailed_feedback"')
                    if isinstance(strict_feedback_val, str):
                        extracted_feedback = strict_feedback_val.strip('"').strip(',').strip()

        ai_score = extracted_score
        ai_feedback = extracted_feedback

        submission_id = submission_data.get("submission_id")

        ai_submission_query = db.query(AISubmission).filter(
            and_(
                AISubmission.user_id == user_id,
                AISubmission.assignment_id == assignment_id
            )
        )

        ai_submission = None
        if submission_id:
            ai_submission = ai_submission_query.filter(AISubmission.id == submission_id).first()
            if ai_submission is None:
                logger.warning(
                    "Submission ID provided but not found for auto-grading",
                    extra={"assignment_id": assignment_id, "submission_id": submission_id, "user_id": user_id}
                )

        if not ai_submission:
            file_type_value = None
            if filename:
                suffix = Path(filename).suffix
                if suffix:
                    file_type_value = suffix.lstrip('.')
            saved_file_path = str(raw_path) if raw_path else submission_file_path
            if not file_type_value and saved_file_path:
                alt_suffix = Path(saved_file_path).suffix
                if alt_suffix:
                    file_type_value = alt_suffix.lstrip('.')
            ai_submission = AISubmission(
                user_id=user_id,
                course_id=student_assignment.course_id,
                assignment_id=assignment_id,
                block_id=getattr(assignment, "block_id", None),
                submission_type=assignment.assignment_type or "assessment",
                original_filename=filename,
                file_path=saved_file_path,
                file_type=file_type_value,
                submitted_at=current_time,
            )
            db.add(ai_submission)
            db.flush()
        else:
            ai_submission.course_id = student_assignment.course_id
            ai_submission.assignment_id = assignment_id
            ai_submission.submitted_at = current_time
            if submission_file_path:
                ai_submission.file_path = str(raw_path) if raw_path else submission_file_path
            if filename:
                ai_submission.original_filename = filename
                suffix = Path(filename).suffix
                if suffix:
                    ai_submission.file_type = suffix.lstrip('.')
            if ai_submission.submission_type in (None, "") and assignment.assignment_type:
                ai_submission.submission_type = assignment.assignment_type

        attempts_today = recent_attempts_before + 1

        student_assignment.ai_grade = ai_score
        student_assignment.grade = ai_score
        student_assignment.feedback = ai_feedback
        student_assignment.submitted_at = current_time
        student_assignment.submission_content = (submission_content or "")[:1000]
        if submission_file_path:
            student_assignment.submission_file_path = submission_file_path
        student_assignment.updated_at = current_time

        passing_grade = (ai_score or 0) >= 80.0

        if passing_grade:
            student_assignment.status = "passed"
            status_message = (
                f"Congratulations! You passed with {ai_score:.1f}%" if ai_score is not None else "Submission passed"
            )
        else:
            if attempts_today >= 3:
                student_assignment.status = "failed"
                status_message = (
                    f"Assignment failed with {ai_score or 0:.1f}%. Maximum attempts (3) reached in 24 hours."
                )
            else:
                student_assignment.status = "needs_retry"
                remaining_attempts = 3 - attempts_today
                if ai_score is not None:
                    status_message = (
                        f"Score: {ai_score:.1f}% - Try again! You need 80% to pass. "
                        f"{remaining_attempts} attempts remaining today."
                    )
                else:
                    status_message = (
                        "AI couldn't determine a score. Please review your submission and try again. "
                        f"{remaining_attempts} attempts remaining today."
                    )

        ai_submission.ai_processed = True
        ai_submission.ai_score = ai_score
        ai_submission.ai_feedback = ai_feedback
        ai_submission.ai_strengths = None  # Not using normalized fields
        ai_submission.ai_improvements = None  # Not using normalized fields
        ai_submission.ai_corrections = None  # Not using normalized fields
        ai_submission.processed_at = datetime.utcnow()

        db.commit()

        logger.info(
            "Auto grading complete",
            extra={"assignment_id": assignment_id, "user_id": user_id, "ai_score": ai_score},
        )

        return {
            "status": "success",
            "message": status_message,
            "assignment": {
                "id": assignment.id,
                "title": assignment.title,
                "type": assignment.assignment_type
            },
            "grade_result": {
                "score": grade_result.get("score"),
                "percentage": ai_score,
                "grade_letter": grade_result.get("grade_letter"),
                "overall_feedback": grade_result.get("overall_feedback"),
                "detailed_feedback": ai_feedback,
                "strengths": grade_result.get("strengths", []),
                "improvements": grade_result.get("improvements", []),
                "recommendations": grade_result.get("recommendations", []),
                "raw": grade_result,  # Return raw data instead of normalized
                "passing_grade": passing_grade,
                "required_percentage": 80.0
            },
            "student_assignment": {
                "id": student_assignment.id,
                "status": student_assignment.status,
                "grade": student_assignment.grade,
                "submitted_at": student_assignment.submitted_at.isoformat(),
                "graded_by": "Gemini AI",
                "submission_id": ai_submission.id,
                "attempts_used": attempts_today,
                "can_retry": not passing_grade and attempts_today < 3,
                "attempts_remaining": max(0, 3 - attempts_today) if not passing_grade else 0
            },
            "processed_at": datetime.utcnow().isoformat()
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(
            "Unexpected error during auto grading",
            extra={"assignment_id": assignment_id, "user_id": current_user["user_id"]},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Auto-grading failed: {str(e)}"
        )

@router.post("/assignments/{assignment_id}/retry")
async def retry_assignment_attempt(
    assignment_id: int,
    db: db_dependency,
    current_user: dict = user_dependency,
    submission_data: dict = Body(default_factory=dict)
):
    """
    Handle assignment retry attempts with proper validation
    """
    user_id = current_user["user_id"]
    
    try:
        assignment = db.query(CourseAssignment).filter(CourseAssignment.id == assignment_id).first()
        if not assignment:
            raise HTTPException(status_code=404, detail="Assignment not found")

        # Check eligibility before allowing retry
        student_assignment = db.query(StudentAssignment).filter(
            and_(
                StudentAssignment.assignment_id == assignment_id,
                StudentAssignment.user_id == user_id
            )
        ).first()
        
        if not student_assignment:
            raise HTTPException(status_code=404, detail="Student assignment not found")
        
        # Check if already passed
        current_grade = student_assignment.grade or 0
        if current_grade >= 80.0:
            raise HTTPException(
                status_code=400,
                detail=f"Assignment already passed with {current_grade:.1f}%"
            )
        
        # Count attempts in last 24 hours
        twenty_four_hours_ago = datetime.utcnow() - timedelta(hours=24)
        recent_attempts = db.query(func.count(AISubmission.id)).filter(
            and_(
                AISubmission.user_id == user_id,
                AISubmission.assignment_id == assignment_id,
                AISubmission.submitted_at >= twenty_four_hours_ago
            )
        ).scalar() or 0
        
        logger.info(
            "Retry attempt check",
            extra={
                "assignment_id": assignment_id,
                "user_id": user_id,
                "recent_attempts": recent_attempts,
                "current_grade": current_grade
            }
        )
        
        # IMPORTANT: Don't block the retry button click itself
        # Only block if they try to submit NEW work after 3 attempts
        # The frontend just needs confirmation that retry is available
        
        payload = submission_data or {}
        has_submission_payload = any(
            payload.get(key)
            for key in ("submission_content", "content", "submission_file_path", "file_path")
        )

        latest_submission = db.query(AISubmission).filter(
            and_(
                AISubmission.user_id == user_id,
                AISubmission.assignment_id == assignment_id
            )
        ).order_by(desc(AISubmission.submitted_at)).first()

        attempts_remaining = max(0, 3 - recent_attempts)

        if not has_submission_payload:
            # User clicked retry but hasn't submitted new work yet
            # Just return status showing they can retry
            message = (
                f"Ready to retry. You have {attempts_remaining} attempt(s) remaining today."
                if attempts_remaining > 0
                else "No attempts remaining today. Try again tomorrow."
            )

            return {
                "status": "ready",
                "message": message,
                "assignment": {
                    "id": assignment.id,
                    "title": assignment.title,
                    "type": assignment.assignment_type
                },
                "grade_result": None,
                "student_assignment": {
                    "id": student_assignment.id,
                    "status": student_assignment.status,
                    "grade": student_assignment.grade,
                    "submitted_at": student_assignment.submitted_at.isoformat() if student_assignment.submitted_at else None,
                    "graded_by": "Gemini AI" if student_assignment.ai_grade is not None else None,
                    "submission_id": latest_submission.id if latest_submission else None,
                    "attempts_used": recent_attempts,
                    "can_retry": attempts_remaining > 0,
                    "attempts_remaining": attempts_remaining
                },
                "retry_info": {
                    "is_retry_attempt": True,
                    "attempts_used": recent_attempts,
                    "attempts_remaining": attempts_remaining
                },
                "processed_at": datetime.utcnow().isoformat()
            }

        # User is submitting new work - NOW check if they've exceeded attempts
        if recent_attempts >= 3:
            raise HTTPException(
                status_code=400,
                detail="Maximum attempts (3) reached in 24 hours. Try again tomorrow."
            )

        # Proceed with auto-grading
        grade_response = await auto_grade_assignment_submission(
            assignment_id, submission_data, db, current_user
        )
        
        student_assignment_payload = grade_response.get("student_assignment", {})
        attempts_used = student_assignment_payload.get("attempts_used", recent_attempts + 1)
        attempts_remaining = student_assignment_payload.get("attempts_remaining", max(0, 3 - attempts_used))

        grade_response["retry_info"] = {
            "is_retry_attempt": True,
            "attempts_used": attempts_used,
            "attempts_remaining": attempts_remaining
        }
        
        return grade_response
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Retry attempt failed: {str(e)}"
        )

@router.get("/assignments/{assignment_id}/status")
async def get_assignment_status_with_grade(
    assignment_id: int,
    db: db_dependency,
    current_user: dict = user_dependency
):
    """
    Get assignment status with grade display and retry information
    """
    user_id = current_user["user_id"]
    
    try:
        # Get the assignment details
        assignment = db.query(CourseAssignment).filter(CourseAssignment.id == assignment_id).first()
        if not assignment:
            raise HTTPException(status_code=404, detail="Assignment not found")
        
        # Get or create the student assignment record
        student_assignment = db.query(StudentAssignment).filter(
            and_(
                StudentAssignment.assignment_id == assignment_id,
                StudentAssignment.user_id == user_id
            )
        ).first()

        if not student_assignment:
            due_days = getattr(assignment, "due_days_after_assignment", None) or 7
            student_assignment = StudentAssignment(
                user_id=user_id,
                assignment_id=assignment.id,
                course_id=assignment.course_id,
                due_date=datetime.utcnow() + timedelta(days=due_days),
                status="assigned",
            )
            try:
                db.add(student_assignment)
                db.commit()
                db.refresh(student_assignment)
            except Exception:
                db.rollback()
                student_assignment = db.query(StudentAssignment).filter(
                    and_(
                        StudentAssignment.assignment_id == assignment_id,
                        StudentAssignment.user_id == user_id
                    )
                ).first()
                if not student_assignment:
                    raise HTTPException(status_code=500, detail="Failed to create student assignment record")

        required_pct = 80.0
        current_grade = float(student_assignment.grade) if student_assignment.grade is not None else 0.0
        passing_grade = current_grade >= required_pct
        
        latest_submission = db.query(AISubmission).filter(
            and_(
                AISubmission.user_id == user_id,
                AISubmission.assignment_id == assignment_id
            )
        ).order_by(desc(AISubmission.submitted_at)).first()

        twenty_four_hours_ago = datetime.utcnow() - timedelta(hours=24)
        recent_attempts = db.query(func.count(AISubmission.id)).filter(
            and_(
                AISubmission.user_id == user_id,
                AISubmission.assignment_id == assignment_id,
                AISubmission.submitted_at >= twenty_four_hours_ago
            )
        ).scalar() or 0

        attempts_remaining = max(0, 3 - recent_attempts)
        if passing_grade:
            attempts_remaining = 0
        can_retry = not passing_grade and attempts_remaining > 0

        # Determine message based on status
        if student_assignment.submitted_at is None:
            message = "Assignment not yet started. Submit your first attempt to get graded."
        elif passing_grade:
            message = f"✅ Passed with {current_grade:.1f}%! Great job!"
        elif student_assignment.status == "failed" or attempts_remaining == 0:
            message = f"❌ Failed with {current_grade:.1f}%. No more attempts available today."
        elif student_assignment.status == "needs_retry":
            message = f"📝 Score: {current_grade:.1f}% (Need {required_pct:.0f}% to pass). {attempts_remaining} attempts remaining today."
        else:
            message = f"Score: {current_grade:.1f}%"
        
        return {
            "assignment": {
                "id": assignment.id,
                "title": assignment.title,
                "description": assignment.description,
                "points": assignment.points,
                "required_percentage": required_pct
            },
            "student_assignment": {
                "id": student_assignment.id,
                "status": student_assignment.status,
                "grade": current_grade,
                "submitted_at": student_assignment.submitted_at.isoformat() if student_assignment.submitted_at else None,
                "feedback": student_assignment.feedback,
                "submission_id": latest_submission.id if latest_submission else None
            },
            "attempts_info": {
                "attempts_used": recent_attempts,
                "attempts_remaining": attempts_remaining,
                "can_retry": can_retry,
                "latest_submission_at": latest_submission.submitted_at.isoformat() if latest_submission and latest_submission.submitted_at else None
            },
            "message": message,
            "passing_grade": passing_grade
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error getting assignment status: {str(e)}"
        )

@router.post("/submissions/{submission_id}/process-with-ai")
async def process_submission_with_gemini_ai(
    submission_id: int,
    db: db_dependency,
    current_user: dict = user_dependency
):
    """
    Process an individual AI submission using Gemini AI grading
    
    This endpoint handles immediate processing of submissions:
    - Retrieves submission content and context
    - Applies Gemini AI grading with appropriate rubrics
    - Updates all related records (AISubmission, StudySession, StudentAssignment)
    - Provides comprehensive feedback and scoring
    
    Used for real-time grading of student work
    """
    
    try:
        submission = db.query(AISubmission).options(
            joinedload(AISubmission.course),
            joinedload(AISubmission.lesson),
            joinedload(AISubmission.block)
        ).filter(AISubmission.id == submission_id).first()

        if not submission:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="AI submission not found"
            )

        if submission.ai_processed:
            return {
                "status": "already_processed",
                "message": "Submission already graded",
                "existing_score": submission.ai_score
            }

        file_bytes: Optional[bytes] = None
        filename: Optional[str] = None
        submission_content = ""

        if submission.file_path:
            file_path = Path(submission.file_path)
            if not file_path.is_absolute():
                file_path = Path(os.getcwd()) / file_path
            try:
                file_bytes = file_path.read_bytes()
                filename = file_path.name
            except FileNotFoundError:
                logger.warning(
                    "Submission file missing for processing",
                    extra={"submission_id": submission_id, "file_path": str(file_path)},
                )
            except Exception:
                logger.exception(
                    "Error reading submission file",
                    extra={"submission_id": submission_id, "file_path": str(file_path)},
                )

            if file_bytes is None:
                try:
                    submission_content = file_path.read_text(encoding="utf-8")
                except Exception:
                    submission_content = ""

        assignment_title = ""
        assignment_description = ""
        rubric = ""
        max_points = 100

        if submission.assignment_id:
            assignment = db.query(CourseAssignment).filter(CourseAssignment.id == submission.assignment_id).first()
            if assignment:
                assignment_title = assignment.title
                assignment_description = assignment.description or ""
                rubric = assignment.rubric or assignment.description or ""
                if assignment.points:
                    max_points = assignment.points
        elif submission.lesson:
            assignment_title = f"Lesson: {submission.lesson.title}"
            assignment_description = submission.lesson.learning_objectives or ""
            rubric = submission.lesson.learning_objectives or f"Lesson assessment: {submission.lesson.title}"
        elif submission.block:
            assignment_title = f"Block {submission.block.week}.{submission.block.block_number}: {submission.block.title}"
            assignment_description = submission.block.description or ""
            rubric = ", ".join(submission.block.learning_objectives) if submission.block.learning_objectives else assignment_title
        else:
            assignment_title = f"Course Work: {submission.course.title}"
            assignment_description = submission.course.description or ""
            rubric = submission.course.description or "General course assessment"

        logger.info(
            "Processing submission with Gemini AI",
            extra={"submission_id": submission_id, "has_file": file_bytes is not None},
        )

        if file_bytes is not None:
            grade_result = await gemini_service.grade_submission_from_file(
                file_bytes=file_bytes,
                filename=filename or f"submission_{submission_id}.pdf",
                assignment_title=assignment_title,
                assignment_description=assignment_description,
                rubric=rubric,
                max_points=max_points,
                submission_type=submission.submission_type
            )
        else:
            if not submission_content:
                raise HTTPException(status_code=400, detail="Submission content unavailable")
            grade_result = await gemini_service.grade_submission(
                submission_content=submission_content,
                assignment_title=assignment_title,
                assignment_description=assignment_description,
                rubric=rubric,
                max_points=max_points,
                submission_type=submission.submission_type
            )

        # Extract score and feedback from raw data (best effort, handle malformed keys)
        extracted_score = None
        extracted_feedback = None
        
        if isinstance(grade_result, dict):
            # Extract score
            score_val = grade_result.get('score') or grade_result.get('"score"') or grade_result.get('percentage') or grade_result.get('"percentage"')
            if isinstance(score_val, (int, float)):
                extracted_score = float(score_val)
            elif isinstance(score_val, str):
                cleaned = score_val.rstrip(',').strip()
                try:
                    extracted_score = float(cleaned)
                except:
                    pass
            
            # Extract feedback
            feedback_val = grade_result.get('overall_feedback') or grade_result.get('"overall_feedback"') or grade_result.get('detailed_feedback') or grade_result.get('"detailed_feedback"')
            if isinstance(feedback_val, str):
                extracted_feedback = feedback_val.strip('"').strip(',').strip()

        # If no score extracted and we have file, try strict grading
        if file_bytes is not None and extracted_score is None:
            strict = await gemini_service.grade_submission_from_file_strict(
                file_bytes=file_bytes,
                filename=filename or f"submission_{submission_id}.pdf",
                assignment_title=assignment_title,
                assignment_description=assignment_description,
                max_points=max_points,
                submission_type=submission.submission_type,
            )
            # Extract from strict result
            if isinstance(strict, dict):
                strict_score_val = strict.get('score') or strict.get('"score"') or strict.get('percentage') or strict.get('"percentage"')
                if isinstance(strict_score_val, (int, float)):
                    extracted_score = float(strict_score_val)
                elif isinstance(strict_score_val, str):
                    cleaned = strict_score_val.rstrip(',').strip()
                    try:
                        extracted_score = float(cleaned)
                    except:
                        pass
                
                # Use strict feedback if main feedback is missing
                if not extracted_feedback:
                    strict_feedback_val = strict.get('overall_feedback') or strict.get('"overall_feedback"') or strict.get('detailed_feedback') or strict.get('"detailed_feedback"')
                    if isinstance(strict_feedback_val, str):
                        extracted_feedback = strict_feedback_val.strip('"').strip(',').strip()

        ai_score = extracted_score
        ai_feedback = extracted_feedback

        submission.ai_processed = True
        submission.ai_score = ai_score
        submission.ai_feedback = ai_feedback
        submission.ai_strengths = None  # Not using normalized fields
        submission.ai_improvements = None  # Not using normalized fields
        submission.ai_corrections = None  # Not using normalized fields
        submission.processed_at = datetime.utcnow()

        if submission.session_id:
            session = db.query(StudySession).filter(StudySession.id == submission.session_id).first()
            if session:
                session.ai_score = ai_score
                session.ai_feedback = ai_feedback
                session.ai_recommendations = None  # Not using normalized fields
                session.updated_at = datetime.utcnow()

        if submission.assignment_id:
            student_assignment = db.query(StudentAssignment).filter(
                and_(
                    StudentAssignment.user_id == submission.user_id,
                    StudentAssignment.assignment_id == submission.assignment_id
                )
            ).first()

            if student_assignment:
                student_assignment.ai_grade = ai_score
                student_assignment.grade = ai_score
                student_assignment.feedback = ai_feedback
                student_assignment.status = "graded"
                student_assignment.updated_at = datetime.utcnow()

        db.commit()

        logger.info(
            "Submission processed with Gemini AI",
            extra={"submission_id": submission_id, "ai_score": ai_score},
        )

        return {
            "status": "success",
            "message": "Submission processed successfully with Gemini AI",
            "submission_id": submission_id,
            "grade_result": {
                **grade_result,
                "raw": grade_result,  # Return raw data instead of normalized
                "percentage": ai_score,
                "detailed_feedback": ai_feedback,
            },
            "processing_details": {
                "assignment_title": assignment_title,
                "rubric_used": rubric[:100] + "..." if len(rubric) > 100 else rubric,
                "max_points": max_points,
                "processed_by": "Gemini AI"
            },
            "processed_at": datetime.utcnow().isoformat()
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(
            "Failed processing submission with Gemini AI",
            extra={"submission_id": submission_id},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process submission: {str(e)}"
        )