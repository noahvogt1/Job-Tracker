"""
Dashboard API endpoints.

Provides aggregated statistics and recent activity for the dashboard.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

from job_tracker.api.dependencies import get_db, get_current_user, require_auth
from job_tracker.db import Database

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/stats")
async def get_dashboard_stats(
    user_id: Optional[int] = Depends(get_current_user),
    db: Database = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get aggregated dashboard statistics.
    
    Returns:
    - total_jobs: Total number of active jobs
    - total_applications: Total number of user's applications
    - saved_jobs: Total number of saved jobs
    - total_companies: Total number of companies
    - recent_activity: List of recent activities
    """
    stats = {
        "total_jobs": 0,
        "total_applications": 0,
        "saved_jobs": 0,
        "total_companies": 0,
        "recent_activity": []
    }
    
    try:
        # Get total jobs count (active jobs seen in last 30 days)
        jobs_result = db.execute_query(
            """
            SELECT COUNT(DISTINCT job_id) as total
            FROM jobs
            WHERE active = 1 AND last_seen > datetime('now', '-30 days')
            """
        )
        if jobs_result:
            stats["total_jobs"] = jobs_result[0][0] if jobs_result[0] else 0
        
        # Get total applications (if authenticated)
        if user_id:
            apps_result = db.execute_query(
                "SELECT COUNT(*) FROM applications WHERE user_id = ?",
                (user_id,)
            )
            if apps_result:
                stats["total_applications"] = apps_result[0][0] if apps_result[0] else 0
            
            # Get saved jobs count
            saved_result = db.execute_query(
                "SELECT COUNT(*) FROM saved_jobs WHERE user_id = ?",
                (user_id,)
            )
            if saved_result:
                stats["saved_jobs"] = saved_result[0][0] if saved_result[0] else 0
            
            # Get recent activity - join with latest job version for title
            recent_apps = db.execute_query(
                """
                SELECT 
                    a.application_id,
                    a.status,
                    a.updated_at,
                    a.created_at,
                    v.title as job_title,
                    c.name as company_name
                FROM applications a
                LEFT JOIN jobs j ON a.job_id = j.job_id
                LEFT JOIN companies c ON j.company_id = c.id
                LEFT JOIN job_versions v ON j.job_id = v.job_id
                LEFT JOIN (
                    SELECT job_id, MAX(timestamp) as max_timestamp
                    FROM job_versions
                    GROUP BY job_id
                ) latest ON v.job_id = latest.job_id AND v.timestamp = latest.max_timestamp
                WHERE a.user_id = ?
                ORDER BY COALESCE(a.updated_at, a.created_at) DESC
                LIMIT 10
                """,
                (user_id,)
            )
            
            activities = []
            for app in recent_apps:
                activity = {
                    "type": "application",
                    "title": f"Application: {app[4] or 'Unknown Job'}",
                    "description": f"Status: {app[1] or 'Unknown'}",
                    "timestamp": app[2] or app[3],
                    "application_id": app[0]
                }
                if app[5]:  # company_name
                    activity["description"] += f" at {app[5]}"
                activities.append(activity)
            
            stats["recent_activity"] = activities
        
        # Get total companies count
        companies_result = db.execute_query("SELECT COUNT(*) FROM companies")
        if companies_result:
            stats["total_companies"] = companies_result[0][0] if companies_result[0] else 0
            
    except Exception as e:
        # Log error but return partial stats
        print(f"Error calculating dashboard stats: {e}")
    
    return stats
