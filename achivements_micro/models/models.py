from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, BigInteger
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime
from sqlalchemy import Table, MetaData
from db.database import engine

Base = declarative_base()

# Reflect the existing users table and create a User class from it
metadata = MetaData()
users_table = Table('users', metadata, autoload_with=engine)

# Create User class from reflected table
class User(Base):
    __table__ = users_table
    
    # Define the back-references for relationships
    progress = relationship("UserProgress", back_populates="user", uselist=False)
    achievements = relationship("UserAchievement", back_populates="user")
    xp_transactions = relationship("XPTransaction", back_populates="user")

class Rank(Base):
    __tablename__ = "ranks"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), unique=True, nullable=False)
    tier = Column(String(20), nullable=False)
    level = Column(Integer, nullable=False)
    required_xp = Column(BigInteger, nullable=False)
    emoji = Column(String(10), nullable=True)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class Achievement(Base):
    __tablename__ = "achievements"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)
    description = Column(Text, nullable=False)
    category = Column(String(50), nullable=False)
    badge_icon = Column(String(100), nullable=True)
    xp_reward = Column(Integer, default=0)
    is_hidden = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class UserProgress(Base):
    __tablename__ = "user_progress"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey(users_table.c.id), nullable=False, index=True)
    total_xp = Column(BigInteger, default=0)
    current_rank_id = Column(Integer, ForeignKey("ranks.id"), nullable=True)
    login_streak = Column(Integer, default=0)
    last_login = Column(DateTime, nullable=True)
    total_quiz_completed = Column(Integer, default=0)
    tournaments_won = Column(Integer, default=0)
    tournaments_entered = Column(Integer, default=0)
    courses_completed = Column(Integer, default=0)
    time_spent_hours = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="progress")
    current_rank = relationship("Rank")

class UserAchievement(Base):
    __tablename__ = "user_achievements"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey(users_table.c.id), nullable=False, index=True)
    achievement_id = Column(Integer, ForeignKey("achievements.id"), nullable=False)
    earned_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="achievements")
    achievement = relationship("Achievement")

class XPTransaction(Base):
    __tablename__ = "xp_transactions"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey(users_table.c.id), nullable=False, index=True)
    amount = Column(Integer, nullable=False)
    source = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="xp_transactions")