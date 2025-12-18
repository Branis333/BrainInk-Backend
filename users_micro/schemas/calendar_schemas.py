"""
Calendar Schemas for BrainInk Platform
Handles calendar events, attendees, reminders, and views
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from enum import Enum

# === ENUMS ===

class CalendarEventTypeEnum(str, Enum):
    assignment_due = "assignment_due"
    assignment_created = "assignment_created"
    syllabus_milestone = "syllabus_milestone"
    class_schedule = "class_schedule"
    exam = "exam"
    holiday = "holiday"
    reminder = "reminder"
    custom_event = "custom_event"

class CalendarEventPriorityEnum(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    urgent = "urgent"

class CalendarEventStatusEnum(str, Enum):
    scheduled = "scheduled"
    in_progress = "in_progress"
    completed = "completed"
    cancelled = "cancelled"
    postponed = "postponed"

class AttendeeResponseEnum(str, Enum):
    pending = "pending"
    accepted = "accepted"
    declined = "declined"
    tentative = "tentative"

class AttendanceStatusEnum(str, Enum):
    unknown = "unknown"
    present = "present"
    absent = "absent"
    late = "late"
    excused = "excused"

class CalendarViewTypeEnum(str, Enum):
    day = "day"
    week = "week"
    month = "month"
    year = "year"
    agenda = "agenda"

class ReminderMethodEnum(str, Enum):
    notification = "notification"
    email = "email"
    sms = "sms"

# === BASE SCHEMAS ===

class CalendarEventBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    event_type: CalendarEventTypeEnum
    priority: CalendarEventPriorityEnum = CalendarEventPriorityEnum.medium
    status: CalendarEventStatusEnum = CalendarEventStatusEnum.scheduled
    
    # Date and time
    start_date: datetime
    end_date: Optional[datetime] = None
    all_day: bool = False
    
    # Recurrence
    is_recurring: bool = False
    recurrence_pattern: Optional[str] = None  # daily, weekly, monthly, yearly
    recurrence_interval: int = 1
    recurrence_end_date: Optional[datetime] = None
    
    # Associations
    subject_id: Optional[int] = None
    assignment_id: Optional[int] = None
    syllabus_id: Optional[int] = None
    classroom_id: Optional[int] = None
    
    # Notifications
    send_notification: bool = True
    notification_minutes_before: int = 60

class CalendarEventCreate(CalendarEventBase):
    school_id: int
    attendee_user_ids: Optional[List[int]] = []

class CalendarEventUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    event_type: Optional[CalendarEventTypeEnum] = None
    priority: Optional[CalendarEventPriorityEnum] = None
    status: Optional[CalendarEventStatusEnum] = None
    
    # Date and time
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    all_day: Optional[bool] = None
    
    # Recurrence
    is_recurring: Optional[bool] = None
    recurrence_pattern: Optional[str] = None
    recurrence_interval: Optional[int] = None
    recurrence_end_date: Optional[datetime] = None
    
    # Associations
    subject_id: Optional[int] = None
    assignment_id: Optional[int] = None
    syllabus_id: Optional[int] = None
    classroom_id: Optional[int] = None
    
    # Notifications
    send_notification: Optional[bool] = None
    notification_minutes_before: Optional[int] = None

class CalendarEventAttendeeInfo(BaseModel):
    id: int
    user_id: int
    user_name: str
    user_email: str
    student_id: Optional[int] = None
    teacher_id: Optional[int] = None
    response_status: AttendeeResponseEnum
    response_date: Optional[datetime] = None
    attendance_status: AttendanceStatusEnum
    notes: Optional[str] = None
    added_date: datetime

class CalendarEventResponse(CalendarEventBase):
    id: int
    school_id: int
    created_by: int
    creator_name: str
    created_date: datetime
    updated_date: datetime
    is_active: bool
    
    # Related entities
    subject_name: Optional[str] = None
    assignment_title: Optional[str] = None
    syllabus_title: Optional[str] = None
    classroom_name: Optional[str] = None
    
    # Attendees and reminders
    attendee_count: int = 0
    attendees: List[CalendarEventAttendeeInfo] = []
    
    class Config:
        from_attributes = True

class CalendarEventSummary(BaseModel):
    id: int
    title: str
    event_type: CalendarEventTypeEnum
    priority: CalendarEventPriorityEnum
    status: CalendarEventStatusEnum
    start_date: datetime
    end_date: Optional[datetime] = None
    all_day: bool
    subject_name: Optional[str] = None
    classroom_name: Optional[str] = None
    attendee_count: int = 0

# === ATTENDEE SCHEMAS ===

class CalendarEventAttendeeCreate(BaseModel):
    event_id: int
    user_ids: List[int]

class CalendarEventAttendeeUpdate(BaseModel):
    response_status: Optional[AttendeeResponseEnum] = None
    attendance_status: Optional[AttendanceStatusEnum] = None
    notes: Optional[str] = None

class CalendarEventAttendeeResponse(BaseModel):
    id: int
    event_id: int
    user_id: int
    student_id: Optional[int] = None
    teacher_id: Optional[int] = None
    response_status: AttendeeResponseEnum
    response_date: Optional[datetime] = None
    attendance_status: AttendanceStatusEnum
    notes: Optional[str] = None
    added_date: datetime
    is_active: bool
    
    # User info
    user_name: str
    user_email: str
    
    class Config:
        from_attributes = True

# === REMINDER SCHEMAS ===

class CalendarReminderCreate(BaseModel):
    event_id: int
    user_id: int
    reminder_minutes_before: int = Field(..., ge=0, le=10080)  # Max 1 week
    reminder_method: ReminderMethodEnum = ReminderMethodEnum.notification

class CalendarReminderUpdate(BaseModel):
    reminder_minutes_before: Optional[int] = Field(None, ge=0, le=10080)
    reminder_method: Optional[ReminderMethodEnum] = None
    is_active: Optional[bool] = None

class CalendarReminderResponse(BaseModel):
    id: int
    event_id: int
    user_id: int
    reminder_minutes_before: int
    reminder_method: ReminderMethodEnum
    is_sent: bool
    sent_date: Optional[datetime] = None
    scheduled_for: datetime
    created_date: datetime
    is_active: bool
    
    # Event info
    event_title: str
    event_start_date: datetime
    
    class Config:
        from_attributes = True

# === CALENDAR VIEW SCHEMAS ===

class CalendarViewCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    view_type: CalendarViewTypeEnum = CalendarViewTypeEnum.month
    default_view: bool = False
    show_weekends: bool = True
    start_hour: int = Field(8, ge=0, le=23)
    end_hour: int = Field(18, ge=0, le=23)
    
    # Filters
    filter_subjects: Optional[List[int]] = []
    filter_event_types: Optional[List[CalendarEventTypeEnum]] = []
    filter_priorities: Optional[List[CalendarEventPriorityEnum]] = []
    show_completed: bool = True
    
    # Color scheme
    color_scheme: Optional[Dict[str, Any]] = None

class CalendarViewUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    view_type: Optional[CalendarViewTypeEnum] = None
    default_view: Optional[bool] = None
    show_weekends: Optional[bool] = None
    start_hour: Optional[int] = Field(None, ge=0, le=23)
    end_hour: Optional[int] = Field(None, ge=0, le=23)
    
    # Filters
    filter_subjects: Optional[List[int]] = None
    filter_event_types: Optional[List[CalendarEventTypeEnum]] = None
    filter_priorities: Optional[List[CalendarEventPriorityEnum]] = None
    show_completed: Optional[bool] = None
    
    # Color scheme
    color_scheme: Optional[Dict[str, Any]] = None

class CalendarViewResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    user_id: int
    school_id: int
    view_type: CalendarViewTypeEnum
    default_view: bool
    show_weekends: bool
    start_hour: int
    end_hour: int
    
    # Filters
    filter_subjects: List[int] = []
    filter_event_types: List[CalendarEventTypeEnum] = []
    filter_priorities: List[CalendarEventPriorityEnum] = []
    show_completed: bool
    
    # Color scheme
    color_scheme: Optional[Dict[str, Any]] = None
    
    created_date: datetime
    updated_date: datetime
    is_active: bool
    
    class Config:
        from_attributes = True

# === CALENDAR DASHBOARD SCHEMAS ===

class CalendarDashboard(BaseModel):
    user_id: int
    school_id: int
    
    # Today's events
    today_events: List[CalendarEventSummary] = []
    
    # Upcoming events (next 7 days)
    upcoming_events: List[CalendarEventSummary] = []
    
    # Overdue assignments
    overdue_assignments: List[CalendarEventSummary] = []
    
    # This week summary
    week_summary: Dict[str, int] = {
        "total_events": 0,
        "assignments_due": 0,
        "exams": 0,
        "classes": 0
    }
    
    # Monthly summary
    month_summary: Dict[str, int] = {
        "total_events": 0,
        "assignments_due": 0,
        "exams": 0,
        "classes": 0,
        "completed_events": 0
    }

class CalendarFilterRequest(BaseModel):
    start_date: datetime
    end_date: datetime
    event_types: Optional[List[CalendarEventTypeEnum]] = None
    priorities: Optional[List[CalendarEventPriorityEnum]] = None
    statuses: Optional[List[CalendarEventStatusEnum]] = None
    subject_ids: Optional[List[int]] = None
    classroom_ids: Optional[List[int]] = None
    include_completed: bool = True

class CalendarEventListResponse(BaseModel):
    total_events: int
    events: List[CalendarEventResponse]
    page: int = 1
    page_size: int = 50
    total_pages: int = 1

# === INTEGRATION SCHEMAS ===

class SyllabusCalendarIntegration(BaseModel):
    syllabus_id: int
    generate_milestones: bool = True
    milestone_interval_weeks: int = 2
    create_final_exam: bool = True
    final_exam_date: Optional[datetime] = None

class AssignmentCalendarIntegration(BaseModel):
    assignment_id: int
    create_due_date_event: bool = True
    create_reminder_events: bool = True
    reminder_days_before: List[int] = [7, 3, 1]  # Days before due date
    notify_students: bool = True
    notify_teachers: bool = True

class BulkEventCreate(BaseModel):
    events: List[CalendarEventCreate]
    notify_attendees: bool = True
    
class BulkEventResponse(BaseModel):
    created_count: int
    failed_count: int
    created_events: List[CalendarEventResponse] = []
    errors: List[str] = []
