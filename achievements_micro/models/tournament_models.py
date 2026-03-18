from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, ForeignKey, Float, Table, MetaData
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
import enum
from db.database import engine

# Use the same approach as your main models
Base = declarative_base()

# Reflect the existing users table
metadata = MetaData()
users_table = Table('users', metadata, autoload_with=engine)

# Keep Python enums for validation but use String in database
class TournamentStatus(enum.Enum):
    DRAFT = "draft"
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"

class TournamentType(enum.Enum):
    PUBLIC = "public"
    PRIVATE = "private"
    INVITE_ONLY = "invite_only"

class BracketType(enum.Enum):
    SINGLE_ELIMINATION = "single_elimination"
    DOUBLE_ELIMINATION = "double_elimination"
    ROUND_ROBIN = "round_robin"

class DifficultyLevel(enum.Enum):
    ELEMENTARY = "elementary"
    MIDDLE_SCHOOL = "middle_school"
    HIGH_SCHOOL = "high_school"
    UNIVERSITY = "university"
    PROFESSIONAL = "professional"
    MIXED = "mixed"

class Tournament(Base):
    __tablename__ = "tournaments"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    creator_id = Column(Integer, ForeignKey(users_table.c.id), nullable=False)
    
    # Tournament Configuration - Using String instead of Enum
    max_players = Column(Integer, nullable=False, default=32)
    current_players = Column(Integer, default=0)
    tournament_type = Column(String(20), default="public")
    bracket_type = Column(String(30), default="single_elimination")
    
    # Prize Configuration
    has_prizes = Column(Boolean, default=False)
    first_place_prize = Column(String(255))
    second_place_prize = Column(String(255))
    third_place_prize = Column(String(255))
    prize_type = Column(String(50))
    
    # Question Configuration
    total_questions = Column(Integer, default=50)
    time_limit_minutes = Column(Integer, default=60)
    difficulty_level = Column(String(20), default="mixed")
    subject_category = Column(String(100))
    custom_topics = Column(Text)
    
    # Status and Timing
    status = Column(String(20), default="draft")
    registration_start = Column(DateTime, default=datetime.utcnow)
    registration_end = Column(DateTime)
    tournament_start = Column(DateTime)
    tournament_end = Column(DateTime)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships - Fixed
    participants = relationship("TournamentParticipant", back_populates="tournament")
    brackets = relationship("TournamentBracket", back_populates="tournament")
    matches = relationship("TournamentMatch", back_populates="tournament")
    invitations = relationship("TournamentInvitation", back_populates="tournament")
    questions = relationship("TournamentQuestion", back_populates="tournament")

class TournamentParticipant(Base):
    __tablename__ = "tournament_participants"
    
    id = Column(Integer, primary_key=True, index=True)
    tournament_id = Column(Integer, ForeignKey("tournaments.id"), nullable=False)
    user_id = Column(Integer, ForeignKey(users_table.c.id), nullable=False)
    
    # Participation Details
    joined_at = Column(DateTime, default=datetime.utcnow)
    seed_number = Column(Integer)
    is_eliminated = Column(Boolean, default=False)
    final_position = Column(Integer)
    
    # Performance Stats
    total_score = Column(Integer, default=0)
    questions_answered = Column(Integer, default=0)
    correct_answers = Column(Integer, default=0)
    time_spent_seconds = Column(Integer, default=0)
    
    # Relationships - Fixed
    tournament = relationship("Tournament", back_populates="participants")

class TournamentBracket(Base):
    __tablename__ = "tournament_brackets"
    
    id = Column(Integer, primary_key=True, index=True)
    tournament_id = Column(Integer, ForeignKey("tournaments.id"), nullable=False)
    
    round_number = Column(Integer, nullable=False)
    round_name = Column(String(50))
    total_matches = Column(Integer, nullable=False)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships - Fixed
    tournament = relationship("Tournament", back_populates="brackets")
    matches = relationship("TournamentMatch", back_populates="bracket")  # ✅ Fixed this line

class TournamentMatch(Base):
    __tablename__ = "tournament_matches"
    
    id = Column(Integer, primary_key=True, index=True)
    tournament_id = Column(Integer, ForeignKey("tournaments.id"), nullable=False)
    bracket_id = Column(Integer, ForeignKey("tournament_brackets.id"), nullable=False)
    
    # Match Details
    match_number = Column(Integer, nullable=False)
    round_number = Column(Integer, nullable=False)
    
    # Participants
    player1_id = Column(Integer, ForeignKey(users_table.c.id))
    player2_id = Column(Integer, ForeignKey(users_table.c.id))
    winner_id = Column(Integer, ForeignKey(users_table.c.id))
    
    # Match Results
    player1_score = Column(Integer, default=0)
    player2_score = Column(Integer, default=0)
    player1_time = Column(Integer, default=0)
    player2_time = Column(Integer, default=0)
    
    # Status
    is_completed = Column(Boolean, default=False)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    
    # Relationships - Fixed
    tournament = relationship("Tournament", back_populates="matches")
    bracket = relationship("TournamentBracket", back_populates="matches")  # ✅ This should match the above

class TournamentInvitation(Base):
    __tablename__ = "tournament_invitations"
    
    id = Column(Integer, primary_key=True, index=True)
    tournament_id = Column(Integer, ForeignKey("tournaments.id"), nullable=False)
    inviter_id = Column(Integer, ForeignKey(users_table.c.id), nullable=False)
    invitee_id = Column(Integer, ForeignKey(users_table.c.id), nullable=False)
    
    # Invitation Status
    status = Column(String(20), default="pending")
    invited_at = Column(DateTime, default=datetime.utcnow)
    responded_at = Column(DateTime)
    
    # Relationships - Fixed
    tournament = relationship("Tournament", back_populates="invitations")

class TournamentQuestion(Base):
    __tablename__ = "tournament_questions"
    
    id = Column(Integer, primary_key=True, index=True)
    tournament_id = Column(Integer, ForeignKey("tournaments.id"), nullable=False)
    
    # Question Content
    question_text = Column(Text, nullable=False)
    option_a = Column(String(500))
    option_b = Column(String(500))
    option_c = Column(String(500))
    option_d = Column(String(500))
    correct_answer = Column(String(1))
    
    # Question Metadata
    category = Column(String(100))
    difficulty = Column(String(20))
    points_value = Column(Integer, default=10)
    time_limit_seconds = Column(Integer, default=30)
    
    # AI Generation Info
    generated_by_ai = Column(Boolean, default=False)
    source_topic = Column(String(255))
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships - Fixed
    tournament = relationship("Tournament", back_populates="questions")