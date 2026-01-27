"""
Company intelligence API endpoints.

Provides endpoints for viewing company profiles, analytics, notes,
and managing company-related data.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Body, Query
from typing import Optional, List, Dict, Any
from datetime import datetime
import json
import sqlite3

from job_tracker.api.schemas import (
    CompanyResponse, CompanyAnalyticsResponse, CompanyNoteCreate,
    CompanyNoteUpdate, CompanyNoteResponse, CompanyProfileUpdate
)
from job_tracker.api.dependencies import get_db, require_auth, get_current_user
from job_tracker.db import Database
from job_tracker.analytics import calculate_company_analytics, update_company_analytics

router = APIRouter(prefix="/api/companies", tags=["companies"])


def _company_row_to_response(row: sqlite3.Row) -> CompanyResponse:
    """Convert a database row to CompanyResponse."""
    # sqlite3.Row doesn't have .get() method, so we need to check keys or use try/except
    def get_value(key: str, default=None):
        try:
            return row[key] if key in row.keys() else default
        except (KeyError, IndexError):
            return default
    
    return CompanyResponse(
        id=row["id"],
        slug=row["slug"],
        name=row["name"],
        source=row["source"],
        website=get_value("website"),
        description=get_value("description"),
        industry=get_value("industry"),
        size=get_value("size"),
        headquarters=get_value("headquarters"),
        founded_year=get_value("founded_year"),
        employee_count=get_value("employee_count"),
        linkedin_url=get_value("linkedin_url"),
        glassdoor_url=get_value("glassdoor_url"),
        profile_notes=get_value("profile_notes")
    )


def _company_note_row_to_response(row: sqlite3.Row) -> CompanyNoteResponse:
    """Convert a database row to CompanyNoteResponse."""
    # Helper to safely get values from sqlite3.Row
    def get_value(key: str, default=None):
        try:
            return row[key] if key in row.keys() else default
        except (KeyError, IndexError):
            return default
    
    # Parse datetime strings
    created_at = row["created_at"]
    if isinstance(created_at, str):
        try:
            created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
        except (ValueError, AttributeError):
            created_at = datetime.now()
    elif not isinstance(created_at, datetime):
        created_at = datetime.now()
    
    updated_at = row["updated_at"]
    if isinstance(updated_at, str):
        try:
            updated_at = datetime.fromisoformat(updated_at.replace('Z', '+00:00'))
        except (ValueError, AttributeError):
            updated_at = datetime.now()
    elif not isinstance(updated_at, datetime):
        updated_at = datetime.now()
    
    return CompanyNoteResponse(
        note_id=row["note_id"],
        user_id=row["user_id"],
        username=get_value("username"),
        company_id=row["company_id"],
        note_text=row["note_text"],
        rating=get_value("rating"),
        created_at=created_at,
        updated_at=updated_at
    )


@router.get("", response_model=List[CompanyResponse])
async def list_companies(
    search: Optional[str] = Query(None, description="Search companies by name"),
    db: Database = Depends(get_db)
):
    """List all companies, optionally filtered by search term."""
    companies = db.get_all_companies()
    
    # Filter by search term if provided
    if search:
        search_lower = search.lower()
        companies = [c for c in companies if search_lower in c["name"].lower()]
    
    return [_company_row_to_response(row) for row in companies]


@router.get("/{company_id}", response_model=CompanyResponse)
async def get_company(
    company_id: int,
    db: Database = Depends(get_db)
):
    """Get company profile with extended information."""
    company = db.get_company_profile(company_id)
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Company {company_id} not found"
        )
    return _company_row_to_response(company)


@router.patch("/{company_id}/profile", response_model=CompanyResponse)
async def update_company_profile(
    company_id: int,
    profile: CompanyProfileUpdate,
    user_id: int = Depends(require_auth),
    db: Database = Depends(get_db)
):
    """Update company profile information."""
    # Verify company exists
    company = db.get_company_profile(company_id)
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Company {company_id} not found"
        )
    
    # Update profile
    db.upsert_company_profile(
        company_id=company_id,
        website=profile.website,
        description=profile.description,
        industry=profile.industry,
        size=profile.size,
        headquarters=profile.headquarters,
        founded_year=profile.founded_year,
        employee_count=profile.employee_count,
        linkedin_url=profile.linkedin_url,
        glassdoor_url=profile.glassdoor_url,
        notes=profile.notes
    )
    
    # Return updated company
    updated_company = db.get_company_profile(company_id)
    return _company_row_to_response(updated_company)


@router.get("/{company_id}/analytics", response_model=CompanyAnalyticsResponse)
async def get_company_analytics(
    company_id: int,
    refresh: bool = Query(False, description="Force recalculation of analytics"),
    db: Database = Depends(get_db)
):
    """Get company hiring analytics."""
    # Verify company exists
    company = db.get_company_profile(company_id)
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Company {company_id} not found"
        )
    
    # Refresh analytics if requested
    if refresh:
        update_company_analytics(db, company_id)
    
    # Get cached analytics
    analytics = db.get_company_analytics(company_id)
    
    if not analytics:
        # Calculate on the fly if not cached
        analytics_data = calculate_company_analytics(db, company_id)
        return CompanyAnalyticsResponse(
            company_id=company_id,
            **analytics_data
        )
    
    return CompanyAnalyticsResponse(
        analytics_id=analytics.get("analytics_id"),
        company_id=analytics["company_id"],
        snapshot_date=analytics.get("snapshot_date"),
        total_jobs_posted=analytics["total_jobs_posted"] or 0,
        total_jobs_removed=analytics["total_jobs_removed"] or 0,
        avg_posting_duration_days=analytics["avg_posting_duration_days"] or 0.0,
        ghost_posting_rate=analytics["ghost_posting_rate"] or 0.0,
        posting_frequency_per_month=analytics["posting_frequency_per_month"] or 0,
        removal_frequency_per_month=analytics["removal_frequency_per_month"] or 0,
        job_churn_rate=analytics["job_churn_rate"] or 0.0,
        reliability_score=analytics["reliability_score"] or 0.0,
        new_grad_friendly_score=analytics["new_grad_friendly_score"] or 0.0
    )


@router.post("/{company_id}/analytics/refresh")
async def refresh_company_analytics(
    company_id: int,
    user_id: int = Depends(require_auth),
    db: Database = Depends(get_db)
):
    """Recalculate and update company analytics."""
    # Verify company exists
    company = db.get_company_profile(company_id)
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Company {company_id} not found"
        )
    
    update_company_analytics(db, company_id)
    return {"message": "Analytics updated successfully"}


@router.get("/{company_id}/notes", response_model=List[CompanyNoteResponse])
async def get_company_notes(
    company_id: int,
    user_only: bool = Query(False, description="Only return notes from the current user"),
    user_id: Optional[int] = Depends(get_current_user),
    db: Database = Depends(get_db)
):
    """Get notes for a company."""
    # Verify company exists
    company = db.get_company_profile(company_id)
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Company {company_id} not found"
        )
    
    notes_user_id = user_id if user_only else None
    notes = db.get_company_notes(company_id, notes_user_id)
    return [_company_note_row_to_response(row) for row in notes]


@router.post("/{company_id}/notes", response_model=CompanyNoteResponse, status_code=status.HTTP_201_CREATED)
async def add_company_note(
    company_id: int,
    note: CompanyNoteCreate,
    user_id: int = Depends(require_auth),
    db: Database = Depends(get_db)
):
    """Add a note about a company."""
    # Verify company exists
    company = db.get_company_profile(company_id)
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Company {company_id} not found"
        )
    
    note_id = db.add_company_note(
        user_id=user_id,
        company_id=company_id,
        note_text=note.note_text,
        rating=note.rating
    )
    
    # Get the created note
    notes = db.get_company_notes(company_id, user_id)
    created_note = next((n for n in notes if n["note_id"] == note_id), None)
    
    if not created_note:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve created note"
        )
    
    return _company_note_row_to_response(created_note)


@router.patch("/{company_id}/notes/{note_id}", response_model=CompanyNoteResponse)
async def update_company_note(
    company_id: int,
    note_id: int,
    note_update: CompanyNoteUpdate,
    user_id: int = Depends(require_auth),
    db: Database = Depends(get_db)
):
    """Update a company note."""
    # Verify company exists
    company = db.get_company_profile(company_id)
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Company {company_id} not found"
        )
    
    # Update note
    updated = db.update_company_note(
        note_id=note_id,
        user_id=user_id,
        note_text=note_update.note_text,
        rating=note_update.rating
    )
    
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Note {note_id} not found or does not belong to you"
        )
    
    # Get updated note
    notes = db.get_company_notes(company_id, user_id)
    updated_note = next((n for n in notes if n["note_id"] == note_id), None)
    
    if not updated_note:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve updated note"
        )
    
    return _company_note_row_to_response(updated_note)


@router.delete("/{company_id}/notes/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_company_note(
    company_id: int,
    note_id: int,
    user_id: int = Depends(require_auth),
    db: Database = Depends(get_db)
):
    """Delete a company note."""
    deleted = db.delete_company_note(note_id, user_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Note {note_id} not found or does not belong to you"
        )
    return None


@router.get("/{company_id}/jobs", response_model=List[Dict[str, Any]])
async def get_company_jobs(
    company_id: int,
    active_only: bool = Query(True, description="Only return active jobs"),
    db: Database = Depends(get_db)
):
    """Get all jobs for a company."""
    # Verify company exists
    company = db.get_company_profile(company_id)
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Company {company_id} not found"
        )
    
    jobs = db.get_company_jobs(company_id, active_only=active_only)
    
    # Convert rows to dictionaries
    result = []
    for row in jobs:
        job_dict = dict(row)
        # Parse extra JSON if present
        if "extra" in job_dict and job_dict["extra"]:
            try:
                job_dict["extra"] = json.loads(job_dict["extra"])
            except (json.JSONDecodeError, TypeError):
                pass
        result.append(job_dict)
    
    return result
