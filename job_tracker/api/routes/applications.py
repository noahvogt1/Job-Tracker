"""
Application tracking API endpoints.

Provides endpoints for managing job applications, interviews, offers,
and tracking application status throughout the hiring process.
"""

from fastapi import APIRouter, Depends, Query, HTTPException, status
from typing import Optional, List, Dict, Any
from datetime import datetime, date
import json
import sqlite3

from job_tracker.api.schemas import (
    ApplicationCreate, ApplicationUpdate, ApplicationResponse,
    InterviewCreate, InterviewUpdate, InterviewResponse,
    OfferCreate, OfferUpdate, OfferResponse,
    JobResponse
)
from job_tracker.api.dependencies import get_db, require_auth
from job_tracker.db import Database

router = APIRouter(prefix="/api/applications", tags=["applications"])


@router.post("", response_model=ApplicationResponse, status_code=status.HTTP_201_CREATED)
async def create_application(
    application: ApplicationCreate,
    user_id: int = Depends(require_auth),
    db: Database = Depends(get_db)
):
    """
    Create a new job application.
    
    Automatically creates an initial event in the application timeline.
    """
    # Verify job exists
    job = db.get_job(application.job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {application.job_id} not found"
        )
    
    # Check if application already exists
    existing = db.conn.cursor().execute(
        "SELECT application_id FROM applications WHERE user_id = ? AND job_id = ?",
        (user_id, application.job_id)
    ).fetchone()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Application already exists for this job"
        )
    
    # Create application
    application_id = db.create_application(
        user_id=user_id,
        job_id=application.job_id,
        status=application.status,
        applied_at=datetime.now(),
        application_method=application.application_method,
        application_url=application.application_url,
        notes=application.notes,
        tags=application.tags,
        priority=application.priority,
    )
    
    # Get created application
    app_row = db.get_application(application_id, user_id)
    if not app_row:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve created application"
        )
    
    return _application_row_to_response(app_row)


@router.get("", response_model=Dict[str, Any])
async def list_applications(
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status"),
    job_id: Optional[str] = Query(None, description="Filter by job ID"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=1000, description="Items per page"),
    user_id: int = Depends(require_auth),
    db: Database = Depends(get_db)
):
    """
    List applications for the authenticated user with optional filters.
    
    Returns paginated results with job details included.
    """
    # Get total count
    count_query = "SELECT COUNT(*) as total FROM applications WHERE user_id = ?"
    count_params: List[Any] = [user_id]
    
    if status_filter:
        count_query += " AND status = ?"
        count_params.append(status_filter)
    if job_id:
        count_query += " AND job_id = ?"
        count_params.append(job_id)
    
    cur = db.conn.cursor()
    total = cur.execute(count_query, count_params).fetchone()["total"]
    
    # Get applications
    offset = (page - 1) * page_size
    applications = db.list_applications(
        user_id=user_id,
        status=status_filter,
        job_id=job_id,
        limit=page_size,
        offset=offset
    )
    
    # Enrich with job details
    enriched_apps = []
    for app_row in applications:
        app_dict = _application_row_to_response(app_row).model_dump()
        
        # Get job details
        job = db.get_job(app_row["job_id"])
        if job:
            # Get company name
            company_row = cur.execute(
                "SELECT name FROM companies WHERE id = ?",
                (job["company_id"],)
            ).fetchone()
            
            # Get latest job version
            job_version = db.get_latest_job_version(app_row["job_id"])
            
            app_dict["job"] = {
                "job_id": job["job_id"],
                "company": company_row["name"] if company_row else "Unknown",
                "company_id": job["company_id"],
                "title": job_version["title"] if job_version else "Unknown",
                "location": job_version["location"] if job_version else "",
                "url": job["url"],
            }
        
        enriched_apps.append(app_dict)
    
    return {
        "applications": enriched_apps,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size if page_size > 0 else 0
    }


@router.get("/stats", response_model=Dict[str, Any])
async def get_application_stats(
    user_id: int = Depends(require_auth),
    db: Database = Depends(get_db)
):
    """
    Get application statistics for the authenticated user.
    
    Returns counts by status, success rate, and other metrics.
    """
    cur = db.conn.cursor()
    
    # Total applications
    total = cur.execute(
        "SELECT COUNT(*) as total FROM applications WHERE user_id = ?",
        (user_id,)
    ).fetchone()["total"]
    
    # Counts by status
    status_counts = cur.execute(
        """
        SELECT status, COUNT(*) as count 
        FROM applications 
        WHERE user_id = ? 
        GROUP BY status
        """,
        (user_id,)
    ).fetchall()
    
    status_dict = {row["status"]: row["count"] for row in status_counts}
    
    # Applications with offers
    offers_count = cur.execute(
        """
        SELECT COUNT(DISTINCT a.application_id) as count
        FROM applications a
        JOIN offers o ON a.application_id = o.application_id
        WHERE a.user_id = ?
        """,
        (user_id,)
    ).fetchone()["count"]
    
    # Upcoming interviews
    upcoming_interviews = cur.execute(
        """
        SELECT COUNT(*) as count
        FROM interviews i
        JOIN applications a ON i.application_id = a.application_id
        WHERE a.user_id = ? AND i.scheduled_at > ? AND i.status = 'scheduled'
        """,
        (user_id, datetime.now())
    ).fetchone()["count"]
    
    # Calculate success rate (offers / total applications)
    success_rate = (offers_count / total * 100) if total > 0 else 0.0
    
    return {
        "total_applications": total,
        "by_status": status_dict,
        "total_offers": offers_count,
        "upcoming_interviews": upcoming_interviews,
        "success_rate": round(success_rate, 2)
    }


@router.get("/{application_id}", response_model=Dict[str, Any])
async def get_application(
    application_id: int,
    user_id: int = Depends(require_auth),
    db: Database = Depends(get_db)
):
    """
    Get detailed information about a specific application.
    
    Includes job details, timeline events, interviews, and offer if available.
    """
    app_row = db.get_application(application_id, user_id)
    if not app_row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Application {application_id} not found"
        )
    
    cur = db.conn.cursor()
    
    # Get job details
    job = db.get_job(app_row["job_id"])
    job_details = None
    if job:
        company_row = cur.execute(
            "SELECT name FROM companies WHERE id = ?",
            (job["company_id"],)
        ).fetchone()
        job_version = db.get_latest_job_version(app_row["job_id"])
        
        job_details = {
            "job_id": job["job_id"],
            "company": company_row["name"] if company_row else "Unknown",
            "company_id": job["company_id"],
            "title": job_version["title"] if job_version else "Unknown",
            "location": job_version["location"] if job_version else "",
            "url": job["url"],
            "source": job["source"],
        }
    
    # Get timeline events
    events = db.get_application_events(application_id)
    timeline = [
        {
            "event_id": event["event_id"],
            "event_type": event["event_type"],
            "event_data": json.loads(event["event_data"]) if event["event_data"] else {},
            "created_at": event["created_at"]
        }
        for event in events
    ]
    
    # Get interviews
    interviews = db.list_interviews(application_id=application_id)
    interview_list = [
        {
            "interview_id": int(row["interview_id"]),
            "interview_type": row["interview_type"],
            "scheduled_at": row["scheduled_at"],
            "duration_minutes": row["duration_minutes"],
            "interviewer_name": row["interviewer_name"],
            "interviewer_email": row["interviewer_email"],
            "location": row["location"],
            "notes": row["notes"],
            "preparation_notes": row["preparation_notes"],
            "status": row["status"],
            "created_at": row["created_at"]
        }
        for row in interviews
    ]
    
    # Get offer if exists
    offer_row = db.get_offer(application_id)
    offer = None
    if offer_row:
        offer = {
            "offer_id": int(offer_row["offer_id"]),
            "offer_date": offer_row["offer_date"],
            "salary_amount": offer_row["salary_amount"],
            "salary_currency": offer_row["salary_currency"],
            "salary_period": offer_row["salary_period"],
            "equity": offer_row["equity"],
            "benefits": offer_row["benefits"],
            "start_date": offer_row["start_date"],
            "decision_deadline": offer_row["decision_deadline"],
            "status": offer_row["status"],
            "notes": offer_row["notes"],
            "created_at": offer_row["created_at"]
        }
    
    return {
        "application": _application_row_to_response(app_row).model_dump(),
        "job": job_details,
        "timeline": timeline,
        "interviews": interview_list,
        "offer": offer
    }


@router.patch("/{application_id}", response_model=ApplicationResponse)
async def update_application(
    application_id: int,
    update: ApplicationUpdate,
    user_id: int = Depends(require_auth),
    db: Database = Depends(get_db)
):
    """
    Update an application.
    
    Status changes are automatically tracked in the timeline.
    """
    # Verify application exists and belongs to user
    app_row = db.get_application(application_id, user_id)
    if not app_row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Application {application_id} not found"
        )
    
    # Update application
    updated = db.update_application(
        application_id=application_id,
        user_id=user_id,
        status=update.status,
        notes=update.notes,
        tags=update.tags,
        priority=update.priority,
    )
    
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update application"
        )
    
    # Get updated application
    updated_app = db.get_application(application_id, user_id)
    if not updated_app:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve updated application"
        )
    
    return _application_row_to_response(updated_app)


@router.delete("/{application_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_application(
    application_id: int,
    user_id: int = Depends(require_auth),
    db: Database = Depends(get_db)
):
    """Delete an application and all associated data."""
    deleted = db.delete_application(application_id, user_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Application {application_id} not found"
        )
    return None


# Interview endpoints
@router.post("/{application_id}/interviews", response_model=InterviewResponse, status_code=status.HTTP_201_CREATED)
async def create_interview(
    application_id: int,
    interview: InterviewCreate,
    user_id: int = Depends(require_auth),
    db: Database = Depends(get_db)
):
    """Create a new interview for an application."""
    # Verify application exists and belongs to user
    app_row = db.get_application(application_id, user_id)
    if not app_row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Application {application_id} not found"
        )
    
    # Override application_id from path
    interview_data = interview.model_dump()
    interview_data.pop("application_id", None)  # Remove if present
    
    interview_id = db.create_interview(
        application_id=application_id,
        interview_type=interview.interview_type,
        scheduled_at=interview.scheduled_at,
        duration_minutes=interview.duration_minutes,
        interviewer_name=interview.interviewer_name,
        interviewer_email=interview.interviewer_email,
        location=interview.location,
        notes=interview.notes,
        preparation_notes=interview.preparation_notes,
    )
    
    interview_row = db.get_interview(interview_id)
    if not interview_row:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve created interview"
        )
    
    return _interview_row_to_response(interview_row)


@router.get("/{application_id}/interviews", response_model=List[InterviewResponse])
async def list_application_interviews(
    application_id: int,
    user_id: int = Depends(require_auth),
    db: Database = Depends(get_db)
):
    """List all interviews for an application."""
    # Verify application exists and belongs to user
    app_row = db.get_application(application_id, user_id)
    if not app_row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Application {application_id} not found"
        )
    
    interviews = db.list_interviews(application_id=application_id)
    return [_interview_row_to_response(row) for row in interviews]


@router.patch("/interviews/{interview_id}", response_model=InterviewResponse)
async def update_interview(
    interview_id: int,
    interview_update: InterviewUpdate,
    user_id: int = Depends(require_auth),
    db: Database = Depends(get_db)
):
    """Update an interview."""
    # Verify interview exists and belongs to user's application
    interview_row = db.get_interview(interview_id)
    if not interview_row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Interview {interview_id} not found"
        )
    
    # Verify application belongs to user
    app_row = db.get_application(interview_row["application_id"], user_id)
    if not app_row:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Interview does not belong to your applications"
        )
    
    # Update interview
    updated = db.update_interview(
        interview_id=interview_id,
        interview_type=interview_update.interview_type,
        scheduled_at=interview_update.scheduled_at,
        duration_minutes=interview_update.duration_minutes,
        interviewer_name=interview_update.interviewer_name,
        interviewer_email=interview_update.interviewer_email,
        location=interview_update.location,
        notes=interview_update.notes,
        preparation_notes=interview_update.preparation_notes,
        status=interview_update.status,
    )
    
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update interview"
        )
    
    updated_interview = db.get_interview(interview_id)
    if not updated_interview:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve updated interview"
        )
    
    return _interview_row_to_response(updated_interview)


@router.delete("/interviews/{interview_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_interview(
    interview_id: int,
    user_id: int = Depends(require_auth),
    db: Database = Depends(get_db)
):
    """Delete an interview."""
    # Verify interview exists and belongs to user's application
    interview_row = db.get_interview(interview_id)
    if not interview_row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Interview {interview_id} not found"
        )
    
    app_row = db.get_application(interview_row["application_id"], user_id)
    if not app_row:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Interview does not belong to your applications"
        )
    
    deleted = db.delete_interview(interview_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete interview"
        )
    return None


# Offer endpoints
@router.post("/{application_id}/offers", response_model=OfferResponse, status_code=status.HTTP_201_CREATED)
async def create_offer(
    application_id: int,
    offer: OfferCreate,
    user_id: int = Depends(require_auth),
    db: Database = Depends(get_db)
):
    """Create a new offer for an application."""
    # Verify application exists and belongs to user
    app_row = db.get_application(application_id, user_id)
    if not app_row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Application {application_id} not found"
        )
    
    # Check if offer already exists
    existing_offer = db.get_offer(application_id)
    if existing_offer:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Offer already exists for this application"
        )
    
    offer_id = db.create_offer(
        application_id=application_id,
        offer_date=offer.offer_date,
        salary_amount=offer.salary_amount,
        salary_currency=offer.salary_currency,
        salary_period=offer.salary_period,
        equity=offer.equity,
        benefits=offer.benefits,
        start_date=offer.start_date,
        decision_deadline=offer.decision_deadline,
        status=offer.status,
        notes=offer.notes,
    )
    
    offer_row = db.get_offer(application_id)
    if not offer_row:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve created offer"
        )
    
    return _offer_row_to_response(offer_row)


@router.get("/{application_id}/offers", response_model=Optional[OfferResponse])
async def get_application_offer(
    application_id: int,
    user_id: int = Depends(require_auth),
    db: Database = Depends(get_db)
):
    """Get the offer for an application (if exists)."""
    # Verify application exists and belongs to user
    app_row = db.get_application(application_id, user_id)
    if not app_row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Application {application_id} not found"
        )
    
    offer_row = db.get_offer(application_id)
    if not offer_row:
        return None
    
    return _offer_row_to_response(offer_row)


@router.patch("/{application_id}/offers", response_model=OfferResponse)
async def update_offer(
    application_id: int,
    offer_update: OfferUpdate,
    user_id: int = Depends(require_auth),
    db: Database = Depends(get_db)
):
    """Update an offer."""
    # Verify application exists and belongs to user
    app_row = db.get_application(application_id, user_id)
    if not app_row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Application {application_id} not found"
        )
    
    # Update offer
    updated = db.update_offer(
        application_id=application_id,
        offer_date=offer_update.offer_date,
        salary_amount=offer_update.salary_amount,
        salary_currency=offer_update.salary_currency,
        salary_period=offer_update.salary_period,
        equity=offer_update.equity,
        benefits=offer_update.benefits,
        start_date=offer_update.start_date,
        decision_deadline=offer_update.decision_deadline,
        status=offer_update.status,
        notes=offer_update.notes,
    )
    
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Offer not found for this application"
        )
    
    offer_row = db.get_offer(application_id)
    if not offer_row:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve updated offer"
        )
    
    return _offer_row_to_response(offer_row)


# Calendar/upcoming endpoints
@router.get("/upcoming/interviews")
async def get_upcoming_interviews(
    days: int = Query(30, ge=1, le=365, description="Number of days ahead to look"),
    user_id: int = Depends(require_auth),
    db: Database = Depends(get_db)
):
    """Get upcoming interviews for the authenticated user."""
    from datetime import timedelta
    
    # Calculate the cutoff date based on days parameter
    cutoff_date = datetime.now() + timedelta(days=days)
    
    interviews = db.list_interviews(
        user_id=user_id,
        upcoming_only=True
    )
    
    # Filter interviews within the specified days and before cutoff
    filtered_interviews = []
    for interview_row in interviews:
        scheduled_at = interview_row.get("scheduled_at")
        if scheduled_at and isinstance(scheduled_at, str):
            scheduled_at = datetime.fromisoformat(scheduled_at.replace('Z', '+00:00'))
        elif scheduled_at and isinstance(scheduled_at, datetime):
            pass  # Already a datetime
        else:
            continue
        
        # Only include interviews within the days window
        if scheduled_at <= cutoff_date:
            filtered_interviews.append(interview_row)
    
    # Enrich with application and job details
    cur = db.conn.cursor()
    enriched = []
    for interview_row in filtered_interviews:
        app_row = db.get_application(interview_row["application_id"], user_id)
        if not app_row:
            continue
        
        job = db.get_job(app_row["job_id"])
        if not job:
            continue
        
        company_row = cur.execute(
            "SELECT name FROM companies WHERE id = ?",
            (job["company_id"],)
        ).fetchone()
        job_version = db.get_latest_job_version(app_row["job_id"])
        
        enriched.append({
            "interview": _interview_row_to_response(interview_row).model_dump(),
            "application_id": int(app_row["application_id"]),
            "job": {
                "job_id": job["job_id"],
                "company": company_row["name"] if company_row else "Unknown",
                "title": job_version["title"] if job_version else "Unknown",
            }
        })
    
    return enriched


# Helper functions
def _application_row_to_response(row: sqlite3.Row) -> ApplicationResponse:
    """Convert a database row to ApplicationResponse."""
    tags = None
    if row["tags"]:
        try:
            tags = json.loads(row["tags"])
        except (json.JSONDecodeError, TypeError):
            tags = None
    
    return ApplicationResponse(
        application_id=int(row["application_id"]),
        user_id=int(row["user_id"]),
        job_id=row["job_id"],
        status=row["status"],
        applied_at=row["applied_at"],
        application_method=row["application_method"],
        application_url=row["application_url"],
        notes=row["notes"],
        tags=row["tags"],  # Keep as JSON string for response
        priority=int(row["priority"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"]
    )


def _interview_row_to_response(row: sqlite3.Row) -> InterviewResponse:
    """Convert a database row to InterviewResponse."""
    return InterviewResponse(
        interview_id=int(row["interview_id"]),
        application_id=int(row["application_id"]),
        interview_type=row["interview_type"],
        scheduled_at=row["scheduled_at"],
        duration_minutes=row["duration_minutes"],
        interviewer_name=row["interviewer_name"],
        interviewer_email=row["interviewer_email"],
        location=row["location"],
        notes=row["notes"],
        preparation_notes=row["preparation_notes"],
        status=row["status"],
        created_at=row["created_at"]
    )


def _offer_row_to_response(row: sqlite3.Row) -> OfferResponse:
    """Convert a database row to OfferResponse."""
    return OfferResponse(
        offer_id=int(row["offer_id"]),
        application_id=int(row["application_id"]),
        offer_date=row["offer_date"],
        salary_amount=row["salary_amount"],
        salary_currency=row["salary_currency"],
        salary_period=row["salary_period"],
        equity=row["equity"],
        benefits=row["benefits"],
        start_date=row["start_date"],
        decision_deadline=row["decision_deadline"],
        status=row["status"],
        notes=row["notes"],
        created_at=row["created_at"]
    )
