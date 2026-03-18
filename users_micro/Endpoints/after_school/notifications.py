"""
After-School Notification System Endpoints

Comprehensive notification management for:
1. Due Date Notifications - Alerts when assignments are due soon
2. Daily Encouragement - Daily motivational messages
3. Completion Notifications - Congratulations when courses/blocks complete

Features:
- Push notification support with token management (FCM, Expo)
- Persistent notification storage and history
- User preferences and opt-in management
- Scheduled notification delivery
- Read/dismissal tracking
"""

from datetime import datetime, timedelta
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, or_, desc, asc
from pydantic import BaseModel, Field

from db.connection import db_dependency
from Endpoints.auth import get_current_user
from models.afterschool_models import (
    Notification, 
    NotificationPreference,
    StudentAssignment,
    Course,
    CourseAssignment
)

router = APIRouter(prefix="/after-school/notifications", tags=["After-School Notifications"])

user_dependency = Depends(get_current_user)


# ===============================
# PYDANTIC SCHEMAS
# ===============================

class NotificationPreferenceUpdate(BaseModel):
    """Update user notification preferences"""
    due_date_notifications: Optional[bool] = None
    daily_encouragement: Optional[bool] = None
    completion_notifications: Optional[bool] = None
    push_notifications_enabled: Optional[bool] = None
    push_token: Optional[str] = None
    due_date_days_before: Optional[int] = Field(None, ge=0, le=7)
    daily_encouragement_time: Optional[str] = None  # HH:MM format


class NotificationOut(BaseModel):
    """Notification response schema"""
    id: int
    user_id: int
    type: str  # due_date, daily_encouragement, completion
    title: str
    body: str
    course_id: Optional[int] = None
    assignment_id: Optional[int] = None
    block_id: Optional[int] = None
    status: str
    is_read: bool
    read_at: Optional[datetime] = None
    dismissed_at: Optional[datetime] = None
    created_at: datetime
    
    class Config:
        from_attributes = True


class NotificationPreferenceOut(BaseModel):
    """Notification preference response schema"""
    id: int
    user_id: int
    due_date_notifications: bool
    daily_encouragement: bool
    completion_notifications: bool
    push_notifications_enabled: bool
    push_token: Optional[str] = None
    due_date_days_before: int
    daily_encouragement_time: str
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class NotificationStatsOut(BaseModel):
    """Summary of notification statistics"""
    total_unread: int
    due_date_unread: int
    daily_encouragement_unread: int
    completion_unread: int
    total_dismissed: int


# ===============================
# PREFERENCE MANAGEMENT ENDPOINTS
# ===============================

@router.get("/preferences", response_model=NotificationPreferenceOut)
async def get_notification_preferences(
    db: db_dependency,
    current_user: dict = user_dependency
):
    """
    Get user's notification preferences and settings
    
    Returns current notification opt-in status, push token, and delivery preferences.
    If user has no preferences set, creates defaults.
    """
    user_id = current_user["user_id"]
    
    prefs = db.query(NotificationPreference).filter(
        NotificationPreference.user_id == user_id
    ).first()
    
    if not prefs:
        # Auto-create default preferences for new user
        prefs = NotificationPreference(
            user_id=user_id,
            due_date_notifications=True,
            daily_encouragement=True,
            completion_notifications=True,
            push_notifications_enabled=False,
            due_date_days_before=1,
            daily_encouragement_time="09:00"
        )
        db.add(prefs)
        db.commit()
        db.refresh(prefs)
        print(f"✅ Created default notification preferences for user {user_id}")
    
    return prefs


@router.put("/preferences", response_model=NotificationPreferenceOut)
async def update_notification_preferences(
    preferences: NotificationPreferenceUpdate,
    db: db_dependency,
    current_user: dict = user_dependency
):
    """
    Update user's notification preferences
    
    Allows users to:
    - Enable/disable specific notification types
    - Register push notification token (FCM, Expo)
    - Set notification delivery time preferences
    - Control notification frequency
    
    Example push tokens:
    - Expo: "ExponentPushToken[...]"
    - FCM: "Firebase Cloud Messaging token string"
    """
    user_id = current_user["user_id"]
    
    try:
        prefs = db.query(NotificationPreference).filter(
            NotificationPreference.user_id == user_id
        ).first()
        
        if not prefs:
            # Create if doesn't exist
            prefs = NotificationPreference(user_id=user_id)
            db.add(prefs)
        
        # Update only provided fields
        update_data = preferences.dict(exclude_unset=True)
        for field, value in update_data.items():
            if value is not None:
                setattr(prefs, field, value)
        
        db.commit()
        db.refresh(prefs)
        
        # Log the update
        enabled_types = []
        if prefs.due_date_notifications:
            enabled_types.append("due_dates")
        if prefs.daily_encouragement:
            enabled_types.append("daily_encouragement")
        if prefs.completion_notifications:
            enabled_types.append("completion")
        
        push_status = "enabled" if prefs.push_notifications_enabled else "disabled"
        print(f"✅ Updated notification preferences for user {user_id}: types={enabled_types}, push={push_status}")
        
        return prefs
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update preferences: {str(e)}"
        )


# ===============================
# NOTIFICATION RETRIEVAL ENDPOINTS
# ===============================

@router.get("/", response_model=List[NotificationOut])
async def list_notifications(
    db: db_dependency,
    current_user: dict = user_dependency,
    notification_type: Optional[str] = Query(None, description="Filter by type: due_date, daily_encouragement, completion"),
    is_read: Optional[bool] = Query(None, description="Filter by read status"),
    limit: int = Query(50, ge=1, le=200, description="Max notifications to return"),
    skip: int = Query(0, ge=0, description="Skip N notifications for pagination")
):
    """
    List notifications for the current user
    
    Features:
    - Filter by notification type (due_date, daily_encouragement, completion)
    - Filter by read status (true/false/none for all)
    - Pagination support
    - Ordered by most recent first
    
    Returns list of notifications with metadata for UI display.
    """
    user_id = current_user["user_id"]
    
    try:
        query = db.query(Notification).filter(
            Notification.user_id == user_id
        )
        
        # Filter by type
        if notification_type:
            if notification_type not in ["due_date", "daily_encouragement", "completion"]:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid notification type. Must be one of: due_date, daily_encouragement, completion"
                )
            query = query.filter(Notification.type == notification_type)
        
        # Filter by read status
        if is_read is not None:
            query = query.filter(Notification.is_read == is_read)
        
        # Total count
        total = query.count()
        
        # Order by most recent first
        notifications = query.order_by(desc(Notification.created_at)).offset(skip).limit(limit).all()
        
        print(f"📬 Retrieved {len(notifications)} notifications for user {user_id}")
        
        return notifications
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve notifications: {str(e)}"
        )


@router.get("/stats", response_model=NotificationStatsOut)
async def get_notification_stats(
    db: db_dependency,
    current_user: dict = user_dependency
):
    """
    Get notification statistics for the user
    
    Returns counts of:
    - Unread notifications by type
    - Total dismissed notifications
    - Helpful for badge counts and summary views
    """
    user_id = current_user["user_id"]
    
    try:
        # Count unread by type
        unread_query = db.query(Notification).filter(
            and_(
                Notification.user_id == user_id,
                Notification.is_read == False
            )
        )
        
        total_unread = unread_query.count()
        due_date_unread = unread_query.filter(Notification.type == "due_date").count()
        daily_encouragement_unread = unread_query.filter(Notification.type == "daily_encouragement").count()
        completion_unread = unread_query.filter(Notification.type == "completion").count()
        
        # Count dismissed
        dismissed = db.query(Notification).filter(
            and_(
                Notification.user_id == user_id,
                Notification.dismissed_at.isnot(None)
            )
        ).count()
        
        return NotificationStatsOut(
            total_unread=total_unread,
            due_date_unread=due_date_unread,
            daily_encouragement_unread=daily_encouragement_unread,
            completion_unread=completion_unread,
            total_dismissed=dismissed
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve stats: {str(e)}"
        )


# ===============================
# NOTIFICATION INTERACTION ENDPOINTS
# ===============================

@router.put("/{notification_id}/read")
async def mark_notification_as_read(
    notification_id: int,
    db: db_dependency,
    current_user: dict = user_dependency
):
    """
    Mark a notification as read
    
    Updates the read status and read_at timestamp.
    """
    user_id = current_user["user_id"]
    
    try:
        notification = db.query(Notification).filter(
            and_(
                Notification.id == notification_id,
                Notification.user_id == user_id
            )
        ).first()
        
        if not notification:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Notification not found"
            )
        
        if not notification.is_read:
            notification.is_read = True
            notification.read_at = datetime.utcnow()
            db.commit()
            print(f"✅ Marked notification {notification_id} as read")
        
        return {"message": "Notification marked as read"}
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update notification: {str(e)}"
        )


@router.put("/{notification_id}/dismiss")
async def dismiss_notification(
    notification_id: int,
    db: db_dependency,
    current_user: dict = user_dependency
):
    """
    Dismiss/delete a notification
    
    Marks notification as dismissed. The record is kept for history/analytics.
    """
    user_id = current_user["user_id"]
    
    try:
        notification = db.query(Notification).filter(
            and_(
                Notification.id == notification_id,
                Notification.user_id == user_id
            )
        ).first()
        
        if not notification:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Notification not found"
            )
        
        if not notification.dismissed_at:
            notification.dismissed_at = datetime.utcnow()
            notification.status = "dismissed"
            db.commit()
            print(f"✅ Dismissed notification {notification_id}")
        
        return {"message": "Notification dismissed"}
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to dismiss notification: {str(e)}"
        )


@router.post("/mark-all-as-read")
async def mark_all_notifications_as_read(
    db: db_dependency,
    current_user: dict = user_dependency
):
    """Mark all unread notifications as read"""
    user_id = current_user["user_id"]
    
    try:
        unread = db.query(Notification).filter(
            and_(
                Notification.user_id == user_id,
                Notification.is_read == False
            )
        ).all()
        
        updated_count = 0
        for notification in unread:
            notification.is_read = True
            notification.read_at = datetime.utcnow()
            updated_count += 1
        
        db.commit()
        print(f"✅ Marked {updated_count} notifications as read for user {user_id}")
        
        return {"message": f"Marked {updated_count} notifications as read"}
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to mark notifications as read: {str(e)}"
        )


# ===============================
# INTERNAL HELPER FUNCTIONS (used by background jobs)
# ===============================

def create_due_date_notification(
    db,
    user_id: int,
    assignment: StudentAssignment,
    days_until_due: int
):
    """
    Create a due date notification for an upcoming assignment
    
    Called by scheduled job that checks due assignments daily.
    """
    try:
        # Avoid duplicates: check if we already sent notification for this assignment today
        today = datetime.utcnow().date()
        existing = db.query(Notification).filter(
            and_(
                Notification.user_id == user_id,
                Notification.assignment_id == assignment.assignment_id,
                Notification.type == "due_date",
                Notification.created_at >= datetime.combine(today, datetime.min.time())
            )
        ).first()
        
        if existing:
            print(f"ℹ️ Due date notification already exists for user {user_id}, assignment {assignment.assignment_id}")
            return None
        
        # Get assignment details for title and body
        course_assignment = db.query(CourseAssignment).filter(
            CourseAssignment.id == assignment.assignment_id
        ).first()
        
        if not course_assignment:
            print(f"⚠️ Assignment {assignment.assignment_id} not found")
            return None
        
        # Build notification
        due_date_str = assignment.due_date.strftime("%B %d, %Y")
        
        if days_until_due == 0:
            title = "⏰ Assignment Due Today!"
            body = f"Your assignment '{course_assignment.title}' is due today. Complete it now!"
        elif days_until_due == 1:
            title = "⏰ Assignment Due Tomorrow"
            body = f"Your assignment '{course_assignment.title}' is due tomorrow. Start working on it!"
        else:
            title = f"📋 Assignment Due in {days_until_due} Days"
            body = f"Your assignment '{course_assignment.title}' is due on {due_date_str}. Plan accordingly!"
        
        notification = Notification(
            user_id=user_id,
            type="due_date",
            title=title,
            body=body,
            course_id=assignment.course_id,
            assignment_id=assignment.assignment_id,
            status="created",
            scheduled_for=datetime.utcnow()
        )
        
        db.add(notification)
        db.commit()
        db.refresh(notification)
        
        print(f"✅ Created due date notification for user {user_id}: {title}")
        return notification
        
    except Exception as e:
        db.rollback()
        print(f"❌ Error creating due date notification: {str(e)}")
        return None


def create_daily_encouragement_notification(
    db,
    user_id: int,
    user_name: Optional[str] = None
):
    """
    Create a daily encouragement notification
    
    Called by scheduled job that sends encouragement messages daily.
    Includes random motivational messages and course suggestions.
    """
    try:
        # Avoid duplicates: check if we already sent encouragement today
        today = datetime.utcnow().date()
        existing = db.query(Notification).filter(
            and_(
                Notification.user_id == user_id,
                Notification.type == "daily_encouragement",
                Notification.created_at >= datetime.combine(today, datetime.min.time())
            )
        ).first()
        
        if existing:
            print(f"ℹ️ Daily encouragement already sent to user {user_id} today")
            return None
        
        # Get active courses for the user (from study sessions)
        from models.afterschool_models import StudySession
        active_courses = db.query(Course).join(
            StudySession, Course.id == StudySession.course_id
        ).filter(
            StudySession.user_id == user_id
        ).distinct().limit(1).all()
        
        # Build motivational message
        encouragement_messages = [
            "🌟 Keep up the great work! Every step brings you closer to success.",
            "💪 You're doing amazing! Your dedication is inspiring.",
            "🚀 Ready to learn something new today? Check out a course!",
            "🎯 Focus on your goals. You've got this!",
            "✨ Your effort today creates your success tomorrow.",
            "🏆 Challenge yourself to grow. You're capable of great things!",
            "📚 Learning is a superpower. Keep shining!",
            "💯 Every lesson learned is a step forward.",
            "🌈 Stay positive and keep pushing toward your goals.",
            "⚡ Energy, passion, and persistence—that's the recipe for success!"
        ]
        
        import random
        random_message = random.choice(encouragement_messages)
        
        title = f"🌟 Daily Motivation"
        body = random_message
        
        if active_courses:
            course = active_courses[0]
            body += f"\n\n📖 Continue learning: {course.title}"
        
        notification = Notification(
            user_id=user_id,
            type="daily_encouragement",
            title=title,
            body=body,
            status="created",
            scheduled_for=datetime.utcnow()
        )
        
        db.add(notification)
        db.commit()
        db.refresh(notification)
        
        print(f"✅ Created daily encouragement notification for user {user_id}")
        return notification
        
    except Exception as e:
        db.rollback()
        print(f"❌ Error creating daily encouragement notification: {str(e)}")
        return None


def create_completion_notification(
    db,
    user_id: int,
    course_id: int,
    course_title: str,
    completion_type: str = "course"  # course or block
):
    """
    Create a completion/congratulations notification
    
    Called when user completes a course or major block.
    """
    try:
        course = db.query(Course).filter(Course.id == course_id).first()
        
        if completion_type == "course":
            title = "🎉 Course Completed!"
            body = f"Congratulations! You've successfully completed '{course_title}'. Great effort and dedication! 🏆"
        else:  # block
            title = "✅ Block Complete!"
            body = f"Excellent work! You've finished a major block in '{course_title}'. You're on your way to mastery! 🚀"
        
        notification = Notification(
            user_id=user_id,
            type="completion",
            title=title,
            body=body,
            course_id=course_id,
            status="created",
            scheduled_for=datetime.utcnow()
        )
        
        db.add(notification)
        db.commit()
        db.refresh(notification)
        
        print(f"✅ Created completion notification for user {user_id}: {title}")
        return notification
        
    except Exception as e:
        db.rollback()
        print(f"❌ Error creating completion notification: {str(e)}")
        return None
