from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey
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
    
    # Role relationship (many-to-many)
    roles = relationship("Role", secondary="user_roles", back_populates="users")
    
    # Account status
    is_active = Column(Boolean, default=True)
    email_confirmed = Column(Boolean, default=False)
    is_verified = Column(Boolean, default=False)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships with study area models
    schools_managed = relationship("School", back_populates="principal")
    school_requests = relationship("SchoolRequest", foreign_keys="SchoolRequest.principal_id", back_populates="principal")
    student_profile = relationship("Student", back_populates="user", uselist=False)
    teacher_profile = relationship("Teacher", back_populates="user", uselist=False)
    subjects_created = relationship("Subject", back_populates="creator")
    uploaded_images = relationship("StudentImage", back_populates="uploader")
    
    def has_role(self, role_name):
        """Check if user has a specific role"""
        from models.study_area_models import UserRole
        if isinstance(role_name, str):
            role_name = UserRole(role_name)
        return any(role.name == role_name for role in self.roles)
    
    def add_role(self, role):
        """Add a role to the user"""
        if role not in self.roles:
            self.roles.append(role)
    
    def remove_role(self, role):
        """Remove a role from the user"""
        if role in self.roles:
            self.roles.remove(role)
    
    def get_role_names(self):
        """Get list of role names as strings"""
        return [role.name.value for role in self.roles]
    
    def __repr__(self):
        return f"<User(username={self.username}, email={self.email})>"