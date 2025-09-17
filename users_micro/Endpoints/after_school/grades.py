from fastapi import APIRouter, HTTPException, Depends, status, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_, desc, func
from typing import List, Optional
from datetime import datetime, timedelta
import json
import os
import base64
import requests

from db.connection import db_dependency
from Endpoints.auth import get_current_user
from models.afterschool_models import (
    Course, CourseLesson, StudySession, AISubmission, StudentProgress
)
from schemas.afterschool_schema import (
    StudySessionStart, StudySessionEnd, StudySessionOut,
    AISubmissionUpdate, AIGradingResponse, StudentProgressOut, MessageResponse
)

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
    Start a new study session for a lesson
    """
    user_id = current_user["user_id"]
    
    # Verify course and lesson exist
    course = db.query(Course).filter(Course.id == session_data.course_id).first()
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found"
        )
    
    lesson = db.query(CourseLesson).filter(
        and_(
            CourseLesson.id == session_data.lesson_id,
            CourseLesson.course_id == session_data.course_id
        )
    ).first()
    if not lesson:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lesson not found"
        )
    
    # Check if user has an active session for this lesson
    active_session = db.query(StudySession).filter(
        and_(
            StudySession.user_id == user_id,
            StudySession.lesson_id == session_data.lesson_id,
            StudySession.status == "in_progress"
        )
    ).first()
    
    if active_session:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You already have an active session for this lesson"
        )
    
    # Create new study session
    new_session = StudySession(
        user_id=user_id,
        course_id=session_data.course_id,
        lesson_id=session_data.lesson_id,
        status="in_progress"
    )
    
    db.add(new_session)
    db.commit()
    db.refresh(new_session)
    
    # Update or create student progress
    progress = db.query(StudentProgress).filter(
        and_(
            StudentProgress.user_id == user_id,
            StudentProgress.course_id == session_data.course_id
        )
    ).first()
    
    if not progress:
        # Get total lessons count for this course
        total_lessons = db.query(CourseLesson).filter(
            CourseLesson.course_id == session_data.course_id
        ).count()
        
        progress = StudentProgress(
            user_id=user_id,
            course_id=session_data.course_id,
            total_lessons=total_lessons,
            sessions_count=1
        )
        db.add(progress)
    else:
        progress.sessions_count += 1
    
    progress.last_activity = datetime.utcnow()
    
    db.commit()
    
    return new_session

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
        
        # If lesson completed, update completion count
        if session_data.completion_percentage >= 100:
            # Check if this lesson was already completed
            completed_before = db.query(StudySession).filter(
                and_(
                    StudySession.user_id == user_id,
                    StudySession.lesson_id == session.lesson_id,
                    StudySession.completion_percentage >= 100,
                    StudySession.id != session_id
                )
            ).first()
            
            if not completed_before:
                progress.lessons_completed += 1
                progress.completion_percentage = (progress.lessons_completed / progress.total_lessons) * 100
                
                # Check if course is fully completed
                if progress.completion_percentage >= 100:
                    progress.completed_at = datetime.utcnow()
    
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
# PROGRESS TRACKING ENDPOINTS
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
    """
    Get detailed progress for a specific course
    """
    user_id = current_user["user_id"]
    
    progress = db.query(StudentProgress).filter(
        and_(
            StudentProgress.user_id == user_id,
            StudentProgress.course_id == course_id
        )
    ).first()
    
    if not progress:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No progress found for this course"
        )
    
    return progress

# ===============================
# ANALYTICS ENDPOINTS
# ===============================

@router.get("/analytics/summary")
async def get_learning_analytics(
    db: db_dependency,
    current_user: dict = user_dependency,
    days: int = Query(30, description="Number of days to analyze")
):
    """
    Get learning analytics summary for the student
    """
    user_id = current_user["user_id"]
    since_date = datetime.utcnow() - timedelta(days=days)
    
    # Get recent sessions
    recent_sessions = db.query(StudySession).filter(
        and_(
            StudySession.user_id == user_id,
            StudySession.started_at >= since_date
        )
    ).all()
    
    # Calculate metrics
    total_sessions = len(recent_sessions)
    total_study_time = sum(s.duration_minutes or 0 for s in recent_sessions)
    completed_sessions = len([s for s in recent_sessions if s.status == "completed"])
    
    # Average score from recent sessions with AI feedback
    scored_sessions = [s for s in recent_sessions if s.ai_score is not None]
    average_score = None
    if scored_sessions:
        average_score = sum(s.ai_score for s in scored_sessions) / len(scored_sessions)
    
    # Study streak (consecutive days with sessions)
    study_dates = set()
    for session in recent_sessions:
        study_dates.add(session.started_at.date())
    
    streak_days = 0
    current_date = datetime.utcnow().date()
    while current_date in study_dates:
        streak_days += 1
        current_date = current_date - timedelta(days=1)
    
    return {
        "period_days": days,
        "total_sessions": total_sessions,
        "completed_sessions": completed_sessions,
        "total_study_time_minutes": total_study_time,
        "average_score": average_score,
        "study_streak_days": streak_days,
        "sessions_per_day": round(total_sessions / days, 2) if days > 0 else 0
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
    Grade submissions for multiple students in a course using K.A.N.A. AI
    Accessible to all authenticated users - grades student submissions for a specific course and lesson
    """
    try:
        
        # Extract data from request
        course_id = request.get("course_id")
        lesson_id = request.get("lesson_id", None)  # Optional - can grade entire course
        student_ids = request.get("student_ids", [])
        grade_all_students = request.get("grade_all_students", False)
        
        print(f"After-school grading request: course_id={course_id}, lesson_id={lesson_id}, grade_all={grade_all_students}")
        
        if not course_id:
            raise HTTPException(status_code=400, detail="Course ID is required")
        
        # Get course and lesson
        course = db.query(Course).filter(Course.id == course_id).first()
        if not course:
            raise HTTPException(status_code=404, detail="Course not found")
        
        lesson = None
        if lesson_id:
            lesson = db.query(CourseLesson).filter(
                and_(CourseLesson.id == lesson_id, CourseLesson.course_id == course_id)
            ).first()
            if not lesson:
                raise HTTPException(status_code=404, detail="Lesson not found in this course")
        
        print(f"Found course: {course.title}, lesson: {lesson.title if lesson else 'All lessons'}")
    
    except Exception as e:
        print(f"Error in grade_course_submissions: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
    
    # Get submissions to grade
    submissions_query = db.query(AISubmission).options(
        joinedload(AISubmission.session),
        joinedload(AISubmission.course),
        joinedload(AISubmission.lesson)
    ).filter(AISubmission.course_id == course_id)
    
    # Filter by lesson if specified
    if lesson_id:
        submissions_query = submissions_query.filter(AISubmission.lesson_id == lesson_id)
    
    # Filter by students if specified
    if not grade_all_students and student_ids:
        submissions_query = submissions_query.filter(AISubmission.user_id.in_(student_ids))
    
    # Only get PDF submissions for KANA grading
    submissions = submissions_query.filter(AISubmission.file_type == "pdf").all()
    
    if not submissions:
        raise HTTPException(status_code=404, detail="No PDF submissions found for grading")
    
    # Collect submission data for K.A.N.A. processing
    grading_data = []
    for submission in submissions:
        try:
            # Get student name from user table
            from models.users_models import User
            user = db.query(User).filter(User.id == submission.user_id).first()
            student_name = f"{user.fname or ''} {user.lname or ''}".strip() if user else f"User {submission.user_id}"
            if not student_name:
                student_name = f"User {submission.user_id}"
            
            submission_data = {
                "submission_id": submission.id,
                "user_id": submission.user_id,
                "student_name": student_name,
                "course_title": course.title,
                "lesson_title": lesson.title if lesson else submission.lesson.title,
                "file_path": submission.file_path,
                "filename": submission.original_filename,
                "submission_type": submission.submission_type,
                "has_work": True
            }
            grading_data.append(submission_data)
            print(f"Added submission {submission.id} from {student_name} to grading data")
                
        except Exception as e:
            print(f"Error processing submission {submission.id}: {str(e)}")
            continue
    
    if not grading_data:
        raise HTTPException(status_code=404, detail="No valid submissions found for grading")
    
    print(f"Total grading data entries: {len(grading_data)}")
    
    # Process the actual grading with K.A.N.A.
    try:
        
        pdf_files = []
        student_names = []
        submission_ids = []
        
        for submission_data in grading_data:
            pdf_path = submission_data.get("file_path", "")
            
            # Convert PDF file to base64
            try:
                if not os.path.isabs(pdf_path):
                    pdf_full_path = os.path.join(os.getcwd(), pdf_path)
                else:
                    pdf_full_path = pdf_path
                
                print(f"Reading PDF from: {pdf_full_path}")
                
                if os.path.exists(pdf_full_path):
                    with open(pdf_full_path, 'rb') as pdf_file:
                        pdf_content = pdf_file.read()
                        pdf_base64 = base64.b64encode(pdf_content).decode('utf-8')
                        pdf_files.append(pdf_base64)
                        student_names.append(submission_data["student_name"])
                        submission_ids.append(submission_data["submission_id"])
                        
                    print(f"Successfully encoded PDF for {submission_data['student_name']} ({len(pdf_base64)} chars)")
                else:
                    print(f"PDF file not found: {pdf_full_path}")
                        
            except Exception as pdf_error:
                print(f"Error reading PDF for {submission_data['student_name']}: {pdf_error}")
                continue
        
        if not pdf_files:
            raise HTTPException(status_code=404, detail="No valid PDF files found for grading")
        
        # Call K.A.N.A. bulk PDF grading endpoint
        lesson_objectives = lesson.learning_objectives if lesson else f"Learning objectives for {course.title}"
        course_description = course.description or f"After-school learning course: {course.title}"
        
        kana_payload = {
            "pdf_files": pdf_files,
            "assignment_title": lesson.title if lesson else f"{course.title} - Multiple Lessons",
            "max_points": 100,  # Standard 100-point scale for after-school
            "grading_rubric": lesson_objectives or course_description,
            "feedback_type": "both",
            "student_names": student_names
        }
        
        print(f"Calling K.A.N.A. with {len(pdf_files)} PDFs...")
        print(f"Assignment title: '{kana_payload['assignment_title']}'")
        print(f"Max points: {kana_payload['max_points']}")
        print(f"Rubric: '{kana_payload['grading_rubric'][:100] if kana_payload['grading_rubric'] else 'None'}'...")
        
        # Use environment variable or default K.A.N.A. endpoint
        kana_base_url = os.getenv("KANA_BASE_URL", "http://localhost:10000")
        kana_endpoint = f"{kana_base_url}/api/kana/bulk-grade-pdfs"
        
        response = requests.post(
            kana_endpoint,
            json=kana_payload,
            timeout=300  # 5 minute timeout for bulk grading
        )
        
        if response.status_code == 200:
            kana_results = response.json()
            print(f"✅ K.A.N.A. grading successful: {kana_results.get('batch_summary', {}).get('successfully_graded', 0)} students graded")
            
            # Store grades in database by updating AI submissions
            grading_results = []
            
            for i, result in enumerate(kana_results.get("student_results", [])):
                if result.get("success", False) and i < len(submission_ids):
                    submission_id = submission_ids[i]
                    student_name = result.get("student_name", "")
                    score = result.get("score", 0)
                    percentage = result.get("percentage", 0)
                    feedback = result.get("detailed_feedback", "")
                    
                    try:
                        # Update the AI submission with K.A.N.A. results
                        submission = db.query(AISubmission).filter(AISubmission.id == submission_id).first()
                        if submission:
                            submission.ai_processed = True
                            submission.ai_score = percentage  # Use percentage (0-100)
                            submission.ai_feedback = feedback
                            submission.ai_corrections = result.get("corrections", "")
                            submission.ai_strengths = result.get("strengths", "")
                            submission.ai_improvements = result.get("suggestions", "")
                            submission.processed_at = datetime.utcnow()
                            
                            # Update the associated study session
                            if submission.session_id:
                                session = db.query(StudySession).filter(StudySession.id == submission.session_id).first()
                                if session:
                                    session.ai_score = percentage
                                    session.ai_feedback = feedback
                                    session.ai_recommendations = result.get("suggestions", "")
                                    session.updated_at = datetime.utcnow()
                            
                            grading_results.append({
                                "submission_id": submission_id,
                                "user_id": submission.user_id,
                                "student_name": student_name,
                                "score": score,
                                "percentage": percentage,
                                "feedback": feedback,
                                "corrections": result.get("corrections", ""),
                                "strengths": result.get("strengths", ""),
                                "improvements": result.get("suggestions", ""),
                                "success": True
                            })
                        
                    except Exception as grade_error:
                        print(f"Error saving grade for {student_name}: {grade_error}")
                        grading_results.append({
                            "student_name": student_name,
                            "error": str(grade_error),
                            "success": False
                        })
            
            # Commit all updates to database
            try:
                db.commit()
                print(f"✅ Successfully updated {len([r for r in grading_results if r.get('success')])} submissions in database")
            except Exception as commit_error:
                db.rollback()
                print(f"❌ Error committing grades: {commit_error}")
                raise HTTPException(status_code=500, detail=f"Failed to save grades: {str(commit_error)}")
            
            # Return enhanced response with actual grading results
            return {
                "status": "success",
                "message": f"Successfully graded {len([r for r in grading_results if r.get('success')])} submissions with K.A.N.A.",
                "course": {
                    "id": course.id,
                    "title": course.title,
                    "description": course.description,
                    "subject": course.subject
                },
                "lesson": {
                    "id": lesson.id,
                    "title": lesson.title,
                    "learning_objectives": lesson.learning_objectives
                } if lesson else None,
                "grading_results": grading_results,
                "batch_summary": kana_results.get("batch_summary", {}),
                "total_submissions": len(grading_data),
                "submissions_graded": len([r for r in grading_results if r.get("success")]),
                "submissions_failed": len([r for r in grading_results if not r.get("success")])
            }
            
        else:
            print(f"❌ K.A.N.A. grading failed: {response.status_code} - {response.text}")
            raise HTTPException(status_code=500, detail=f"K.A.N.A. grading failed: {response.status_code} - {response.text}")
    
    except requests.RequestException as req_error:
        print(f"❌ K.A.N.A. request error: {req_error}")
        raise HTTPException(status_code=503, detail=f"Unable to connect to K.A.N.A. grading service: {str(req_error)}")
    except Exception as kana_error:
        print(f"❌ K.A.N.A. integration error: {kana_error}")
        raise HTTPException(status_code=500, detail=f"Grading service error: {str(kana_error)}")

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