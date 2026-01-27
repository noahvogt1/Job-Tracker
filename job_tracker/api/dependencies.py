"""
Shared dependencies for FastAPI routes.

Provides database connection, authentication, and other shared dependencies
used across API endpoints.
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from job_tracker.db import Database
from pathlib import Path
import secrets
from datetime import datetime, timedelta
import sqlite3
import os

security = HTTPBearer(auto_error=False)


def get_db(db_path: str | None = None) -> Database:
    """Dependency to get database connection.
    
    Uses DB_PATH environment variable if provided, otherwise defaults to
    'live_jobs.db' in the current working directory.
    """
    if db_path is None:
        db_path = os.getenv("DB_PATH", "live_jobs.db")
    return Database(Path(db_path))


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: Database = Depends(get_db)
) -> int | None:
    """Get current user from session token.
    
    Returns the user_id if a valid session token is provided, otherwise None.
    This allows for optional authentication - endpoints can choose to require
    authentication or work without it.
    
    Raises:
        HTTPException: If token is provided but invalid or expired.
    """
    if credentials is None:
        return None
    
    session_id = credentials.credentials
    
    # Check session
    cur = db.conn.cursor()
    cur.execute(
        "SELECT user_id, expires_at FROM user_sessions WHERE session_id = ?",
        (session_id,)
    )
    row = cur.fetchone()
    
    if not row:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid session"
        )
    
    user_id, expires_at = row
    if datetime.fromisoformat(expires_at) < datetime.now():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired"
        )
    
    return int(user_id)


def require_auth(
    user_id: int | None = Depends(get_current_user)
) -> int:
    """Require authentication - raises 401 if user is not authenticated."""
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
    return user_id


def create_session(user_id: int, db: Database, days: int = 30) -> str:
    """Create a new session for user.
    
    Args:
        user_id: The user ID to create a session for
        db: Database connection
        days: Number of days until session expires (default: 30)
    
    Returns:
        The session token string
    """
    session_id = secrets.token_urlsafe(32)
    expires_at = datetime.now() + timedelta(days=days)
    
    cur = db.conn.cursor()
    cur.execute(
        "INSERT INTO user_sessions (session_id, user_id, created_at, expires_at) VALUES (?, ?, ?, ?)",
        (session_id, user_id, datetime.now(), expires_at)
    )
    db.conn.commit()
    return session_id
