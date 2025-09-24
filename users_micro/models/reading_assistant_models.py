from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey, Float, JSON, Enum as SQLEnum
from sqlalchemy.orm import relationship
from db.database import Base
import enum

class ReadingLevel(enum.Enum):
    """Reading levels for kindergarten to primary 3"""
    KINDERGARTEN = "KINDERGARTEN"
    GRADE_1 = "GRADE_1"
    GRADE_2 = "GRADE_2"
    GRADE_3 = "GRADE_3"

class DifficultyLevel(enum.Enum):
    """Difficulty within each grade level - using existing database enum values"""
    ELEMENTARY = "ELEMENTARY"
    MIDDLE_SCHOOL = "MIDDLE_SCHOOL" 
    HIGH_SCHOOL = "HIGH_SCHOOL"
    UNIVERSITY = "UNIVERSITY"
    PROFESSIONAL = "PROFESSIONAL"
    MIXED = "MIXED"

class ReadingContent(Base):
    """Stories and sentences for reading practice"""
    __tablename__ = "reading_content"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    content = Column(Text, nullable=False)  # The text to be read
    content_type = Column(String(20), nullable=False)  # sentence, story, paragraph
    reading_level = Column(SQLEnum(ReadingLevel), nullable=False)
    difficulty_level = Column(SQLEnum(DifficultyLevel), nullable=False, default=DifficultyLevel.ELEMENTARY)
    
    # Educational metadata
    vocabulary_words = Column(JSON, nullable=True)  # Key vocabulary with definitions
    learning_objectives = Column(JSON, nullable=True)  # What students learn
    phonics_focus = Column(JSON, nullable=True)  # Specific sounds/patterns being taught
    
    # Content metrics
    word_count = Column(Integer, nullable=False, default=0)
    estimated_reading_time = Column(Integer, nullable=True)  # in seconds
    complexity_score = Column(Float, nullable=True)  # AI-calculated complexity
    
    # Management
    created_by = Column(Integer, nullable=False)  # User ID who created content
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    reading_sessions = relationship("ReadingSession", back_populates="content")
    reading_attempts = relationship("ReadingAttempt", back_populates="content")

class ReadingSession(Base):
    """A reading practice session for a student"""
    __tablename__ = "reading_sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, nullable=False)  # User ID of the student
    content_id = Column(Integer, ForeignKey("reading_content.id"), nullable=False)
    
    # Session data
    session_type = Column(String(50), default="practice")  # practice, assessment, guided
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    total_duration = Column(Integer, nullable=True)  # seconds
    
    # Performance metrics
    accuracy_score = Column(Float, nullable=True)  # 0-100
    fluency_score = Column(Float, nullable=True)  # words per minute
    pronunciation_score = Column(Float, nullable=True)  # 0-100
    overall_score = Column(Float, nullable=True)  # weighted average
    
    # AI feedback
    strengths = Column(JSON, nullable=True)  # What student did well
    areas_for_improvement = Column(JSON, nullable=True)  # What needs work
    suggested_next_content = Column(JSON, nullable=True)  # Recommendations
    
    # Status
    is_completed = Column(Boolean, default=False)
    needs_teacher_review = Column(Boolean, default=False)
    
    # Relationships
    content = relationship("ReadingContent", back_populates="reading_sessions")
    attempts = relationship("ReadingAttempt", back_populates="session", cascade="all, delete-orphan")
    feedback_entries = relationship("ReadingFeedback", back_populates="session", cascade="all, delete-orphan")

class ReadingAttempt(Base):
    """Individual reading attempts within a session"""
    __tablename__ = "reading_attempts"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("reading_sessions.id"), nullable=False)
    content_id = Column(Integer, ForeignKey("reading_content.id"), nullable=False)
    attempt_number = Column(Integer, nullable=False, default=1)
    
    # Audio data
    audio_file_path = Column(String(500), nullable=True)  # Path to recorded audio
    transcribed_text = Column(Text, nullable=True)  # What AI heard
    
    # Analysis results
    word_accuracy = Column(JSON, nullable=True)  # Word-by-word analysis
    pronunciation_errors = Column(JSON, nullable=True)  # Specific mispronunciations
    reading_speed = Column(Float, nullable=True)  # words per minute
    pauses_analysis = Column(JSON, nullable=True)  # Where student paused/struggled
    
    # Scores
    accuracy_percentage = Column(Float, nullable=True)
    fluency_score = Column(Float, nullable=True)
    pronunciation_score = Column(Float, nullable=True)
    
    # Timing
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    duration = Column(Integer, nullable=True)  # seconds
    
    # Relationships
    session = relationship("ReadingSession", back_populates="attempts")
    content = relationship("ReadingContent", back_populates="reading_attempts")
    word_feedback = relationship("WordFeedback", back_populates="attempt", cascade="all, delete-orphan")

class WordFeedback(Base):
    """Detailed feedback for individual words"""
    __tablename__ = "word_feedback"
    
    id = Column(Integer, primary_key=True, index=True)
    attempt_id = Column(Integer, ForeignKey("reading_attempts.id"), nullable=False)
    
    # Word details
    target_word = Column(String(100), nullable=False)  # Correct word
    spoken_word = Column(String(100), nullable=True)  # What student said
    word_position = Column(Integer, nullable=False)  # Position in text
    
    # Analysis
    is_correct = Column(Boolean, default=False)
    pronunciation_accuracy = Column(Float, nullable=True)  # 0-100
    phonetic_errors = Column(JSON, nullable=True)  # Specific sound issues
    
    # AI suggestions
    pronunciation_tip = Column(Text, nullable=True)
    practice_suggestion = Column(Text, nullable=True)
    similar_words = Column(JSON, nullable=True)  # Words with similar patterns
    
    # Relationships
    attempt = relationship("ReadingAttempt", back_populates="word_feedback")

class ReadingFeedback(Base):
    """AI-generated feedback and suggestions"""
    __tablename__ = "reading_feedback"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("reading_sessions.id"), nullable=False)
    
    # Feedback content
    feedback_type = Column(String(50), nullable=False)  # encouragement, correction, suggestion
    message = Column(Text, nullable=False)
    audio_message_path = Column(String(500), nullable=True)  # TTS audio file
    
    # Targeting
    focus_area = Column(String(100), nullable=True)  # pronunciation, fluency, comprehension
    difficulty_adjustment = Column(String(50), nullable=True)  # easier, same, harder
    
    # Management
    is_delivered = Column(Boolean, default=False)
    delivered_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    session = relationship("ReadingSession", back_populates="feedback_entries")

class ReadingProgress(Base):
    """Track student's overall reading progress"""
    __tablename__ = "reading_progress"
    
    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, nullable=False)  # User ID of the student
    
    # Current level
    current_reading_level = Column(SQLEnum(ReadingLevel), nullable=False)
    current_difficulty = Column(SQLEnum(DifficultyLevel), nullable=False)
    
    # Progress metrics
    total_sessions = Column(Integer, default=0)
    total_reading_time = Column(Integer, default=0)  # seconds
    average_accuracy = Column(Float, nullable=True)
    average_fluency = Column(Float, nullable=True)
    words_read_correctly = Column(Integer, default=0)
    
    # Learning analytics
    strengths = Column(JSON, nullable=True)  # Areas of strength
    challenges = Column(JSON, nullable=True)  # Areas needing work
    vocabulary_learned = Column(JSON, nullable=True)  # New words mastered
    
    # Milestones
    last_level_up = Column(DateTime, nullable=True)
    next_level_requirements = Column(JSON, nullable=True)  # What's needed to advance
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class ReadingGoal(Base):
    """Learning goals and targets for students"""
    __tablename__ = "reading_goals"
    
    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, nullable=False)  # User ID of the student
    
    # Goal details
    goal_type = Column(String(50), nullable=False)  # accuracy, fluency, vocabulary, level_up
    target_value = Column(Float, nullable=False)
    current_value = Column(Float, default=0)
    target_date = Column(DateTime, nullable=True)
    
    # Description
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    
    # Status
    is_achieved = Column(Boolean, default=False)
    achieved_at = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)