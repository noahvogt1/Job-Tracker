"""
Settings API routes for user preferences and configuration.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import Optional
from job_tracker.api.dependencies import get_db, get_current_user
from job_tracker.db import Database

router = APIRouter(prefix="/api/settings", tags=["settings"])


class PreferencesUpdate(BaseModel):
    theme: Optional[str] = None
    notifications_enabled: Optional[bool] = None
    email_digest_frequency: Optional[str] = None
    default_view: Optional[str] = None  # 'kanban', 'timeline', 'calendar' for applications
    items_per_page: Optional[int] = None
    auto_refresh: Optional[bool] = None
    auto_refresh_interval: Optional[int] = None  # seconds


@router.get("/preferences")
async def get_preferences(
    user_id: int = Depends(get_current_user),
    db: Database = Depends(get_db)
):
    """Get user preferences."""
    preferences = db.get_user_preferences(user_id)
    return preferences


@router.patch("/preferences")
async def update_preferences(
    preferences: PreferencesUpdate,
    user_id: int = Depends(get_current_user),
    db: Database = Depends(get_db)
):
    """Update user preferences."""
    current_prefs = db.get_user_preferences(user_id)
    
    # Merge with new preferences
    if preferences.theme is not None:
        current_prefs["theme"] = preferences.theme
    if preferences.notifications_enabled is not None:
        current_prefs["notifications_enabled"] = preferences.notifications_enabled
    if preferences.email_digest_frequency is not None:
        current_prefs["email_digest_frequency"] = preferences.email_digest_frequency
    if preferences.default_view is not None:
        current_prefs["default_view"] = preferences.default_view
    if preferences.items_per_page is not None:
        current_prefs["items_per_page"] = preferences.items_per_page
    if preferences.auto_refresh is not None:
        current_prefs["auto_refresh"] = preferences.auto_refresh
    if preferences.auto_refresh_interval is not None:
        current_prefs["auto_refresh_interval"] = preferences.auto_refresh_interval
    
    updated = db.update_user_preferences(user_id, current_prefs)
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update preferences"
        )
    
    return current_prefs
