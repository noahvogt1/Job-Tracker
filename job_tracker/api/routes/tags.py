"""
Tags API endpoints for managing custom tags on jobs and applications.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Body
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
import json

from job_tracker.api.dependencies import get_db, require_auth
from job_tracker.db import Database

router = APIRouter(prefix="/api/tags", tags=["tags"])


class TagCreate(BaseModel):
    name: str
    color: Optional[str] = None


class TagResponse(BaseModel):
    tag_id: int
    user_id: int
    name: str
    color: Optional[str] = None
    created_at: datetime


@router.get("", response_model=List[TagResponse])
async def list_tags(
    user_id: int = Depends(require_auth),
    db: Database = Depends(get_db)
):
    """List all tags for the authenticated user."""
    cur = db.conn.cursor()
    rows = cur.execute(
        "SELECT * FROM tags WHERE user_id = ? ORDER BY name",
        (user_id,)
    ).fetchall()
    
    return [
        TagResponse(
            tag_id=row["tag_id"],
            user_id=row["user_id"],
            name=row["name"],
            color=row["color"],
            created_at=datetime.fromisoformat(row["created_at"]) if isinstance(row["created_at"], str) else row["created_at"]
        )
        for row in rows
    ]


@router.post("", response_model=TagResponse, status_code=status.HTTP_201_CREATED)
async def create_tag(
    tag: TagCreate = Body(...),
    user_id: int = Depends(require_auth),
    db: Database = Depends(get_db)
):
    """Create a new tag."""
    cur = db.conn.cursor()
    
    # Check if tag already exists
    existing = cur.execute(
        "SELECT tag_id FROM tags WHERE user_id = ? AND name = ?",
        (user_id, tag.name)
    ).fetchone()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tag with this name already exists"
        )
    
    cur.execute(
        "INSERT INTO tags (user_id, name, color, created_at) VALUES (?, ?, ?, ?)",
        (user_id, tag.name, tag.color, datetime.now())
    )
    db.conn.commit()
    
    tag_id = cur.lastrowid
    row = cur.execute("SELECT * FROM tags WHERE tag_id = ?", (tag_id,)).fetchone()
    
    return TagResponse(
        tag_id=row["tag_id"],
        user_id=row["user_id"],
        name=row["name"],
        color=row["color"],
        created_at=datetime.fromisoformat(row["created_at"]) if isinstance(row["created_at"], str) else row["created_at"]
    )


@router.delete("/{tag_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tag(
    tag_id: int,
    user_id: int = Depends(require_auth),
    db: Database = Depends(get_db)
):
    """Delete a tag."""
    cur = db.conn.cursor()
    
    existing = cur.execute(
        "SELECT tag_id FROM tags WHERE tag_id = ? AND user_id = ?",
        (tag_id, user_id)
    ).fetchone()
    
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tag not found")
    
    # Remove tag from all jobs
    cur.execute("DELETE FROM job_tags WHERE tag_id = ?", (tag_id,))
    
    # Remove tag from applications (update tags JSON)
    apps = cur.execute("SELECT application_id, tags FROM applications WHERE user_id = ? AND tags IS NOT NULL", (user_id,)).fetchall()
    for app in apps:
        if app["tags"]:
            try:
                tags = json.loads(app["tags"])
                if isinstance(tags, list) and tag_id in tags:
                    tags.remove(tag_id)
                    cur.execute(
                        "UPDATE applications SET tags = ? WHERE application_id = ?",
                        (json.dumps(tags), app["application_id"])
                    )
            except:
                pass
    
    cur.execute("DELETE FROM tags WHERE tag_id = ? AND user_id = ?", (tag_id, user_id))
    db.conn.commit()
    return None


@router.post("/jobs/{job_id}")
async def tag_job(
    job_id: str,
    tag_id: int = Body(...),
    user_id: int = Depends(require_auth),
    db: Database = Depends(get_db)
):
    """Add a tag to a job."""
    cur = db.conn.cursor()
    
    # Verify tag belongs to user
    tag = cur.execute("SELECT tag_id FROM tags WHERE tag_id = ? AND user_id = ?", (tag_id, user_id)).fetchone()
    if not tag:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tag not found")
    
    # Add tag to job
    cur.execute(
        "INSERT OR IGNORE INTO job_tags (job_id, tag_id) VALUES (?, ?)",
        (job_id, tag_id)
    )
    db.conn.commit()
    
    return {"message": "Tag added to job"}


@router.delete("/jobs/{job_id}/{tag_id}", status_code=status.HTTP_204_NO_CONTENT)
async def untag_job(
    job_id: str,
    tag_id: int,
    user_id: int = Depends(require_auth),
    db: Database = Depends(get_db)
):
    """Remove a tag from a job."""
    cur = db.conn.cursor()
    
    cur.execute("DELETE FROM job_tags WHERE job_id = ? AND tag_id = ?", (job_id, tag_id))
    db.conn.commit()
    return None
