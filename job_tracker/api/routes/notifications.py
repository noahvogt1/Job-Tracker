"""
Notification API routes.
"""

from fastapi import APIRouter, Depends, Query
from typing import Optional
from job_tracker.api.dependencies import get_db, get_current_user
from job_tracker.db import Database

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


@router.get("")
async def get_notifications(
    unread_only: bool = Query(False),
    limit: int = Query(50, ge=1, le=100),
    user_id: int = Depends(get_current_user),
    db: Database = Depends(get_db)
):
    """Get notifications"""
    rows = db.get_notifications(user_id, unread_only=unread_only, limit=limit)
    return [dict(row) for row in rows]


@router.put("/{notification_id}/read")
async def mark_read(
    notification_id: int,
    user_id: int = Depends(get_current_user),
    db: Database = Depends(get_db)
):
    """Mark notification as read"""
    db.mark_notification_read(notification_id, user_id)
    return {"message": "Notification marked as read"}


@router.put("/read-all")
async def mark_all_read(
    user_id: int = Depends(get_current_user),
    db: Database = Depends(get_db)
):
    """Mark all notifications as read"""
    db.mark_all_notifications_read(user_id)
    return {"message": "All notifications marked as read"}


@router.get("/preferences")
async def get_preferences(
    user_id: int = Depends(get_current_user),
    db: Database = Depends(get_db)
):
    """Get notification preferences"""
    prefs = db.get_notification_preferences(user_id)
    return dict(prefs)


@router.put("/preferences")
async def update_preferences(
    email_enabled: Optional[bool] = None,
    job_alerts: Optional[bool] = None,
    status_changes: Optional[bool] = None,
    reminders: Optional[bool] = None,
    deadlines: Optional[bool] = None,
    weekly_digest: Optional[bool] = None,
    user_id: int = Depends(get_current_user),
    db: Database = Depends(get_db)
):
    """Update notification preferences"""
    db.update_notification_preferences(
        user_id,
        email_enabled=email_enabled,
        job_alerts=job_alerts,
        status_changes=status_changes,
        reminders=reminders,
        deadlines=deadlines,
        weekly_digest=weekly_digest
    )
    return {"message": "Preferences updated"}
