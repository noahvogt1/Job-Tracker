"""
Saved search and job alert API endpoints.

Provides endpoints for managing saved searches and job alerts.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Body
from typing import List, Dict, Any, Optional
from datetime import datetime
import json

from job_tracker.api.schemas import SavedSearchCreate, SavedSearchResponse
from job_tracker.api.dependencies import get_db, require_auth
from job_tracker.db import Database

router = APIRouter(prefix="/api/searches", tags=["searches"])


@router.post("", response_model=SavedSearchResponse, status_code=status.HTTP_201_CREATED)
async def create_saved_search(
    search: SavedSearchCreate = Body(...),
    user_id: int = Depends(require_auth),
    db: Database = Depends(get_db)
):
    """Create a new saved search."""
    cur = db.conn.cursor()
    
    # Check if search with same name already exists
    existing = cur.execute(
        "SELECT search_id FROM saved_searches WHERE user_id = ? AND name = ?",
        (user_id, search.name)
    ).fetchone()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A saved search with this name already exists"
        )
    
    # Insert saved search
    filters_json = json.dumps(search.filters)
    now = datetime.now()
    cur.execute(
        """
        INSERT INTO saved_searches (user_id, name, filters, notification_enabled, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (user_id, search.name, filters_json, 1 if search.notification_enabled else 0, now)
    )
    db.conn.commit()
    
    search_id = cur.lastrowid
    
    # Fetch created search
    row = cur.execute(
        "SELECT * FROM saved_searches WHERE search_id = ?",
        (search_id,)
    ).fetchone()
    
    return SavedSearchResponse(
        search_id=row["search_id"],
        user_id=row["user_id"],
        name=row["name"],
        filters=row["filters"],
        created_at=datetime.fromisoformat(row["created_at"]) if isinstance(row["created_at"], str) else row["created_at"],
        last_run_at=datetime.fromisoformat(row["last_run_at"]) if row["last_run_at"] and isinstance(row["last_run_at"], str) else row["last_run_at"],
        notification_enabled=bool(row["notification_enabled"])
    )


@router.get("", response_model=List[SavedSearchResponse])
async def list_saved_searches(
    user_id: int = Depends(require_auth),
    db: Database = Depends(get_db)
):
    """List all saved searches for the authenticated user."""
    cur = db.conn.cursor()
    rows = cur.execute(
        "SELECT * FROM saved_searches WHERE user_id = ? ORDER BY created_at DESC",
        (user_id,)
    ).fetchall()
    
    searches = []
    for row in rows:
        searches.append(SavedSearchResponse(
            search_id=row["search_id"],
            user_id=row["user_id"],
            name=row["name"],
            filters=row["filters"],
            created_at=datetime.fromisoformat(row["created_at"]) if isinstance(row["created_at"], str) else row["created_at"],
            last_run_at=datetime.fromisoformat(row["last_run_at"]) if row["last_run_at"] and isinstance(row["last_run_at"], str) else row["last_run_at"],
            notification_enabled=bool(row["notification_enabled"])
        ))
    
    return searches


@router.get("/{search_id}", response_model=SavedSearchResponse)
async def get_saved_search(
    search_id: int,
    user_id: int = Depends(require_auth),
    db: Database = Depends(get_db)
):
    """Get a specific saved search."""
    cur = db.conn.cursor()
    row = cur.execute(
        "SELECT * FROM saved_searches WHERE search_id = ? AND user_id = ?",
        (search_id, user_id)
    ).fetchone()
    
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Saved search not found"
        )
    
    return SavedSearchResponse(
        search_id=row["search_id"],
        user_id=row["user_id"],
        name=row["name"],
        filters=row["filters"],
        created_at=datetime.fromisoformat(row["created_at"]) if isinstance(row["created_at"], str) else row["created_at"],
        last_run_at=datetime.fromisoformat(row["last_run_at"]) if row["last_run_at"] and isinstance(row["last_run_at"], str) else row["last_run_at"],
        notification_enabled=bool(row["notification_enabled"])
    )


@router.put("/{search_id}", response_model=SavedSearchResponse)
async def update_saved_search(
    search_id: int,
    search: SavedSearchCreate = Body(...),
    user_id: int = Depends(require_auth),
    db: Database = Depends(get_db)
):
    """Update a saved search."""
    cur = db.conn.cursor()
    
    # Verify ownership
    existing = cur.execute(
        "SELECT search_id FROM saved_searches WHERE search_id = ? AND user_id = ?",
        (search_id, user_id)
    ).fetchone()
    
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Saved search not found"
        )
    
    # Update search
    filters_json = json.dumps(search.filters)
    cur.execute(
        """
        UPDATE saved_searches
        SET name = ?, filters = ?, notification_enabled = ?
        WHERE search_id = ? AND user_id = ?
        """,
        (search.name, filters_json, 1 if search.notification_enabled else 0, search_id, user_id)
    )
    db.conn.commit()
    
    # Fetch updated search
    row = cur.execute(
        "SELECT * FROM saved_searches WHERE search_id = ?",
        (search_id,)
    ).fetchone()
    
    return SavedSearchResponse(
        search_id=row["search_id"],
        user_id=row["user_id"],
        name=row["name"],
        filters=row["filters"],
        created_at=datetime.fromisoformat(row["created_at"]) if isinstance(row["created_at"], str) else row["created_at"],
        last_run_at=datetime.fromisoformat(row["last_run_at"]) if row["last_run_at"] and isinstance(row["last_run_at"], str) else row["last_run_at"],
        notification_enabled=bool(row["notification_enabled"])
    )


@router.delete("/{search_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_saved_search(
    search_id: int,
    user_id: int = Depends(require_auth),
    db: Database = Depends(get_db)
):
    """Delete a saved search."""
    cur = db.conn.cursor()
    
    # Verify ownership
    existing = cur.execute(
        "SELECT search_id FROM saved_searches WHERE search_id = ? AND user_id = ?",
        (search_id, user_id)
    ).fetchone()
    
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Saved search not found"
        )
    
    cur.execute(
        "DELETE FROM saved_searches WHERE search_id = ? AND user_id = ?",
        (search_id, user_id)
    )
    db.conn.commit()
    
    return None
