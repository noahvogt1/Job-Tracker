"""
Advanced search API endpoints for full-text search across jobs, companies, and applications.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List, Dict, Any, Optional
from datetime import datetime

from job_tracker.api.dependencies import get_db, require_auth
from job_tracker.db import Database

router = APIRouter(prefix="/api/search", tags=["search"])


@router.get("")
async def advanced_search(
    q: str = Query(..., description="Search query"),
    types: Optional[str] = Query(None, description="Comma-separated types: jobs,companies,applications"),
    user_id: Optional[int] = Depends(require_auth),
    db: Database = Depends(get_db)
):
    """
    Advanced full-text search across jobs, companies, and applications.
    
    Searches in:
    - Jobs: title, location, company name
    - Companies: name, industry, description
    - Applications: notes (if authenticated)
    """
    search_types = types.split(",") if types else ["jobs", "companies", "applications"]
    query_lower = q.lower()
    results = {
        "query": q,
        "jobs": [],
        "companies": [],
        "applications": []
    }
    
    cur = db.conn.cursor()
    
    if "jobs" in search_types:
        # Search jobs by title, location, company name
        job_rows = cur.execute(
            """
            SELECT DISTINCT
                j.job_id,
                c.name AS company,
                v.title,
                v.location,
                v.remote,
                j.url,
                v.sector
            FROM jobs j
            JOIN companies c ON j.company_id = c.id
            JOIN job_versions v ON v.job_id = j.job_id
            JOIN (
                SELECT job_id, MAX(timestamp) AS max_ts
                FROM job_versions
                GROUP BY job_id
            ) latest ON latest.job_id = v.job_id AND latest.max_ts = v.timestamp
            WHERE j.active = 1
              AND (
                  LOWER(v.title) LIKE ? OR
                  LOWER(v.location) LIKE ? OR
                  LOWER(c.name) LIKE ? OR
                  LOWER(v.sector) LIKE ? OR
                  LOWER(v.extra) LIKE ?
              )
            LIMIT 50
            """,
            (f"%{query_lower}%", f"%{query_lower}%", f"%{query_lower}%", f"%{query_lower}%", f"%{query_lower}%")
        ).fetchall()
        
        results["jobs"] = [
            {
                "job_id": row["job_id"],
                "company": row["company"],
                "title": row["title"],
                "location": row["location"],
                "url": row["url"]
            }
            for row in job_rows
        ]
    
    if "companies" in search_types:
        # Search companies by name, industry, description
        company_rows = cur.execute(
            """
            SELECT c.id, c.name, c.slug, cp.industry, cp.description
            FROM companies c
            LEFT JOIN company_profiles cp ON cp.company_id = c.id
            WHERE LOWER(c.name) LIKE ? OR
                  LOWER(cp.industry) LIKE ? OR
                  LOWER(cp.description) LIKE ?
            LIMIT 50
            """,
            (f"%{query_lower}%", f"%{query_lower}%", f"%{query_lower}%")
        ).fetchall()
        
        results["companies"] = [
            {
                "id": row["id"],
                "name": row["name"],
                "slug": row["slug"],
                "industry": row["industry"]
            }
            for row in company_rows
        ]
    
    if "applications" in search_types and user_id:
        # Search applications by notes (user-specific)
        app_rows = cur.execute(
            """
            SELECT a.application_id, a.status, a.notes, a.job_id,
                   c.name AS company_name, v.title AS job_title
            FROM applications a
            JOIN jobs j ON a.job_id = j.job_id
            JOIN companies c ON j.company_id = c.id
            LEFT JOIN job_versions v ON v.job_id = j.job_id
            LEFT JOIN (
                SELECT job_id, MAX(timestamp) AS max_ts
                FROM job_versions
                GROUP BY job_id
            ) latest ON latest.job_id = v.job_id AND latest.max_ts = v.timestamp
            WHERE a.user_id = ? AND LOWER(a.notes) LIKE ?
            LIMIT 50
            """,
            (user_id, f"%{query_lower}%")
        ).fetchall()
        
        results["applications"] = [
            {
                "application_id": row["application_id"],
                "status": row["status"],
                "company": row["company_name"],
                "job_title": row["job_title"]
            }
            for row in app_rows
        ]
    
    return results
