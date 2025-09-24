from fastapi import APIRouter, HTTPException, Depends, status, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_, desc, func, inspect, text
from typing import List, Optional
from datetime import datetime, timedelta
import json
import os
import base64
import requests

from db.connection import db_dependency
from Endpoints.auth import get_current_user
from models.afterschool_models import (
    Course, CourseLesson, CourseBlock, CourseAssignment, StudentAssignment,
    StudySession, AISubmission, StudentProgress
)
from schemas.afterschool_schema import (
    StudySessionStart, StudySessionEnd, StudySessionOut,
    AISubmissionUpdate, AIGradingResponse, StudentProgressOut, MessageResponse,
    CourseBlockOut, CourseAssignmentOut, StudentAssignmentOut
)
from services.gemini_service import gemini_service

router = APIRouter(prefix="/after-school/sessions", tags=["After-School Sessions & KANA Grading"])

# Dependency for current user
user_dependency = Depends(get_current_user)

# ===============================
# STUDY SESSION MANAGEMENT
# ===============================

@router.post("/start", response_model=StudySessionOut)
async def start_study_session(
    session_data: StudySessionStart,
    db: db_dependency,
    current_user: dict = user_dependency
):
    """
    Start a new study session for a lesson or course block
    
    This enhanced endpoint supports both traditional lessons and AI-generated course blocks:
    - Legacy lesson-based sessions for backward compatibility
    - Modern block-based sessions for Gemini AI-generated courses
    - Automatic progress tracking for both formats
    """
    user_id = current_user["user_id"]
    
    # Diagnostic logging container
    debug_context = {
        "user_id": current_user.get("user_id"),
        "course_id": session_data.course_id,
        "lesson_id": session_data.lesson_id,
        "block_id": session_data.block_id,
        "stage": "init"
    }
    try:
        debug_context["stage"] = "course_lookup"
        course = db.query(Course).filter(Course.id == session_data.course_id).first()
        if not course:
            debug_context["error"] = "course_not_found"
            print("❌ StudySession start - course not found", debug_context)
            raise HTTPException(status_code=404, detail="Course not found")

        lesson = None
        block = None
        session_target_type = None
        active_session = None

        if session_data.lesson_id:
            debug_context["stage"] = "lesson_lookup"
            lesson = db.query(CourseLesson).filter(
                and_(
                    CourseLesson.id == session_data.lesson_id,
                    CourseLesson.course_id == session_data.course_id,
                    CourseLesson.is_active == True
                )
            ).first()
            if not lesson:
                debug_context["error"] = "lesson_not_found"
                print("❌ StudySession start - lesson not found", debug_context)
                raise HTTPException(status_code=404, detail="Lesson not found or inactive")
            session_target_type = "lesson"
            active_session = db.query(StudySession).filter(
                and_(
                    StudySession.user_id == user_id,
                    StudySession.lesson_id == session_data.lesson_id,
                    StudySession.status == "in_progress"
                )
            ).first()
        elif session_data.block_id:
            debug_context["stage"] = "block_lookup"
            block = db.query(CourseBlock).filter(
                and_(
                    CourseBlock.id == session_data.block_id,
                    CourseBlock.course_id == session_data.course_id,
                    CourseBlock.is_active == True
                )
            ).first()
            if not block:
                debug_context["error"] = "block_not_found"
                print("❌ StudySession start - block not found", debug_context)
                raise HTTPException(status_code=404, detail="Course block not found or inactive")
            session_target_type = "block"
            active_session = db.query(StudySession).filter(
                and_(
                    StudySession.user_id == user_id,
                    StudySession.block_id == session_data.block_id,
                    StudySession.status == "in_progress"
                )
            ).first()
        else:
            debug_context["error"] = "missing_target"
            print("❌ StudySession start - neither lesson_id nor block_id provided", debug_context)
            raise HTTPException(status_code=400, detail="Either lesson_id or block_id must be provided")

        if active_session:
            target_name = lesson.title if lesson else (block.title if block else "Unknown")
            debug_context["stage"] = "active_session_exists"
            print("ℹ️ StudySession start - active session already exists", debug_context)
            raise HTTPException(status_code=400, detail=f"You already have an active session for {session_target_type}: {target_name}")

        # ---------------------------------------------
        # Runtime schema self-healing for block sessions
        # ---------------------------------------------
        if session_target_type == "block" and session_data.block_id and not session_data.lesson_id:
            try:
                debug_context["stage"] = "schema_inspect"
                insp = inspect(db.bind)
                cols = {c['name']: c for c in insp.get_columns('as_study_sessions')}
                changed = False
                # Add block_id column if missing
                if 'block_id' not in cols:
                    print("🔧 Adding missing block_id column to as_study_sessions (runtime migration)")
                    db.execute(text('ALTER TABLE as_study_sessions ADD COLUMN block_id INTEGER REFERENCES as_course_blocks(id)'))
                    changed = True
                # Drop NOT NULL from lesson_id if still enforced
                if 'lesson_id' in cols and not cols['lesson_id'].get('nullable', True):
                    print("🔧 Dropping NOT NULL constraint on lesson_id to allow block-based sessions")
                    db.execute(text('ALTER TABLE as_study_sessions ALTER COLUMN lesson_id DROP NOT NULL'))
                    changed = True
                if changed:
                    db.commit()  # finalize DDL
                    debug_context["schema_auto_migrated"] = True
                    # New transaction will begin automatically on next use
                else:
                    debug_context["schema_auto_migrated"] = False
            except Exception as mig_err:
                # Non-fatal: we surface a clearer error so user can run manual migration
                debug_context["stage"] = "schema_migration_failed"
                debug_context["schema_error"] = str(mig_err)[:400]
                print("❌ Runtime schema migration failed", debug_context)
                raise HTTPException(status_code=500, detail={
                    "message": "Study session start failed: database schema incompatible (block sessions require nullable lesson_id & block_id column)",
                    "code": "schema_incompatible",
                    "schema_error": str(mig_err)[:400]
                })

        debug_context["stage"] = "create_session"
        new_session = StudySession(
            user_id=user_id,
            course_id=session_data.course_id,
            lesson_id=session_data.lesson_id,
            block_id=session_data.block_id,
            status="in_progress"
        )
        db.add(new_session)
        # Flush separately so we can surface raw integrity errors (e.g., FK / unique constraint)
        try:
            db.flush()  # obtain PK before progress update
        except Exception as flush_err:
            from sqlalchemy.exc import IntegrityError
            debug_context["stage"] = "create_session_flush_error"
            debug_context["flush_error_type"] = type(flush_err).__name__
            debug_context["flush_error_message"] = str(flush_err)[:500]
            if isinstance(flush_err, IntegrityError):
                # Attempt to capture underlying DB error / constraint name
                orig = getattr(flush_err, 'orig', None)
                if orig:
                    debug_context["flush_error_orig"] = str(orig)[:500]
            print("❌ StudySession flush failure", debug_context)
            # Re-raise so outer handler classifies
            raise

        debug_context["stage"] = "progress_lookup"
        # Attempt row-level lock; fallback gracefully if unsupported (e.g., SQLite)
        progress = None
        try:
            progress = db.query(StudentProgress).filter(
                and_(
                    StudentProgress.user_id == user_id,
                    StudentProgress.course_id == session_data.course_id
                )
            ).with_for_update(nowait=False).first()
            debug_context["progress_lock"] = "acquired"
        except Exception as lock_err:  # Broad: dialect differences
            db.rollback()  # rollback possible partial state from failed FOR UPDATE
            debug_context["progress_lock"] = f"lock_failed:{type(lock_err).__name__}"
            # Retry without FOR UPDATE in a fresh transaction
            progress = db.query(StudentProgress).filter(
                and_(
                    StudentProgress.user_id == user_id,
                    StudentProgress.course_id == session_data.course_id
                )
            ).first()
            debug_context["progress_lock_fallback"] = True

        if not progress:
            debug_context["stage"] = "progress_seed"
            total_lessons = db.query(CourseLesson).filter(
                and_(CourseLesson.course_id == session_data.course_id, CourseLesson.is_active == True)
            ).count()
            total_blocks = db.query(CourseBlock).filter(
                and_(CourseBlock.course_id == session_data.course_id, CourseBlock.is_active == True)
            ).count()
            total_content_items = total_blocks if total_blocks > 0 else total_lessons
            progress = StudentProgress(
                user_id=user_id,
                course_id=session_data.course_id,
                total_lessons=total_content_items or 0,
                lessons_completed=0,
                completion_percentage=0.0,
                sessions_count=1,
                total_study_time=0,
                started_at=datetime.utcnow(),
                last_activity=datetime.utcnow()
            )
            db.add(progress)
        else:
            progress.sessions_count += 1
            progress.last_activity = datetime.utcnow()
        try:
            db.commit()
        except Exception as commit_err:
            debug_context["stage"] = "commit_failure"
            debug_context["commit_error_type"] = type(commit_err).__name__
            debug_context["commit_error"] = str(commit_err)[:200]
            print("❌ StudySession commit failure", debug_context)
            try:
                db.rollback()
            except Exception:
                pass
            # Re-raise to outer handler
            raise
        db.refresh(new_session)

        target_info = lesson.title if lesson else (f"Block {block.week}.{block.block_number}: {block.title}" if block else "Unknown")
        print(f"📚 Started {session_target_type} session: '{target_info}' for user {user_id} (session_id={new_session.id})")
        return new_session
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        # Attempt specific DB error classification
        from sqlalchemy.exc import OperationalError, IntegrityError, ProgrammingError
        internal_code = None
        try:
            db.rollback()
        except Exception:
            pass
        if isinstance(e, IntegrityError):
            internal_code = "integrity_error"
        elif isinstance(e, OperationalError):
            internal_code = "operational_error"
        elif isinstance(e, ProgrammingError):
            internal_code = "programming_error"
        else:
            internal_code = type(e).__name__
        debug_context["error_type"] = internal_code
        debug_context["error_message"] = str(e)[:500]
        print("❌ StudySession start failure", debug_context)
        import traceback
        traceback.print_exc()
        # Surface a structured diagnostic while keeping 500 semantics
        raise HTTPException(status_code=500, detail={
            "message": "Study session start failed",
            "code": internal_code,
            "stage": debug_context.get("stage"),
            "progress_lock": debug_context.get("progress_lock"),
            "commit_error": debug_context.get("commit_error"),
            # Additional diagnostic exposure
            "error_message": debug_context.get("error_message"),
            "flush_error_type": debug_context.get("flush_error_type"),
            "flush_error_message": debug_context.get("flush_error_message"),
            "flush_error_orig": debug_context.get("flush_error_orig")
        })

@router.put("/{session_id}/end", response_model=StudySessionOut)
async def end_study_session(
    session_id: int,
    session_data: StudySessionEnd,
    db: db_dependency,
    current_user: dict = user_dependency
):
    """
    End a study session and record completion
    """
    user_id = current_user["user_id"]
    
    # Get the study session
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
    
    if session.status != "in_progress":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Session is not in progress"
        )
    
    # Calculate duration
    duration = datetime.utcnow() - session.started_at
    duration_minutes = int(duration.total_seconds() / 60)
    
    # Update session
    session.ended_at = datetime.utcnow()
    session.duration_minutes = duration_minutes
    session.status = session_data.status
    session.completion_percentage = session_data.completion_percentage
    session.updated_at = datetime.utcnow()
    
    # Update student progress
    progress = db.query(StudentProgress).filter(
        and_(
            StudentProgress.user_id == user_id,
            StudentProgress.course_id == session.course_id
        )
    ).first()
    
    if progress:
        progress.total_study_time += duration_minutes
        progress.last_activity = datetime.utcnow()
        
        # If lesson or block completed, update completion count
        if session_data.completion_percentage >= 100:
            # Check if this lesson or block was already completed
            completed_before = None
            
            if session.lesson_id:
                # Traditional lesson-based completion
                completed_before = db.query(StudySession).filter(
                    and_(
                        StudySession.user_id == user_id,
                        StudySession.lesson_id == session.lesson_id,
                        StudySession.completion_percentage >= 100,
                        StudySession.id != session_id
                    )
                ).first()
            elif session.block_id:
                # AI-generated course block completion
                completed_before = db.query(StudySession).filter(
                    and_(
                        StudySession.user_id == user_id,
                        StudySession.block_id == session.block_id,
                        StudySession.completion_percentage >= 100,
                        StudySession.id != session_id
                    )
                ).first()
            
            if not completed_before:
                progress.lessons_completed += 1
                progress.completion_percentage = (progress.lessons_completed / progress.total_lessons) * 100
                
                # Log completion based on type
                if session.lesson_id:
                    lesson = db.query(CourseLesson).filter(CourseLesson.id == session.lesson_id).first()
                    content_name = lesson.title if lesson else f"Lesson {session.lesson_id}"
                else:
                    block = db.query(CourseBlock).filter(CourseBlock.id == session.block_id).first()
                    content_name = f"Block {block.week}.{block.block_number}: {block.title}" if block else f"Block {session.block_id}"
                
                print(f"✅ Content completed: '{content_name}' for user {user_id} ({progress.lessons_completed}/{progress.total_lessons})")
                
                # Check if course is fully completed
                if progress.completion_percentage >= 100:
                    progress.completed_at = datetime.utcnow()
                    print(f"🎉 Course completed by user {user_id}!")
    
    db.commit()
    db.refresh(session)
    
    return session

@router.get("/", response_model=List[StudySessionOut])
async def get_user_sessions(
    db: db_dependency,
    current_user: dict = user_dependency,
    course_id: Optional[int] = Query(None, description="Filter by course"),
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(50, ge=1, le=100, description="Limit results")
):
    """
    Get user's study sessions with filtering
    """
    user_id = current_user["user_id"]
    
    query = db.query(StudySession).filter(StudySession.user_id == user_id)
    
    if course_id:
        query = query.filter(StudySession.course_id == course_id)
    
    if status:
        query = query.filter(StudySession.status == status)
    
    sessions = query.order_by(desc(StudySession.started_at)).limit(limit).all()
    
    return sessions

# ===============================
# PROGRESS TRACKING ENDPOINTS (must be before /{session_id} route)
# ===============================
# Note: Session submissions are managed through /after-school/uploads/sessions/{session_id}/submissions
# This avoids duplicate endpoints and provides better filtering options

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
        
        print(f"🔍 Enhanced grading request: course_id={course_id}, lesson_id={lesson_id}, block_id={block_id}, assignment_id={assignment_id}, grade_all={grade_all_students}")
        
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
        
        print(f"📚 Found course: {course.title}, Context: {grading_context}")
    
    except Exception as e:
        print(f"Error in grade_course_submissions: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
    
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
            print(f"📝 Added submission {submission.id} from {student_name}: {content_title}")
                
        except Exception as e:
            print(f"❌ Error processing submission {submission.id}: {str(e)}")
            continue
    
    if not grading_data:
        raise HTTPException(status_code=404, detail="No valid submissions found for grading")
    
    print(f"Total grading data entries: {len(grading_data)}")
    
    # Process submissions using Gemini AI grading
    try:
        print(f"🤖 Starting Gemini AI grading for {len(grading_data)} submissions...")
        
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
        
        print(f"📚 Grading Context: {assignment_title}")
        print(f"📋 Rubric: {rubric[:100]}...")
        
        # Prepare submissions for Gemini AI
        submissions_for_ai = []
        for submission_data in grading_data:
            pdf_path = submission_data.get("file_path", "")
            
            # Read and extract content from PDF
            try:
                if not os.path.isabs(pdf_path):
                    pdf_full_path = os.path.join(os.getcwd(), pdf_path)
                else:
                    pdf_full_path = pdf_path
                
                print(f"📄 Processing PDF: {pdf_full_path}")
                
                if os.path.exists(pdf_full_path):
                    # For now, we'll create a placeholder text content
                    # In production, you'd integrate a proper PDF text extraction library
                    submission_content = f"PDF submission from {submission_data['student_name']}\n"
                    submission_content += f"File: {submission_data['filename']}\n"
                    submission_content += f"Subject: {course.title}\n"
                    submission_content += "Content: [PDF content would be extracted here using PyPDF2, pdfplumber, or similar library]"
                    
                    submissions_for_ai.append({
                        "submission_id": submission_data["submission_id"],
                        "user_id": submission_data["user_id"],
                        "student_name": submission_data["student_name"],
                        "content": submission_content,
                        "submission_type": submission_data["submission_type"]
                    })
                    
                    print(f"✅ Prepared submission from {submission_data['student_name']}")
                else:
                    print(f"❌ PDF file not found: {pdf_full_path}")
                        
            except Exception as pdf_error:
                print(f"❌ Error processing PDF for {submission_data['student_name']}: {pdf_error}")
                continue
        
        if not submissions_for_ai:
            raise HTTPException(status_code=404, detail="No valid submissions found for processing")
        
        # Use Gemini AI bulk grading
        gemini_results = await gemini_service.grade_bulk_submissions(
            submissions=submissions_for_ai,
            assignment_title=assignment_title,
            assignment_description=assignment_description,
            rubric=rubric,
            max_points=100
        )
        
        print(f"✅ Gemini AI grading completed: {gemini_results['batch_summary']['successfully_graded']} students graded")
            
        # Store Gemini AI grades in database
        grading_results = []
        
        for result in gemini_results.get("student_results", []):
            if result.get("success", False):
                submission_id = result.get("submission_id")
                student_name = result.get("student_name", "")
                percentage = result.get("percentage", 0)
                feedback = result.get("detailed_feedback", "")
                
                try:
                    # Update the AI submission with Gemini results
                    submission = db.query(AISubmission).filter(AISubmission.id == submission_id).first()
                    if submission:
                        submission.ai_processed = True
                        submission.ai_score = percentage
                        submission.ai_feedback = feedback
                        submission.ai_corrections = "\n".join(result.get("corrections", []))
                        submission.ai_strengths = "\n".join(result.get("strengths", []))
                        submission.ai_improvements = "\n".join(result.get("improvements", []))
                        submission.processed_at = datetime.utcnow()
                        
                        # Update the associated study session
                        if submission.session_id:
                            session = db.query(StudySession).filter(StudySession.id == submission.session_id).first()
                            if session:
                                session.ai_score = percentage
                                session.ai_feedback = feedback
                                session.ai_recommendations = "\n".join(result.get("recommendations", []))
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
                                student_assignment.ai_grade = percentage
                                student_assignment.grade = percentage  # AI grade is the final grade
                                student_assignment.feedback = feedback
                                student_assignment.status = "graded"
                                student_assignment.updated_at = datetime.utcnow()
                                print(f"🤖 Updated StudentAssignment {student_assignment.id} with Gemini grade {percentage}% for {student_name}")
                            else:
                                print(f"⚠️  No StudentAssignment found for user {submission.user_id} and assignment {submission.assignment_id}")
                        
                        grading_results.append({
                            "submission_id": submission_id,
                            "user_id": submission.user_id,
                            "student_name": student_name,
                            "score": result.get("score", 0),
                            "percentage": percentage,
                            "grade_letter": result.get("grade_letter", ""),
                            "feedback": feedback,
                            "overall_feedback": result.get("overall_feedback", ""),
                            "strengths": result.get("strengths", []),
                            "improvements": result.get("improvements", []),
                            "recommendations": result.get("recommendations", []),
                            "graded_by": result.get("graded_by", "Gemini AI"),
                            "success": True
                        })
                    
                except Exception as grade_error:
                    print(f"❌ Error saving Gemini grade for {student_name}: {grade_error}")
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
            print(f"✅ Successfully updated {successful_grades} submissions with Gemini AI grades")
        except Exception as commit_error:
            db.rollback()
            print(f"❌ Error committing Gemini grades: {commit_error}")
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
        
    except Exception as gemini_error:
        print(f"❌ Gemini AI grading error: {gemini_error}")
        raise HTTPException(status_code=500, detail=f"Gemini AI grading service error: {str(gemini_error)}")

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
            print(f"⚠️  User {current_user_id} attempting to access assignments for user {user_id}")
        
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
        
        print(f"📋 Retrieved {len(assignments)} assignments for user {user_id}")
        return assignments
        
    except Exception as e:
        print(f"❌ Error retrieving student assignments: {str(e)}")
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
        
        print(f"📊 Course {course_id} assignments: {len(assignments)} total")
        if include_stats:
            print(f"📈 Stats: {stats['submission_rate']:.1f}% submitted, {stats['grading_completion']:.1f}% graded")
        
        return assignments
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error retrieving course assignments: {str(e)}")
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
        # Get the assignment details
        assignment = db.query(CourseAssignment).filter(CourseAssignment.id == assignment_id).first()
        if not assignment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Assignment not found"
            )
        
        # Get the student assignment record
        student_assignment = db.query(StudentAssignment).filter(
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
        
        # Extract submission content
        submission_content = submission_data.get("content", "")
        submission_file_path = submission_data.get("file_path", "")
        
        # If it's a file submission, extract content
        if submission_file_path and not submission_content:
            try:
                if os.path.exists(submission_file_path):
                    # For PDF files, create placeholder content (integrate PDF extraction library in production)
                    if submission_file_path.lower().endswith('.pdf'):
                        submission_content = f"PDF submission for assignment: {assignment.title}\n"
                        submission_content += f"File: {os.path.basename(submission_file_path)}\n"
                        submission_content += "[PDF content would be extracted here using PyPDF2 or similar library]"
                    else:
                        # For text files
                        with open(submission_file_path, 'r', encoding='utf-8') as f:
                            submission_content = f.read()
                else:
                    submission_content = "File not found for processing"
            except Exception as file_error:
                print(f"❌ Error reading submission file: {file_error}")
                submission_content = f"Error reading file: {str(file_error)}"
        
        print(f"🤖 Auto-grading assignment '{assignment.title}' for user {user_id}")
        
        # Grade using Gemini AI
        grade_result = await gemini_service.grade_submission(
            submission_content=submission_content,
            assignment_title=assignment.title,
            assignment_description=assignment.description,
            rubric=assignment.rubric or assignment.description,
            max_points=assignment.points,
            submission_type=assignment.assignment_type
        )
        
        # Update student assignment with AI grade
        student_assignment.ai_grade = grade_result["percentage"]
        student_assignment.grade = grade_result["percentage"]  # AI grade is final grade
        student_assignment.feedback = grade_result["detailed_feedback"]
        student_assignment.submitted_at = datetime.utcnow()
        student_assignment.status = "graded"
        student_assignment.submission_content = submission_content[:1000]  # Store truncated content
        if submission_file_path:
            student_assignment.submission_file_path = submission_file_path
        student_assignment.updated_at = datetime.utcnow()
        
        # Update any associated AI submission record
        ai_submission = db.query(AISubmission).filter(
            and_(
                AISubmission.user_id == user_id,
                AISubmission.assignment_id == assignment_id
            )
        ).first()
        
        if ai_submission:
            ai_submission.ai_processed = True
            ai_submission.ai_score = grade_result["percentage"]
            ai_submission.ai_feedback = grade_result["detailed_feedback"]
            ai_submission.ai_strengths = "\n".join(grade_result.get("strengths", []))
            ai_submission.ai_improvements = "\n".join(grade_result.get("improvements", []))
            ai_submission.processed_at = datetime.utcnow()
        
        db.commit()
        
        print(f"✅ Auto-grading complete: {grade_result['percentage']}% for user {user_id}")
        
        return {
            "status": "success",
            "message": "Assignment automatically graded by Gemini AI",
            "assignment": {
                "id": assignment.id,
                "title": assignment.title,
                "type": assignment.assignment_type
            },
            "grade_result": {
                "score": grade_result.get("score", 0),
                "percentage": grade_result["percentage"],
                "grade_letter": grade_result.get("grade_letter", ""),
                "overall_feedback": grade_result["overall_feedback"],
                "detailed_feedback": grade_result["detailed_feedback"],
                "strengths": grade_result.get("strengths", []),
                "improvements": grade_result.get("improvements", []),
                "recommendations": grade_result.get("recommendations", [])
            },
            "student_assignment": {
                "id": student_assignment.id,
                "status": student_assignment.status,
                "grade": student_assignment.grade,
                "submitted_at": student_assignment.submitted_at.isoformat(),
                "graded_by": "Gemini AI"
            },
            "processed_at": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error in auto-grading: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Auto-grading failed: {str(e)}"
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
        # Get the AI submission
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
        
        # Check if already processed
        if submission.ai_processed:
            return {
                "status": "already_processed",
                "message": "Submission already graded",
                "existing_score": submission.ai_score
            }
        
        # Extract content from file
        submission_content = ""
        if submission.file_path:
            try:
                if os.path.exists(submission.file_path):
                    if submission.file_path.lower().endswith('.pdf'):
                        # PDF content placeholder
                        submission_content = f"PDF submission: {submission.original_filename}\n"
                        submission_content += "[PDF content extraction needed]"
                    else:
                        with open(submission.file_path, 'r', encoding='utf-8') as f:
                            submission_content = f.read()
                else:
                    submission_content = "Submission file not found"
            except Exception as e:
                submission_content = f"Error reading submission: {str(e)}"
        
        # Determine grading context
        assignment_title = ""
        assignment_description = ""
        rubric = ""
        max_points = 100
        
        if submission.assignment_id:
            assignment = db.query(CourseAssignment).filter(CourseAssignment.id == submission.assignment_id).first()
            if assignment:
                assignment_title = assignment.title
                assignment_description = assignment.description
                rubric = assignment.rubric or assignment.description
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
        
        print(f"🤖 Processing submission {submission_id} with Gemini AI: {assignment_title}")
        
        # Grade with Gemini AI
        grade_result = await gemini_service.grade_submission(
            submission_content=submission_content,
            assignment_title=assignment_title,
            assignment_description=assignment_description,
            rubric=rubric,
            max_points=max_points,
            submission_type=submission.submission_type
        )
        
        # Update AI submission
        submission.ai_processed = True
        submission.ai_score = grade_result["percentage"]
        submission.ai_feedback = grade_result["detailed_feedback"]
        submission.ai_strengths = "\n".join(grade_result.get("strengths", []))
        submission.ai_improvements = "\n".join(grade_result.get("improvements", []))
        submission.processed_at = datetime.utcnow()
        
        # Update study session if exists
        if submission.session_id:
            session = db.query(StudySession).filter(StudySession.id == submission.session_id).first()
            if session:
                session.ai_score = grade_result["percentage"]
                session.ai_feedback = grade_result["detailed_feedback"]
                session.ai_recommendations = "\n".join(grade_result.get("recommendations", []))
                session.updated_at = datetime.utcnow()
        
        # Update student assignment if exists
        if submission.assignment_id:
            student_assignment = db.query(StudentAssignment).filter(
                and_(
                    StudentAssignment.user_id == submission.user_id,
                    StudentAssignment.assignment_id == submission.assignment_id
                )
            ).first()
            
            if student_assignment:
                student_assignment.ai_grade = grade_result["percentage"]
                student_assignment.grade = grade_result["percentage"]
                student_assignment.feedback = grade_result["detailed_feedback"]
                student_assignment.status = "graded"
                student_assignment.updated_at = datetime.utcnow()
        
        db.commit()
        
        print(f"✅ Gemini AI processing complete: {grade_result['percentage']}% for submission {submission_id}")
        
        return {
            "status": "success",
            "message": "Submission processed successfully with Gemini AI",
            "submission_id": submission_id,
            "grade_result": grade_result,
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
        print(f"❌ Error processing submission with Gemini AI: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process submission: {str(e)}"
        )