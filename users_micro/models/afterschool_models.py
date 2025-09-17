from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey, Float, UniqueConstraint
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
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    lessons = relationship("CourseLesson", back_populates="course", cascade="all, delete-orphan")
    study_sessions = relationship("StudySession", back_populates="course")
    ai_submissions = relationship("AISubmission", back_populates="course")

    # Ensure unique course title per subject
    __table_args__ = (
        UniqueConstraint('title', 'subject', name='uq_as_course_title_subject'),
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

class StudySession(Base):
    __tablename__ = "as_study_sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False)  # student user_id
    course_id = Column(Integer, ForeignKey("as_courses.id"), nullable=False)
    lesson_id = Column(Integer, ForeignKey("as_course_lessons.id"), nullable=False)
    
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
    ai_submissions = relationship("AISubmission", back_populates="session")

class AISubmission(Base):
    __tablename__ = "as_ai_submissions"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False)  # student user_id
    course_id = Column(Integer, ForeignKey("as_courses.id"), nullable=False)
    lesson_id = Column(Integer, ForeignKey("as_course_lessons.id"), nullable=False)
    session_id = Column(Integer, ForeignKey("as_study_sessions.id"), nullable=False)
    
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
    session = relationship("StudySession", back_populates="ai_submissions")

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