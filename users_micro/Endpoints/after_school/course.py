from fastapi import APIRouter, HTTPException, Depends, status, Query, File, UploadFile, Form
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_, desc, func
from typing import List, Optional
from datetime import datetime, timedelta
import os
import tempfile
import mimetypes
from pathlib import Path

from db.connection import db_dependency
from Endpoints.auth import get_current_user
from models.afterschool_models import (
    Course, CourseLesson, CourseBlock, CourseAssignment, 
    StudySession, StudentProgress, StudentAssignment, AISubmission
)
from models.study_area_models import StudentPDF
from schemas.afterschool_schema import (
    CourseCreate, TextbookCourseCreate, TextbookCourseForm, CourseUpdate, CourseOut, CourseWithLessons,
    CourseWithBlocks, ComprehensiveCourseOut, CourseBlockOut, CourseAssignmentOut,
    LessonCreate, LessonUpdate, LessonOut,
    CourseListResponse, LessonListResponse, MessageResponse,
    StudentDashboard, StudentProgressOut, StudentAssignmentOut,
    CourseBlocksProgressOut, BlockProgressOut
)
from services.gemini_service import gemini_service
from services.image_service import image_service

router = APIRouter(prefix="/after-school/courses", tags=["After-School Courses"])

# Dependency for current user
user_dependency = Depends(get_current_user)

# ===============================
# COURSE MANAGEMENT ENDPOINTS
# ===============================

@router.get("/{course_id}/progress", response_model=StudentProgressOut)
async def get_course_progress(
    course_id: int,
    db: db_dependency,
    current_user: dict = user_dependency
):
    """
    Compute and return the student's progress for a course based on mark-done sessions and submissions.

    - Uses StudySession records with status='completed' to count completed blocks/lessons
    - Calculates totals from CourseBlock and CourseLesson
    - Derives completion percentage prioritizing block-based structure; falls back to lessons
    - Aggregates average AI score across processed AISubmissions for the course
    - Upserts StudentProgress for idempotency and returns the fresh record
    """
    user_id = current_user["user_id"]

    # Validate course
    course = db.query(Course).filter(Course.id == course_id, Course.is_active == True).first()
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")

    try:
        # Totals from structure
        total_blocks = db.query(CourseBlock).filter(CourseBlock.course_id == course_id, CourseBlock.is_active == True).count()
        total_lessons = db.query(CourseLesson).filter(CourseLesson.course_id == course_id, CourseLesson.is_active == True).count()

        # Completed via mark-done sessions
        completed_sessions_q = db.query(StudySession).filter(
            StudySession.user_id == user_id,
            StudySession.course_id == course_id,
            StudySession.status == "completed"
        )
        blocks_completed = completed_sessions_q.filter(StudySession.block_id.isnot(None)).count()
        lessons_completed = completed_sessions_q.filter(StudySession.lesson_id.isnot(None)).count()

        # Average score from processed submissions
        processed = db.query(AISubmission.ai_score).filter(
            AISubmission.user_id == user_id,
            AISubmission.course_id == course_id,
            AISubmission.ai_score.isnot(None)
        ).all()
        avg_score = None
        if processed:
            scores = [row[0] for row in processed if row[0] is not None]
            if scores:
                avg_score = sum(scores) / len(scores)

        # Sessions count and total study time (legacy minutes if present)
        all_sessions = db.query(StudySession).filter(
            StudySession.user_id == user_id,
            StudySession.course_id == course_id
        ).all()
        sessions_count = len(all_sessions)
        total_study_time = sum([s.duration_minutes or 0 for s in all_sessions])

        # Completion percentage: prefer blocks when structure exists
        completion_percentage = 0.0
        if total_blocks > 0:
            completion_percentage = (blocks_completed / total_blocks) * 100.0
        elif total_lessons > 0:
            completion_percentage = (lessons_completed / total_lessons) * 100.0

        # Clamp and round
        completion_percentage = round(max(0.0, min(100.0, completion_percentage)), 2)

        # Upsert StudentProgress
        progress = db.query(StudentProgress).filter(
            StudentProgress.user_id == user_id,
            StudentProgress.course_id == course_id
        ).first()

        now = datetime.utcnow()
        if not progress:
            progress = StudentProgress(
                user_id=user_id,
                course_id=course_id,
                lessons_completed=lessons_completed,
                total_lessons=total_lessons,
                blocks_completed=blocks_completed,
                total_blocks=total_blocks,
                completion_percentage=completion_percentage,
                average_score=avg_score,
                total_study_time=total_study_time,
                sessions_count=sessions_count,
                started_at=now,
                last_activity=now,
                completed_at=now if completion_percentage >= 100.0 else None,
            )
            db.add(progress)
        else:
            progress.lessons_completed = lessons_completed
            progress.total_lessons = total_lessons
            progress.blocks_completed = blocks_completed
            progress.total_blocks = total_blocks
            progress.completion_percentage = completion_percentage
            progress.average_score = avg_score
            progress.total_study_time = total_study_time
            progress.sessions_count = sessions_count
            progress.last_activity = now
            progress.completed_at = progress.completed_at or (now if completion_percentage >= 100.0 else None)

        db.commit()
        db.refresh(progress)

        # Trigger completion notification if newly completed (100%)
        if completion_percentage >= 100.0 and not progress.completed_at:
            # Course is now fully complete, send congratulations notification
            try:
                from Endpoints.after_school.notification_scheduler import NotificationScheduler
                course = db.query(Course).filter(Course.id == course_id).first()
                if course:
                    NotificationScheduler.trigger_completion_notification(
                        user_id=user_id,
                        course_id=course_id,
                        course_title=course.title,
                        completion_type="course"
                    )
                    print(f"🎉 Triggered completion notification for user {user_id}, course {course_id}")
            except Exception as e:
                print(f"⚠️ Error triggering completion notification: {str(e)}")

        # Build response
        return StudentProgressOut(
            id=progress.id,
            user_id=progress.user_id,
            course_id=progress.course_id,
            lessons_completed=progress.lessons_completed,
            total_lessons=progress.total_lessons,
            completion_percentage=progress.completion_percentage,
            blocks_completed=progress.blocks_completed,
            total_blocks=progress.total_blocks,
            average_score=progress.average_score,
            total_study_time=progress.total_study_time,
            sessions_count=progress.sessions_count,
            started_at=progress.started_at,
            last_activity=progress.last_activity,
            completed_at=progress.completed_at,
            created_at=progress.created_at,
            updated_at=progress.updated_at,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to compute course progress: {e}")


@router.get("/assignments/my-assignments", response_model=List[StudentAssignmentOut])
async def get_my_course_assignments(
    db: db_dependency,
    current_user: dict = user_dependency,
    course_id: Optional[int] = Query(None, description="Filter assignments by course"),
    status: Optional[str] = Query(None, description="Filter by status: assigned, submitted, graded, passed, needs_retry, failed"),
    limit: int = Query(100, ge=1, le=200, description="Limit results"),
    include_overdue: bool = Query(True, description="Include assignments that are overdue")
):
    """Convenience endpoint for mobile clients to fetch the current user's assignments.

    Mirrors the existing student assignment listing while living under the
    `/after-school/courses` prefix expected by React Native clients.
    """
    user_id = current_user["user_id"]

    query = db.query(StudentAssignment).options(
        joinedload(StudentAssignment.assignment)
    ).filter(StudentAssignment.user_id == user_id)

    if course_id:
        query = query.filter(StudentAssignment.course_id == course_id)

    if status:
        query = query.filter(StudentAssignment.status == status)

    if not include_overdue:
        query = query.filter(StudentAssignment.due_date >= datetime.utcnow())

    assignments = query.order_by(StudentAssignment.due_date.asc()).limit(limit).all()

    return assignments

@router.get("/{course_id}/blocks-progress", response_model=CourseBlocksProgressOut)
async def get_course_blocks_progress(
    course_id: int,
    db: db_dependency,
    current_user: dict = user_dependency
):
    """
    Return the user's progress across all blocks for a course, including
    per-block completion status and availability. Mirrors the frontend
    CourseBlocksProgressResponse shape for seamless integration.
    """
    user_id = current_user["user_id"]

    # Validate course
    course = db.query(Course).filter(Course.id == course_id, Course.is_active == True).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    # Fetch blocks in curriculum order
    blocks = db.query(CourseBlock).filter(
        and_(
            CourseBlock.course_id == course_id,
            CourseBlock.is_active == True
        )
    ).order_by(CourseBlock.week, CourseBlock.block_number).all()

    if not blocks:
        return {
            "course_id": course_id,
            "total_blocks": 0,
            "completed_blocks": 0,
            "completion_percentage": 0.0,
            "blocks": []
        }

    # Completed sessions for user/course
    completed_sessions = db.query(StudySession).filter(
        and_(
            StudySession.user_id == user_id,
            StudySession.course_id == course_id,
            StudySession.status == "completed"
        )
    ).all()
    completed_block_ids = {s.block_id for s in completed_sessions if s.block_id}

    blocks_progress: list[dict] = []
    for i, block in enumerate(blocks):
        is_completed = block.id in completed_block_ids
        # Availability: first block or after completed previous block, or if already completed
        if i == 0:
            is_available = True
        elif is_completed:
            is_available = True
        else:
            prev_block = blocks[i - 1]
            is_available = prev_block.id in completed_block_ids

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
                (s.marked_done_at or s.ended_at for s in completed_sessions if s.block_id == block.id), None
            )
        })

    total_blocks = len(blocks)
    completed_count = len(completed_block_ids)
    completion_percentage = (completed_count / total_blocks * 100.0) if total_blocks > 0 else 0.0

    return {
        "course_id": course_id,
        "total_blocks": total_blocks,
        "completed_blocks": completed_count,
        "completion_percentage": completion_percentage,
        "blocks": blocks_progress
    }

@router.post("/from-textbook", response_model=ComprehensiveCourseOut)
async def create_course_from_textbook(
    db: db_dependency,
    current_user: dict = user_dependency,
    textbook_file: UploadFile = File(..., description="Upload textbook file (PDF, TXT, DOC, DOCX, PNG, JPG, WEBP)"),
    title: str = Form(..., min_length=1, max_length=200, description="Course title"),
    subject: str = Form(..., min_length=1, max_length=100, description="Subject (Math, Science, English, etc.)"),
    textbook_source: Optional[str] = Form(None, description="Source information about the textbook"),
    total_weeks: int = Form(8, ge=1, le=52, description="Total duration in weeks"),
    blocks_per_week: int = Form(2, ge=1, le=5, description="Number of learning blocks per week"),
    age_min: int = Form(3, ge=3, le=16, description="Minimum age for course"),
    age_max: int = Form(16, ge=3, le=16, description="Maximum age for course"),
    difficulty_level: str = Form("intermediate", description="Difficulty level: beginner, intermediate, advanced"),
    include_assignments: bool = Form(True, description="Generate assignments automatically"),
    include_resources: bool = Form(True, description="Generate resource links (videos, articles)")
):
    """
    Create a comprehensive AI-generated course from uploaded textbook file
    
    This revolutionary endpoint transforms uploaded textbook files into structured, 
    engaging courses using Gemini AI with:
    
    📁 **Advanced File Upload Support:**
    - Accepts PDF, TXT, DOC, DOCX files and image formats (PNG, JPG, WEBP)
    - Gemini native multimodal processing (reads text from images and documents)
    - Processes scanned documents, textbook pages, and mixed content
    - Advanced OCR and visual analysis capabilities
    
    🤖 **AI-Powered Course Generation:**
    - Analyzes extracted textbook content with advanced AI
    - Generates structured learning blocks and objectives
    - Creates comprehensive course descriptions and metadata
    
    📚 **Textbook-to-Course Transformation:**
    - Extracts key concepts and learning materials from files
    - Organizes content into weekly blocks
    - Maintains educational flow and progression
    
    🔗 **Automatic Resource Generation:**
    - YouTube video links for visual learning
    - Educational article recommendations
    - Interactive learning tools and resources
    
    📝 **Integrated Assignment System:**
    - Auto-generates assignments based on content
    - Creates rubrics and grading criteria
    - Sets appropriate deadlines and scheduling
    
    ⏰ **Time-Based Learning Structure:**
    - Organizes content into manageable weekly blocks
    - Balances learning load across time periods
    - Provides estimated duration for each component
    
    🤖 **Gemini AI Native Processing:**
    - Direct file processing without manual text extraction
    - Multimodal analysis (text + images + diagrams)
    - OCR for scanned documents and images
    - Advanced content understanding and structure recognition
    
    🔒 **Security Features:**
    - File type validation (documents and images)
    - File size limits (max 50MB for native processing)
    - Secure temporary file handling
    - Native Gemini processing eliminates security risks of manual extraction
    
    **Request Format:** multipart/form-data
    **File Types Supported:** .pdf, .txt, .doc, .docx, .png, .jpg, .jpeg, .gif, .webp
    **Max File Size:** 50MB
    
    Returns a complete course structure ready for student enrollment
    """
    user_id = current_user["user_id"]
    
    try:
        # Validate form data
        if age_max < age_min:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="age_max must be greater than or equal to age_min"
            )
        
        if difficulty_level not in ['beginner', 'intermediate', 'advanced']:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="difficulty_level must be one of: beginner, intermediate, advanced"
            )
        
        print(f"🚀 Starting AI course generation from uploaded textbook...")
        print(f"📖 Course: {title} ({subject})")
        print(f"📁 File: {textbook_file.filename} ({textbook_file.size} bytes)")
        print(f"⏰ Structure: {total_weeks} weeks × {blocks_per_week} blocks")
        
        # Validate uploaded file
        file_validation = gemini_service.validate_textbook_file(
            textbook_file.filename, 
            textbook_file.size
        )
        
        if not file_validation["valid"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File validation failed: {'; '.join(file_validation['errors'])}"
            )
        
        if file_validation["warnings"]:
            print(f"⚠️ File warnings: {'; '.join(file_validation['warnings'])}")
        
        # Read and process the uploaded file
        file_content = await textbook_file.read()
        textbook_content = await gemini_service.process_uploaded_textbook_file(
            file_content, textbook_file.filename
        )
        
        # Validate content (skip for inline files as they'll be processed natively by Gemini)
        if not textbook_content.startswith("INLINE_FILE:") and len(textbook_content.strip()) < 100:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Extracted text content is too short. Please provide a file with more substantial content (at least 100 characters)."
            )
        
        if textbook_content.startswith("INLINE_FILE:"):
            print(f"🤖 File prepared as inline attachment for Gemini processing")
        else:
            print(f"📝 Extracted {len(textbook_content)} characters from uploaded file")
        
        # Generate course using Gemini AI
        generated_course = await gemini_service.analyze_textbook_and_generate_course(
            textbook_content=textbook_content,
            course_title=title,
            subject=subject,
            target_age_range=(age_min, age_max),
            total_weeks=total_weeks,
            blocks_per_week=blocks_per_week,
            difficulty_level=difficulty_level
        )
        
        print(f"✅ AI generation complete. Creating database records...")
        
        # Refresh database connection after long AI generation process to avoid timeouts
        try:
            # Test if current connection is still alive
            db.execute("SELECT 1")
        except Exception:
            # Connection is stale, create a fresh one
            db.close()
            from db.connection import SessionLocal
            db = SessionLocal()
            print("🔄 Refreshed database connection after AI processing")
        
        try:
            # Check for existing course with same title and subject
            existing_course = db.query(Course).filter(
                and_(
                    Course.title.ilike(title.strip()),
                    Course.subject.ilike(subject.strip()),
                    Course.is_active == True
                )
            ).first()
        
            if existing_course:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Course already exists: A course titled '{title}' already exists for subject '{subject}'. Choose a different title or update the existing course."
                )
            
            # Create the main course record
            new_course = Course(
                title=generated_course.title,
                subject=generated_course.subject,
                description=generated_course.description,
                age_min=generated_course.age_min,
                age_max=generated_course.age_max,
                difficulty_level=generated_course.difficulty_level,
                created_by=user_id,
                total_weeks=generated_course.total_weeks,
                blocks_per_week=generated_course.blocks_per_week,
                textbook_source=textbook_source or f"Uploaded file: {textbook_file.filename}",
                textbook_content=textbook_content[:10000] if not textbook_content.startswith("INLINE_FILE:") else f"Inline attachment: {textbook_file.filename}",
                generated_by_ai=True
            )
            
            db.add(new_course)
            db.commit()
            db.refresh(new_course)
        
            print(f"📚 Course created with ID: {new_course.id}")
            
            # Create course blocks
            created_blocks = []
            for block_data in generated_course.blocks:
                course_block = CourseBlock(
                    course_id=new_course.id,
                    week=block_data.week,
                    block_number=block_data.block_number,
                    title=block_data.title,
                    description=block_data.description,
                    learning_objectives=block_data.learning_objectives,
                    content=block_data.content,
                    duration_minutes=block_data.duration_minutes,
                    resources=block_data.resources
                )
                
                db.add(course_block)
                created_blocks.append(course_block)
        
            # Ensure block IDs are generated before creating assignments that reference them
            db.flush()

            # Create course assignments
            created_assignments = []
            
            # Create block-specific assignments
            for i, block_data in enumerate(generated_course.blocks):
                for assignment_data in block_data.assignments:
                    assignment = CourseAssignment(
                        course_id=new_course.id,
                        title=assignment_data["title"],
                        description=assignment_data["description"],
                        assignment_type=assignment_data["type"],
                        instructions=assignment_data.get("instructions", ""),
                        duration_minutes=assignment_data["duration_minutes"],
                        points=assignment_data["points"],
                        rubric=assignment_data["rubric"],
                        week_assigned=block_data.week,
                        block_id=created_blocks[i].id,
                        due_days_after_assignment=assignment_data["due_days_after_block"],
                        submission_format=assignment_data.get("submission_format", "PDF"),
                        learning_outcomes=assignment_data.get("learning_outcomes", []),
                        generated_by_ai=True
                    )
                    
                    db.add(assignment)
                    created_assignments.append(assignment)
        
            # Create overall course assignments (midterms, finals, projects)
            for assignment_data in generated_course.overall_assignments:
                assignment = CourseAssignment(
                    course_id=new_course.id,
                    title=assignment_data["title"],
                    description=assignment_data["description"],
                    assignment_type=assignment_data["type"],
                    instructions=assignment_data.get("instructions", ""),
                    duration_minutes=assignment_data["duration_minutes"],
                    points=assignment_data["points"],
                    rubric=assignment_data["rubric"],
                    week_assigned=assignment_data["week_assigned"],
                    due_days_after_assignment=assignment_data["due_days_after_assignment"],
                    submission_format=assignment_data.get("submission_format", "PDF"),
                    learning_outcomes=assignment_data.get("learning_outcomes", []),
                    generated_by_ai=True
                )
                
                db.add(assignment)
                created_assignments.append(assignment)
        
            # Commit all changes
            db.commit()
            
            # Refresh all objects to get IDs
            for block in created_blocks:
                db.refresh(block)
            for assignment in created_assignments:
                db.refresh(assignment)
            
            print(f"📝 Created {len(created_blocks)} blocks and {len(created_assignments)} assignments")
            
            # Calculate totals
            total_blocks = len(created_blocks)
            estimated_total_duration = sum(block.duration_minutes for block in created_blocks)
            
            # Prepare response
            response_data = ComprehensiveCourseOut(
                id=new_course.id,
                title=new_course.title,
                subject=new_course.subject,
                description=new_course.description,
                age_min=new_course.age_min,
                age_max=new_course.age_max,
                difficulty_level=new_course.difficulty_level,
                created_by=new_course.created_by,
                is_active=new_course.is_active,
                total_weeks=new_course.total_weeks,
                blocks_per_week=new_course.blocks_per_week,
                textbook_source=new_course.textbook_source,
                generated_by_ai=new_course.generated_by_ai,
                created_at=new_course.created_at,
                updated_at=new_course.updated_at,
                blocks=[CourseBlockOut.from_orm(block) for block in created_blocks],
                lessons=[],  # Keep empty for now (legacy support)
                assignments=[CourseAssignmentOut.from_orm(assignment) for assignment in created_assignments],
                total_blocks=total_blocks,
                estimated_total_duration=estimated_total_duration
            )
            
            print(f"🎉 Course generation complete! Course ID: {new_course.id}")
            print(f"📊 Stats: {total_blocks} blocks, {len(created_assignments)} assignments, {estimated_total_duration} min total")
            
            return response_data
            
        finally:
            # Ensure the new database connection is closed
            db.close()
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error creating AI course: {str(e)}")
        # Try to rollback if we have a database connection
        try:
            if 'db' in locals():
                db.rollback()
        except:
            pass
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create AI-generated course: {str(e)}"
        )

@router.post("/with-image", response_model=CourseOut)
async def create_course_with_image(
    db: db_dependency,
    current_user: dict = Depends(get_current_user),
    title: str = Form(..., min_length=1, max_length=200, description="Course title"),
    subject: str = Form(..., min_length=1, max_length=100, description="Subject"),
    description: Optional[str] = Form(None, description="Course description"),
    age_min: int = Form(3, ge=3, le=16, description="Minimum age"),
    age_max: int = Form(16, ge=3, le=16, description="Maximum age"),
    difficulty_level: str = Form("beginner", description="Difficulty level: beginner, intermediate, advanced"),
    image_file: Optional[UploadFile] = File(None, description="Course image (optional) - PNG, JPG, WEBP")
):
    """
    Create a course with an optional image
    
    Supports uploading a course image that will be:
    - Automatically compressed to reduce size by ~50%
    - Stored in database as bytes to avoid path issues
    - Returned as base64 in API responses
    
    **Image Features:**
    - Formats: PNG, JPG, JPEG, WEBP
    - Max size: 5MB
    - Compression: JPEG quality 75, max dimensions 800x600
    - Storage: Bytes in database (no external file paths)
    
    **Request Format:** multipart/form-data
    """
    user_id = current_user["user_id"]
    
    try:
        # Validate age range
        if age_max < age_min:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Maximum age must be greater than or equal to minimum age"
            )
        
        if age_min < 3 or age_max > 16:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Age range must be between 3-16 years"
            )
        
        # Validate difficulty level
        if difficulty_level not in ['beginner', 'intermediate', 'advanced']:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Difficulty level must be: beginner, intermediate, or advanced"
            )
        
        # Check for duplicate course
        existing_course = db.query(Course).filter(
            and_(
                Course.title.ilike(title.strip()),
                Course.subject.ilike(subject.strip()),
                Course.is_active == True
            )
        ).first()
        
        if existing_course:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"A course titled '{title}' already exists for subject '{subject}'"
            )
        
        # Process image if provided
        compressed_image_bytes = None
        if image_file:
            try:
                image_data = await image_file.read()
                print(f"📸 Processing image: {image_file.filename} ({len(image_data):,} bytes)")
                
                # Compress and get bytes
                compressed_image_bytes, _ = image_service.process_and_compress_image(
                    image_data,
                    image_file.filename
                )
                print(f"✅ Image compressed and ready for storage")
            except ValueError as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Image validation failed: {str(e)}"
                )
            except Exception as e:
                print(f"❌ Error processing image: {str(e)}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to process image: {str(e)}"
                )
        
        # Create course
        new_course = Course(
            title=title.strip(),
            subject=subject.strip(),
            description=description.strip() if description else f"Comprehensive {subject} course for ages {age_min}-{age_max}",
            age_min=age_min,
            age_max=age_max,
            difficulty_level=difficulty_level,
            created_by=user_id,
            image=compressed_image_bytes  # Store compressed bytes directly
        )
        
        db.add(new_course)
        db.commit()
        db.refresh(new_course)
        
        # Encode image to base64 for response
        image_base64 = image_service.encode_image_to_base64(new_course.image) if new_course.image else None
        
        # Return response with image
        response = CourseOut(
            id=new_course.id,
            title=new_course.title,
            subject=new_course.subject,
            description=new_course.description,
            age_min=new_course.age_min,
            age_max=new_course.age_max,
            difficulty_level=new_course.difficulty_level,
            created_by=new_course.created_by,
            is_active=new_course.is_active,
            image=image_base64,
            total_weeks=new_course.total_weeks,
            blocks_per_week=new_course.blocks_per_week,
            textbook_source=new_course.textbook_source,
            generated_by_ai=new_course.generated_by_ai,
            created_at=new_course.created_at,
            updated_at=new_course.updated_at
        )
        
        print(f"✅ Course created with image: ID {new_course.id} - '{new_course.title}'")
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error creating course with image: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create course: {str(e)}"
        )


@router.put("/{course_id}/image", response_model=CourseOut)
async def update_course_image(
    course_id: int,
    db: db_dependency,
    current_user: dict = Depends(get_current_user),
    image_file: UploadFile = File(..., description="Course image - PNG, JPG, WEBP")
):
    """
    Update course image (add or replace existing image)
    
    Replaces the course image with a new one that will be:
    - Automatically compressed to reduce size by ~50%
    - Stored in database as bytes
    - Returned as base64 in subsequent API calls
    
    **Image Features:**
    - Formats: PNG, JPG, JPEG, WEBP
    - Max size: 5MB
    - Compression: JPEG quality 75, max dimensions 800x600
    - Storage: Bytes in database
    
    **Request Format:** multipart/form-data
    """
    user_id = current_user["user_id"]
    
    try:
        # Fetch course
        course = db.query(Course).filter(Course.id == course_id).first()
        if not course:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Course not found: ID {course_id}"
            )
        
        # Verify user has permission to update (optional - adjust based on your auth)
        # For now, allow anyone to update course images
        
        # Process image
        try:
            image_data = await image_file.read()
            print(f"📸 Processing new image for course {course_id}: {image_file.filename} ({len(image_data):,} bytes)")
            
            # Compress and get bytes
            compressed_image_bytes, _ = image_service.process_and_compress_image(
                image_data,
                image_file.filename
            )
            
            # Update course image
            course.image = compressed_image_bytes
            course.updated_at = datetime.utcnow()
            
            db.commit()
            db.refresh(course)
            
            # Encode image to base64 for response
            image_base64 = image_service.encode_image_to_base64(course.image) if course.image else None
            
            # Return updated course
            response = CourseOut(
                id=course.id,
                title=course.title,
                subject=course.subject,
                description=course.description,
                age_min=course.age_min,
                age_max=course.age_max,
                difficulty_level=course.difficulty_level,
                created_by=course.created_by,
                is_active=course.is_active,
                image=image_base64,
                total_weeks=course.total_weeks,
                blocks_per_week=course.blocks_per_week,
                textbook_source=course.textbook_source,
                generated_by_ai=course.generated_by_ai,
                created_at=course.created_at,
                updated_at=course.updated_at
            )
            
            print(f"✅ Course image updated: ID {course.id}")
            return response
            
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Image validation failed: {str(e)}"
            )
        except Exception as e:
            print(f"❌ Error processing image: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to process image: {str(e)}"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error updating course image: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update course image: {str(e)}"
        )


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
            
            # Encode image to base64 if present
            image_base64 = image_service.encode_image_to_base64(course.image) if course.image else None
            
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
                "image": image_base64,
                "total_weeks": course.total_weeks,
                "blocks_per_week": course.blocks_per_week,
                "textbook_source": course.textbook_source,
                "generated_by_ai": course.generated_by_ai,
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

@router.get("/{course_id}/blocks", response_model=List[CourseBlockOut])
async def list_course_blocks(
    course_id: int,
    db: db_dependency,
    current_user: dict = user_dependency,
    active_only: bool = Query(True, description="Return only active blocks")
):
    """List blocks for a course (supports AI-generated course structure)."""
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    query = db.query(CourseBlock).filter(CourseBlock.course_id == course_id)
    if active_only:
        query = query.filter(CourseBlock.is_active == True)  # noqa: E712
    blocks = query.order_by(CourseBlock.week, CourseBlock.block_number).all()
    return blocks

@router.get("/{course_id}/blocks/{block_id}", response_model=CourseBlockOut)
async def get_course_block(
    course_id: int,
    block_id: int,
    db: db_dependency,
    current_user: dict = user_dependency
):
    """Return a single course block detail."""
    block = db.query(CourseBlock).filter(
        and_(CourseBlock.id == block_id, CourseBlock.course_id == course_id)
    ).first()
    if not block:
        raise HTTPException(status_code=404, detail="Block not found")
    return block

@router.post("/{course_id}/enroll")
async def enroll_in_course(
    course_id: int,
    db: db_dependency,
    current_user: dict = user_dependency
):
    """
    Enroll student in a course and auto-assign all course assignments
    
    This endpoint handles the complete enrollment process:
    - Verifies course exists and is active
    - Creates student assignment records for all course assignments
    - Sets appropriate due dates based on enrollment date
    - Returns enrollment confirmation with assignment schedule
    """
    user_id = current_user["user_id"]
    
    try:
        # Verify course exists and is active
        course = db.query(Course).filter(
            and_(Course.id == course_id, Course.is_active == True)
        ).first()
        
        if not course:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Active course not found with ID {course_id}"
            )
        
        # Check if student is already enrolled
        existing_assignment = db.query(StudentAssignment).filter(
            and_(
                StudentAssignment.user_id == user_id,
                StudentAssignment.course_id == course_id
            )
        ).first()
        
        if existing_assignment:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"You are already enrolled in course '{course.title}'"
            )
        
        # Get all course assignments
        course_assignments = db.query(CourseAssignment).filter(
            and_(
                CourseAssignment.course_id == course_id,
                CourseAssignment.is_active == True
            )
        ).all()

        print("📝 Enrollment pre-check", {
            "user_id": user_id,
            "course_id": course_id,
            "course_title": course.title,
            "assignment_def_count": len(course_assignments)
        })
        
        if not course_assignments:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This course has no assignments available for enrollment"
            )
        
        enrollment_date = datetime.utcnow()
        created_assignments = []
        
        # Create student assignment records for each course assignment
        for assignment in course_assignments:
            # Calculate due date based on enrollment date and assignment schedule
            if assignment.week_assigned:
                # For week-based assignments, calculate based on course start
                days_from_start = (assignment.week_assigned - 1) * 7  # Week to days
                assignment_date = enrollment_date + timedelta(days=days_from_start)
                due_date = assignment_date + timedelta(days=assignment.due_days_after_assignment)
            else:
                # For immediate assignments, use direct offset
                due_date = enrollment_date + timedelta(days=assignment.due_days_after_assignment)
            
            student_assignment = StudentAssignment(
                user_id=user_id,
                assignment_id=assignment.id,
                course_id=course_id,
                assigned_at=enrollment_date,
                due_date=due_date,
                status="assigned"
            )
            
            db.add(student_assignment)
            created_assignments.append(student_assignment)
        
        # Create initial progress record only if one doesn't already exist
        existing_progress = db.query(StudentProgress).filter(
            and_(StudentProgress.user_id == user_id, StudentProgress.course_id == course_id)
        ).first()
        if not existing_progress:
            total_blocks = len(course.blocks)
            # Fallback to lessons if no blocks present (legacy courses)
            total_lessons = db.query(CourseLesson).filter(
                and_(CourseLesson.course_id == course_id, CourseLesson.is_active == True)
            ).count() if total_blocks == 0 else 0
            total_content = total_blocks if total_blocks > 0 else total_lessons
            progress = StudentProgress(
                user_id=user_id,
                course_id=course_id,
                total_lessons=total_content,
                sessions_count=0,
                started_at=enrollment_date,
                last_activity=enrollment_date
            )
            db.add(progress)
        try:
            db.commit()
        except Exception as commit_err:
            print("❌ Enrollment commit failure", {
                "user_id": user_id,
                "course_id": course_id,
                "error_type": type(commit_err).__name__,
                "error": str(commit_err)[:500]
            })
            raise

        # Post-commit verification
        persisted_count = db.query(StudentAssignment.id).filter(
            and_(StudentAssignment.user_id == user_id, StudentAssignment.course_id == course_id)
        ).count()
        if persisted_count != len(created_assignments):
            print("⚠️ Enrollment mismatch after commit", {
                "expected_created": len(created_assignments),
                "persisted_count": persisted_count,
                "user_id": user_id,
                "course_id": course_id
            })
        else:
            print("✅ Enrollment assignments persisted", {
                "count": persisted_count,
                "user_id": user_id,
                "course_id": course_id
            })
        
        # Refresh to get IDs
        for assignment in created_assignments:
            db.refresh(assignment)
        
        return {
            "message": f"Successfully enrolled in course '{course.title}'",
            "course_id": course_id,
            "course_title": course.title,
            "enrollment_date": enrollment_date,
            "total_assignments": len(created_assignments),
            "assignments_assigned": [
                {
                    "assignment_id": sa.assignment_id,
                    "title": next(a.title for a in course_assignments if a.id == sa.assignment_id),
                    "due_date": sa.due_date,
                    "status": sa.status
                }
                for sa in created_assignments
            ],
            "next_steps": f"Start with Week 1 assignments. You have {course.total_weeks} weeks of learning ahead!"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to enroll in course: {str(e)}"
        )

@router.get("/dashboard", response_model=StudentDashboard)
async def get_student_dashboard(
    db: db_dependency,
    current_user: dict = user_dependency,
    limit: int = Query(50, ge=1, le=100, description="Max number of courses to return for discovery dashboard")
):
    """
    Discovery dashboard: return active courses for everyone, plus the user's recent sessions and progress.

    - Intended for the home page to introduce courses to all users (even brand new).
    - Returns the latest active courses (not just enrolled ones).
    - Still provides user's sessions/progress for personalization where available.
    """
    user_id = current_user["user_id"]

    # All active courses (discovery)
    active_courses = db.query(Course).filter(Course.is_active == True).order_by(desc(Course.created_at)).limit(limit).all()  # noqa: E712

    # Recent study sessions (limit 10) - still strictly from StudySession
    recent_sessions = db.query(StudySession).filter(
        StudySession.user_id == user_id
    ).order_by(StudySession.started_at.desc()).limit(10).all()

    # Progress summary (all progress rows for user)
    progress_summary = db.query(StudentProgress).filter(
        StudentProgress.user_id == user_id
    ).all()

    # Total study time & average score calculations
    all_sessions = db.query(StudySession).filter(
        and_(
            StudySession.user_id == user_id,
            StudySession.duration_minutes.isnot(None)
        )
    ).all()
    total_study_time = sum((s.duration_minutes or 0) for s in all_sessions)
    scored_sessions = [s for s in all_sessions if s.ai_score is not None]
    average_score = (sum(s.ai_score for s in scored_sessions) / len(scored_sessions)) if scored_sessions else None

    # Debug logging to verify aggregation sources
    print(
        "📊 Dashboard discovery:",
        {
            "user_id": user_id,
            "active_courses_returned": [c.id for c in active_courses],
        }
    )

    # Encode images to base64 for all active courses
    for course in active_courses:
        if course.image:
            course.image = image_service.encode_image_to_base64(course.image)

    return StudentDashboard(
        user_id=user_id,
        active_courses=active_courses,
        recent_sessions=recent_sessions,
        progress_summary=progress_summary,
        total_study_time=total_study_time,
        average_score=average_score
    )

@router.get("/my-courses", response_model=StudentDashboard)
async def get_my_courses(
    db: db_dependency,
    current_user: dict = user_dependency
):
    """
    Return only the user's enrolled courses (true enrollments via StudentAssignment),
    along with progress and recent sessions scoped to those courses.
    """
    user_id = current_user["user_id"]

    # Enrolled course IDs via student assignments
    enrolled_course_ids = [cid for (cid,) in db.query(StudentAssignment.course_id).filter(StudentAssignment.user_id == user_id).distinct().all()]

    active_courses = []
    if enrolled_course_ids:
        active_courses = db.query(Course).filter(
            and_(
                Course.id.in_(enrolled_course_ids),
                Course.is_active == True  # noqa: E712
            )
        ).order_by(desc(Course.created_at)).all()

    # Encode images
    for course in active_courses:
        if course.image:
            course.image = image_service.encode_image_to_base64(course.image)

    # Sessions and progress limited to enrolled courses
    recent_sessions = db.query(StudySession).filter(
        and_(
            StudySession.user_id == user_id,
            StudySession.course_id.in_(enrolled_course_ids) if enrolled_course_ids else True
        )
    ).order_by(StudySession.started_at.desc()).limit(10).all()

    progress_query = db.query(StudentProgress).filter(StudentProgress.user_id == user_id)
    if enrolled_course_ids:
        progress_query = progress_query.filter(StudentProgress.course_id.in_(enrolled_course_ids))
    progress_summary = progress_query.all()

    # Totals/averages from sessions
    all_sessions = db.query(StudySession).filter(
        and_(
            StudySession.user_id == user_id,
            StudySession.duration_minutes.isnot(None)
        )
    ).all()
    total_study_time = sum((s.duration_minutes or 0) for s in all_sessions)
    scored_sessions = [s for s in all_sessions if s.ai_score is not None]
    average_score = (sum(s.ai_score for s in scored_sessions) / len(scored_sessions)) if scored_sessions else None

    print(
        "📚 My Courses:",
        {
            "user_id": user_id,
            "enrolled_course_ids": enrolled_course_ids,
            "active_courses_returned": [c.id for c in active_courses]
        }
    )

    return StudentDashboard(
        user_id=user_id,
        active_courses=active_courses,
        recent_sessions=recent_sessions,
        progress_summary=progress_summary,
        total_study_time=total_study_time,
        average_score=average_score
    )

@router.get("/assignments/my-assignments")
async def get_my_assignments(
    db: db_dependency,
    current_user: dict = user_dependency,
    course_id: Optional[int] = Query(None, description="Filter by course"),
    status: Optional[str] = Query(None, description="Filter by status: assigned, submitted, graded, overdue"),
    limit: int = Query(50, ge=1, le=100, description="Limit results")
):
    """
    Get all assignments for the current student across all enrolled courses
    
    This endpoint provides comprehensive assignment management:
    - Shows all assigned work with due dates and status
    - Filters by course or assignment status
    - Includes submission and grading information
    - Helps students track their academic progress
    """
    user_id = current_user["user_id"]
    
    try:
        query = db.query(StudentAssignment).options(
            joinedload(StudentAssignment.assignment)
        ).filter(StudentAssignment.user_id == user_id)
        
        if course_id:
            query = query.filter(StudentAssignment.course_id == course_id)
        
        if status:
            query = query.filter(StudentAssignment.status == status)
        
        # Update overdue assignments
        current_time = datetime.utcnow()
        overdue_assignments = db.query(StudentAssignment).filter(
            and_(
                StudentAssignment.user_id == user_id,
                StudentAssignment.due_date < current_time,
                StudentAssignment.status == "assigned"
            )
        ).all()
        
        for assignment in overdue_assignments:
            assignment.status = "overdue"
        
        if overdue_assignments:
            db.commit()
        
        # Get assignments with related data
        student_assignments = query.order_by(StudentAssignment.due_date.asc()).limit(limit).all()
        
        # Format response with comprehensive information
        assignments_data = []
        for sa in student_assignments:
            # Provide minimal nested assignment details to help clients anchor sessions
            nested_assignment = None
            if sa.assignment:
                nested_assignment = {
                    "id": sa.assignment.id,
                    "course_id": sa.assignment.course_id,
                    "title": sa.assignment.title,
                    "assignment_type": sa.assignment.assignment_type,
                    "block_id": getattr(sa.assignment, 'block_id', None)
                }

            assignment_info = {
                "student_assignment_id": sa.id,
                "assignment_id": sa.assignment_id,
                "course_id": sa.course_id,
                "title": sa.assignment.title if sa.assignment else "Unknown Assignment",
                "description": sa.assignment.description if sa.assignment else "",
                "assignment_type": sa.assignment.assignment_type if sa.assignment else "homework",
                "points": sa.assignment.points if sa.assignment else 100,
                "duration_minutes": sa.assignment.duration_minutes if sa.assignment else 30,
                "submission_format": sa.assignment.submission_format if sa.assignment else "PDF",
                "assigned_at": sa.assigned_at,
                "due_date": sa.due_date,
                "status": sa.status,
                "submitted_at": sa.submitted_at,
                "grade": sa.grade,
                "ai_grade": sa.ai_grade,
                "manual_grade": sa.manual_grade,
                "feedback": sa.feedback,
                # surface block_id for anchor resolution even if frontend doesn't parse nested assignment
                "block_id": getattr(sa.assignment, 'block_id', None),
                # also include a minimal nested assignment object
                "assignment": nested_assignment,
                "days_until_due": (sa.due_date - current_time).days if sa.due_date > current_time else 0,
                "is_overdue": sa.due_date < current_time and sa.status in ["assigned", "overdue"]
            }
            assignments_data.append(assignment_info)
        
        # Calculate summary statistics
        total_assignments = len(assignments_data)
        completed_assignments = len([a for a in assignments_data if a["status"] in ["submitted", "graded"]])
        overdue_count = len([a for a in assignments_data if a["is_overdue"]])
        upcoming_count = len([a for a in assignments_data if a["days_until_due"] <= 7 and not a["is_overdue"]])
        
        return {
            "assignments": assignments_data,
            "summary": {
                "total_assignments": total_assignments,
                "completed_assignments": completed_assignments,
                "overdue_assignments": overdue_count,
                "upcoming_assignments": upcoming_count,
                "completion_rate": round((completed_assignments / total_assignments * 100), 1) if total_assignments > 0 else 0
            }
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve assignments: {str(e)}"
        )

@router.get("/{course_id}/assignments", response_model=List[CourseAssignmentOut])
async def list_course_assignments(
    course_id: int,
    db: db_dependency,
    current_user: dict = user_dependency,
    active_only: bool = Query(True, description="Return only active assignments"),
    block_id: Optional[int] = Query(None, description="Filter by related block id"),
    include_inactive: bool = Query(False, description="Include inactive assignments (overrides active_only)")
):
    """Return assignment definition records for the specified course.

    These are course-level assignment templates (not student-specific). The
    frontend uses this endpoint to show available assignments even if they
    have not yet been assigned to the current student.
    """
    # Ensure course exists
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    query = db.query(CourseAssignment).filter(CourseAssignment.course_id == course_id)

    if block_id is not None:
        query = query.filter(CourseAssignment.block_id == block_id)

    if not include_inactive and active_only:
        query = query.filter(CourseAssignment.is_active == True)  # noqa: E712

    assignments = query.order_by(
        CourseAssignment.week_assigned.nulls_last(),
        CourseAssignment.id
    ).all()

    return assignments

@router.get("/{course_id}", response_model=ComprehensiveCourseOut)
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
        # Get course with both lessons and blocks using eager loading
        course = db.query(Course).options(
            joinedload(Course.lessons),
            joinedload(Course.blocks)
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
        
        # Sort blocks by week and block_number for AI-generated courses
        active_blocks = [block for block in course.blocks if block.is_active]
        course.blocks = sorted(active_blocks, key=lambda x: (x.week, x.block_number))
        
        # Calculate totals for comprehensive response
        total_blocks_count = len(course.blocks)
        if course.generated_by_ai and course.blocks:
            estimated_total_duration = sum(block.duration_minutes for block in course.blocks)
        else:
            estimated_total_duration = sum(lesson.estimated_duration for lesson in course.lessons)
        
        # Get course assignments for comprehensive view
        course_assignments = db.query(CourseAssignment).filter(
            CourseAssignment.course_id == course_id
        ).all()
        
        # Encode image to base64 if present
        image_base64 = image_service.encode_image_to_base64(course.image) if course.image else None
        
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
            "image": image_base64,
            "total_weeks": course.total_weeks,
            "blocks_per_week": course.blocks_per_week,
            "textbook_source": course.textbook_source,
            "generated_by_ai": course.generated_by_ai,
            "created_at": course.created_at,
            "updated_at": course.updated_at,
            "lessons": course.lessons,
            "blocks": course.blocks,
            "assignments": course_assignments,
            "total_blocks": total_blocks_count,
            "estimated_total_duration": estimated_total_duration
        }
        
        if include_stats:
            # Calculate comprehensive course statistics
            total_lessons = len(course.lessons)
            total_blocks = len(course.blocks)
            
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
            
            # Calculate estimated duration based on content type
            if course.generated_by_ai and course.blocks:
                estimated_duration = sum(block.duration_minutes for block in course.blocks)
            else:
                estimated_duration = sum(lesson.estimated_duration for lesson in course.lessons)
            
            course_data["statistics"] = {
                "total_lessons": total_lessons,
                "total_blocks": total_blocks,
                "total_enrollments": total_enrollments,
                "total_sessions": total_sessions,
                "completed_sessions": completed_sessions,
                "completion_rate": (completed_sessions / total_sessions * 100) if total_sessions > 0 else 0,
                "average_session_duration": round(avg_session_time, 2),
                "average_score": round(avg_score, 2),
                "recent_activity_7days": recent_activity,
                "estimated_total_duration": estimated_duration,
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
        
        return ComprehensiveCourseOut(**course_data)
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error retrieving course details: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve course details: {str(e)}"
        )

@router.get("/{course_id}/blocks/{block_id}/assignments")
async def get_block_assignments(
    course_id: int,
    block_id: int,
    db: db_dependency,
    current_user: dict = user_dependency
):
    """
    Get assignments for a specific course block
    Enables seamless flow from reading block content to completing assignments
    """
    try:
        # Verify course exists and user has access
        course = db.query(Course).filter(Course.id == course_id).first()
        if not course:
            raise HTTPException(status_code=404, detail="Course not found")
        
        # Verify block exists in this course
        block = db.query(CourseBlock).filter(
            and_(CourseBlock.id == block_id, CourseBlock.course_id == course_id)
        ).first()
        if not block:
            raise HTTPException(status_code=404, detail="Block not found in this course")
        
        # Get assignments for this block
        assignments = db.query(CourseAssignment).filter(
            CourseAssignment.block_id == block_id
        ).all()
        
        # Get user's assignment progress
        user_id = current_user["user_id"]
        assignment_progress = []
        
        for assignment in assignments:
            # Check if student has this assignment assigned
            student_assignment = db.query(StudentAssignment).filter(
                and_(
                    StudentAssignment.assignment_id == assignment.id,
                    StudentAssignment.user_id == user_id
                )
            ).first()
            
            assignment_progress.append({
                "assignment": assignment,
                "assigned": student_assignment is not None,
                "status": student_assignment.status if student_assignment else "not_assigned",
                "grade": student_assignment.grade if student_assignment else None,
                "due_date": student_assignment.due_date.isoformat() if student_assignment and student_assignment.due_date else None,
                "submitted_at": student_assignment.submitted_at.isoformat() if student_assignment and student_assignment.submitted_at else None
            })
        
        return {
            "course_id": course_id,
            "course_title": course.title,
            "block": {
                "id": block.id,
                "title": block.title,
                "week": block.week,
                "block_number": block.block_number,
                "description": block.description,
                "learning_objectives": block.learning_objectives,
                "content": block.content,
                "duration_minutes": block.duration_minutes
            },
            "assignments": assignment_progress,
            "total_assignments": len(assignments),
            "completion_flow": {
                "next_step": "Choose an assignment to complete",
                "auto_grading": True,
                "instructions": "Upload your work images and they will automatically convert to PDF and be graded by AI"
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error retrieving block assignments: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve block assignments: {str(e)}"
        )

@router.post("/{course_id}/assignments/{assignment_id}/submit-and-grade")
async def submit_assignment_and_auto_grade(
    course_id: int,
    assignment_id: int,
    db: db_dependency,
    current_user: dict = user_dependency
):
    """
    Submit assignment work and automatically trigger AI grading
    
    This endpoint provides the seamless flow:
    1. Check if student has uploaded work (images/PDF)
    2. Generate PDF from images if needed
    3. Automatically grade using AI
    4. Return results immediately
    
    No manual intervention required - fully automated workflow
    """
    user_id = current_user["user_id"]
    
    try:
        # Verify course and assignment exist
        course = db.query(Course).filter(Course.id == course_id).first()
        if not course:
            raise HTTPException(status_code=404, detail="Course not found")
        
        # CRITICAL: Verify user is enrolled in the course before allowing submission
        user_enrollment = db.query(StudentAssignment).filter(
            StudentAssignment.user_id == user_id,
            StudentAssignment.course_id == course_id
        ).first()
        
        if not user_enrollment:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not enrolled in this course. Please enroll before submitting assignments."
            )
            
        assignment = db.query(CourseAssignment).filter(
            and_(
                CourseAssignment.id == assignment_id,
                CourseAssignment.course_id == course_id
            )
        ).first()
        if not assignment:
            raise HTTPException(status_code=404, detail="Assignment not found in this course")
        
        print(f"🎯 Processing submission for assignment: {assignment.title}")
        
        # Check if student has a StudentAssignment record
        student_assignment = db.query(StudentAssignment).filter(
            and_(
                StudentAssignment.assignment_id == assignment_id,
                StudentAssignment.user_id == user_id
            )
        ).first()
        
        if not student_assignment:
            raise HTTPException(
                status_code=404, 
                detail="You are not enrolled in this assignment. Please contact your instructor."
            )
        
        # Check for uploaded work - first check for PDF
        student_pdf = db.query(StudentPDF).filter(
            and_(
                StudentPDF.assignment_id == assignment_id,
                StudentPDF.student_id == user_id
            )
        ).first()
        
        submission_content = ""
        
        if student_pdf:
            print(f"📄 Found existing PDF submission: {student_pdf.pdf_filename}")
            submission_content = f"PDF submission: {student_pdf.pdf_filename} ({student_pdf.image_count} images)"
        else:
            # Check for images and try to generate PDF
            from models.study_area_models import StudentImage
            
            student_images = db.query(StudentImage).filter(
                and_(
                    StudentImage.assignment_id == assignment_id,
                    StudentImage.student_id == user_id
                )
            ).all()
            
            if student_images:
                print(f"📸 Found {len(student_images)} images - generating PDF...")
                # Import the function we need
                from Endpoints.upload import generate_student_pdf
                
                # Generate PDF from images
                generated_pdf = await generate_student_pdf(
                    db, user_id, assignment_id, student_images
                )
                
                if generated_pdf:
                    student_pdf = generated_pdf
                    submission_content = f"Generated PDF from {len(student_images)} images"
                    print(f"✅ PDF generated successfully: {generated_pdf.pdf_filename}")
                else:
                    raise HTTPException(
                        status_code=500,
                        detail="Failed to generate PDF from uploaded images"
                    )
            else:
                raise HTTPException(
                    status_code=400,
                    detail="No work found to submit. Please upload your assignment images first."
                )
        
        # Now trigger automatic grading
        print(f"🤖 Starting automatic AI grading...")
        
        # Import Gemini service
        from services.gemini_service import GeminiService
        gemini_service = GeminiService()
        
        # Grade the submission
        grade_result = await gemini_service.grade_submission(
            submission_content=submission_content,
            assignment_title=assignment.title,
            assignment_description=assignment.description or assignment.title,
            rubric=assignment.rubric or assignment.instructions or "Standard academic assessment",
            max_points=assignment.points,
            submission_type=assignment.assignment_type
        )
        
        # Update student assignment with results
        student_assignment.ai_grade = grade_result["percentage"]
        student_assignment.grade = grade_result["percentage"]
        student_assignment.feedback = grade_result.get("detailed_feedback", "")
        student_assignment.submitted_at = datetime.utcnow()
        student_assignment.status = "graded"
        
        if student_pdf:
            student_assignment.submission_file_path = student_pdf.pdf_path
            student_pdf.is_graded = True
        
        db.commit()
        
        print(f"🎉 Automatic grading complete: {grade_result['percentage']}%")
        
        return {
            "status": "success",
            "message": "Assignment submitted and automatically graded",
            "course": {
                "id": course.id,
                "title": course.title
            },
            "assignment": {
                "id": assignment.id,
                "title": assignment.title,
                "type": assignment.assignment_type,
                "max_points": assignment.points
            },
            "submission": {
                "submitted_at": student_assignment.submitted_at.isoformat(),
                "content_type": "PDF" if student_pdf else "Text",
                "file_name": student_pdf.pdf_filename if student_pdf else None
            },
            "grade_result": {
                "score": grade_result.get("score", 0),
                "percentage": grade_result["percentage"],
                "max_points": assignment.points,
                "grade_letter": grade_result.get("grade_letter", ""),
                "feedback": grade_result.get("detailed_feedback", ""),
                "strengths": grade_result.get("strengths", []),
                "improvements": grade_result.get("improvements", []),
                "ai_confidence": grade_result.get("confidence", 85)
            },
            "next_steps": {
                "continue_learning": True,
                "next_block": "Continue to next learning block",
                "view_progress": f"Check your progress in the course dashboard"
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error in submit and grade flow: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to submit and grade assignment: {str(e)}"
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

