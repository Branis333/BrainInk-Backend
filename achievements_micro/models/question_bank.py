from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, Float
from datetime import datetime
from models.models import Base  # Use the same Base as your other models

class QuestionBank(Base):
    __tablename__ = "question_bank"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Question Content
    question_text = Column(Text, nullable=False)
    option_a = Column(String(500), nullable=False)
    option_b = Column(String(500), nullable=False)
    option_c = Column(String(500), nullable=False)
    option_d = Column(String(500), nullable=False)
    correct_answer = Column(String(1), nullable=False)  # A, B, C, D
    
    # Question Metadata
    subject = Column(String(50), nullable=False, index=True)  # Math, Science, History, etc.
    topic = Column(String(100), nullable=False, index=True)   # Algebra, Physics, World War II, etc.
    difficulty_level = Column(String(20), nullable=False, index=True)  # elementary, middle_school, high_school, university, professional
    
    # Additional Info
    explanation = Column(Text)  # Why the answer is correct
    source = Column(String(200))  # Where the question came from
    points_value = Column(Integer, default=10)
    time_limit_seconds = Column(Integer, default=30)
    
    # Usage Stats
    times_used = Column(Integer, default=0)
    correct_rate = Column(Float, default=0.0)  # Percentage of correct answers
    
    # Metadata
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)