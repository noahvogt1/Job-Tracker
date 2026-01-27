"""
Job search and management API endpoints.

Provides endpoints for searching jobs, viewing job details, saving jobs,
and managing job-related data.
"""

from fastapi import APIRouter, Depends, Query, HTTPException, status
from typing import Optional, List, Dict, Any
from datetime import datetime
import json

from job_tracker.api.schemas import JobResponse, JobDetailResponse
from job_tracker.api.dependencies import get_db, get_current_user, require_auth
from job_tracker.db import Database

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


@router.get("", response_model=Dict[str, Any])
async def search_jobs(
    location: Optional[str] = Query(None, description="Filter by location (partial match)"),
    remote: Optional[bool] = Query(None, description="Filter by remote work availability"),
    company: Optional[str] = Query(None, description="Comma-separated company IDs"),
    sector: Optional[str] = Query(None, description="Comma-separated sectors"),
    keywords: Optional[str] = Query(None, description="Search keywords in title and description"),
    new_grad: Optional[bool] = Query(None, description="Filter for new grad positions"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=1000, description="Items per page"),
    db: Database = Depends(get_db)
):
    """
    Search jobs with comprehensive filtering options.
    
    Returns paginated results with total count for proper pagination UI.
    """
    # Build base query to get latest job versions
    base_query = """
        SELECT DISTINCT
            j.job_id,
            c.name AS company,
            c.id AS company_id,
            v.title,
            v.location,
            v.remote,
            j.url,
            j.source,
            v.sector,
            j.first_seen AS posted_at,
            j.last_seen,
            v.extra
        FROM jobs j
        JOIN companies c ON j.company_id = c.id
        JOIN job_versions v ON v.job_id = j.job_id
        JOIN (
            SELECT job_id, MAX(timestamp) AS max_ts
            FROM job_versions
            GROUP BY job_id
        ) latest ON latest.job_id = v.job_id AND latest.max_ts = v.timestamp
        WHERE j.active = 1
    """
    
    params: List[Any] = []
    conditions: List[str] = []
    
    # Apply filters
    if location:
        conditions.append("v.location LIKE ?")
        params.append(f"%{location}%")
    
    if remote is not None:
        conditions.append("v.remote = ?")
        params.append(1 if remote else 0)
    
    if company:
        try:
            company_ids = [int(c.strip()) for c in company.split(",") if c.strip()]
            if company_ids:
                placeholders = ",".join("?" * len(company_ids))
                conditions.append(f"c.id IN ({placeholders})")
                params.extend(company_ids)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid company IDs format"
            )
    
    if sector:
        sectors = [s.strip() for s in sector.split(",") if s.strip()]
        if sectors:
            placeholders = ",".join("?" * len(sectors))
            conditions.append(f"v.sector IN ({placeholders})")
            params.extend(sectors)
    
    if keywords:
        keyword_pattern = f"%{keywords}%"
        conditions.append("(v.title LIKE ? OR v.extra LIKE ?)")
        params.extend([keyword_pattern, keyword_pattern])
    
    # Get cursor for queries
    cur = db.conn.cursor()
    
    # Handle new_grad filter - need to join with latest snapshot
    if new_grad is not None:
        # Get the latest snapshot ID
        latest_snapshot = cur.execute("""
            SELECT snapshot_id FROM snapshots 
            ORDER BY timestamp DESC LIMIT 1
        """).fetchone()
        
        if latest_snapshot:
            snapshot_id = latest_snapshot["snapshot_id"]
            conditions.append("EXISTS (SELECT 1 FROM snapshot_jobs sj WHERE sj.job_id = j.job_id AND sj.snapshot_id = ? AND sj.is_new_grad = ?)")
            params.extend([snapshot_id, 1 if new_grad else 0])
        else:
            # No snapshots yet, return empty result if filtering for new_grad
            if new_grad:
                return {
                    "jobs": [],
                    "total": 0,
                    "page": page,
                    "page_size": page_size,
                    "total_pages": 0
                }
    
    # Add conditions to query
    if conditions:
        base_query += " AND " + " AND ".join(conditions)
    
    # Get total count for pagination
    # Alias the subquery so we can reference its columns
    count_query = f"SELECT COUNT(DISTINCT sub.job_id) as total FROM ({base_query}) AS sub"
    count_row = cur.execute(count_query, params).fetchone()
    total = count_row["total"] if count_row else 0
    
    # Add ordering and pagination
    query = base_query + " ORDER BY j.last_seen DESC"
    offset = (page - 1) * page_size
    query += " LIMIT ? OFFSET ?"
    params.extend([page_size, offset])
    
    # Execute query
    rows = cur.execute(query, params).fetchall()
    
    # Parse extra field (JSON)
    jobs = []
    for row in rows:
        extra_data = None
        if row["extra"]:
            try:
                extra_data = json.loads(row["extra"])
            except (json.JSONDecodeError, TypeError):
                extra_data = {}
        
        # Determine is_new_grad from latest snapshot if needed
        is_new_grad = False
        if new_grad is None:  # Only check if not already filtered
            snapshot_check = cur.execute("""
                SELECT sj.is_new_grad
                FROM snapshot_jobs sj
                JOIN snapshots s ON sj.snapshot_id = s.snapshot_id
                WHERE sj.job_id = ?
                ORDER BY s.timestamp DESC
                LIMIT 1
            """, (row["job_id"],)).fetchone()
            if snapshot_check:
                is_new_grad = bool(snapshot_check["is_new_grad"])
        
        jobs.append(JobResponse(
            job_id=row["job_id"],
            company=row["company"],
            company_id=row["company_id"],
            title=row["title"],
            location=row["location"] or "",
            remote=bool(row["remote"]) if row["remote"] is not None else None,
            url=row["url"],
            source=row["source"],
            sector=row["sector"],
            posted_at=row["posted_at"],
            is_new_grad=is_new_grad if new_grad is None else new_grad
        ))
    
    return {
        "jobs": jobs,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size if page_size > 0 else 0
    }


@router.get("/{job_id}", response_model=JobDetailResponse)
async def get_job(
    job_id: str,
    db: Database = Depends(get_db)
):
    """
    Get detailed information about a specific job.
    
    Includes full job details, company information, and any additional
    metadata stored in the job_versions extra field.
    """
    cur = db.conn.cursor()
    
    # Get latest job version with company info
    query = """
        SELECT
            j.job_id,
            c.name AS company,
            c.id AS company_id,
            v.title,
            v.location,
            v.remote,
            j.url,
            j.source,
            v.sector,
            j.first_seen AS posted_at,
            j.last_seen,
            v.extra,
            v.timestamp AS version_timestamp
        FROM jobs j
        JOIN companies c ON j.company_id = c.id
        JOIN job_versions v ON v.job_id = j.job_id
        WHERE j.job_id = ?
        ORDER BY v.timestamp DESC
        LIMIT 1
    """
    
    row = cur.execute(query, (job_id,)).fetchone()
    
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found"
        )
    
    # Parse extra field
    extra_data = None
    if row["extra"]:
        try:
            extra_data = json.loads(row["extra"])
        except (json.JSONDecodeError, TypeError):
            extra_data = {}
    
    # Check if new grad from latest snapshot
    snapshot_check = cur.execute("""
        SELECT sj.is_new_grad
        FROM snapshot_jobs sj
        JOIN snapshots s ON sj.snapshot_id = s.snapshot_id
        WHERE sj.job_id = ?
        ORDER BY s.timestamp DESC
        LIMIT 1
    """, (job_id,)).fetchone()
    
    is_new_grad = bool(snapshot_check["is_new_grad"]) if snapshot_check else False
    
    # Extract description from extra if available
    description = None
    if extra_data:
        description = extra_data.get("description") or extra_data.get("content") or extra_data.get("body")
    
    return JobDetailResponse(
        job_id=row["job_id"],
        company=row["company"],
        company_id=row["company_id"],
        title=row["title"],
        location=row["location"] or "",
        remote=bool(row["remote"]) if row["remote"] is not None else None,
        url=row["url"],
        source=row["source"],
        sector=row["sector"],
        posted_at=row["posted_at"],
        is_new_grad=is_new_grad,
        extra=extra_data,
        description=description
    )


@router.get("/filters/options", response_model=Dict[str, List[Dict[str, Any]]])
async def get_filter_options(
    db: Database = Depends(get_db)
):
    """
    Get available filter options for the job search.
    
    Returns lists of companies and sectors that have active jobs.
    """
    cur = db.conn.cursor()
    
    # Get distinct companies with active jobs
    companies_query = """
        SELECT DISTINCT c.id, c.name, COUNT(DISTINCT j.job_id) as job_count
        FROM companies c
        JOIN jobs j ON j.company_id = c.id
        WHERE j.active = 1
        GROUP BY c.id, c.name
        ORDER BY c.name ASC
    """
    companies_rows = cur.execute(companies_query).fetchall()
    companies = [
        {"id": row["id"], "name": row["name"], "job_count": row["job_count"]}
        for row in companies_rows
    ]
    
    # Get distinct sectors with active jobs
    sectors_query = """
        SELECT DISTINCT v.sector, COUNT(DISTINCT j.job_id) as job_count
        FROM job_versions v
        JOIN jobs j ON j.job_id = v.job_id
        JOIN (
            SELECT job_id, MAX(timestamp) AS max_ts
            FROM job_versions
            GROUP BY job_id
        ) latest ON latest.job_id = v.job_id AND latest.max_ts = v.timestamp
        WHERE j.active = 1 AND v.sector IS NOT NULL AND v.sector != ''
        GROUP BY v.sector
        ORDER BY job_count DESC, v.sector ASC
    """
    sectors_rows = cur.execute(sectors_query).fetchall()
    sectors = [
        {"name": row["sector"], "job_count": row["job_count"]}
        for row in sectors_rows
    ]
    
    return {
        "companies": companies,
        "sectors": sectors
    }


@router.post("/{job_id}/save")
async def save_job(
    job_id: str,
    user_id: int = Depends(require_auth),
    db: Database = Depends(get_db)
):
    """
    Save a job for the authenticated user.
    
    Creates a saved_jobs entry if it doesn't already exist.
    """
    cur = db.conn.cursor()
    
    # Verify job exists
    job = cur.execute("SELECT job_id FROM jobs WHERE job_id = ? AND active = 1", (job_id,)).fetchone()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found"
        )
    
    # Check if already saved
    existing = cur.execute(
        "SELECT saved_id FROM saved_jobs WHERE user_id = ? AND job_id = ?",
        (user_id, job_id)
    ).fetchone()
    
    if existing:
        return {"message": "Job already saved", "saved_id": existing["saved_id"]}
    
    # Save the job
    cur.execute(
        "INSERT INTO saved_jobs (user_id, job_id, saved_at) VALUES (?, ?, ?)",
        (user_id, job_id, datetime.now())
    )
    db.conn.commit()
    
    return {"message": "Job saved successfully", "saved_id": cur.lastrowid}


@router.delete("/{job_id}/save")
async def unsave_job(
    job_id: str,
    user_id: int = Depends(require_auth),
    db: Database = Depends(get_db)
):
    """
    Remove a saved job for the authenticated user.
    """
    cur = db.conn.cursor()
    
    result = cur.execute(
        "DELETE FROM saved_jobs WHERE user_id = ? AND job_id = ?",
        (user_id, job_id)
    )
    db.conn.commit()
    
    if result.rowcount == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Saved job not found"
        )
    
    return {"message": "Job unsaved successfully"}


@router.get("/saved/list", response_model=Dict[str, Any])
async def get_saved_jobs(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    user_id: int = Depends(require_auth),
    db: Database = Depends(get_db)
):
    """
    Get list of saved jobs for the authenticated user.
    """
    cur = db.conn.cursor()
    
    # Get total count
    count_query = """
        SELECT COUNT(*) as total
        FROM saved_jobs sj
        JOIN jobs j ON sj.job_id = j.job_id
        WHERE sj.user_id = ? AND j.active = 1
    """
    total = cur.execute(count_query, (user_id,)).fetchone()["total"]
    
    # Get saved jobs with job details
    query = """
        SELECT
            sj.saved_id,
            sj.saved_at,
            sj.notes,
            sj.priority,
            sj.deadline,
            j.job_id,
            c.name AS company,
            c.id AS company_id,
            v.title,
            v.location,
            v.remote,
            j.url,
            j.source,
            v.sector,
            j.first_seen AS posted_at
        FROM saved_jobs sj
        JOIN jobs j ON sj.job_id = j.job_id
        JOIN companies c ON j.company_id = c.id
        JOIN job_versions v ON v.job_id = j.job_id
        JOIN (
            SELECT job_id, MAX(timestamp) AS max_ts
            FROM job_versions
            GROUP BY job_id
        ) latest ON latest.job_id = v.job_id AND latest.max_ts = v.timestamp
        WHERE sj.user_id = ? AND j.active = 1
        ORDER BY sj.saved_at DESC
        LIMIT ? OFFSET ?
    """
    
    offset = (page - 1) * page_size
    rows = cur.execute(query, (user_id, page_size, offset)).fetchall()
    
    jobs = []
    for row in rows:
        # Check if new grad
        snapshot_check = cur.execute("""
            SELECT sj.is_new_grad
            FROM snapshot_jobs sj
            JOIN snapshots s ON sj.snapshot_id = s.snapshot_id
            WHERE sj.job_id = ?
            ORDER BY s.timestamp DESC
            LIMIT 1
        """, (row["job_id"],)).fetchone()
        
        is_new_grad = bool(snapshot_check["is_new_grad"]) if snapshot_check else False
        
        jobs.append({
            "saved_id": row["saved_id"],
            "saved_at": row["saved_at"],
            "notes": row["notes"],
            "priority": row["priority"],
            "deadline": row["deadline"],
            "job": JobResponse(
                job_id=row["job_id"],
                company=row["company"],
                company_id=row["company_id"],
                title=row["title"],
                location=row["location"] or "",
                remote=bool(row["remote"]) if row["remote"] is not None else None,
                url=row["url"],
                source=row["source"],
                sector=row["sector"],
                posted_at=row["posted_at"],
                is_new_grad=is_new_grad
            ).model_dump()
        })
    
    return {
        "jobs": jobs,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size if page_size > 0 else 0
    }
