from sqlalchemy import Column, Integer, String, Text, DateTime, Float, Boolean
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()

class StudyNotes(Base):
    __tablename__ = "study_notes"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)  # No FK constraint, just reference
    
    # Note content
    title = Column(String(255), nullable=False)
    original_text = Column(Text, nullable=False)  # Original transcription text
    brief_notes = Column(Text, nullable=False)    # Generated study notes
    key_points = Column(Text, nullable=True)      # JSON array of key points
    summary = Column(Text, nullable=True)         # Brief summary
    
    # Metadata
    subject = Column(String(100), nullable=True)  # e.g., "Mathematics", "History"
    language = Column(String(10), nullable=True)
    word_count_original = Column(Integer, nullable=True)
    word_count_notes = Column(Integer, nullable=True)
    
    # Processing info
    processing_time_seconds = Column(Float, nullable=True)
    gemini_model_used = Column(String(50), nullable=True)
    
    # User interactions
    is_favorite = Column(Boolean, default=False)
    view_count = Column(Integer, default=0)
    last_viewed = Column(DateTime, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"<StudyNotes(id={self.id}, title='{self.title[:30]}...', user_id={self.user_id})>"