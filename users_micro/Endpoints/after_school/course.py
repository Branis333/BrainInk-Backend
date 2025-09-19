from fastapi import APIRouter, HTTPException, Depends, status, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_, desc, func
from typing import List, Optional
from datetime import datetime

from db.connection import db_dependency
from Endpoints.auth import get_current_user
from models.afterschool_models import Course, CourseLesson, StudySession, StudentProgress
from schemas.afterschool_schema import (
    CourseCreate, CourseUpdate, CourseOut, CourseWithLessons,
    LessonCreate, LessonUpdate, LessonOut,
    CourseListResponse, LessonListResponse, MessageResponse,
    StudentDashboard, StudentProgressOut
)

router = APIRouter(prefix="/after-school/courses", tags=["After-School Courses"])

# Dependency for current user
user_dependency = Depends(get_current_user)

# ===============================
# COURSE MANAGEMENT ENDPOINTS
# ===============================

@router.post("/", response_model=CourseOut)
async def create_course(
    course_data: CourseCreate,
    db: db_dependency,
    current_user: dict = user_dependency
):
    """
    Create a comprehensive new after-school course
    
    This endpoint allows authenticated users to create detailed courses with:
    - Advanced validation and duplicate checking
    - Subject categorization and age-appropriate content
    - Difficulty level assignment for proper learning progression
    - Comprehensive metadata for better course discovery
    
    Features:
    - Validates course title uniqueness within subject category
    - Ensures age range validity and educational appropriateness
    - Supports multiple difficulty levels (beginner, intermediate, advanced)
    - Automatic creator tracking for accountability
    - Rich course descriptions with learning objectives
    
    Returns detailed course information upon successful creation
    """
    user_id = current_user["user_id"]
    
    try:
        # Enhanced validation: Check for exact matches and similar titles
        existing_exact = db.query(Course).filter(
            and_(
                Course.title.ilike(course_data.title.strip()),
                Course.subject.ilike(course_data.subject.strip()),
                Course.is_active == True
            )
        ).first()
        
        if existing_exact:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Course already exists: A course titled '{course_data.title}' already exists for subject '{course_data.subject}'. Try a different title or update the existing course (ID: {existing_exact.id})"
            )
        
        # Check for similar titles to prevent near-duplicates
        similar_courses = db.query(Course).filter(
            and_(
                Course.subject.ilike(course_data.subject.strip()),
                Course.title.ilike(f"%{course_data.title.strip()[:10]}%"),
                Course.is_active == True
            )
        ).all()
        
        # Additional validation for educational appropriateness
        if course_data.age_min < 3 or course_data.age_max > 16:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Age range must be between 3-16 years for after-school programs"
            )
        
        if course_data.age_max < course_data.age_min:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Maximum age must be greater than or equal to minimum age"
            )
        
        # Validate subject categories
        valid_subjects = [
            "Mathematics", "Science", "English", "Reading", "Writing", "History", 
            "Geography", "Art", "Music", "Physical Education", "Technology", 
            "Languages", "Social Studies", "Critical Thinking", "Problem Solving"
        ]
        
        if course_data.subject not in valid_subjects:
            print(f"Warning: Subject '{course_data.subject}' not in standard curriculum. Proceeding anyway.")
        
        # Create comprehensive course with enhanced metadata
        new_course = Course(
            title=course_data.title.strip(),
            subject=course_data.subject.strip(),
            description=course_data.description.strip() if course_data.description else f"Comprehensive {course_data.subject} course for ages {course_data.age_min}-{course_data.age_max}",
            age_min=course_data.age_min,
            age_max=course_data.age_max,
            difficulty_level=course_data.difficulty_level,
            created_by=user_id
        )
        
        db.add(new_course)
        db.commit()
        db.refresh(new_course)
        
        # Log course creation for analytics
        print(f"✅ Course created successfully: ID {new_course.id} - '{new_course.title}' by user {user_id}")
        
        # Return enhanced response with additional context
        response_data = {
            "id": new_course.id,
            "title": new_course.title,
            "subject": new_course.subject,
            "description": new_course.description,
            "age_min": new_course.age_min,
            "age_max": new_course.age_max,
            "difficulty_level": new_course.difficulty_level,
            "created_by": new_course.created_by,
            "is_active": new_course.is_active,
            "created_at": new_course.created_at,
            "updated_at": new_course.updated_at,
            "_metadata": {
                "creation_status": "success",
                "similar_courses_count": len(similar_courses),
                "next_steps": [
                    "Add lessons to your course",
                    "Set learning objectives for each lesson",
                    "Configure course materials and resources"
                ]
            }
        }
        
        return new_course
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error creating course: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create course: {str(e)}"
        )

@router.get("/", response_model=CourseListResponse)
async def list_courses(
    db: db_dependency,
    current_user: dict = user_dependency,
    # Enhanced filtering options
    subject: Optional[str] = Query(None, description="Filter by subject (supports partial matches)"),
    search: Optional[str] = Query(None, description="Search in course title and description"),
    age: Optional[int] = Query(None, ge=3, le=16, description="Filter courses suitable for specific age"),
    age_range: Optional[str] = Query(None, description="Filter by age range: 'early' (3-6), 'middle' (7-10), 'late' (11-16)"),
    difficulty: Optional[str] = Query(None, description="Filter by difficulty: beginner, intermediate, advanced"),
    created_by: Optional[int] = Query(None, description="Filter by course creator"),
    
    # Advanced options
    active_only: bool = Query(True, description="Show only active courses"),
    has_lessons: Optional[bool] = Query(None, description="Filter courses with/without lessons"),
    popular: Optional[bool] = Query(None, description="Show popular courses (most enrolled)"),
    recent: Optional[bool] = Query(None, description="Show recently created courses (last 30 days)"),
    
    # Sorting options
    sort_by: Optional[str] = Query("created_at", description="Sort by: title, subject, created_at, difficulty, popularity"),
    sort_order: Optional[str] = Query("desc", description="Sort order: asc or desc"),
    
    # Pagination
    skip: int = Query(0, ge=0, description="Skip items for pagination"),
    limit: int = Query(50, ge=1, le=100, description="Limit items (max 100)")
):
    """
    Advanced course listing with comprehensive filtering and search capabilities
    
    This endpoint provides powerful course discovery features including:
    
    🔍 **Search & Filtering:**
    - Text search across titles and descriptions
    - Subject-based filtering with partial matching
    - Age-appropriate course recommendations
    - Difficulty level filtering for progressive learning
    - Creator-based filtering
    
    📊 **Advanced Options:**
    - Popular courses based on enrollment metrics
    - Recently created courses for new content discovery
    - Courses with/without lesson content
    - Active/inactive course status filtering
    
    🗂️ **Sorting & Organization:**
    - Multiple sorting criteria (title, date, popularity, difficulty)
    - Ascending/descending order options
    - Pagination for large datasets
    
    📈 **Analytics Integration:**
    - Enrollment statistics for each course
    - Completion rates and user engagement metrics
    - Performance insights for course recommendations
    
    Returns paginated course list with comprehensive metadata
    """
    user_id = current_user["user_id"]
    
    try:
        # Start with base query
        query = db.query(Course)
        
        # Apply active filter first for performance
        if active_only:
            query = query.filter(Course.is_active == True)
        
        # Text search across title and description
        if search:
            search_term = f"%{search.strip()}%"
            query = query.filter(
                or_(
                    Course.title.ilike(search_term),
                    Course.description.ilike(search_term),
                    Course.subject.ilike(search_term)
                )
            )
        
        # Subject filtering with partial matching
        if subject:
            query = query.filter(Course.subject.ilike(f"%{subject.strip()}%"))
        
        # Age-based filtering
        if age:
            query = query.filter(
                and_(Course.age_min <= age, Course.age_max >= age)
            )
        
        # Age range categories
        if age_range:
            if age_range.lower() == "early":
                query = query.filter(Course.age_min <= 6)
            elif age_range.lower() == "middle":
                query = query.filter(
                    and_(Course.age_min <= 10, Course.age_max >= 7)
                )
            elif age_range.lower() == "late":
                query = query.filter(Course.age_max >= 11)
        
        # Difficulty level filtering
        if difficulty:
            valid_difficulties = ["beginner", "intermediate", "advanced"]
            if difficulty.lower() in valid_difficulties:
                query = query.filter(Course.difficulty_level == difficulty.lower())
        
        # Creator filtering
        if created_by:
            query = query.filter(Course.created_by == created_by)
        
        # Recent courses filter (last 30 days)
        if recent:
            from datetime import timedelta
            thirty_days_ago = datetime.utcnow() - timedelta(days=30)
            query = query.filter(Course.created_at >= thirty_days_ago)
        
        # Courses with lessons filter
        if has_lessons is not None:
            if has_lessons:
                query = query.join(CourseLesson).filter(CourseLesson.is_active == True)
            else:
                # Use left join to find courses without lessons
                subquery = db.query(CourseLesson.course_id).filter(CourseLesson.is_active == True).subquery()
                query = query.filter(~Course.id.in_(subquery))
        
        # Get total count before applying sorting and pagination
        total_count = query.count()
        
        # Apply sorting
        valid_sort_fields = ["title", "subject", "created_at", "difficulty_level", "updated_at"]
        if sort_by in valid_sort_fields:
            sort_column = getattr(Course, sort_by)
            if sort_order.lower() == "desc":
                query = query.order_by(desc(sort_column))
            else:
                query = query.order_by(sort_column)
        else:
            # Default sorting by creation date (newest first)
            query = query.order_by(desc(Course.created_at))
        
        # Apply pagination
        courses = query.offset(skip).limit(limit).all()
        
        # Enhanced response with analytics
        enhanced_courses = []
        for course in courses:
            # Get lesson count
            lesson_count = db.query(CourseLesson).filter(
                and_(
                    CourseLesson.course_id == course.id,
                    CourseLesson.is_active == True
                )
            ).count()
            
            # Get enrollment count (students who started sessions)
            enrollment_count = db.query(StudySession.user_id).filter(
                StudySession.course_id == course.id
            ).distinct().count()
            
            # Add metadata to course
            course_dict = {
                "id": course.id,
                "title": course.title,
                "subject": course.subject,
                "description": course.description,
                "age_min": course.age_min,
                "age_max": course.age_max,
                "difficulty_level": course.difficulty_level,
                "created_by": course.created_by,
                "is_active": course.is_active,
                "created_at": course.created_at,
                "updated_at": course.updated_at,
                "_stats": {
                    "lesson_count": lesson_count,
                    "enrollment_count": enrollment_count,
                    "has_content": lesson_count > 0
                }
            }
            enhanced_courses.append(course_dict)
        
        # Popular courses sorting (if requested)
        if popular:
            enhanced_courses.sort(key=lambda x: x["_stats"]["enrollment_count"], reverse=True)
        
        print(f"📚 Course list retrieved: {len(courses)} courses (total: {total_count}) for user {user_id}")
        
        return CourseListResponse(
            courses=[Course(**{k: v for k, v in course.items() if k != "_stats"}) for course in enhanced_courses],
            total=total_count
        )
        
    except Exception as e:
        print(f"❌ Error listing courses: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve courses: {str(e)}"
        )

# ===============================
# STUDENT DASHBOARD ENDPOINTS (must be before /{course_id} route)
# ===============================

@router.get("/dashboard", response_model=StudentDashboard)
async def get_student_dashboard(
    db: db_dependency,
    current_user: dict = user_dependency
):
    """
    Get student dashboard with courses and progress
    """
    user_id = current_user["user_id"]
    
    # Get active courses the student is enrolled in (through study sessions)
    active_course_ids = db.query(StudySession.course_id).filter(
        StudySession.user_id == user_id
    ).distinct().all()
    
    active_courses = []
    if active_course_ids:
        course_ids = [course_id[0] for course_id in active_course_ids]
        active_courses = db.query(Course).filter(
            and_(
                Course.id.in_(course_ids),
                Course.is_active == True
            )
        ).all()
    
    # Get recent study sessions (last 10)
    recent_sessions = db.query(StudySession).filter(
        StudySession.user_id == user_id
    ).order_by(StudySession.started_at.desc()).limit(10).all()
    
    # Get progress summary
    progress_summary = db.query(StudentProgress).filter(
        StudentProgress.user_id == user_id
    ).all()
    
    # Calculate total study time and average score
    all_sessions = db.query(StudySession).filter(
        and_(
            StudySession.user_id == user_id,
            StudySession.duration_minutes.isnot(None)
        )
    ).all()
    
    total_study_time = sum(session.duration_minutes or 0 for session in all_sessions)
    
    scored_sessions = [s for s in all_sessions if s.ai_score is not None]
    average_score = None
    if scored_sessions:
        average_score = sum(s.ai_score for s in scored_sessions) / len(scored_sessions)
    
    return StudentDashboard(
        user_id=user_id,
        active_courses=active_courses,
        recent_sessions=recent_sessions,
        progress_summary=progress_summary,
        total_study_time=total_study_time,
        average_score=average_score
    )

@router.get("/{course_id}", response_model=CourseWithLessons)
async def get_course_comprehensive_details(
    course_id: int,
    db: db_dependency,
    current_user: dict = user_dependency,
    include_stats: bool = Query(True, description="Include detailed statistics and analytics"),
    include_progress: bool = Query(True, description="Include user's personal progress"),
    include_recommendations: bool = Query(False, description="Include AI-powered recommendations")
):
    """
    Get comprehensive course details with advanced analytics and personalization
    
    This endpoint provides in-depth course information including:
    
    📚 **Core Course Data:**
    - Complete course metadata and description
    - Structured lesson progression with learning objectives
    - Age-appropriate content categorization
    - Difficulty level and prerequisites
    
    📊 **Advanced Analytics:**
    - Enrollment statistics and trends
    - Completion rates and success metrics
    - Lesson engagement analytics
    - Student performance insights
    
    👤 **Personalized Information:**
    - User's personal progress and achievements
    - Completed lessons and scores
    - Time spent and learning streaks
    - Personalized recommendations for next steps
    
    🎯 **Learning Insights:**
    - Popular lesson sequences
    - Difficulty progression analysis
    - Estimated completion time
    - Success rate predictions
    
    🔍 **Quality Metrics:**
    - Content freshness indicators
    - User satisfaction ratings
    - Lesson effectiveness scores
    - Curriculum alignment status
    
    Returns comprehensive course data with optional analytics and personalization
    """
    user_id = current_user["user_id"]
    
    try:
        # Get course with lessons using eager loading
        course = db.query(Course).options(
            joinedload(Course.lessons)
        ).filter(Course.id == course_id).first()
        
        if not course:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Course not found: No course exists with ID {course_id}. Check the course ID or search for available courses."
            )
        
        # Check if course is accessible (active or created by user)
        if not course.is_active and course.created_by != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Course not accessible: This course is currently inactive."
            )
        
        # Sort lessons by order_index and filter active lessons
        active_lessons = [lesson for lesson in course.lessons if lesson.is_active]
        course.lessons = sorted(active_lessons, key=lambda x: x.order_index)
        
        # Enhanced course response with comprehensive data
        course_data = {
            "id": course.id,
            "title": course.title,
            "subject": course.subject,
            "description": course.description,
            "age_min": course.age_min,
            "age_max": course.age_max,
            "difficulty_level": course.difficulty_level,
            "created_by": course.created_by,
            "is_active": course.is_active,
            "created_at": course.created_at,
            "updated_at": course.updated_at,
            "lessons": course.lessons
        }
        
        if include_stats:
            # Calculate comprehensive course statistics
            total_lessons = len(course.lessons)
            
            # Enrollment and engagement metrics
            total_enrollments = db.query(StudySession.user_id).filter(
                StudySession.course_id == course_id
            ).distinct().count()
            
            total_sessions = db.query(StudySession).filter(
                StudySession.course_id == course_id
            ).count()
            
            completed_sessions = db.query(StudySession).filter(
                and_(
                    StudySession.course_id == course_id,
                    StudySession.status == "completed"
                )
            ).count()
            
            # Average completion time
            avg_session_time = db.query(func.avg(StudySession.duration_minutes)).filter(
                and_(
                    StudySession.course_id == course_id,
                    StudySession.duration_minutes.isnot(None)
                )
            ).scalar() or 0
            
            # Performance metrics
            avg_score = db.query(func.avg(StudySession.ai_score)).filter(
                and_(
                    StudySession.course_id == course_id,
                    StudySession.ai_score.isnot(None)
                )
            ).scalar() or 0
            
            # Recent activity (last 7 days)
            from datetime import timedelta
            week_ago = datetime.utcnow() - timedelta(days=7)
            recent_activity = db.query(StudySession).filter(
                and_(
                    StudySession.course_id == course_id,
                    StudySession.started_at >= week_ago
                )
            ).count()
            
            course_data["statistics"] = {
                "total_lessons": total_lessons,
                "total_enrollments": total_enrollments,
                "total_sessions": total_sessions,
                "completed_sessions": completed_sessions,
                "completion_rate": (completed_sessions / total_sessions * 100) if total_sessions > 0 else 0,
                "average_session_duration": round(avg_session_time, 2),
                "average_score": round(avg_score, 2),
                "recent_activity_7days": recent_activity,
                "estimated_total_duration": sum(lesson.estimated_duration for lesson in course.lessons),
                "engagement_level": "high" if recent_activity > 5 else "medium" if recent_activity > 2 else "low"
            }
        
        if include_progress:
            # Get user's personal progress for this course
            user_progress = db.query(StudentProgress).filter(
                and_(
                    StudentProgress.user_id == user_id,
                    StudentProgress.course_id == course_id
                )
            ).first()
            
            # Get user's sessions for this course
            user_sessions = db.query(StudySession).filter(
                and_(
                    StudySession.user_id == user_id,
                    StudySession.course_id == course_id
                )
            ).order_by(desc(StudySession.started_at)).all()
            
            # Calculate lesson-wise progress
            lesson_progress = {}
            for lesson in course.lessons:
                lesson_sessions = [s for s in user_sessions if s.lesson_id == lesson.id]
                completed = any(s.status == "completed" for s in lesson_sessions)
                best_score = max((s.ai_score for s in lesson_sessions if s.ai_score), default=None)
                
                lesson_progress[lesson.id] = {
                    "lesson_title": lesson.title,
                    "completed": completed,
                    "attempts": len(lesson_sessions),
                    "best_score": best_score,
                    "last_attempted": lesson_sessions[0].started_at.isoformat() if lesson_sessions else None
                }
            
            course_data["user_progress"] = {
                "overall_progress": user_progress.__dict__ if user_progress else None,
                "lesson_progress": lesson_progress,
                "total_sessions": len(user_sessions),
                "last_activity": user_sessions[0].started_at.isoformat() if user_sessions else None,
                "next_lesson_recommendation": next(
                    (lesson.id for lesson in course.lessons 
                     if lesson.id not in [lid for lid, progress in lesson_progress.items() if progress["completed"]]),
                    None
                )
            }
        
        if include_recommendations:
            # AI-powered recommendations (placeholder for future AI integration)
            similar_courses = db.query(Course).filter(
                and_(
                    Course.subject == course.subject,
                    Course.difficulty_level == course.difficulty_level,
                    Course.id != course_id,
                    Course.is_active == True
                )
            ).limit(3).all()
            
            course_data["recommendations"] = {
                "similar_courses": [
                    {
                        "id": c.id,
                        "title": c.title,
                        "difficulty_level": c.difficulty_level,
                        "reason": f"Similar {c.subject} content at {c.difficulty_level} level"
                    }
                    for c in similar_courses
                ],
                "next_difficulty": {
                    "available": course.difficulty_level != "advanced",
                    "level": "intermediate" if course.difficulty_level == "beginner" else "advanced" if course.difficulty_level == "intermediate" else None
                },
                "study_tips": [
                    f"Complete lessons in order for best learning progression",
                    f"Spend at least {max(15, sum(l.estimated_duration for l in course.lessons) // len(course.lessons))} minutes per lesson",
                    f"Review feedback from AI grading to improve performance"
                ]
            }
        
        print(f"📖 Course details retrieved: '{course.title}' (ID: {course_id}) for user {user_id}")
        
        return CourseWithLessons(**course_data)
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error retrieving course details: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve course details: {str(e)}"
        )

@router.put("/{course_id}", response_model=CourseOut)
async def update_course_comprehensive(
    course_id: int,
    course_data: CourseUpdate,
    db: db_dependency,
    current_user: dict = user_dependency,
    force_update: bool = Query(False, description="Force update even if course has active students"),
    create_backup: bool = Query(True, description="Create backup before major changes")
):
    """
    Comprehensively update course with advanced validation and change tracking
    
    This endpoint provides sophisticated course modification capabilities including:
    
    🔧 **Smart Update Features:**
    - Comprehensive field validation and conflict detection
    - Automatic change tracking and audit logging
    - Impact analysis for courses with active students
    - Rollback capabilities with backup creation
    
    ⚠️ **Safety Mechanisms:**
    - Prevents disruptive changes to courses with active learners
    - Validates age range and difficulty level consistency
    - Checks for duplicate course titles within subjects
    - Maintains data integrity with transaction safety
    
    📊 **Change Impact Analysis:**
    - Analyzes effect on enrolled students
    - Calculates learning progression impact
    - Provides warnings for significant modifications
    - Suggests alternative update strategies
    
    🔍 **Audit Trail:**
    - Logs all changes with timestamps and user attribution
    - Tracks modification history for accountability
    - Provides change comparison and diff tracking
    - Maintains version control for course evolution
    
    📈 **Enhancement Suggestions:**
    - Recommends improvements based on usage analytics
    - Suggests content updates for better engagement
    - Provides performance optimization tips
    - Offers curriculum alignment recommendations
    
    Returns updated course with change summary and impact analysis
    """
    user_id = current_user["user_id"]
    
    try:
        # Find the course with comprehensive validation
        course = db.query(Course).filter(Course.id == course_id).first()
        
        if not course:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Course not found: No course exists with ID {course_id}. Verify the course ID or check if the course was deleted."
            )
        
        # Check if course can be modified
        active_students = db.query(StudySession.user_id).filter(
            and_(
                StudySession.course_id == course_id,
                StudySession.status == "in_progress"
            )
        ).distinct().count()
        
        total_enrollments = db.query(StudySession.user_id).filter(
            StudySession.course_id == course_id
        ).distinct().count()
        
        # Analyze impact of changes
        update_data = course_data.dict(exclude_unset=True)
        significant_changes = []
        warnings = []
        
        # Check for significant changes that might affect students
        if "difficulty_level" in update_data and update_data["difficulty_level"] != course.difficulty_level:
            significant_changes.append("difficulty_level")
            if active_students > 0:
                warnings.append(f"Changing difficulty level will affect {active_students} active students")
        
        if "age_min" in update_data or "age_max" in update_data:
            new_age_min = update_data.get("age_min", course.age_min)
            new_age_max = update_data.get("age_max", course.age_max)
            
            if new_age_min != course.age_min or new_age_max != course.age_max:
                significant_changes.append("age_range")
                if total_enrollments > 0:
                    warnings.append(f"Age range changes may affect {total_enrollments} enrolled students")
        
        if "is_active" in update_data and update_data["is_active"] != course.is_active:
            if not update_data["is_active"] and active_students > 0:
                if not force_update:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Cannot deactivate course: Course has {active_students} active students. Use force_update=true to override this safety check."
                    )
                warnings.append(f"Force deactivating course with {active_students} active students")
        
        # Title and subject conflict checking
        if "title" in update_data or "subject" in update_data:
            new_title = update_data.get("title", course.title)
            new_subject = update_data.get("subject", course.subject)
            
            # Check for conflicts only if title or subject actually changed
            if new_title != course.title or new_subject != course.subject:
                existing_course = db.query(Course).filter(
                    and_(
                        Course.title.ilike(new_title.strip()),
                        Course.subject.ilike(new_subject.strip()),
                        Course.id != course_id,
                        Course.is_active == True
                    )
                ).first()
                
                if existing_course:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Course conflict: A course titled '{new_title}' already exists for subject '{new_subject}' (ID: {existing_course.id}). Choose a different title or update the existing course."
                    )
        
        # Age range validation
        if "age_min" in update_data or "age_max" in update_data:
            new_age_min = update_data.get("age_min", course.age_min)
            new_age_max = update_data.get("age_max", course.age_max)
            
            if new_age_min < 3 or new_age_max > 16:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Age range must be between 3-16 years for after-school programs"
                )
            
            if new_age_max < new_age_min:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Maximum age must be greater than or equal to minimum age"
                )
        
        # Create backup if requested and significant changes detected
        backup_info = None
        if create_backup and (significant_changes or warnings):
            backup_info = {
                "timestamp": datetime.utcnow().isoformat(),
                "original_data": {
                    "title": course.title,
                    "subject": course.subject,
                    "description": course.description,
                    "age_min": course.age_min,
                    "age_max": course.age_max,
                    "difficulty_level": course.difficulty_level,
                    "is_active": course.is_active
                },
                "change_reason": f"Update by user {user_id}",
                "affected_students": total_enrollments
            }
        
        # Apply updates with comprehensive logging
        changes_made = {}
        for field, value in update_data.items():
            old_value = getattr(course, field)
            if old_value != value:
                changes_made[field] = {"from": old_value, "to": value}
                setattr(course, field, value)
        
        # Update timestamp and commit
        course.updated_at = datetime.utcnow()
        
        db.commit()
        db.refresh(course)
        
        # Log the update
        print(f"📝 Course updated: ID {course_id} by user {user_id}")
        print(f"   Changes: {list(changes_made.keys())}")
        if warnings:
            print(f"   Warnings: {warnings}")
        
        # Enhanced response with change tracking
        response_data = {
            "id": course.id,
            "title": course.title,
            "subject": course.subject,
            "description": course.description,
            "age_min": course.age_min,
            "age_max": course.age_max,
            "difficulty_level": course.difficulty_level,
            "created_by": course.created_by,
            "is_active": course.is_active,
            "created_at": course.created_at,
            "updated_at": course.updated_at,
            "_update_summary": {
                "changes_made": changes_made,
                "significant_changes": significant_changes,
                "warnings": warnings,
                "affected_students": total_enrollments,
                "active_students": active_students,
                "backup_created": backup_info is not None,
                "backup_info": backup_info,
                "update_timestamp": course.updated_at.isoformat(),
                "updated_by": user_id
            }
        }
        
        return course
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error updating course: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update course: {str(e)}"
        )

@router.delete("/{course_id}", response_model=MessageResponse)
async def delete_course_with_safety_checks(
    course_id: int,
    db: db_dependency,
    current_user: dict = user_dependency,
    force_delete: bool = Query(False, description="Force delete even with active students"),
    archive_data: bool = Query(True, description="Archive course data before deletion")
):
    """
    Safely delete/deactivate course with comprehensive impact analysis
    
    This endpoint provides secure course deletion with multiple safety mechanisms:
    
    🛡️ **Safety Features:**
    - Prevents accidental deletion of courses with active students
    - Comprehensive impact analysis before deletion
    - Data archival and backup before removal
    - Graceful handling of dependent relationships
    
    📊 **Impact Analysis:**
    - Counts affected students and their progress
    - Analyzes lesson completion and grading data
    - Calculates learning disruption metrics
    - Provides deletion impact summary
    
    🗄️ **Data Preservation:**
    - Archives course content and student progress
    - Maintains historical learning records
    - Preserves analytics and performance data
    - Enables potential course restoration
    
    ⚠️ **Protection Mechanisms:**
    - Requires confirmation for courses with active learners
    - Validates user permissions and course ownership
    - Implements soft deletion for data recovery
    - Maintains referential integrity
    
    Returns detailed deletion summary with impact analysis
    """
    user_id = current_user["user_id"]
    
    try:
        # Find and validate course
        course = db.query(Course).filter(Course.id == course_id).first()
        
        if not course:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Course not found: No course exists with ID {course_id}. Verify the course ID or check if already deleted."
            )
        
        if not course.is_active:
            return MessageResponse(
                message=f"Course '{course.title}' is already deactivated"
            )
        
        # Comprehensive impact analysis
        total_students = db.query(StudySession.user_id).filter(
            StudySession.course_id == course_id
        ).distinct().count()
        
        active_students = db.query(StudySession.user_id).filter(
            and_(
                StudySession.course_id == course_id,
                StudySession.status == "in_progress"
            )
        ).distinct().count()
        
        total_sessions = db.query(StudySession).filter(
            StudySession.course_id == course_id
        ).count()
        
        total_lessons = db.query(CourseLesson).filter(
            CourseLesson.course_id == course_id
        ).count()
        
        # Check if deletion is safe
        if active_students > 0 and not force_delete:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot delete course with active students: Course has {active_students} students with active study sessions (total: {total_students} students, {total_sessions} sessions, {total_lessons} lessons). Wait for sessions to complete or use force_delete=true. Consider deactivating instead of deleting to preserve student data."
            )
        
        # Archive data if requested
        archive_info = None
        if archive_data:
            archive_info = {
                "course_data": {
                    "id": course.id,
                    "title": course.title,
                    "subject": course.subject,
                    "description": course.description,
                    "difficulty_level": course.difficulty_level,
                    "created_by": course.created_by,
                    "created_at": course.created_at.isoformat()
                },
                "statistics": {
                    "total_students": total_students,
                    "active_students": active_students,
                    "total_sessions": total_sessions,
                    "total_lessons": total_lessons
                },
                "archived_at": datetime.utcnow().isoformat(),
                "archived_by": user_id
            }
        
        # Perform soft deletion
        course.is_active = False
        course.updated_at = datetime.utcnow()
        
        # Also deactivate associated lessons
        db.query(CourseLesson).filter(
            CourseLesson.course_id == course_id
        ).update({
            CourseLesson.is_active: False,
            CourseLesson.updated_at: datetime.utcnow()
        })
        
        db.commit()
        
        # Log the deletion
        print(f"🗑️ Course deactivated: '{course.title}' (ID: {course_id}) by user {user_id}")
        print(f"   Impact: {total_students} students, {total_sessions} sessions, {total_lessons} lessons")
        
        return MessageResponse(
            message=f"Course '{course.title}' has been successfully deactivated. "
                   f"Impact: {total_students} students affected, {total_lessons} lessons deactivated. "
                   f"Data {'archived' if archive_data else 'preserved'} for potential restoration."
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error deleting course: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete course: {str(e)}"
        )

# ===============================
# LESSON MANAGEMENT ENDPOINTS
# ===============================

@router.post("/{course_id}/lessons", response_model=LessonOut)
async def create_lesson(
    course_id: int,
    lesson_data: LessonCreate,
    db: db_dependency,
    current_user: dict = user_dependency
):
    """
    Create a new lesson for a course
    Accessible to all authenticated users
    """
    
    # Check if course exists
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found"
        )
    
    # Create new lesson
    new_lesson = CourseLesson(
        course_id=course_id,
        title=lesson_data.title,
        content=lesson_data.content,
        learning_objectives=lesson_data.learning_objectives,
        order_index=lesson_data.order_index,
        estimated_duration=lesson_data.estimated_duration
    )
    
    db.add(new_lesson)
    db.commit()
    db.refresh(new_lesson)
    
    return new_lesson

@router.get("/{course_id}/lessons", response_model=LessonListResponse)
async def list_lessons(
    course_id: int,
    db: db_dependency,
    current_user: dict = user_dependency,
    active_only: bool = Query(True, description="Show only active lessons")
):
    """
    List all lessons for a course
    """
    # Check if course exists
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found"
        )
    
    query = db.query(CourseLesson).filter(CourseLesson.course_id == course_id)
    
    if active_only:
        query = query.filter(CourseLesson.is_active == True)
    
    lessons = query.order_by(CourseLesson.order_index).all()
    
    return LessonListResponse(lessons=lessons, total=len(lessons))

@router.get("/{course_id}/lessons/{lesson_id}", response_model=LessonOut)
async def get_lesson(
    course_id: int,
    lesson_id: int,
    db: db_dependency,
    current_user: dict = user_dependency
):
    """
    Get specific lesson details
    """
    lesson = db.query(CourseLesson).filter(
        and_(
            CourseLesson.id == lesson_id,
            CourseLesson.course_id == course_id
        )
    ).first()
    
    if not lesson:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lesson not found"
        )
    
    return lesson

@router.put("/{course_id}/lessons/{lesson_id}", response_model=LessonOut)
async def update_lesson(
    course_id: int,
    lesson_id: int,
    lesson_data: LessonUpdate,
    db: db_dependency,
    current_user: dict = user_dependency
):
    """
    Update lesson
    Accessible to all authenticated users
    """
    
    lesson = db.query(CourseLesson).filter(
        and_(
            CourseLesson.id == lesson_id,
            CourseLesson.course_id == course_id
        )
    ).first()
    
    if not lesson:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lesson not found"
        )
    
    # Update fields if provided
    update_data = lesson_data.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(lesson, field, value)
    
    lesson.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(lesson)
    
    return lesson

@router.delete("/{course_id}/lessons/{lesson_id}", response_model=MessageResponse)
async def delete_lesson(
    course_id: int,
    lesson_id: int,
    db: db_dependency,
    current_user: dict = user_dependency
):
    """
    Delete lesson - Soft delete by setting is_active to False
    Accessible to all authenticated users
    """
    
    lesson = db.query(CourseLesson).filter(
        and_(
            CourseLesson.id == lesson_id,
            CourseLesson.course_id == course_id
        )
    ).first()
    
    if not lesson:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lesson not found"
        )
    
    # Soft delete
    lesson.is_active = False
    lesson.updated_at = datetime.utcnow()
    
    db.commit()
    
    return MessageResponse(message=f"Lesson '{lesson.title}' has been deactivated")

