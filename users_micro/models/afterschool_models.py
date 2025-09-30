from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey, Float, UniqueConstraint, CheckConstraint, JSON
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
    duration_minutes = Column(Integer, nullable=True)  # calculated when session ends
    
    # AI Scoring and Feedback
    ai_score = Column(Float, nullable=True)  # 0-100 score from AI
    ai_feedback = Column(Text, nullable=True)  # AI generated feedback
    ai_recommendations = Column(Text, nullable=True)  # AI suggestions for improvement
    
    # Session status
    status = Column(String(20), nullable=False, default="in_progress")  # in_progress, completed, abandoned
    completion_percentage = Column(Float, nullable=False, default=0.0)  # 0-100
    
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
    session_id = Column(Integer, ForeignKey("as_study_sessions.id"), nullable=False)
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