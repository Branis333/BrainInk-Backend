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
    assignment_images = relationship("StudentImage", back_populates="student", cascade="all, delete-orphan")
    assignment_pdfs = relationship("StudentPDF", back_populates="student", cascade="all, delete-orphan")

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
    grading_sessions = relationship("GradingSession", back_populates="teacher", cascade="all, delete-orphan")

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
    creator = relationship("User", back_populates="subjects_created")
    teachers = relationship("Teacher", secondary=subject_teachers, back_populates="subjects")
    students = relationship("Student", secondary=subject_students, back_populates="subjects")
    assignments = relationship("Assignment", back_populates="subject", cascade="all, delete-orphan")
    grading_sessions = relationship("GradingSession", back_populates="subject", cascade="all, delete-orphan")
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
    description = Column(Text, nullable=False)  # Now required
    rubric = Column(Text, nullable=False)  # Now required
    subtopic = Column(String, nullable=True)
    subject_id = Column(Integer, ForeignKey("subjects.id"), nullable=False)
    teacher_id = Column(Integer, ForeignKey("teachers.id"), nullable=False)
    max_points = Column(Integer, default=100, nullable=False)
    due_date = Column(DateTime, nullable=True)
    created_date = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    
    # Relationships
    subject = relationship("Subject", back_populates="assignments")
    teacher = relationship("Teacher", back_populates="assignments")
    grades = relationship("Grade", back_populates="assignment", cascade="all, delete-orphan")
    student_images = relationship("StudentImage", back_populates="assignment", cascade="all, delete-orphan")
    student_pdfs = relationship("StudentPDF", back_populates="assignment", cascade="all, delete-orphan")
    grading_sessions = relationship("GradingSession", back_populates="assignment", cascade="all, delete-orphan")

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
    
    # AI Grading fields
    ai_generated = Column(Boolean, default=False)
    ai_confidence = Column(Integer, nullable=True)  # 1-100 confidence score
    
    # Relationships
    assignment = relationship("Assignment", back_populates="grades")
    student = relationship("Student", back_populates="grades")
    teacher = relationship("Teacher", back_populates="grades_given")
    student_pdf = relationship("StudentPDF", back_populates="grade", uselist=False)
    
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

# --- Student Image Model for Assignment Grading ---
class StudentImage(Base):
    __tablename__ = "student_images"
    id = Column(Integer, primary_key=True, index=True)
    assignment_id = Column(Integer, ForeignKey("assignments.id"), nullable=False)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    filename = Column(String, nullable=False)
    original_filename = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    file_size = Column(Integer, nullable=False)
    mime_type = Column(String, nullable=False)
    uploaded_by = Column(Integer, ForeignKey("users.id"), nullable=False)  # Teacher who uploaded
    upload_date = Column(DateTime, default=datetime.utcnow)
    is_processed = Column(Boolean, default=False)
    description = Column(Text, nullable=True)
    
    # AI Analysis fields
    extracted_text = Column(Text, nullable=True)
    ai_analysis = Column(Text, nullable=True)
    analysis_date = Column(DateTime, nullable=True)
    
    # Relationships
    assignment = relationship("Assignment", back_populates="student_images")
    student = relationship("Student", back_populates="assignment_images")
    uploader = relationship("User", back_populates="uploaded_images")

# --- Student PDF Model for Compiled Assignment Submissions ---
class StudentPDF(Base):
    __tablename__ = "student_pdfs"
    id = Column(Integer, primary_key=True, index=True)
    assignment_id = Column(Integer, ForeignKey("assignments.id"), nullable=False)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    pdf_filename = Column(String, nullable=False)
    pdf_path = Column(String, nullable=False)
    image_count = Column(Integer, default=0)
    generated_date = Column(DateTime, default=datetime.utcnow)
    is_graded = Column(Boolean, default=False)
    grade_id = Column(Integer, ForeignKey("grades.id"), nullable=True)
    
    # Relationships
    assignment = relationship("Assignment", back_populates="student_pdfs")
    student = relationship("Student", back_populates="assignment_pdfs")
    grade = relationship("Grade", back_populates="student_pdf")

# --- Grading Session Model for Bulk Grading Workflow ---
class GradingSession(Base):
    __tablename__ = "grading_sessions"
    id = Column(Integer, primary_key=True, index=True)
    assignment_id = Column(Integer, ForeignKey("assignments.id"), nullable=False)
    teacher_id = Column(Integer, ForeignKey("teachers.id"), nullable=False)
    subject_id = Column(Integer, ForeignKey("subjects.id"), nullable=False)
    created_date = Column(DateTime, default=datetime.utcnow)
    completed_date = Column(DateTime, nullable=True)
    is_completed = Column(Boolean, default=False)
    total_students = Column(Integer, default=0)
    graded_count = Column(Integer, default=0)
    
    # Relationships
    assignment = relationship("Assignment", back_populates="grading_sessions")
    teacher = relationship("Teacher", back_populates="grading_sessions")
    subject = relationship("Subject", back_populates="grading_sessions")

# --- Calendar Models ---

# --- Calendar Event Type Enum ---
class CalendarEventType(enum.Enum):
    assignment_due = "assignment_due"
    assignment_created = "assignment_created"
    syllabus_milestone = "syllabus_milestone"
    class_schedule = "class_schedule"
    exam = "exam"
    holiday = "holiday"
    reminder = "reminder"
    custom_event = "custom_event"

# --- Calendar Event Priority Enum ---
class CalendarEventPriority(enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"
    urgent = "urgent"

# --- Calendar Event Status Enum ---
class CalendarEventStatus(enum.Enum):
    scheduled = "scheduled"
    in_progress = "in_progress"
    completed = "completed"
    cancelled = "cancelled"
    postponed = "postponed"

# --- Calendar Event Model ---
class CalendarEvent(Base):
    __tablename__ = "calendar_events"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    event_type = Column(Enum(CalendarEventType), nullable=False)
    priority = Column(Enum(CalendarEventPriority), default=CalendarEventPriority.medium)
    status = Column(Enum(CalendarEventStatus), default=CalendarEventStatus.scheduled)
    
    # Date and time
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=True)
    all_day = Column(Boolean, default=False)
    
    # Recurrence
    is_recurring = Column(Boolean, default=False)
    recurrence_pattern = Column(String, nullable=True)  # daily, weekly, monthly, yearly
    recurrence_interval = Column(Integer, default=1)  # every X days/weeks/months
    recurrence_end_date = Column(DateTime, nullable=True)
    
    # Associations
    school_id = Column(Integer, ForeignKey("schools.id"), nullable=False)
    subject_id = Column(Integer, ForeignKey("subjects.id"), nullable=True)
    assignment_id = Column(Integer, ForeignKey("assignments.id"), nullable=True)
    syllabus_id = Column(Integer, ForeignKey("syllabuses.id"), nullable=True)
    classroom_id = Column(Integer, ForeignKey("classrooms.id"), nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Management
    created_date = Column(DateTime, default=datetime.utcnow)
    updated_date = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    
    # Notifications
    send_notification = Column(Boolean, default=True)
    notification_minutes_before = Column(Integer, default=60)  # Minutes before event to send notification
    
    # Relationships
    school = relationship("School")
    subject = relationship("Subject")
    assignment = relationship("Assignment")
    syllabus = relationship("Syllabus")
    classroom = relationship("Classroom")
    creator = relationship("User")
    attendees = relationship("CalendarEventAttendee", back_populates="event", cascade="all, delete-orphan")
    reminders = relationship("CalendarReminder", back_populates="event", cascade="all, delete-orphan")

# --- Calendar Event Attendee Model ---
class CalendarEventAttendee(Base):
    __tablename__ = "calendar_event_attendees"
    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(Integer, ForeignKey("calendar_events.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=True)
    teacher_id = Column(Integer, ForeignKey("teachers.id"), nullable=True)
    
    # Attendance tracking
    response_status = Column(String, default="pending")  # pending, accepted, declined, tentative
    response_date = Column(DateTime, nullable=True)
    attendance_status = Column(String, default="unknown")  # present, absent, late, excused
    notes = Column(Text, nullable=True)
    
    # Management
    added_date = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    
    # Relationships
    event = relationship("CalendarEvent", back_populates="attendees")
    user = relationship("User")
    student = relationship("Student")
    teacher = relationship("Teacher")
    
    # Ensure one attendee record per user per event
    __table_args__ = (
        UniqueConstraint('event_id', 'user_id', name='uq_event_user_attendee'),
    )

# --- Calendar Reminder Model ---
class CalendarReminder(Base):
    __tablename__ = "calendar_reminders"
    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(Integer, ForeignKey("calendar_events.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Reminder settings
    reminder_minutes_before = Column(Integer, nullable=False)  # Minutes before event
    reminder_method = Column(String, default="notification")  # notification, email, sms
    
    # Status tracking
    is_sent = Column(Boolean, default=False)
    sent_date = Column(DateTime, nullable=True)
    scheduled_for = Column(DateTime, nullable=False)  # When to send reminder
    
    # Management
    created_date = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    
    # Relationships
    event = relationship("CalendarEvent", back_populates="reminders")
    user = relationship("User")

# --- Calendar View Model (for custom calendar views) ---
class CalendarView(Base):
    __tablename__ = "calendar_views"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    school_id = Column(Integer, ForeignKey("schools.id"), nullable=False)
    
    # View settings
    view_type = Column(String, default="month")  # day, week, month, year, agenda
    default_view = Column(Boolean, default=False)
    show_weekends = Column(Boolean, default=True)
    start_hour = Column(Integer, default=8)  # 24-hour format
    end_hour = Column(Integer, default=18)  # 24-hour format
    
    # Filter settings (JSON)
    filter_subjects = Column(Text, nullable=True)  # JSON array of subject IDs
    filter_event_types = Column(Text, nullable=True)  # JSON array of event types
    filter_priorities = Column(Text, nullable=True)  # JSON array of priorities
    show_completed = Column(Boolean, default=True)
    
    # Colors and styling (JSON)
    color_scheme = Column(Text, nullable=True)  # JSON color configuration
    
    # Management
    created_date = Column(DateTime, default=datetime.utcnow)
    updated_date = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    
    # Relationships
    user = relationship("User")
    school = relationship("School")

# --- Report Models ---

# --- Report Type Enum ---
class ReportType(enum.Enum):
    student_progress = "student_progress"
    class_performance = "class_performance"
    subject_analytics = "subject_analytics"
    assignment_analysis = "assignment_analysis"
    grade_distribution = "grade_distribution"
    attendance_report = "attendance_report"
    teacher_performance = "teacher_performance"
    school_overview = "school_overview"

# --- Report Status Enum ---
class ReportStatus(enum.Enum):
    pending = "pending"
    generating = "generating"
    completed = "completed"
    failed = "failed"
    expired = "expired"

# --- Report Format Enum ---
class ReportFormat(enum.Enum):
    pdf = "pdf"
    excel = "excel"
    csv = "csv"
    json = "json"

# --- Report Template Model ---
class ReportTemplate(Base):
    __tablename__ = "report_templates"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    report_type = Column(Enum(ReportType), nullable=False)
    template_config = Column(Text, nullable=False)  # JSON configuration
    school_id = Column(Integer, ForeignKey("schools.id"), nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_date = Column(DateTime, default=datetime.utcnow)
    updated_date = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    is_default = Column(Boolean, default=False)
    
    # Relationships
    school = relationship("School")
    creator = relationship("User")
    reports = relationship("Report", back_populates="template")

# --- Report Model ---
class Report(Base):
    __tablename__ = "reports"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    report_type = Column(Enum(ReportType), nullable=False)
    template_id = Column(Integer, ForeignKey("report_templates.id"), nullable=True)
    
    # Report scope
    school_id = Column(Integer, ForeignKey("schools.id"), nullable=False)
    subject_id = Column(Integer, ForeignKey("subjects.id"), nullable=True)
    classroom_id = Column(Integer, ForeignKey("classrooms.id"), nullable=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=True)
    teacher_id = Column(Integer, ForeignKey("teachers.id"), nullable=True)
    assignment_id = Column(Integer, ForeignKey("assignments.id"), nullable=True)
    
    # Report parameters
    date_from = Column(DateTime, nullable=True)
    date_to = Column(DateTime, nullable=True)
    parameters = Column(Text, nullable=True)  # JSON parameters
    
    # Report generation
    requested_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    requested_date = Column(DateTime, default=datetime.utcnow)
    generated_date = Column(DateTime, nullable=True)
    status = Column(Enum(ReportStatus), default=ReportStatus.pending)
    format = Column(Enum(ReportFormat), default=ReportFormat.pdf)
    
    # File information
    file_path = Column(String, nullable=True)
    file_name = Column(String, nullable=True)
    file_size = Column(Integer, nullable=True)
    
    # Report data and metadata
    report_data = Column(Text, nullable=True)  # JSON report data
    summary_stats = Column(Text, nullable=True)  # JSON summary statistics
    error_message = Column(Text, nullable=True)
    
    # Expiration and access
    expires_date = Column(DateTime, nullable=True)
    access_count = Column(Integer, default=0)
    last_accessed = Column(DateTime, nullable=True)
    is_public = Column(Boolean, default=False)
    
    # Relationships
    school = relationship("School")
    subject = relationship("Subject")
    classroom = relationship("Classroom")
    student = relationship("Student")
    teacher = relationship("Teacher")
    assignment = relationship("Assignment")
    requester = relationship("User")
    template = relationship("ReportTemplate", back_populates="reports")

# --- Report Share Model ---
class ReportShare(Base):
    __tablename__ = "report_shares"
    id = Column(Integer, primary_key=True, index=True)
    report_id = Column(Integer, ForeignKey("reports.id"), nullable=False)
    shared_with_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    shared_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    share_date = Column(DateTime, default=datetime.utcnow)
    access_level = Column(String, default="view")  # view, download, edit
    expires_date = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)
    access_count = Column(Integer, default=0)
    last_accessed = Column(DateTime, nullable=True)
    
    # Relationships
    report = relationship("Report")
    shared_with = relationship("User", foreign_keys=[shared_with_user_id])
    shared_by = relationship("User", foreign_keys=[shared_by_user_id])

# --- Report Schedule Model ---
class ReportSchedule(Base):
    __tablename__ = "report_schedules"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    template_id = Column(Integer, ForeignKey("report_templates.id"), nullable=False)
    
    # Schedule configuration
    frequency = Column(String, nullable=False)  # daily, weekly, monthly, quarterly
    schedule_config = Column(Text, nullable=False)  # JSON cron-like configuration
    
    # Report parameters
    school_id = Column(Integer, ForeignKey("schools.id"), nullable=False)
    subject_id = Column(Integer, ForeignKey("subjects.id"), nullable=True)
    classroom_id = Column(Integer, ForeignKey("classrooms.id"), nullable=True)
    parameters = Column(Text, nullable=True)  # JSON parameters
    
    # Recipients
    recipient_emails = Column(Text, nullable=False)  # JSON array of emails
    recipient_user_ids = Column(Text, nullable=True)  # JSON array of user IDs
    
    # Schedule management
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_date = Column(DateTime, default=datetime.utcnow)
    last_run_date = Column(DateTime, nullable=True)
    next_run_date = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)
    
    # Statistics
    total_runs = Column(Integer, default=0)
    successful_runs = Column(Integer, default=0)
    failed_runs = Column(Integer, default=0)
    
    # Relationships
    template = relationship("ReportTemplate")
    school = relationship("School")
    subject = relationship("Subject")
    classroom = relationship("Classroom")
    creator = relationship("User")
