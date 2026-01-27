"""
Notification service for creating and sending notifications.
"""

from datetime import datetime, timedelta
from job_tracker.db import Database
from typing import Optional


def notify_job_alert(db: Database, user_id: int, job_id: str, job_title: str, company_name: str):
    """Notify user of new job matching saved search"""
    db.create_notification(
        user_id=user_id,
        notification_type="job_alert",
        title=f"New job: {job_title}",
        message=f"{company_name} posted a new job matching your saved search",
        related_job_id=job_id
    )


def notify_status_change(db: Database, user_id: int, application_id: int, old_status: str, new_status: str):
    """Notify user of application status change"""
    db.create_notification(
        user_id=user_id,
        notification_type="status_change",
        title="Application status updated",
        message=f"Your application status changed from {old_status} to {new_status}",
        related_application_id=application_id
    )


def notify_interview_reminder(db: Database, user_id: int, interview_id: int, interview_time: datetime):
    """Notify user of upcoming interview"""
    db.create_notification(
        user_id=user_id,
        notification_type="reminder",
        title="Interview reminder",
        message=f"You have an interview scheduled for {interview_time.strftime('%Y-%m-%d %H:%M')}",
        related_application_id=interview_id
    )


def check_and_send_reminders(db: Database):
    """Check for upcoming interviews and send reminders"""
    # Get interviews in next 24 hours
    tomorrow = datetime.now() + timedelta(days=1)
    cur = db.conn.cursor()
    cur.execute(
        """
        SELECT i.*, a.user_id
        FROM interviews i
        JOIN applications a ON a.application_id = i.application_id
        WHERE i.scheduled_at BETWEEN datetime('now') AND ?
          AND i.status = 'scheduled'
        """,
        (tomorrow,)
    )
    interviews = cur.fetchall()
    
    for interview in interviews:
        # Check if reminder already sent (simplified - would need reminder_sent flag)
        notify_interview_reminder(db, interview["user_id"], interview["interview_id"], interview["scheduled_at"])
