from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean, ForeignKey, JSON, Table, MetaData
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
from db.database import engine

Base = declarative_base()

# Try to reflect the existing users table - if it doesn't exist, we'll handle users by ID only
metadata = MetaData()
try:
    users_table = Table('users', metadata, autoload_with=engine)
    USERS_TABLE_EXISTS = True
except Exception:
    # Users table doesn't exist in this database - we'll store user IDs as integers
    USERS_TABLE_EXISTS = False
    users_table = None

class VideoCallRoom(Base):
    __tablename__ = "video_call_rooms"
    
    id = Column(Integer, primary_key=True, index=True)
    room_id = Column(String(255), unique=True, index=True, nullable=False)
    room_name = Column(String(255), nullable=False)
    created_by = Column(Integer, nullable=False, index=True)  # Store user ID without FK constraint
    created_at = Column(DateTime, default=datetime.utcnow)
    ended_at = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)
    max_participants = Column(Integer, default=10)
    room_settings = Column(JSON, nullable=True)  # Store room configuration
    
    # Relationships
    participants = relationship("VideoCallParticipant", back_populates="room", cascade="all, delete-orphan")
    transcription_sessions = relationship("TranscriptionSession", back_populates="room", cascade="all, delete-orphan")

class VideoCallParticipant(Base):
    __tablename__ = "video_call_participants"
    
    id = Column(Integer, primary_key=True, index=True)
    room_id = Column(Integer, ForeignKey('video_call_rooms.id'), nullable=False)
    user_id = Column(Integer, nullable=False, index=True)  # Store user ID without FK constraint
    joined_at = Column(DateTime, default=datetime.utcnow)
    left_at = Column(DateTime, nullable=True)
    is_currently_in_call = Column(Boolean, default=True)
    participant_settings = Column(JSON, nullable=True)  # Store user-specific settings
    
    # Relationships
    room = relationship("VideoCallRoom", back_populates="participants")
    transcriptions = relationship("TranscriptionData", back_populates="participant", cascade="all, delete-orphan")

class TranscriptionSession(Base):
    __tablename__ = "transcription_sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    room_id = Column(Integer, ForeignKey('video_call_rooms.id'), nullable=False)
    session_name = Column(String(255), nullable=False)
    started_by = Column(Integer, nullable=False, index=True)  # Store user ID without FK constraint
    started_at = Column(DateTime, default=datetime.utcnow)
    ended_at = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)
    language = Column(String(10), default="auto")  # Language detection/selection
    session_settings = Column(JSON, nullable=True)
    
    # Summary fields for "Analyze Session"
    total_duration_minutes = Column(Integer, default=0)
    total_words = Column(Integer, default=0)
    participant_count = Column(Integer, default=0)
    session_summary = Column(Text, nullable=True)
    key_topics = Column(JSON, nullable=True)  # Store extracted topics/keywords
    
    # Relationships
    room = relationship("VideoCallRoom", back_populates="transcription_sessions")
    transcription_data = relationship("TranscriptionData", back_populates="session", cascade="all, delete-orphan")

class TranscriptionData(Base):
    __tablename__ = "transcription_data"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey('transcription_sessions.id'), nullable=False)
    participant_id = Column(Integer, ForeignKey('video_call_participants.id'), nullable=False)
    user_id = Column(Integer, nullable=False, index=True)  # Store user ID without FK constraint
    
    # Transcription content
    transcribed_text = Column(Text, nullable=False)
    original_language = Column(String(10), nullable=True)
    confidence_score = Column(Integer, nullable=True)  # 0-100
    
    # Timing information
    timestamp = Column(DateTime, default=datetime.utcnow)
    start_time_seconds = Column(Integer, nullable=True)  # Time in call when spoken
    duration_seconds = Column(Integer, nullable=True)   # Duration of speech segment
    
    # Metadata
    is_final = Column(Boolean, default=True)  # False for interim results
    speaker_name = Column(String(255), nullable=True)
    audio_quality = Column(String(50), nullable=True)  # good/medium/poor
    
    # Analysis fields
    sentiment = Column(String(20), nullable=True)  # positive/negative/neutral
    word_count = Column(Integer, default=0)
    contains_question = Column(Boolean, default=False)
    
    # Relationships
    session = relationship("TranscriptionSession", back_populates="transcription_data")
    participant = relationship("VideoCallParticipant", back_populates="transcriptions")

class CallAnalytics(Base):
    __tablename__ = "call_analytics"
    
    id = Column(Integer, primary_key=True, index=True)
    room_id = Column(Integer, ForeignKey('video_call_rooms.id'), nullable=False)
    session_id = Column(Integer, ForeignKey('transcription_sessions.id'), nullable=True)
    
    # Overall call metrics
    total_call_duration_minutes = Column(Integer, default=0)
    total_participants = Column(Integer, default=0)
    total_words_spoken = Column(Integer, default=0)
    
    # Engagement metrics
    most_active_speaker_id = Column(Integer, nullable=True)  # Store user ID without FK constraint
    speaking_time_distribution = Column(JSON, nullable=True)  # {user_id: minutes_spoken}
    question_count = Column(Integer, default=0)
    
    # Content analysis
    main_topics = Column(JSON, nullable=True)
    key_phrases = Column(JSON, nullable=True)
    overall_sentiment = Column(String(20), nullable=True)
    
    # Generated insights
    meeting_summary = Column(Text, nullable=True)
    action_items = Column(JSON, nullable=True)
    discussion_highlights = Column(JSON, nullable=True)
    
    # Timestamps
    analysis_generated_at = Column(DateTime, default=datetime.utcnow)
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
