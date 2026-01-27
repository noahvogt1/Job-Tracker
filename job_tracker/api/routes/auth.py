"""
Authentication API endpoints.

Provides endpoints for user registration, login, logout, and session management.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Dict, Any
from datetime import datetime, timedelta
import secrets
import sqlite3

from job_tracker.api.schemas import (
    UserCreate,
    UserLogin,
    UserResponse,
    PasswordResetRequest,
    PasswordResetConfirm,
)
from job_tracker.api.dependencies import get_db, get_current_user, create_session
from job_tracker.api.auth_utils import (
    hash_password, verify_password, validate_password_strength, validate_username
)
from job_tracker.db import Database

router = APIRouter(prefix="/api/auth", tags=["authentication"])

security = HTTPBearer(auto_error=False)


@router.post("/register", response_model=Dict[str, Any], status_code=status.HTTP_201_CREATED)
async def register(
    user_data: UserCreate,
    db: Database = Depends(get_db)
):
    """
    Register a new user.
    
    Validates username and password strength, creates user account,
    and returns a session token.
    """
    # Validate username
    username_valid, username_error = validate_username(user_data.username)
    if not username_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=username_error
        )
    
    # Validate password strength
    password_valid, password_error = validate_password_strength(user_data.password)
    if not password_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=password_error
        )
    
    # Check if username already exists
    existing_user = db.get_user_by_username(user_data.username)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already taken"
        )
    
    # Check if email already exists (if provided)
    if user_data.email:
        existing_email = db.get_user_by_email(user_data.email)
        if existing_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
    
    # Hash password
    password_hash = hash_password(user_data.password)
    
    # Create user
    try:
        user_id = db.create_user(
            username=user_data.username,
            password_hash=password_hash,
            email=user_data.email
        )
    except sqlite3.IntegrityError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username or email already exists"
        )
    
    # Create session
    session_token = create_session(user_id, db, days=30)
    
    # Get created user
    user = db.get_user_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve created user"
        )
    
    return {
        "message": "User registered successfully",
        "user": {
            "user_id": int(user["user_id"]),
            "username": user["username"],
            "email": user["email"],
            "created_at": user["created_at"]
        },
        "session_token": session_token
    }


@router.post("/login", response_model=Dict[str, Any])
async def login(
    login_data: UserLogin,
    db: Database = Depends(get_db)
):
    """
    Login a user with username and password.
    
    Returns a session token that can be used for authenticated requests.
    """
    # Get user by username
    user = db.get_user_by_username(login_data.username)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password"
        )
    
    # Verify password
    if not user["password_hash"]:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password"
        )
    
    if not verify_password(login_data.password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password"
        )
    
    # Update last login
    db.update_last_login(int(user["user_id"]))
    
    # Create session (longer expiry if remember_me is checked)
    session_days = 90 if login_data.remember_me else 30
    session_token = create_session(int(user["user_id"]), db, days=session_days)
    
    return {
        "message": "Login successful",
        "user": {
            "user_id": int(user["user_id"]),
            "username": user["username"],
            "email": user["email"],
            "created_at": user["created_at"]
        },
        "session_token": session_token
    }


@router.post("/logout", status_code=status.HTTP_200_OK)
async def logout(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: Database = Depends(get_db)
):
    """
    Logout the current user by invalidating their session token.
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )
    
    session_id = credentials.credentials
    deleted = db.delete_user_session(session_id)
    
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )
    
    return {"message": "Logged out successfully"}


@router.get("/me", response_model=Dict[str, Any])
async def get_current_user_info(
    user_id: int = Depends(get_current_user),
    db: Database = Depends(get_db)
):
    """
    Get information about the currently authenticated user.
    """
    user = db.get_user_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return {
        "user_id": int(user["user_id"]),
        "username": user["username"],
        "email": user["email"],
        "created_at": user["created_at"],
        "last_login": user["last_login"]
    }


@router.get("/check", response_model=Dict[str, Any])
async def check_auth(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: Database = Depends(get_db)
):
    """
    Check if the current request is authenticated.
    
    Returns authentication status without requiring authentication.
    """
    user_id = None
    if credentials:
        session_id = credentials.credentials
        cur = db.conn.cursor()
        cur.execute(
            "SELECT user_id, expires_at FROM user_sessions WHERE session_id = ?",
            (session_id,)
        )
        row = cur.fetchone()
        if row:
            from datetime import datetime
            user_id, expires_at = row
            if datetime.fromisoformat(expires_at) >= datetime.now():
                user_id = int(user_id)
            else:
                user_id = None
    
    return {
        "authenticated": user_id is not None,
        "user_id": user_id
    }


@router.post("/password/reset-request", status_code=status.HTTP_200_OK)
async def request_password_reset(
    payload: PasswordResetRequest,
    db: Database = Depends(get_db),
):
    """
    Request a password reset link.

    Always returns 200 to avoid leaking which emails are registered.
    In a production deployment this would send an email containing a
    single-use reset link with the token.
    """
    user = db.get_user_by_email(payload.email)
    if user:
        # Generate secure token and store it with a limited lifetime
        token = secrets.token_urlsafe(32)
        created_at = datetime.now()
        expires_at = created_at + timedelta(hours=1)
        db.create_password_reset_token(int(user["user_id"]), token, created_at, expires_at)
        # For now we log the token server-side; in a real deployment this
        # should be emailed to the user.
        print(
            f"[password-reset] Generated token for user_id={user['user_id']}: "
            f"{token} (expires at {expires_at.isoformat()})"
        )
    # Always respond with a generic success message
    return {"message": "If an account with that email exists, a reset link has been generated."}


@router.post("/password/reset-confirm", status_code=status.HTTP_200_OK)
async def confirm_password_reset(
    payload: PasswordResetConfirm,
    db: Database = Depends(get_db),
):
    """
    Confirm a password reset using a token and set a new password.
    """
    # Look up token and ensure it is valid
    token_row = db.get_valid_password_reset_token(payload.token)
    if not token_row:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token",
        )

    user_id = int(token_row["user_id"])

    # Validate password strength
    password_valid, password_error = validate_password_strength(payload.new_password)
    if not password_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=password_error,
        )

    # Hash and store new password, then invalidate token
    password_hash = hash_password(payload.new_password)
    db.update_user_password_hash(user_id, password_hash)
    db.mark_password_reset_token_used(int(token_row["token_id"]))
    # Optionally, existing sessions could be revoked here:
    # db.delete_user_sessions(user_id)

    return {"message": "Password has been reset successfully."}
