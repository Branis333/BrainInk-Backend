"""
After-School Notification Scheduler

Background jobs for automated notification generation:
1. Due Date Checker - Runs daily to notify users of upcoming due assignments
2. Daily Encouragement - Sends motivational messages at scheduled times
3. Completion Trigger - Fires when courses/blocks are marked complete

These jobs should be integrated with APScheduler or Celery for production use.
"""

from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from typing import List

from db.database import get_session_local
from models.afterschool_models import (
    StudentAssignment,
    NotificationPreference,
    Course,
    Notification
)
from Endpoints.after_school.notifications import (
    create_due_date_notification,
    create_daily_encouragement_notification,
    create_completion_notification
)


class NotificationScheduler:
    """
    Background scheduler for notification jobs
    
    Should be called by APScheduler on a schedule:
    - due_date_checker: Every day at 08:00 AM
    - daily_encouragement_sender: Every day at preferred user times
    - Completion triggers: Called directly when user completes content
    """
    
    @staticmethod
    def check_due_assignments():
        """
        Daily job: Check for assignments due soon and create notifications
        
        Runs once per day (e.g., 08:00 AM).
        Checks all assignments due within the next N days (from preferences).
        Creates notifications for enabled users.
        """
        SessionLocal = get_session_local()
        db = SessionLocal()
        try:
            print("\n🔔 [DUE DATE CHECKER] Starting due assignment notification check...")
            
            # Get all users with due date notifications enabled
            prefs_query = db.query(NotificationPreference).filter(
                NotificationPreference.due_date_notifications == True
            ).all()
            
            print(f"📋 Found {len(prefs_query)} users with due date notifications enabled")
            
            notifications_created = 0
            
            for pref in prefs_query:
                user_id = pref.user_id
                days_before = pref.due_date_days_before
                
                # Calculate the window: today to N days from now
                now = datetime.utcnow()
                window_start = now.date()
                window_end = (now + timedelta(days=days_before)).date()
                
                # Find assignments due within this window
                due_soon = db.query(StudentAssignment).filter(
                    StudentAssignment.user_id == user_id,
                    StudentAssignment.status.in_(["assigned", "overdue"]),  # Not yet submitted
                    StudentAssignment.due_date >= datetime.combine(window_start, datetime.min.time()),
                    StudentAssignment.due_date < datetime.combine(window_end, datetime.max.time())
                ).all()
                
                print(f"👤 User {user_id}: {len(due_soon)} assignments due within {days_before} day(s)")
                
                for assignment in due_soon:
                    days_until_due = (assignment.due_date.date() - now.date()).days
                    
                    # Create notification
                    notif = create_due_date_notification(
                        db,
                        user_id,
                        assignment,
                        days_until_due
                    )
                    
                    if notif:
                        notifications_created += 1
            
            print(f"✅ Due date check complete. Created {notifications_created} notifications\n")
            return {"notifications_created": notifications_created, "status": "success"}
            
        except Exception as e:
            print(f"❌ Error in due date checker: {str(e)}\n")
            return {"status": "failed", "error": str(e)}
        finally:
            db.close()
    
    
    @staticmethod
    def send_daily_encouragement():
        """
        Daily job: Send motivational messages to active users
        
        Runs multiple times per day (at user-preferred times).
        Sends one encouragement message per user per day.
        Only to users with active courses/sessions.
        """
        SessionLocal = get_session_local()
        db = SessionLocal()
        try:
            print("\n💪 [DAILY ENCOURAGEMENT] Starting encouragement message delivery...")
            
            # Get all users with daily encouragement enabled
            prefs_query = db.query(NotificationPreference).filter(
                NotificationPreference.daily_encouragement == True
            ).all()
            
            print(f"📋 Found {len(prefs_query)} users with daily encouragement enabled")
            
            notifications_created = 0
            
            for pref in prefs_query:
                user_id = pref.user_id
                preferred_time = pref.daily_encouragement_time  # HH:MM format
                
                # In production, this would check if current time matches preferred time
                # For now, we create the notification immediately
                # APScheduler would handle time-based triggering
                
                notif = create_daily_encouragement_notification(
                    db,
                    user_id
                )
                
                if notif:
                    notifications_created += 1
            
            print(f"✅ Daily encouragement complete. Created {notifications_created} notifications\n")
            return {"notifications_created": notifications_created, "status": "success"}
            
        except Exception as e:
            print(f"❌ Error in daily encouragement sender: {str(e)}\n")
            return {"status": "failed", "error": str(e)}
        finally:
            db.close()
    
    
    @staticmethod
    def trigger_completion_notification(
        user_id: int,
        course_id: int,
        course_title: str,
        completion_type: str = "course"
    ):
        """
        Direct trigger: Called when user completes a course or block
        
        Should be called from:
        - Course completion endpoint
        - Block completion endpoint
        - Study session mark-done endpoint
        
        Args:
            user_id: Student user ID
            course_id: Course that was completed
            course_title: Course display name
            completion_type: "course" or "block"
        """
        SessionLocal = get_session_local()
        db = SessionLocal()
        try:
            # Check if user has completion notifications enabled
            prefs = db.query(NotificationPreference).filter(
                NotificationPreference.user_id == user_id
            ).first()
            
            if not prefs or not prefs.completion_notifications:
                print(f"ℹ️ User {user_id} has completion notifications disabled")
                return None
            
            # Create the notification
            notif = create_completion_notification(
                db,
                user_id,
                course_id,
                course_title,
                completion_type
            )
            
            return notif
            
        except Exception as e:
            print(f"❌ Error triggering completion notification: {str(e)}")
            return None
        finally:
            db.close()


# ===============================
# APSCHEDULER INTEGRATION EXAMPLE
# ===============================

def setup_notification_scheduler():
    """
    Initialize APScheduler for notification jobs
    
    Add this to your main.py or startup event:
    
    ```python
    from Endpoints.after_school.notification_scheduler import setup_notification_scheduler
    
    setup_notification_scheduler()
    ```
    """
    try:
        # APScheduler imports - Pylance may flag these but they work at runtime
        from apscheduler.schedulers.background import BackgroundScheduler  # type: ignore
        from apscheduler.triggers.cron import CronTrigger  # type: ignore
        
        scheduler = BackgroundScheduler()
        
        # Due date check: Every day at 8:00 AM
        scheduler.add_job(
            NotificationScheduler.check_due_assignments,
            trigger=CronTrigger(hour=8, minute=0),
            id="check_due_assignments",
            name="Check for due assignments",
            replace_existing=True,
            misfire_grace_time=600
        )
        
        # Daily encouragement: Every day at 9:00 AM
        scheduler.add_job(
            NotificationScheduler.send_daily_encouragement,
            trigger=CronTrigger(hour=9, minute=0),
            id="send_daily_encouragement",
            name="Send daily encouragement",
            replace_existing=True,
            misfire_grace_time=600
        )
        
        scheduler.start()
        print("✅ Notification scheduler initialized and running")
        return scheduler
        
    except ImportError as e:
        print(f"❌ Failed to import APScheduler: {str(e)}")
        print("   Make sure APScheduler is installed: pip install apscheduler")
        return None
    except Exception as e:
        print(f"❌ Error setting up notification scheduler: {str(e)}")
        return None


# ===============================
# CELERY TASK ALTERNATIVE
# ===============================

"""
Alternative using Celery for production:

from celery import Celery, shared_task
from celery.schedules import crontab

# In celery_app.py or main config:
celery_app = Celery("brainink")
celery_app.conf.beat_schedule = {
    'check-due-assignments': {
        'task': 'Endpoints.after_school.notification_scheduler.check_due_assignments_task',
        'schedule': crontab(hour=8, minute=0),
    },
    'send-daily-encouragement': {
        'task': 'Endpoints.after_school.notification_scheduler.send_daily_encouragement_task',
        'schedule': crontab(hour=9, minute=0),
    },
}

# In this file:
@shared_task
def check_due_assignments_task():
    return NotificationScheduler.check_due_assignments()

@shared_task
def send_daily_encouragement_task():
    return NotificationScheduler.send_daily_encouragement()
"""
