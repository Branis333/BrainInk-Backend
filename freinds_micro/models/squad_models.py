from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime
from sqlalchemy import Table, MetaData
from db.database import engine
import enum

Base = declarative_base()

# Reflect the existing users table
metadata = MetaData()
users_table = Table('users', metadata, autoload_with=engine)

class SquadRole(enum.Enum):
    LEADER = "leader"
    MEMBER = "member"
    MODERATOR = "moderator"

class Squad(Base):
    __tablename__ = "squads"
    
    id = Column(String(50), primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    emoji = Column(String(10), default="🦄")
    description = Column(Text, nullable=True)
    creator_id = Column(Integer, ForeignKey(users_table.c.id), nullable=False, index=True)
    
    # Squad settings
    is_public = Column(Boolean, default=True)
    max_members = Column(Integer, default=20)
    subject_focus = Column(String(200), nullable=True)  # JSON string of subjects
    
    # Stats
    weekly_xp = Column(Integer, default=0)
    total_xp = Column(Integer, default=0)
    rank = Column(Integer, default=999)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    members = relationship("SquadMembership", back_populates="squad", cascade="all, delete-orphan")
    messages = relationship("SquadMessage", back_populates="squad", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Squad(id={self.id}, name={self.name})>"

class SquadMembership(Base):
    __tablename__ = "squad_memberships"
    
    id = Column(Integer, primary_key=True, index=True)
    squad_id = Column(String(50), ForeignKey("squads.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey(users_table.c.id), nullable=False, index=True)
    role = Column(String(20), default="member", nullable=False)  # leader, member, moderator
    
    # Member stats
    weekly_xp = Column(Integer, default=0)
    total_xp = Column(Integer, default=0)
    
    # Timestamps
    joined_at = Column(DateTime, default=datetime.utcnow)
    last_active = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    squad = relationship("Squad", back_populates="members")
    
    def __repr__(self):
        return f"<SquadMembership(squad_id={self.squad_id}, user_id={self.user_id}, role={self.role})>"

class SquadMessage(Base):
    __tablename__ = "squad_messages"
    
    id = Column(String(50), primary_key=True, index=True)
    squad_id = Column(String(50), ForeignKey("squads.id"), nullable=False, index=True)
    sender_id = Column(Integer, ForeignKey(users_table.c.id), nullable=False, index=True)
    
    # Message content
    content = Column(Text, nullable=False)
    message_type = Column(String(20), default="text")  # text, quiz_drop, achievement, system, challenge
    message_metadata = Column(Text, nullable=True)  # Changed from 'metadata' to 'message_metadata'
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    squad = relationship("Squad", back_populates="messages")
    
    def __repr__(self):
        return f"<SquadMessage(id={self.id}, squad_id={self.squad_id})>"

class SquadBattle(Base):
    __tablename__ = "squad_battles"
    
    id = Column(String(50), primary_key=True, index=True)
    challenger_squad_id = Column(String(50), ForeignKey("squads.id"), nullable=False)
    challenged_squad_id = Column(String(50), ForeignKey("squads.id"), nullable=False)
    
    # Battle details
    battle_type = Column(String(50), default="quiz_battle")  # quiz_battle, study_session, etc.
    status = Column(String(20), default="pending")  # pending, active, completed, cancelled
    
    # Battle settings
    entry_fee = Column(Integer, default=0)
    prize_pool = Column(Integer, default=0)
    duration_minutes = Column(Integer, default=30)
    subject = Column(String(100), nullable=True)
    
    # Results
    challenger_score = Column(Integer, default=0)
    challenged_score = Column(Integer, default=0)
    winner_squad_id = Column(String(50), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    start_time = Column(DateTime, nullable=True)
    end_time = Column(DateTime, nullable=True)
    
    def __repr__(self):
        return f"<SquadBattle(id={self.id}, status={self.status})>"

class StudyLeague(Base):
    __tablename__ = "study_leagues"
    
    id = Column(String(50), primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    subject = Column(String(100), nullable=False)
    
    # League settings
    max_participants = Column(Integer, default=1000)
    entry_fee = Column(Integer, default=0)
    prize_pool = Column(Integer, default=0)
    difficulty = Column(String(20), default="intermediate")  # beginner, intermediate, advanced
    league_type = Column(String(20), default="weekly")  # weekly, monthly, tournament
    
    # Status
    status = Column(String(20), default="upcoming")  # upcoming, active, ended
    
    # Timestamps
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f"<StudyLeague(id={self.id}, name={self.name})>"

class LeagueParticipation(Base):
    __tablename__ = "league_participations"
    
    id = Column(Integer, primary_key=True, index=True)
    league_id = Column(String(50), ForeignKey("study_leagues.id"), nullable=False)
    user_id = Column(Integer, ForeignKey(users_table.c.id), nullable=False, index=True)
    
    # Participation stats
    score = Column(Integer, default=0)
    rank = Column(Integer, default=0)
    questions_answered = Column(Integer, default=0)
    accuracy = Column(Float, default=0.0)
    xp_earned = Column(Integer, default=0)
    
    # Timestamps
    joined_at = Column(DateTime, default=datetime.utcnow)
    last_activity = Column(DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f"<LeagueParticipation(league_id={self.league_id}, user_id={self.user_id})>"