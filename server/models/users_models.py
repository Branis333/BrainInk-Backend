from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

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
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)
    
    def __repr__(self):
        return f"<User(username={self.username}, email={self.email})>"


class OTP(Base):
    __tablename__ = "otps"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True)
    email = Column(String(255), nullable=True)
    otp_code = Column(String(10), nullable=False)
    purpose = Column(String(50))  # registration, password_reset, etc.
    is_used = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)
    
    def __repr__(self):
        return f"<OTP(purpose={self.purpose})>"