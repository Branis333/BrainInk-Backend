from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, Float
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
from sqlalchemy import Table, MetaData
from db.database import engine

Base = declarative_base()

# Reflect the existing users table
metadata = MetaData()
try:
    users_table = Table('users', metadata, autoload_with=engine)
except:
    # If users table doesn't exist, create a basic reference
    users_table = Table('users', metadata,
        Column('id', Integer, primary_key=True),
        Column('username', String(50)),
    )

class SpeechTranscription(Base):
    __tablename__ = "speech_transcriptions"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    
    # File information
    original_filename = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_size = Column(Integer, nullable=False)
    duration_seconds = Column(Float, nullable=True)
    
    # Audio properties
    sample_rate = Column(Integer, nullable=True)
    channels = Column(Integer, nullable=True)
    format = Column(String(20), nullable=False)  # mp3, wav, m4a, etc.
    
    # Transcription results
    transcription_text = Column(Text, nullable=True)
    confidence_score = Column(Float, nullable=True)
    language_detected = Column(String(10), nullable=True)
    
    # Processing information
    processing_status = Column(String(20), default="pending")  # pending, processing, completed, failed
    processing_engine = Column(String(50), nullable=True)  # whisper, google, azure, etc.
    processing_time_seconds = Column(Float, nullable=True)
    error_message = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    
    # Settings used
    settings_json = Column(Text, nullable=True)  # JSON string of settings used
    
    def __repr__(self):
        return f"<SpeechTranscription(id={self.id}, user_id={self.user_id}, status={self.processing_status})>"

class TranscriptionHistory(Base):
    __tablename__ = "transcription_history"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    transcription_id = Column(Integer, ForeignKey("speech_transcriptions.id"), nullable=False, index=True)
    
    # Action details
    action = Column(String(50), nullable=False)  # created, updated, deleted, downloaded
    action_details = Column(Text, nullable=True)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f"<TranscriptionHistory(id={self.id}, action={self.action})>"