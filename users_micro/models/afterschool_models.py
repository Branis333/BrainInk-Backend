from datetime import datetime
from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    DateTime,
    Boolean,
    ForeignKey,
    Float,
    UniqueConstraint,
    CheckConstraint,
    JSON,
    LargeBinary,
)
from sqlalchemy.orm import relationship
from db.database import Base

class Course(Base):
    __tablename__ = "as_courses"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    subject = Column(String(100), nullable=False)  # e.g., Math, Science, English, Reading
    description = Column(Text, nullable=True)
    age_min = Column(Integer, nullable=False, default=3)
    age_max = Column(Integer, nullable=False, default=16)
    difficulty_level = Column(String(20), nullable=False, default="beginner")  # beginner, intermediate, advanced
    created_by = Column(Integer, nullable=False)  # admin user_id who created the course
    is_active = Column(Boolean, default=True)
    
    # Course image - stored as compressed bytes
    image = Column(LargeBinary, nullable=True)  # Compressed image data
    
    # Enhanced course structure fields
    total_weeks = Column(Integer, nullable=False, default=8)
    blocks_per_week = Column(Integer, nullable=False, default=2)
    textbook_source = Column(Text, nullable=True)  # Source textbook information
    textbook_content = Column(Text, nullable=True)  # Original textbook content
    generated_by_ai = Column(Boolean, default=False)  # Whether course was AI-generated
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    lessons = relationship("CourseLesson", back_populates="course", cascade="all, delete-orphan")
    blocks = relationship("CourseBlock", back_populates="course", cascade="all, delete-orphan")
    study_sessions = relationship("StudySession", back_populates="course")
    ai_submissions = relationship("AISubmission", back_populates="course")
    assignments = relationship("CourseAssignment", back_populates="course", cascade="all, delete-orphan")

    # Ensure unique course title per subject
    __table_args__ = (
        UniqueConstraint('title', 'subject', name='uq_as_course_title_subject'),
    )

class CourseBlock(Base):
    __tablename__ = "as_course_blocks"
    
    id = Column(Integer, primary_key=True, index=True)
    course_id = Column(Integer, ForeignKey("as_courses.id"), nullable=False)
    week = Column(Integer, nullable=False)
    block_number = Column(Integer, nullable=False)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    learning_objectives = Column(JSON, nullable=True)  # Store as JSON array
    content = Column(Text, nullable=True)  # Detailed lesson content from textbook
    duration_minutes = Column(Integer, nullable=False, default=45)
    resources = Column(JSON, nullable=True)  # Store links to articles, videos, etc.
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    course = relationship("Course", back_populates="blocks")
    study_sessions = relationship("StudySession", back_populates="block")
    ai_submissions = relationship("AISubmission", back_populates="block")

    # Ensure unique block per week per course
    __table_args__ = (
        UniqueConstraint('course_id', 'week', 'block_number', name='uq_as_course_block'),
    )

class CourseLesson(Base):
    __tablename__ = "as_course_lessons"
    
    id = Column(Integer, primary_key=True, index=True)
    course_id = Column(Integer, ForeignKey("as_courses.id"), nullable=False)
    title = Column(String(200), nullable=False)
    content = Column(Text, nullable=True)  # Lesson content/instructions
    learning_objectives = Column(Text, nullable=True)  # What students should learn
    order_index = Column(Integer, nullable=False, default=1)
    estimated_duration = Column(Integer, nullable=True, default=30)  # in minutes
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    course = relationship("Course", back_populates="lessons")
    study_sessions = relationship("StudySession", back_populates="lesson")
    ai_submissions = relationship("AISubmission", back_populates="lesson")

class CourseAssignment(Base):
    __tablename__ = "as_course_assignments"
    
    id = Column(Integer, primary_key=True, index=True)
    course_id = Column(Integer, ForeignKey("as_courses.id"), nullable=False)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=False)
    assignment_type = Column(String(50), nullable=False)  # homework, quiz, project, assessment
    instructions = Column(Text, nullable=True)
    duration_minutes = Column(Integer, nullable=False, default=30)
    points = Column(Integer, nullable=False, default=100)
    rubric = Column(Text, nullable=True)  # Grading criteria
    
    # Scheduling
    week_assigned = Column(Integer, nullable=True)  # Which week to assign
    block_id = Column(Integer, ForeignKey("as_course_blocks.id"), nullable=True)  # Related block
    due_days_after_assignment = Column(Integer, nullable=False, default=7)
    
    # Assignment metadata
    submission_format = Column(String(100), nullable=True)  # PDF, document, etc.
    learning_outcomes = Column(JSON, nullable=True)  # What students will demonstrate
    generated_by_ai = Column(Boolean, default=False)
    
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    course = relationship("Course", back_populates="assignments")
    student_assignments = relationship("StudentAssignment", back_populates="assignment", cascade="all, delete-orphan")

class StudySession(Base):
    __tablename__ = "as_study_sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False)  # student user_id
    course_id = Column(Integer, ForeignKey("as_courses.id"), nullable=False)
    lesson_id = Column(Integer, ForeignKey("as_course_lessons.id"), nullable=True)  # Made nullable
    block_id = Column(Integer, ForeignKey("as_course_blocks.id"), nullable=True)  # New: for block-based sessions
    
    # Session tracking
    started_at = Column(DateTime, default=datetime.utcnow)
    ended_at = Column(DateTime, nullable=True)
    duration_minutes = Column(Integer, nullable=True)  # legacy field
    
    # AI Scoring and Feedback
    ai_score = Column(Float, nullable=True)  # 0-100 score from AI
    ai_feedback = Column(Text, nullable=True)  # AI generated feedback
    ai_recommendations = Column(Text, nullable=True)  # AI suggestions for improvement
    
    # Session status simplified for mark-done flow
    status = Column(
        String(20),
        nullable=False,
        default="pending",
        doc="pending, in_progress, completed",
    )
    completion_percentage = Column(Float, nullable=False, default=0.0)
    marked_done_at = Column(DateTime, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    course = relationship("Course", back_populates="study_sessions")
    lesson = relationship("CourseLesson", back_populates="study_sessions")
    block = relationship("CourseBlock", back_populates="study_sessions")
    ai_submissions = relationship("AISubmission", back_populates="session")

class StudentAssignment(Base):
    __tablename__ = "as_student_assignments"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False)  # student user_id
    assignment_id = Column(Integer, ForeignKey("as_course_assignments.id"), nullable=False)
    course_id = Column(Integer, ForeignKey("as_courses.id"), nullable=False)
    
    # Assignment status
    assigned_at = Column(DateTime, default=datetime.utcnow)
    due_date = Column(DateTime, nullable=False)
    submitted_at = Column(DateTime, nullable=True)
    status = Column(String(20), nullable=False, default="assigned")  # assigned, submitted, graded, overdue
    
    # Submission and grading
    submission_file_path = Column(String(500), nullable=True)
    submission_content = Column(Text, nullable=True)
    grade = Column(Float, nullable=True)  # Final grade (0-100)
    ai_grade = Column(Float, nullable=True)  # AI-generated grade
    manual_grade = Column(Float, nullable=True)  # Manual override grade
    feedback = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    assignment = relationship("CourseAssignment", back_populates="student_assignments")

    # Ensure one assignment per student
    __table_args__ = (
        UniqueConstraint('user_id', 'assignment_id', name='uq_as_student_assignment'),
    )

class AISubmission(Base):
    __tablename__ = "as_ai_submissions"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False)  # student user_id
    course_id = Column(Integer, ForeignKey("as_courses.id"), nullable=False)
    lesson_id = Column(Integer, ForeignKey("as_course_lessons.id"), nullable=True)  # Made nullable
    block_id = Column(Integer, ForeignKey("as_course_blocks.id"), nullable=True)  # New: for block submissions
    # Session is now optional for mark-done flows (uploads tied to block/lesson without a session)
    session_id = Column(Integer, ForeignKey("as_study_sessions.id"), nullable=True)
    assignment_id = Column(Integer, ForeignKey("as_course_assignments.id"), nullable=True)  # New: link to assignment
    
    # Submission details
    submission_type = Column(String(50), nullable=False)  # homework, quiz, practice, assessment
    
    # File handling (integrating with existing upload system)
    original_filename = Column(String(255), nullable=True)
    file_path = Column(String(500), nullable=True)  # path to uploaded file
    file_type = Column(String(50), nullable=True)  # pdf, image, text
    
    # AI Processing
    ai_processed = Column(Boolean, default=False)
    ai_score = Column(Float, nullable=True)  # 0-100
    ai_feedback = Column(Text, nullable=True)
    ai_corrections = Column(Text, nullable=True)  # suggested corrections
    ai_strengths = Column(Text, nullable=True)  # what student did well
    ai_improvements = Column(Text, nullable=True)  # areas for improvement
    
    # Manual review (if needed)
    requires_review = Column(Boolean, default=False)
    reviewed_by = Column(Integer, nullable=True)  # admin/teacher user_id
    manual_score = Column(Float, nullable=True)
    manual_feedback = Column(Text, nullable=True)
    
    # Timestamps
    submitted_at = Column(DateTime, default=datetime.utcnow)
    processed_at = Column(DateTime, nullable=True)  # when AI finished processing
    reviewed_at = Column(DateTime, nullable=True)  # when manually reviewed (if applicable)

    # Relationships
    course = relationship("Course", back_populates="ai_submissions")
    lesson = relationship("CourseLesson", back_populates="ai_submissions")
    block = relationship("CourseBlock", back_populates="ai_submissions")
    session = relationship("StudySession", back_populates="ai_submissions")

    # Table arguments to ensure at least one of lesson_id or block_id is provided
    __table_args__ = (
        CheckConstraint('(lesson_id IS NOT NULL) OR (block_id IS NOT NULL)',
                       name='ck_as_ai_submissions_lesson_or_block'),
    )

class StudentProgress(Base):
    __tablename__ = "as_student_progress"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False)  # student user_id
    course_id = Column(Integer, ForeignKey("as_courses.id"), nullable=False)
    
    # Progress tracking
    lessons_completed = Column(Integer, nullable=False, default=0)
    total_lessons = Column(Integer, nullable=False, default=0)
    completion_percentage = Column(Float, nullable=False, default=0.0)
    blocks_completed = Column(Integer, nullable=False, default=0)
    total_blocks = Column(Integer, nullable=False, default=0)
    
    # Performance metrics
    average_score = Column(Float, nullable=True)
    total_study_time = Column(Integer, nullable=False, default=0)  # in minutes
    sessions_count = Column(Integer, nullable=False, default=0)
    
    # Milestones
    started_at = Column(DateTime, default=datetime.utcnow)
    last_activity = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Ensure one progress record per user per course
    __table_args__ = (
        UniqueConstraint('user_id', 'course_id', name='uq_as_student_progress'),
    )


class ProgressDigest(Base):
    """
    Stores AI-digested progress summaries for a student.

    Two scopes supported:
    - weekly: Summary across all courses for a 7-day window (period_start..period_end)
    - course: Cumulative summary for a single course (uses course_id; period covers earliest to latest included feedback)

    We persist digests so students can review past weeks and regenerate course summaries on demand.
    """
    __tablename__ = "as_progress_digests"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    course_id = Column(Integer, ForeignKey("as_courses.id"), nullable=True, index=True)

    # weekly | course
    scope = Column(String(20), nullable=False)

    # Time window for which this digest was generated
    period_start = Column(DateTime, nullable=False)
    period_end = Column(DateTime, nullable=False)

    # AI generated content
    summary = Column(Text, nullable=False)

    # Derived metrics for quick display
    assignments_count = Column(Integer, nullable=False, default=0)
    avg_grade = Column(Float, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Helpful relationship (optional usage)
    course = relationship("Course")

    __table_args__ = (
        # Uniqueness by (user, scope, period_start, course)
        # For weekly digests, course_id will be NULL; DB will allow multiple NULLs, so we also rely on app-level upsert.
        UniqueConstraint('user_id', 'scope', 'period_start', 'course_id', name='uq_as_progress_digest_instance'),
    )


# ===============================
# STUDENT NOTES & AI ANALYSIS
# ===============================

class StudentNote(Base):
    """
    Model for student-uploaded notes with AI analysis using Gemini Vision
    Students upload school notes as images, and Gemini Vision AI directly analyzes them
    
    STANDALONE FEATURE: Notes are independent and NOT tied to courses or assignments
    course_id is optional and only used for organizational purposes
    """
    __tablename__ = "as_student_notes"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False)  # student user_id (no FK constraint)
    course_id = Column(Integer, ForeignKey("as_courses.id"), nullable=True)  # Optional: for organization only
    
    # Note metadata
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    subject = Column(String(100), nullable=True)  # e.g., Math, Science, English
    tags = Column(JSON, nullable=True)  # Array of tags for organization
    
    # File information
    original_filename = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=True)  # Path to uploaded file (primary image)
    file_size = Column(Integer, nullable=True)  # Size in bytes (total for all images)
    file_type = Column(String(50), nullable=False)  # "images" for Gemini Vision workflow
    
    # Raw content (DEPRECATED for Vision workflow - kept for backward compatibility)
    extracted_text = Column(Text, nullable=True)  # Not used with Gemini Vision
    
    # AI Analysis Results (from Gemini Vision)
    ai_processed = Column(Boolean, default=False)
    summary = Column(Text, nullable=True)  # AI-generated summary of notes
    key_points = Column(JSON, nullable=True)  # Array of key points extracted
    main_topics = Column(JSON, nullable=True)  # Array of main topics/concepts
    learning_concepts = Column(JSON, nullable=True)  # Key learning concepts
    questions_generated = Column(JSON, nullable=True)  # AI-generated questions based on notes
    
    # Enhanced learning structure
    # objectives: [{"objective": str, "summary": str, "videos": [{title,url,type,description,thumbnail,channel,search_query}]}]
    objectives = Column(JSON, nullable=True)
    # Flashcards generated per objective: index-aligned list of lists
    # objective_flashcards: [[{"front": str, "back": str}], ...]
    objective_flashcards = Column(JSON, nullable=True)
    # Flashcards generated from entire note summary
    overall_flashcards = Column(JSON, nullable=True)
    # Per-objective quiz progress tracking (stored on quiz grade submissions)
    # objective_progress: [{"objective_index": int, "latest_grade": float, "performance_summary": str, "last_quiz_at": str}]
    objective_progress = Column(JSON, nullable=True)
    
    # Processing status
    processing_status = Column(String(50), default="pending")  # pending, processing, completed, failed
    processing_error = Column(Text, nullable=True)  # Error message if processing failed
    processed_at = Column(DateTime, nullable=True)
    
    # Metadata
    is_public = Column(Boolean, default=False)  # Share with classmates
    is_starred = Column(Boolean, default=False)  # User marked as favorite
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    course = relationship("Course", foreign_keys=[course_id])
    
    __table_args__ = (
        UniqueConstraint('user_id', 'original_filename', 'created_at', name='uq_as_student_note_file'),
    )


class NoteAnalysisLog(Base):
    """
    Log of AI analysis attempts for notes using Gemini Vision
    Tracks processing history, errors, and retries
    """
    __tablename__ = "as_note_analysis_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    note_id = Column(Integer, ForeignKey("as_student_notes.id"), nullable=False)
    user_id = Column(Integer, nullable=False)  # student user_id
    
    # Processing details
    processing_type = Column(String(50), nullable=False)  # vision_analysis, extraction, etc.
    status = Column(String(50), nullable=False)  # pending, processing, completed, failed
    
    # Results
    processing_duration_seconds = Column(Float, nullable=True)
    error_message = Column(Text, nullable=True)
    result_data = Column(JSON, nullable=True)  # Detailed results from Gemini Vision
    
    # Retry tracking
    attempt_number = Column(Integer, default=1)
    max_attempts = Column(Integer, default=3)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    note = relationship("StudentNote", foreign_keys=[note_id])


# ===============================
# NOTIFICATION SYSTEM
# ===============================

class NotificationPreference(Base):
    """
    User notification preferences and opt-in settings
    Controls which notification types each user receives
    """
    __tablename__ = "as_notification_preferences"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, unique=True, index=True)  # student user_id
    
    # Notification type toggles
    due_date_notifications = Column(Boolean, default=True)  # Notifications for upcoming due assignments
    daily_encouragement = Column(Boolean, default=True)  # Daily motivational messages
    completion_notifications = Column(Boolean, default=True)  # Course/block completion congratulations
    
    # Push notification settings
    push_notifications_enabled = Column(Boolean, default=False)  # Master toggle for push notifications
    push_token = Column(String(500), nullable=True)  # FCM token or Expo token for push notifications
    
    # Frequency controls
    due_date_days_before = Column(Integer, default=1)  # Notify X days before due date (default: 1 day)
    daily_encouragement_time = Column(String(5), default="09:00")  # HH:MM format for daily message time
    
    # Opt-out tracking
    opted_out_at = Column(DateTime, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        UniqueConstraint('user_id', name='uq_as_notification_preference_user'),
    )


class Notification(Base):
    """
    Notification records for tracking what was sent to users
    Enables persistence, dismissal, and analytics
    """
    __tablename__ = "as_notifications"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)  # student user_id (recipient)
    
    # Notification content
    type = Column(String(50), nullable=False)  # due_date, daily_encouragement, completion
    title = Column(String(200), nullable=False)  # Notification title
    body = Column(Text, nullable=False)  # Notification message content
    
    # Optional metadata linking to course/assignment
    course_id = Column(Integer, ForeignKey("as_courses.id"), nullable=True)
    assignment_id = Column(Integer, ForeignKey("as_course_assignments.id"), nullable=True)
    block_id = Column(Integer, ForeignKey("as_course_blocks.id"), nullable=True)
    
    # Status tracking
    status = Column(String(50), default="created")  # created, scheduled, sent, failed, dismissed, read
    is_read = Column(Boolean, default=False)
    read_at = Column(DateTime, nullable=True)
    dismissed_at = Column(DateTime, nullable=True)
    
    # Push notification tracking
    push_sent_at = Column(DateTime, nullable=True)
    push_failed_reason = Column(Text, nullable=True)
    
    # Scheduling
    scheduled_for = Column(DateTime, nullable=True)  # When the notification should be sent
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    course = relationship("Course", foreign_keys=[course_id])
    assignment = relationship("CourseAssignment", foreign_keys=[assignment_id])
    block = relationship("CourseBlock", foreign_keys=[block_id])
