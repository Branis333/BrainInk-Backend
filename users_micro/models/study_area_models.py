from sqlalchemy import Column, Integer, String, ForeignKey, Enum, DateTime, Boolean, Text, Table, UniqueConstraint
from sqlalchemy.orm import relationship
from db.connection import Base
import enum
from datetime import datetime

# --- Association table for many-to-many User-Role relationship ---
user_roles = Table(
    'user_roles',
    Base.metadata,
    Column('user_id', Integer, ForeignKey('users.id'), primary_key=True),
    Column('role_id', Integer, ForeignKey('roles.id'), primary_key=True)
)

# --- Association table for Subject-Teacher relationship ---
subject_teachers = Table(
    'subject_teachers',
    Base.metadata,
    Column('subject_id', Integer, ForeignKey('subjects.id'), primary_key=True),
    Column('teacher_id', Integer, ForeignKey('teachers.id'), primary_key=True)
)

# --- Association table for Subject-Student relationship ---
subject_students = Table(
    'subject_students',
    Base.metadata,
    Column('subject_id', Integer, ForeignKey('subjects.id'), primary_key=True),
    Column('student_id', Integer, ForeignKey('students.id'), primary_key=True)
)

# --- User Role Enum ---
class UserRole(enum.Enum):
    normal_user = "normal_user"
    student = "student" 
    teacher = "teacher"
    principal = "principal"
    admin = "admin"

# --- Invitation Type Enum ---
class InvitationType(enum.Enum):
    student = "student"
    teacher = "teacher"

# --- Role Model ---
class Role(Base):
    __tablename__ = "roles"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(Enum(UserRole), unique=True, nullable=False, default=UserRole.normal_user)
    description = Column(String, nullable=True)
    users = relationship("User", secondary=user_roles, back_populates="roles")

# --- School Request Status ---
class SchoolRequestStatus(enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"

# --- School Request Model ---
class SchoolRequest(Base):
    __tablename__ = "school_requests"
    id = Column(Integer, primary_key=True, index=True)
    school_name = Column(String, nullable=False)
    school_address = Column(String, nullable=True)
    principal_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    request_date = Column(DateTime, default=datetime.utcnow)
    status = Column(Enum(SchoolRequestStatus), default=SchoolRequestStatus.pending)
    admin_notes = Column(Text, nullable=True)
    reviewed_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    reviewed_date = Column(DateTime, nullable=True)
    # New fields for direct school joining
    request_type = Column(String, default="school_creation")  # "school_creation", "principal_join", "teacher_join"
    target_school_id = Column(Integer, ForeignKey("schools.id"), nullable=True)  # For joining existing schools
    created_date = Column(DateTime, default=datetime.utcnow)
    
    principal = relationship("User", foreign_keys=[principal_id], back_populates="school_requests")
    reviewer = relationship("User", foreign_keys=[reviewed_by])

# --- School Model ---
class School(Base):
    __tablename__ = "schools"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)
    address = Column(String, nullable=True)
    principal_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_date = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    
    principal = relationship("User", back_populates="schools_managed")
    classrooms = relationship("Classroom", back_populates="school", cascade="all, delete-orphan")
    students = relationship("Student", back_populates="school", cascade="all, delete-orphan")
    teachers = relationship("Teacher", back_populates="school", cascade="all, delete-orphan")
    access_codes = relationship("AccessCode", back_populates="school", cascade="all, delete-orphan")
    subjects = relationship("Subject", back_populates="school", cascade="all, delete-orphan")

# --- Classroom Model ---
class Classroom(Base):
    __tablename__ = "classrooms"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    capacity = Column(Integer, default=30)
    location = Column(String, nullable=True)
    school_id = Column(Integer, ForeignKey("schools.id"), nullable=False)
    teacher_id = Column(Integer, ForeignKey("teachers.id"), nullable=True)
    created_date = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    
    school = relationship("School", back_populates="classrooms")
    students = relationship("Student", back_populates="classroom")
    assigned_teacher = relationship("Teacher", back_populates="assigned_classroom")

# --- Access Code Model ---
class AccessCodeType(enum.Enum):
    student = "student"
    teacher = "teacher"

class AccessCode(Base):
    __tablename__ = "access_codes"
    id = Column(Integer, primary_key=True, index=True)
    code = Column(String, unique=True, nullable=False)
    code_type = Column(Enum(AccessCodeType), nullable=False)
    school_id = Column(Integer, ForeignKey("schools.id"), nullable=False)
    email = Column(String, nullable=False)  # Email of the student/teacher this code is for
    created_date = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    
    school = relationship("School", back_populates="access_codes")
    
    # Ensure one code per email per school per type
    __table_args__ = (
        UniqueConstraint('school_id', 'email', 'code_type', name='uq_school_email_type'),
    )

# --- Student Model ---
class Student(Base):
    __tablename__ = "students"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    school_id = Column(Integer, ForeignKey("schools.id"), nullable=False)
    classroom_id = Column(Integer, ForeignKey("classrooms.id"), nullable=True)
    enrollment_date = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    
    user = relationship("User", back_populates="student_profile")
    school = relationship("School", back_populates="students")
    classroom = relationship("Classroom", back_populates="students")
    subjects = relationship("Subject", secondary=subject_students, back_populates="students")
    grades = relationship("Grade", back_populates="student", cascade="all, delete-orphan")

# --- Teacher Model ---
class Teacher(Base):
    __tablename__ = "teachers"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    school_id = Column(Integer, ForeignKey("schools.id"), nullable=False)
    hire_date = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    
    user = relationship("User", back_populates="teacher_profile")
    school = relationship("School", back_populates="teachers")
    assigned_classroom = relationship("Classroom", back_populates="assigned_teacher")
    subjects = relationship("Subject", secondary=subject_teachers, back_populates="teachers")
    assignments = relationship("Assignment", back_populates="teacher", cascade="all, delete-orphan")
    grades_given = relationship("Grade", back_populates="teacher", cascade="all, delete-orphan")

# --- Subject Model ---
class Subject(Base):
    __tablename__ = "subjects"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    school_id = Column(Integer, ForeignKey("schools.id"), nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)  # Principal who created it
    created_date = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    
    # Relationships
    school = relationship("School", back_populates="subjects")
    creator = relationship("User", foreign_keys=[created_by])
    teachers = relationship("Teacher", secondary=subject_teachers, back_populates="subjects")
    students = relationship("Student", secondary=subject_students, back_populates="subjects")
    assignments = relationship("Assignment", back_populates="subject", cascade="all, delete-orphan")
    syllabuses = relationship("Syllabus", back_populates="subject", cascade="all, delete-orphan")
    
    # Ensure subject names are unique per school
    __table_args__ = (
        UniqueConstraint('school_id', 'name', name='uq_school_subject_name'),
    )

# --- Assignment Model ---
class Assignment(Base):
    __tablename__ = "assignments"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    subtopic = Column(String, nullable=True)  # Optional subtopic
    subject_id = Column(Integer, ForeignKey("subjects.id"), nullable=False)
    teacher_id = Column(Integer, ForeignKey("teachers.id"), nullable=False)
    max_points = Column(Integer, nullable=False, default=100)
    due_date = Column(DateTime, nullable=True)
    created_date = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    
    # Relationships
    subject = relationship("Subject", back_populates="assignments")
    teacher = relationship("Teacher", back_populates="assignments")
    grades = relationship("Grade", back_populates="assignment", cascade="all, delete-orphan")

# --- Grade Model ---
class Grade(Base):
    __tablename__ = "grades"
    id = Column(Integer, primary_key=True, index=True)
    assignment_id = Column(Integer, ForeignKey("assignments.id"), nullable=False)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    teacher_id = Column(Integer, ForeignKey("teachers.id"), nullable=False)
    points_earned = Column(Integer, nullable=False)
    feedback = Column(Text, nullable=True)
    graded_date = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    
    # Relationships
    assignment = relationship("Assignment", back_populates="grades")
    student = relationship("Student", back_populates="grades")
    teacher = relationship("Teacher", back_populates="grades_given")
    
    # Ensure one grade per student per assignment
    __table_args__ = (
        UniqueConstraint('assignment_id', 'student_id', name='uq_assignment_student'),
    )

# --- School Invitation Model ---
class SchoolInvitation(Base):
    __tablename__ = "school_invitations"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, nullable=False)
    invitation_type = Column(Enum(InvitationType), nullable=False)
    school_id = Column(Integer, ForeignKey("schools.id"), nullable=False)
    invited_by = Column(Integer, ForeignKey("users.id"), nullable=False)  # Principal who invited
    invited_date = Column(DateTime, default=datetime.utcnow)
    is_used = Column(Boolean, default=False)
    used_date = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)
    
    # Relationships
    school = relationship("School")
    inviter = relationship("User", foreign_keys=[invited_by])
    
    # Ensure one active invitation per email per school per type
    __table_args__ = (
        UniqueConstraint('email', 'school_id', 'invitation_type', name='uq_email_school_type'),
    )

# --- Syllabus Models ---

class SyllabusStatus(enum.Enum):
    draft = "draft"
    active = "active"
    archived = "archived"

class Syllabus(Base):
    __tablename__ = "syllabuses"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    subject_id = Column(Integer, ForeignKey("subjects.id"), nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)  # Principal or Teacher
    term_length_weeks = Column(Integer, nullable=False, default=16)  # Number of weeks in the term
    textbook_filename = Column(String, nullable=True)  # Original textbook filename
    textbook_path = Column(String, nullable=True)  # Path to uploaded textbook
    ai_processing_status = Column(String, default="pending")  # pending, processing, completed, failed
    ai_analysis_data = Column(Text, nullable=True)  # JSON data from K.A.N.A. analysis
    status = Column(Enum(SyllabusStatus), default=SyllabusStatus.draft)
    created_date = Column(DateTime, default=datetime.utcnow)
    updated_date = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    
    # Relationships
    subject = relationship("Subject", back_populates="syllabuses")
    creator = relationship("User", foreign_keys=[created_by])
    weekly_plans = relationship("WeeklyPlan", back_populates="syllabus", cascade="all, delete-orphan")

class WeeklyPlan(Base):
    __tablename__ = "weekly_plans"
    id = Column(Integer, primary_key=True, index=True)
    syllabus_id = Column(Integer, ForeignKey("syllabuses.id"), nullable=False)
    week_number = Column(Integer, nullable=False)  # 1, 2, 3, etc.
    title = Column(String, nullable=False)  # e.g., "Introduction to Algebra"
    description = Column(Text, nullable=True)
    learning_objectives = Column(Text, nullable=True)  # JSON array of objectives
    topics_covered = Column(Text, nullable=True)  # JSON array of topics
    textbook_chapters = Column(String, nullable=True)  # e.g., "Chapters 1-2"
    textbook_pages = Column(String, nullable=True)  # e.g., "Pages 15-45"
    assignments = Column(Text, nullable=True)  # JSON array of assignments
    resources = Column(Text, nullable=True)  # JSON array of additional resources
    notes = Column(Text, nullable=True)
    created_date = Column(DateTime, default=datetime.utcnow)
    updated_date = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    
    # Relationships
    syllabus = relationship("Syllabus", back_populates="weekly_plans")
    
    # Ensure unique week numbers per syllabus
    __table_args__ = (
        UniqueConstraint('syllabus_id', 'week_number', name='uq_syllabus_week'),
    )

class StudentSyllabusProgress(Base):
    __tablename__ = "student_syllabus_progress"
    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    syllabus_id = Column(Integer, ForeignKey("syllabuses.id"), nullable=False)
    current_week = Column(Integer, default=1)
    completed_weeks = Column(Text, nullable=True)  # JSON array of completed week numbers
    progress_percentage = Column(Integer, default=0)  # 0-100
    last_accessed = Column(DateTime, default=datetime.utcnow)
    created_date = Column(DateTime, default=datetime.utcnow)
    updated_date = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    student = relationship("Student")
    syllabus = relationship("Syllabus")
    
    # Ensure one progress record per student per syllabus
    __table_args__ = (
        UniqueConstraint('student_id', 'syllabus_id', name='uq_student_syllabus_progress'),
    )
