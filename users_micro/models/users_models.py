from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
from sqlalchemy.orm import relationship

Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    
    # Primary identifiers
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(255), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    is_google_account = Column(Boolean, default=False)    
    
    # Authentication
    password_hash = Column(String(255), nullable=False)
    
    # Basic profile
    fname = Column(String(50), nullable=True, default="")
    lname = Column(String(50), nullable=True, default="")
    avatar = Column(Text, nullable=True)
    
    # Account status
    is_active = Column(Boolean, default=True)
    email_confirmed = Column(Boolean, default=False)
    is_verified = Column(Boolean, default=False)  # Added this field
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    def __repr__(self):
        return f"<User(username={self.username}, email={self.email})>"