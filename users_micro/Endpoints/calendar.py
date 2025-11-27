from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, Depends, status
from typing import Annotated, List, Optional
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, and_, or_
import json
import traceback

from db.connection import db_dependency
from models.study_area_models import (
    Role, School, Subject, Student, Teacher, UserRole, Assignment, Grade,
    CalendarEvent, CalendarEventAttendee, CalendarReminder, CalendarView,
    CalendarEventType, CalendarEventPriority, CalendarEventStatus, Syllabus,
    subject_students
)
from models.users_models import User
from schemas.calendar_schemas import (
    CalendarEventCreate, CalendarEventUpdate, CalendarEventResponse,
    CalendarEventSummary, CalendarEventAttendeeCreate, CalendarEventAttendeeUpdate,
    CalendarEventAttendeeResponse, CalendarReminderCreate, CalendarReminderUpdate,
    CalendarReminderResponse, CalendarViewCreate, CalendarViewUpdate,
    CalendarViewResponse, CalendarDashboard, CalendarFilterRequest,
    CalendarEventListResponse, SyllabusCalendarIntegration,
    AssignmentCalendarIntegration, BulkEventCreate, BulkEventResponse,
    CalendarEventAttendeeInfo
)
from Endpoints.auth import get_current_user
# Import shared utility functions
from Endpoints.utils import (
    _get_user_roles, check_user_role, ensure_user_role, check_user_has_any_role, 
    ensure_user_has_any_role
)

router = APIRouter(tags=["Calendar Management", "Events", "Reminders"])

user_dependency = Annotated[dict, Depends(get_current_user)]

# === CALENDAR EVENT ENDPOINTS ===

@router.post("/events/create", response_model=CalendarEventResponse)
async def create_calendar_event(
    event: CalendarEventCreate,
    db: db_dependency,
    current_user: user_dependency
):
    """
    Create a new calendar event (all authenticated users)
    """
    ensure_user_has_any_role(
        db, 
        current_user["user_id"], 
        [UserRole.principal, UserRole.teacher, UserRole.student]
    )
    
    # Verify user has access to the school
    user_roles = _get_user_roles(db, current_user["user_id"])
    
    if UserRole.principal in user_roles:
        # Principal must own the school
        school = db.query(School).filter(
            School.id == event.school_id,
            School.principal_id == current_user["user_id"]
        ).first()
        if not school:
            raise HTTPException(status_code=404, detail="School not found or not managed by you")
    
    elif UserRole.teacher in user_roles:
        # Teacher must belong to the school
        teacher = db.query(Teacher).filter(
            Teacher.user_id == current_user["user_id"],
            Teacher.school_id == event.school_id
        ).first()
        if not teacher:
            raise HTTPException(status_code=404, detail="You don't have access to this school")
    
    elif UserRole.student in user_roles:
        # Student must belong to the school
        student = db.query(Student).filter(
            Student.user_id == current_user["user_id"],
            Student.school_id == event.school_id
        ).first()
        if not student:
            raise HTTPException(status_code=404, detail="You don't have access to this school")
    
    # Validate associations
    if event.subject_id:
        subject = db.query(Subject).filter(
            Subject.id == event.subject_id,
            Subject.school_id == event.school_id
        ).first()
        if not subject:
            raise HTTPException(status_code=404, detail="Subject not found in this school")
    
    if event.assignment_id:
        assignment = db.query(Assignment).join(Subject).filter(
            Assignment.id == event.assignment_id,
            Subject.school_id == event.school_id
        ).first()
        if not assignment:
            # For students, also check if they have access to the assignment through their subjects
            if UserRole.student in user_roles:
                student = db.query(Student).filter(
                    Student.user_id == current_user["user_id"],
                    Student.school_id == event.school_id
                ).first()
                if student:
                    # Check if assignment exists in any of the student's subjects
                    assignment = db.query(Assignment).join(Subject).join(subject_students).filter(
                        Assignment.id == event.assignment_id,
                        subject_students.c.student_id == student.id
                    ).first()
            
            if not assignment:
                raise HTTPException(status_code=404, detail="Assignment not found or not accessible")
    
    if event.syllabus_id:
        syllabus = db.query(Syllabus).join(Subject).filter(
            Syllabus.id == event.syllabus_id,
            Subject.school_id == event.school_id
        ).first()
        if not syllabus:
            # For students, also check if they have access to the syllabus through their subjects
            if UserRole.student in user_roles:
                student = db.query(Student).filter(
                    Student.user_id == current_user["user_id"],
                    Student.school_id == event.school_id
                ).first()
                if student:
                    # Check if syllabus exists in any of the student's subjects
                    syllabus = db.query(Syllabus).join(Subject).join(subject_students).filter(
                        Syllabus.id == event.syllabus_id,
                        subject_students.c.student_id == student.id
                    ).first()
            
            if not syllabus:
                raise HTTPException(status_code=404, detail="Syllabus not found or not accessible")
    
    try:
        # Create the calendar event
        db_event = CalendarEvent(
            title=event.title,
            description=event.description,
            event_type=CalendarEventType(event.event_type),
            priority=CalendarEventPriority(event.priority),
            status=CalendarEventStatus(getattr(event, 'status', 'scheduled')),
            start_date=event.start_date,
            end_date=event.end_date,
            all_day=event.all_day,
            is_recurring=event.is_recurring,
            recurrence_pattern=event.recurrence_pattern,
            recurrence_interval=event.recurrence_interval,
            recurrence_end_date=event.recurrence_end_date,
            school_id=event.school_id,
            subject_id=event.subject_id,
            assignment_id=event.assignment_id,
            syllabus_id=event.syllabus_id,
            classroom_id=event.classroom_id,
            created_by=current_user["user_id"],
            send_notification=event.send_notification,
            notification_minutes_before=event.notification_minutes_before
        )
        
        db.add(db_event)
        db.flush()  # Get the event ID
        
        # Add attendees if specified
        if event.attendee_user_ids:
            for user_id in event.attendee_user_ids:
                # Verify user exists and has access to the school
                user = db.query(User).filter(User.id == user_id).first()
                if user:
                    # Get student or teacher profile
                    student = db.query(Student).filter(
                        Student.user_id == user_id,
                        Student.school_id == event.school_id
                    ).first()
                    teacher = db.query(Teacher).filter(
                        Teacher.user_id == user_id,
                        Teacher.school_id == event.school_id
                    ).first()
                    
                    if student or teacher:
                        attendee = CalendarEventAttendee(
                            event_id=db_event.id,
                            user_id=user_id,
                            student_id=student.id if student else None,
                            teacher_id=teacher.id if teacher else None
                        )
                        db.add(attendee)
        
        db.commit()
        db.refresh(db_event)
        
        # Return the created event with full details
        return await _get_calendar_event_response(db, db_event)
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Event creation error: {str(e)}")

@router.get("/events/{event_id}", response_model=CalendarEventResponse)
async def get_calendar_event(
    event_id: int,
    db: db_dependency,
    current_user: user_dependency
):
    """
    Get calendar event details
    """
    ensure_user_has_any_role(
        db, 
        current_user["user_id"], 
        [UserRole.principal, UserRole.teacher, UserRole.student]
    )
    
    event = db.query(CalendarEvent).options(
        joinedload(CalendarEvent.attendees),
        joinedload(CalendarEvent.subject),
        joinedload(CalendarEvent.assignment),
        joinedload(CalendarEvent.syllabus),
        joinedload(CalendarEvent.classroom),
        joinedload(CalendarEvent.creator)
    ).filter(CalendarEvent.id == event_id).first()
    
    if not event:
        raise HTTPException(status_code=404, detail="Calendar event not found")
    
    # Check access permissions
    has_access = await _check_event_access(db, event, current_user["user_id"])
    if not has_access:
        raise HTTPException(status_code=403, detail="Access denied to this event")
    
    return await _get_calendar_event_response(db, event)

@router.put("/events/{event_id}", response_model=CalendarEventResponse)
async def update_calendar_event(
    event_id: int,
    event_update: CalendarEventUpdate,
    db: db_dependency,
    current_user: user_dependency
):
    """
    Update calendar event (creator or principals only)
    """
    ensure_user_has_any_role(
        db, 
        current_user["user_id"], 
        [UserRole.principal, UserRole.teacher, UserRole.student]
    )
    
    event = db.query(CalendarEvent).filter(CalendarEvent.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Calendar event not found")
    
    # Check permissions - must be creator or principal of the school
    user_roles = _get_user_roles(db, current_user["user_id"])
    
    if event.created_by != current_user["user_id"]:
        if UserRole.principal not in user_roles:
            raise HTTPException(status_code=403, detail="Only event creator or principal can update events")
        
        # If principal, verify they manage the school
        if UserRole.principal in user_roles:
            school = db.query(School).filter(
                School.id == event.school_id,
                School.principal_id == current_user["user_id"]
            ).first()
            if not school:
                raise HTTPException(status_code=403, detail="Access denied")
    
    try:
        # Update fields
        update_data = event_update.dict(exclude_unset=True)
        for field, value in update_data.items():
            if hasattr(event, field):
                if field in ["event_type", "priority", "status"]:
                    # Handle enum fields
                    if field == "event_type" and value:
                        value = CalendarEventType(value)
                    elif field == "priority" and value:
                        value = CalendarEventPriority(value)
                    elif field == "status" and value:
                        value = CalendarEventStatus(value)
                setattr(event, field, value)
        
        event.updated_date = datetime.utcnow()
        db.commit()
        db.refresh(event)
        
        return await _get_calendar_event_response(db, event)
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Event update error: {str(e)}")

@router.delete("/events/{event_id}")
async def delete_calendar_event(
    event_id: int,
    db: db_dependency,
    current_user: user_dependency
):
    """
    Delete calendar event (creator or principals only)
    """
    ensure_user_has_any_role(
        db, 
        current_user["user_id"], 
        [UserRole.principal, UserRole.teacher, UserRole.student]
    )
    
    event = db.query(CalendarEvent).filter(CalendarEvent.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Calendar event not found")
    
    # Check permissions - must be creator or principal of the school
    user_roles = _get_user_roles(db, current_user["user_id"])
    
    if event.created_by != current_user["user_id"]:
        if UserRole.principal not in user_roles:
            raise HTTPException(status_code=403, detail="Only event creator or principal can delete events")
        
        # If principal, verify they manage the school
        school = db.query(School).filter(
            School.id == event.school_id,
            School.principal_id == current_user["user_id"]
        ).first()
        if not school:
            raise HTTPException(status_code=403, detail="Access denied")
    
    try:
        # Soft delete
        event.is_active = False
        event.updated_date = datetime.utcnow()
        db.commit()
        
        return {"message": "Calendar event deleted successfully"}
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Event deletion error: {str(e)}")

@router.get("/events", response_model=CalendarEventListResponse)
async def get_calendar_events(
    db: db_dependency,
    current_user: user_dependency,
    page: int = 1,
    page_size: int = 50,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    event_types: Optional[str] = None,  # Comma-separated list
    priorities: Optional[str] = None,   # Comma-separated list
    statuses: Optional[str] = None,     # Comma-separated list
    subject_ids: Optional[str] = None,  # Comma-separated list
    include_completed: bool = True
):
    """
    Get calendar events with filtering and pagination
    """
    ensure_user_has_any_role(
        db, 
        current_user["user_id"], 
        [UserRole.principal, UserRole.teacher, UserRole.student]
    )
    
    # Get user's accessible schools
    accessible_school_ids = await _get_user_accessible_schools(db, current_user["user_id"])
    
    # Build query
    query = db.query(CalendarEvent).filter(
        CalendarEvent.school_id.in_(accessible_school_ids),
        CalendarEvent.is_active == True
    )
    
    # Apply filters
    if start_date:
        query = query.filter(CalendarEvent.start_date >= start_date)
    if end_date:
        query = query.filter(CalendarEvent.start_date <= end_date)
    
    if not include_completed:
        query = query.filter(CalendarEvent.status != CalendarEventStatus.completed)
    
    if event_types:
        type_list = [CalendarEventType(t.strip()) for t in event_types.split(",")]
        query = query.filter(CalendarEvent.event_type.in_(type_list))
    
    if priorities:
        priority_list = [CalendarEventPriority(p.strip()) for p in priorities.split(",")]
        query = query.filter(CalendarEvent.priority.in_(priority_list))
    
    if statuses:
        status_list = [CalendarEventStatus(s.strip()) for s in statuses.split(",")]
        query = query.filter(CalendarEvent.status.in_(status_list))
    
    if subject_ids:
        subject_id_list = [int(s.strip()) for s in subject_ids.split(",")]
        query = query.filter(CalendarEvent.subject_id.in_(subject_id_list))
    
    # Get total count
    total_events = query.count()
    
    # Apply pagination
    offset = (page - 1) * page_size
    events = query.order_by(CalendarEvent.start_date.asc()).offset(offset).limit(page_size).all()
    
    # Convert to response format
    event_responses = []
    for event in events:
        event_response = await _get_calendar_event_response(db, event)
        event_responses.append(event_response)
    
    total_pages = (total_events + page_size - 1) // page_size
    
    return CalendarEventListResponse(
        total_events=total_events,
        events=event_responses,
        page=page,
        page_size=page_size,
        total_pages=total_pages
    )

# === CALENDAR DASHBOARD ENDPOINTS ===

@router.get("/dashboard", response_model=CalendarDashboard)
async def get_calendar_dashboard(
    db: db_dependency,
    current_user: user_dependency
):
    """
    Get calendar dashboard with today's events, upcoming events, and summaries
    """
    ensure_user_has_any_role(
        db, 
        current_user["user_id"], 
        [UserRole.principal, UserRole.teacher, UserRole.student]
    )
    
    # Get user's accessible schools
    accessible_school_ids = await _get_user_accessible_schools(db, current_user["user_id"])
    
    now = datetime.utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start + timedelta(days=1)
    week_end = today_start + timedelta(days=7)
    month_start = today_start.replace(day=1)
    month_end = (month_start + timedelta(days=32)).replace(day=1)
    
    # Get today's events
    today_events_query = db.query(CalendarEvent).filter(
        CalendarEvent.school_id.in_(accessible_school_ids),
        CalendarEvent.is_active == True,
        CalendarEvent.start_date >= today_start,
        CalendarEvent.start_date < today_end
    ).order_by(CalendarEvent.start_date.asc())
    
    today_events = [_convert_to_event_summary(event) for event in today_events_query.all()]
    
    # Get upcoming events (next 7 days, excluding today)
    upcoming_events_query = db.query(CalendarEvent).filter(
        CalendarEvent.school_id.in_(accessible_school_ids),
        CalendarEvent.is_active == True,
        CalendarEvent.start_date >= today_end,
        CalendarEvent.start_date < week_end
    ).order_by(CalendarEvent.start_date.asc()).limit(10)
    
    upcoming_events = [_convert_to_event_summary(event) for event in upcoming_events_query.all()]
    
    # Get overdue assignments
    overdue_query = db.query(CalendarEvent).filter(
        CalendarEvent.school_id.in_(accessible_school_ids),
        CalendarEvent.is_active == True,
        CalendarEvent.event_type == CalendarEventType.assignment_due,
        CalendarEvent.start_date < now,
        CalendarEvent.status.in_([CalendarEventStatus.scheduled, CalendarEventStatus.in_progress])
    ).order_by(CalendarEvent.start_date.desc()).limit(5)
    
    overdue_assignments = [_convert_to_event_summary(event) for event in overdue_query.all()]
    
    # Week summary
    week_events = db.query(CalendarEvent).filter(
        CalendarEvent.school_id.in_(accessible_school_ids),
        CalendarEvent.is_active == True,
        CalendarEvent.start_date >= today_start,
        CalendarEvent.start_date < week_end
    ).all()
    
    week_summary = {
        "total_events": len(week_events),
        "assignments_due": len([e for e in week_events if e.event_type == CalendarEventType.assignment_due]),
        "exams": len([e for e in week_events if e.event_type == CalendarEventType.exam]),
        "classes": len([e for e in week_events if e.event_type == CalendarEventType.class_schedule])
    }
    
    # Month summary
    month_events = db.query(CalendarEvent).filter(
        CalendarEvent.school_id.in_(accessible_school_ids),
        CalendarEvent.is_active == True,
        CalendarEvent.start_date >= month_start,
        CalendarEvent.start_date < month_end
    ).all()
    
    month_summary = {
        "total_events": len(month_events),
        "assignments_due": len([e for e in month_events if e.event_type == CalendarEventType.assignment_due]),
        "exams": len([e for e in month_events if e.event_type == CalendarEventType.exam]),
        "classes": len([e for e in month_events if e.event_type == CalendarEventType.class_schedule]),
        "completed_events": len([e for e in month_events if e.status == CalendarEventStatus.completed])
    }
    
    return CalendarDashboard(
        user_id=current_user["user_id"],
        school_id=accessible_school_ids[0] if accessible_school_ids else 0,
        today_events=today_events,
        upcoming_events=upcoming_events,
        overdue_assignments=overdue_assignments,
        week_summary=week_summary,
        month_summary=month_summary
    )

# === INTEGRATION ENDPOINTS ===

@router.post("/integrate/assignment")
async def integrate_assignment_with_calendar(
    integration: AssignmentCalendarIntegration,
    db: db_dependency,
    current_user: user_dependency
):
    """
    Integrate assignment with calendar (create due date events and reminders)
    """
    ensure_user_has_any_role(
        db, 
        current_user["user_id"], 
        [UserRole.principal, UserRole.teacher]
    )
    
    # Get assignment and verify access
    assignment = db.query(Assignment).join(Subject).filter(
        Assignment.id == integration.assignment_id
    ).first()
    
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")
    
    # Verify user has access to the assignment
    user_roles = _get_user_roles(db, current_user["user_id"])
    
    if UserRole.teacher in user_roles and assignment.teacher_id != db.query(Teacher).filter(Teacher.user_id == current_user["user_id"]).first().id:
        raise HTTPException(status_code=403, detail="Access denied to this assignment")
    
    if UserRole.principal in user_roles:
        school = db.query(School).filter(
            School.id == assignment.subject.school_id,
            School.principal_id == current_user["user_id"]
        ).first()
        if not school:
            raise HTTPException(status_code=403, detail="Access denied")
    
    created_events = []
    
    try:
        # Create due date event if requested and due date exists
        if integration.create_due_date_event and assignment.due_date:
            due_event = CalendarEvent(
                title=f"Assignment Due: {assignment.title}",
                description=f"Assignment: {assignment.title}\nSubject: {assignment.subject.name}\nDescription: {assignment.description[:200]}...",
                event_type=CalendarEventType.assignment_due,
                priority=CalendarEventPriority.high,
                status=CalendarEventStatus.scheduled,
                start_date=assignment.due_date,
                all_day=True,
                school_id=assignment.subject.school_id,
                subject_id=assignment.subject_id,
                assignment_id=assignment.id,
                created_by=current_user["user_id"],
                send_notification=True,
                notification_minutes_before=60
            )
            db.add(due_event)
            db.flush()
            created_events.append(due_event)
            
            # Create reminder events if requested
            if integration.create_reminder_events and integration.reminder_days_before:
                for days_before in integration.reminder_days_before:
                    reminder_date = assignment.due_date - timedelta(days=days_before)
                    if reminder_date > datetime.utcnow():
                        reminder_event = CalendarEvent(
                            title=f"Reminder: {assignment.title} due in {days_before} days",
                            description=f"Assignment: {assignment.title}\nSubject: {assignment.subject.name}\nDue: {assignment.due_date.strftime('%Y-%m-%d')}",
                            event_type=CalendarEventType.reminder,
                            priority=CalendarEventPriority.medium,
                            status=CalendarEventStatus.scheduled,
                            start_date=reminder_date,
                            all_day=True,
                            school_id=assignment.subject.school_id,
                            subject_id=assignment.subject_id,
                            assignment_id=assignment.id,
                            created_by=current_user["user_id"],
                            send_notification=True,
                            notification_minutes_before=60
                        )
                        db.add(reminder_event)
                        db.flush()
                        created_events.append(reminder_event)
        
        db.commit()
        
        return {
            "message": f"Successfully created {len(created_events)} calendar events for assignment",
            "created_events": len(created_events),
            "assignment_title": assignment.title
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Integration error: {str(e)}")

@router.post("/integrate/syllabus")
async def integrate_syllabus_with_calendar(
    integration: SyllabusCalendarIntegration,
    db: db_dependency,
    current_user: user_dependency
):
    """
    Integrate syllabus with calendar (create milestone events)
    """
    ensure_user_has_any_role(
        db, 
        current_user["user_id"], 
        [UserRole.principal, UserRole.teacher]
    )
    
    # Get syllabus and verify access
    syllabus = db.query(Syllabus).join(Subject).filter(
        Syllabus.id == integration.syllabus_id
    ).first()
    
    if not syllabus:
        raise HTTPException(status_code=404, detail="Syllabus not found")
    
    # Verify user has access to the syllabus
    user_roles = _get_user_roles(db, current_user["user_id"])
    
    if UserRole.principal in user_roles:
        school = db.query(School).filter(
            School.id == syllabus.subject.school_id,
            School.principal_id == current_user["user_id"]
        ).first()
        if not school:
            raise HTTPException(status_code=403, detail="Access denied")
    
    elif UserRole.teacher in user_roles:
        # Check if teacher is assigned to the subject
        teacher = db.query(Teacher).filter(Teacher.user_id == current_user["user_id"]).first()
        if not teacher or syllabus.subject not in teacher.subjects:
            raise HTTPException(status_code=403, detail="Access denied to this syllabus")
    
    created_events = []
    
    try:
        # Create milestone events if requested
        if integration.generate_milestones:
            start_date = datetime.utcnow()
            weeks = integration.milestone_interval_weeks
            total_weeks = syllabus.term_length_weeks
            
            milestone_count = 1
            current_week = weeks
            
            while current_week <= total_weeks:
                milestone_date = start_date + timedelta(weeks=current_week)
                
                milestone_event = CalendarEvent(
                    title=f"Syllabus Milestone {milestone_count}: {syllabus.title}",
                    description=f"Syllabus: {syllabus.title}\nSubject: {syllabus.subject.name}\nMilestone {milestone_count} - Week {current_week}",
                    event_type=CalendarEventType.syllabus_milestone,
                    priority=CalendarEventPriority.medium,
                    status=CalendarEventStatus.scheduled,
                    start_date=milestone_date,
                    all_day=True,
                    school_id=syllabus.subject.school_id,
                    subject_id=syllabus.subject_id,
                    syllabus_id=syllabus.id,
                    created_by=current_user["user_id"],
                    send_notification=True,
                    notification_minutes_before=1440  # 24 hours before
                )
                db.add(milestone_event)
                db.flush()
                created_events.append(milestone_event)
                
                milestone_count += 1
                current_week += weeks
        
        # Create final exam event if requested
        if integration.create_final_exam:
            final_exam_date = integration.final_exam_date
            if not final_exam_date:
                # Default to end of term
                final_exam_date = datetime.utcnow() + timedelta(weeks=syllabus.term_length_weeks)
            
            exam_event = CalendarEvent(
                title=f"Final Exam: {syllabus.subject.name}",
                description=f"Final examination for {syllabus.subject.name}\nSyllabus: {syllabus.title}",
                event_type=CalendarEventType.exam,
                priority=CalendarEventPriority.high,
                status=CalendarEventStatus.scheduled,
                start_date=final_exam_date,
                all_day=False,
                school_id=syllabus.subject.school_id,
                subject_id=syllabus.subject_id,
                syllabus_id=syllabus.id,
                created_by=current_user["user_id"],
                send_notification=True,
                notification_minutes_before=2880  # 48 hours before
            )
            db.add(exam_event)
            db.flush()
            created_events.append(exam_event)
        
        db.commit()
        
        return {
            "message": f"Successfully created {len(created_events)} calendar events for syllabus",
            "created_events": len(created_events),
            "syllabus_title": syllabus.title
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Integration error: {str(e)}")

@router.post("/auto-integrate-assignments")
async def auto_integrate_assignments(
    db: db_dependency,
    current_user: user_dependency
):
    """
    Manually trigger automatic integration of assignments (with or without due dates)
    """
    ensure_user_has_any_role(
        db, 
        current_user["user_id"], 
        [UserRole.principal, UserRole.teacher, UserRole.student]
    )
    
    try:
        # Get user's accessible schools
        accessible_school_ids = await _get_user_accessible_schools(db, current_user["user_id"])
        
        # Get all assignments (both with and without due dates)
        assignments = db.query(Assignment).join(Subject).filter(
            Subject.school_id.in_(accessible_school_ids),
            Assignment.is_active == True
        ).all()
        
        created_events = 0
        
        for assignment in assignments:
            # Check if event already exists
            existing_event = db.query(CalendarEvent).filter(
                CalendarEvent.assignment_id == assignment.id,
                CalendarEvent.is_active == True
            ).first()
            
            if not existing_event:
                if assignment.due_date:
                    # Create assignment due event
                    event = CalendarEvent(
                        title=f"Assignment Due: {assignment.title}",
                        description=f"Assignment: {assignment.title}\nSubject: {assignment.subject.name}\nDue Date: {assignment.due_date.strftime('%Y-%m-%d')}",
                        event_type=CalendarEventType.assignment_due,
                        priority=CalendarEventPriority.high,
                        status=CalendarEventStatus.scheduled,
                        start_date=assignment.due_date,
                        end_date=assignment.due_date,
                        all_day=True,
                        school_id=assignment.subject.school_id,
                        subject_id=assignment.subject_id,
                        assignment_id=assignment.id,
                        created_by=current_user["user_id"],
                        send_notification=True,
                        notification_minutes_before=1440  # 24 hours before
                    )
                else:
                    # Create assignment created event (no due date)
                    today = datetime.utcnow().replace(hour=9, minute=0, second=0, microsecond=0)  # 9 AM today
                    
                    event = CalendarEvent(
                        title=f"Assignment: {assignment.title}",
                        description=f"Assignment: {assignment.title}\nSubject: {assignment.subject.name}\n\nNote: This assignment has no due date set.",
                        event_type=CalendarEventType.assignment_created,
                        priority=CalendarEventPriority.medium,
                        status=CalendarEventStatus.scheduled,
                        start_date=today,
                        end_date=today,
                        all_day=False,
                        school_id=assignment.subject.school_id,
                        subject_id=assignment.subject_id,
                        assignment_id=assignment.id,
                        created_by=current_user["user_id"],
                        send_notification=True,
                        notification_minutes_before=60  # 1 hour before
                    )
                
                db.add(event)
                created_events += 1
        
        db.commit()
        
        return {
            "message": f"Successfully integrated {created_events} assignments",
            "created_events": created_events,
            "total_assignments": len(assignments),
            "with_due_dates": len([a for a in assignments if a.due_date]),
            "without_due_dates": len([a for a in assignments if not a.due_date])
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Integration error: {str(e)}")

@router.get("/my-calendar")
async def get_my_calendar_events(
    db: db_dependency,
    current_user: user_dependency,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None
):
    """
    Get calendar events for the current user (student-specific view)
    """
    ensure_user_has_any_role(
        db, 
        current_user["user_id"], 
        [UserRole.principal, UserRole.teacher, UserRole.student]
    )
    
    # Get user's accessible schools
    accessible_school_ids = await _get_user_accessible_schools(db, current_user["user_id"])
    
    if not start_date:
        start_date = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    
    if not end_date:
        end_date = start_date + timedelta(days=30)  # Default to next 30 days
    
    # Build query for events in user's schools
    query = db.query(CalendarEvent).filter(
        CalendarEvent.school_id.in_(accessible_school_ids),
        CalendarEvent.is_active == True,
        CalendarEvent.start_date >= start_date,
        CalendarEvent.start_date <= end_date
    )
    
    # For students, also include events they're attendees of
    user_roles = _get_user_roles(db, current_user["user_id"])
    if UserRole.student in user_roles:
        attendee_events_query = db.query(CalendarEvent).join(CalendarEventAttendee).filter(
            CalendarEventAttendee.user_id == current_user["user_id"],
            CalendarEventAttendee.is_active == True,
            CalendarEvent.is_active == True,
            CalendarEvent.start_date >= start_date,
            CalendarEvent.start_date <= end_date
        )
        
        # Combine queries
        events = query.union(attendee_events_query).order_by(CalendarEvent.start_date.asc()).all()
    else:
        events = query.order_by(CalendarEvent.start_date.asc()).all()
    
    # Convert to response format
    event_responses = []
    for event in events:
        event_response = await _get_calendar_event_response(db, event)
        event_responses.append(event_response)
    
    return {
        "user_id": current_user["user_id"],
        "events": event_responses,
        "total_events": len(event_responses),
        "date_range": {
            "start_date": start_date,
            "end_date": end_date
        }
    }

# === UTILITY FUNCTIONS ===

async def _get_calendar_event_response(db: Session, event: CalendarEvent) -> CalendarEventResponse:
    """Convert CalendarEvent model to CalendarEventResponse"""
    
    # Get creator info
    creator = db.query(User).filter(User.id == event.created_by).first()
    creator_name = "Unknown"
    if creator:
        fname = getattr(creator, 'fname', '') or ''
        lname = getattr(creator, 'lname', '') or ''
        creator_name = f"{fname} {lname}".strip() or "Unknown"
    
    # Get related entity names
    subject_name = event.subject.name if event.subject else None
    assignment_title = event.assignment.title if event.assignment else None
    syllabus_title = event.syllabus.title if event.syllabus else None
    classroom_name = event.classroom.name if event.classroom else None
    
    # Get attendees
    attendees = []
    attendee_count = 0
    
    if hasattr(event, 'attendees') and event.attendees:
        for attendee in event.attendees:
            if attendee.is_active:
                user = db.query(User).filter(User.id == attendee.user_id).first()
                if user:
                    fname = getattr(user, 'fname', '') or ''
                    lname = getattr(user, 'lname', '') or ''
                    user_name = f"{fname} {lname}".strip() or "Unknown User"
                    
                    attendee_info = CalendarEventAttendeeInfo(
                        id=attendee.id,
                        user_id=attendee.user_id,
                        user_name=user_name,
                        user_email=user.email or '',
                        student_id=attendee.student_id,
                        teacher_id=attendee.teacher_id,
                        response_status=attendee.response_status,
                        response_date=attendee.response_date,
                        attendance_status=attendee.attendance_status,
                        notes=attendee.notes,
                        added_date=attendee.added_date
                    )
                    attendees.append(attendee_info)
                    attendee_count += 1
    
    return CalendarEventResponse(
        id=event.id,
        title=event.title,
        description=event.description,
        event_type=event.event_type.value,
        priority=event.priority.value,
        status=event.status.value,
        start_date=event.start_date,
        end_date=event.end_date,
        all_day=event.all_day,
        is_recurring=event.is_recurring,
        recurrence_pattern=event.recurrence_pattern,
        recurrence_interval=event.recurrence_interval,
        recurrence_end_date=event.recurrence_end_date,
        subject_id=event.subject_id,
        assignment_id=event.assignment_id,
        syllabus_id=event.syllabus_id,
        classroom_id=event.classroom_id,
        send_notification=event.send_notification,
        notification_minutes_before=event.notification_minutes_before,
        school_id=event.school_id,
        created_by=event.created_by,
        creator_name=creator_name,
        created_date=event.created_date,
        updated_date=event.updated_date,
        is_active=event.is_active,
        subject_name=subject_name,
        assignment_title=assignment_title,
        syllabus_title=syllabus_title,
        classroom_name=classroom_name,
        attendee_count=attendee_count,
        attendees=attendees
    )

def _convert_to_event_summary(event: CalendarEvent) -> CalendarEventSummary:
    """Convert CalendarEvent to CalendarEventSummary"""
    return CalendarEventSummary(
        id=event.id,
        title=event.title,
        event_type=event.event_type.value,
        priority=event.priority.value,
        status=event.status.value,
        start_date=event.start_date,
        end_date=event.end_date,
        all_day=event.all_day,
        subject_name=event.subject.name if event.subject else None,
        classroom_name=event.classroom.name if event.classroom else None,
        attendee_count=len([a for a in event.attendees if a.is_active]) if hasattr(event, 'attendees') else 0
    )

async def _check_event_access(db: Session, event: CalendarEvent, user_id: int) -> bool:
    """Check if user has access to the calendar event"""
    user_roles = _get_user_roles(db, user_id)
    
    # Principals have access to all events in their school
    if UserRole.principal in user_roles:
        school = db.query(School).filter(
            School.id == event.school_id,
            School.principal_id == user_id
        ).first()
        if school:
            return True
    
    # Teachers have access to events in their school
    if UserRole.teacher in user_roles:
        teacher = db.query(Teacher).filter(
            Teacher.user_id == user_id,
            Teacher.school_id == event.school_id
        ).first()
        if teacher:
            return True
    
    # Students have access to events in their school
    if UserRole.student in user_roles:
        student = db.query(Student).filter(
            Student.user_id == user_id,
            Student.school_id == event.school_id
        ).first()
        if student:
            return True
    
    # Check if user is an attendee
    attendee = db.query(CalendarEventAttendee).filter(
        CalendarEventAttendee.event_id == event.id,
        CalendarEventAttendee.user_id == user_id,
        CalendarEventAttendee.is_active == True
    ).first()
    if attendee:
        return True
    
    return False

async def _get_user_accessible_schools(db: Session, user_id: int) -> List[int]:
    """Get list of school IDs that the user has access to"""
    school_ids = []
    user_roles = _get_user_roles(db, user_id)
    
    # Principal - schools they manage
    if UserRole.principal in user_roles:
        schools = db.query(School).filter(School.principal_id == user_id).all()
        school_ids.extend([school.id for school in schools])
    
    # Teacher - schools they belong to
    if UserRole.teacher in user_roles:
        teacher = db.query(Teacher).filter(Teacher.user_id == user_id).first()
        if teacher:
            school_ids.append(teacher.school_id)
    
    # Student - schools they belong to
    if UserRole.student in user_roles:
        student = db.query(Student).filter(Student.user_id == user_id).first()
        if student:
            school_ids.append(student.school_id)
    
    return list(set(school_ids))  # Remove duplicates