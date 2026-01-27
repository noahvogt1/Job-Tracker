"""
Sharing and collaboration API endpoints for read-only views.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
import secrets

from job_tracker.api.dependencies import get_db, require_auth, get_current_user
from job_tracker.db import Database

router = APIRouter(prefix="/api/sharing", tags=["sharing"])


class ShareLinkCreate(BaseModel):
    resource_type: str  # 'applications', 'jobs', 'dashboard'
    resource_id: Optional[str] = None  # For specific resource, None for all
    expires_days: Optional[int] = 30  # Link expiration in days


class ShareLinkResponse(BaseModel):
    share_id: str
    share_url: str
    resource_type: str
    resource_id: Optional[str] = None
    expires_at: Optional[datetime] = None
    created_at: datetime


@router.post("", response_model=ShareLinkResponse)
async def create_share_link(
    share: ShareLinkCreate = ...,
    user_id: int = Depends(require_auth),
    db: Database = Depends(get_db)
):
    """Create a shareable read-only link."""
    cur = db.conn.cursor()
    
    # Generate unique share ID
    share_id = secrets.token_urlsafe(32)
    
    # Calculate expiration
    expires_at = None
    if share.expires_days:
        expires_at = datetime.now() + timedelta(days=share.expires_days)
    
    # Insert share link
    cur.execute(
        """
        INSERT INTO share_links (share_id, user_id, resource_type, resource_id, expires_at, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (share_id, user_id, share.resource_type, share.resource_id, expires_at, datetime.now())
    )
    db.conn.commit()
    
    # Generate share URL (would be full URL in production)
    share_url = f"/shared/{share_id}"
    
    return ShareLinkResponse(
        share_id=share_id,
        share_url=share_url,
        resource_type=share.resource_type,
        resource_id=share.resource_id,
        expires_at=expires_at,
        created_at=datetime.now()
    )


@router.get("/{share_id}")
async def get_shared_resource(
    share_id: str,
    db: Database = Depends(get_db)
):
    """Get shared resource data (read-only, no auth required)."""
    cur = db.conn.cursor()
    
    # Get share link
    share_row = cur.execute(
        "SELECT * FROM share_links WHERE share_id = ?",
        (share_id,)
    ).fetchone()
    
    if not share_row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Share link not found")
    
    # Check expiration
    if share_row["expires_at"]:
        expires_at = datetime.fromisoformat(share_row["expires_at"]) if isinstance(share_row["expires_at"], str) else share_row["expires_at"]
        if datetime.now() > expires_at:
            raise HTTPException(status_code=status.HTTP_410_GONE, detail="Share link has expired")
    
    user_id = share_row["user_id"]
    resource_type = share_row["resource_type"]
    resource_id = share_row["resource_id"]
    
    # Fetch shared data based on type
    if resource_type == "applications":
        if resource_id:
            # Specific application
            app = db.get_application(int(resource_id), user_id)
            if not app:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found")
            return {"type": "application", "data": dict(app)}
        else:
            # All applications (limited)
            apps = db.list_applications(user_id=user_id, limit=100, offset=0)
            return {"type": "applications", "data": [dict(app) for app in apps]}
    
    elif resource_type == "jobs":
        # Return job data (limited)
        cur.execute(
            """
            SELECT j.*, c.name AS company_name
            FROM jobs j
            JOIN companies c ON j.company_id = c.id
            WHERE j.active = 1
            LIMIT 50
            """
        )
        jobs = cur.fetchall()
        return {"type": "jobs", "data": [dict(job) for job in jobs]}
    
    elif resource_type == "dashboard":
        # Return dashboard stats (read-only)
        cur.execute(
            """
            SELECT COUNT(*) as total_applications FROM applications WHERE user_id = ?
            """,
            (user_id,)
        )
        total_apps = cur.fetchone()["total_applications"]
        
        return {
            "type": "dashboard",
            "data": {
                "total_applications": total_apps,
                "shared_at": datetime.now().isoformat()
            }
        }
    
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid resource type")


@router.get("", response_model=List[ShareLinkResponse])
async def list_share_links(
    user_id: int = Depends(require_auth),
    db: Database = Depends(get_db)
):
    """List all share links for the authenticated user."""
    cur = db.conn.cursor()
    rows = cur.execute(
        "SELECT * FROM share_links WHERE user_id = ? ORDER BY created_at DESC",
        (user_id,)
    ).fetchall()
    
    return [
        ShareLinkResponse(
            share_id=row["share_id"],
            share_url=f"/shared/{row['share_id']}",
            resource_type=row["resource_type"],
            resource_id=row["resource_id"],
            expires_at=datetime.fromisoformat(row["expires_at"]) if row["expires_at"] and isinstance(row["expires_at"], str) else row["expires_at"],
            created_at=datetime.fromisoformat(row["created_at"]) if isinstance(row["created_at"], str) else row["created_at"]
        )
        for row in rows
    ]


@router.delete("/{share_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_share_link(
    share_id: str,
    user_id: int = Depends(require_auth),
    db: Database = Depends(get_db)
):
    """Delete a share link."""
    cur = db.conn.cursor()
    
    existing = cur.execute(
        "SELECT share_id FROM share_links WHERE share_id = ? AND user_id = ?",
        (share_id, user_id)
    ).fetchone()
    
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Share link not found")
    
    cur.execute("DELETE FROM share_links WHERE share_id = ? AND user_id = ?", (share_id, user_id))
    db.conn.commit()
    return None
