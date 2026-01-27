"""
Export API endpoints for CSV and PDF export of jobs and applications.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import StreamingResponse
from typing import Optional, List, Dict, Any
from datetime import datetime
import csv
import io
import json

from job_tracker.api.dependencies import get_db, require_auth
from job_tracker.db import Database

router = APIRouter(prefix="/api/export", tags=["export"])


@router.get("/applications/csv")
async def export_applications_csv(
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status"),
    user_id: int = Depends(require_auth),
    db: Database = Depends(get_db)
):
    """Export applications to CSV."""
    cur = db.conn.cursor()
    
    # Build query
    query = """
        SELECT 
            a.application_id,
            a.status,
            a.applied_at,
            a.application_method,
            a.application_url,
            a.notes,
            a.priority,
            a.created_at,
            a.updated_at,
            c.name AS company_name,
            v.title AS job_title,
            v.location AS job_location,
            j.url AS job_url
        FROM applications a
        JOIN jobs j ON a.job_id = j.job_id
        JOIN companies c ON j.company_id = c.id
        LEFT JOIN job_versions v ON v.job_id = j.job_id
        LEFT JOIN (
            SELECT job_id, MAX(timestamp) AS max_ts
            FROM job_versions
            GROUP BY job_id
        ) latest ON latest.job_id = v.job_id AND latest.max_ts = v.timestamp
        WHERE a.user_id = ?
    """
    params = [user_id]
    
    if status_filter:
        query += " AND a.status = ?"
        params.append(status_filter)
    
    query += " ORDER BY a.created_at DESC"
    
    rows = cur.execute(query, params).fetchall()
    
    # Create CSV
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write header
    writer.writerow([
        'Application ID', 'Status', 'Applied At', 'Company', 'Job Title',
        'Location', 'Application Method', 'Application URL', 'Priority',
        'Notes', 'Created At', 'Updated At', 'Job URL'
    ])
    
    # Write data
    for row in rows:
        writer.writerow([
            row['application_id'],
            row['status'],
            row['applied_at'] or '',
            row['company_name'] or '',
            row['job_title'] or '',
            row['job_location'] or '',
            row['application_method'] or '',
            row['application_url'] or '',
            row['priority'] or 0,
            row['notes'] or '',
            row['created_at'] or '',
            row['updated_at'] or '',
            row['job_url'] or ''
        ])
    
    output.seek(0)
    
    # Generate filename
    filename = f"applications_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@router.get("/jobs/csv")
async def export_jobs_csv(
    location: Optional[str] = Query(None),
    remote: Optional[bool] = Query(None),
    company: Optional[str] = Query(None),
    sector: Optional[str] = Query(None),
    keywords: Optional[str] = Query(None),
    new_grad: Optional[bool] = Query(None),
    user_id: Optional[int] = Depends(require_auth),
    db: Database = Depends(get_db)
):
    """Export jobs to CSV. Requires authentication but filters are optional."""
    cur = db.conn.cursor()
    
    # Build query similar to jobs search
    query = """
        SELECT DISTINCT
            j.job_id,
            c.name AS company,
            v.title,
            v.location,
            v.remote,
            j.url,
            j.source,
            v.sector,
            j.first_seen AS posted_at,
            j.last_seen
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
    
    # Apply filters (same as jobs search endpoint)
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
            pass
    
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
    
    if new_grad is not None:
        latest_snapshot = cur.execute(
            "SELECT snapshot_id FROM snapshots ORDER BY timestamp DESC LIMIT 1"
        ).fetchone()
        if latest_snapshot:
            snapshot_id = latest_snapshot["snapshot_id"]
            conditions.append("EXISTS (SELECT 1 FROM snapshot_jobs sj WHERE sj.job_id = j.job_id AND sj.snapshot_id = ? AND sj.is_new_grad = ?)")
            params.extend([snapshot_id, 1 if new_grad else 0])
    
    if conditions:
        query += " AND " + " AND ".join(conditions)
    
    query += " ORDER BY j.last_seen DESC"
    
    rows = cur.execute(query, params).fetchall()
    
    # Create CSV
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write header
    writer.writerow([
        'Job ID', 'Company', 'Title', 'Location', 'Remote', 'Sector',
        'Source', 'Posted At', 'Last Seen', 'URL'
    ])
    
    # Write data
    for row in rows:
        writer.writerow([
            row['job_id'],
            row['company'] or '',
            row['title'] or '',
            row['location'] or '',
            'Yes' if row['remote'] else 'No',
            row['sector'] or '',
            row['source'] or '',
            row['posted_at'] or '',
            row['last_seen'] or '',
            row['url'] or ''
        ])
    
    output.seek(0)
    
    # Generate filename
    filename = f"jobs_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
