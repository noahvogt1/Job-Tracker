"""
Job alert service for checking saved searches against new jobs.
"""

from datetime import datetime
from typing import List, Dict, Any
import json

from job_tracker.db import Database
from job_tracker.services.notifications import notify_job_alert


def check_saved_searches(db: Database, new_job_ids: List[str]):
    """
    Check saved searches against newly collected jobs and send notifications.
    
    Args:
        db: Database instance
        new_job_ids: List of job IDs that were just collected/added
    """
    if not new_job_ids:
        return
    
    cur = db.conn.cursor()
    
    # Get all active saved searches with notifications enabled
    searches = cur.execute(
        """
        SELECT search_id, user_id, name, filters, last_run_at
        FROM saved_searches
        WHERE notification_enabled = 1
        """
    ).fetchall()
    
    for search in searches:
        try:
            filters = json.loads(search["filters"]) if isinstance(search["filters"], str) else search["filters"]
            user_id = search["user_id"]
            search_id = search["search_id"]
            
            # Get jobs matching this search that are in the new_job_ids list
            matching_jobs = _find_matching_jobs(db, filters, new_job_ids)
            
            # Check if we've already notified for these jobs (since last_run_at)
            last_run = search["last_run_at"]
            if last_run:
                # Filter out jobs that existed before last run
                last_run_dt = datetime.fromisoformat(last_run) if isinstance(last_run, str) else last_run
                matching_jobs = [
                    job for job in matching_jobs
                    if datetime.fromisoformat(job["first_seen"]) > last_run_dt
                ]
            
            # Send notifications for matching jobs
            for job in matching_jobs:
                notify_job_alert(
                    db,
                    user_id,
                    job["job_id"],
                    job["title"],
                    job["company"]
                )
            
            # Update last_run_at
            cur.execute(
                "UPDATE saved_searches SET last_run_at = ? WHERE search_id = ?",
                (datetime.now(), search_id)
            )
            
        except Exception as e:
            # Log error but continue with other searches
            print(f"Error checking saved search {search.get('search_id')}: {e}")
            continue
    
    db.conn.commit()


def _find_matching_jobs(db: Database, filters: Dict[str, Any], job_ids: List[str]) -> List[Dict[str, Any]]:
    """
    Find jobs matching the given filters from the provided job IDs.
    
    This is a simplified matching function. In production, you'd want to
    use the same query logic as the jobs search endpoint.
    """
    if not job_ids:
        return []
    
    cur = db.conn.cursor()
    placeholders = ",".join("?" * len(job_ids))
    
    # Build query similar to jobs search endpoint
    query = f"""
        SELECT DISTINCT
            j.job_id,
            c.name AS company,
            v.title,
            v.location,
            v.remote,
            v.sector,
            j.first_seen,
            v.extra
        FROM jobs j
        JOIN companies c ON j.company_id = c.id
        JOIN job_versions v ON v.job_id = j.job_id
        JOIN (
            SELECT job_id, MAX(timestamp) AS max_ts
            FROM job_versions
            GROUP BY job_id
        ) latest ON latest.job_id = v.job_id AND latest.max_ts = v.timestamp
        WHERE j.job_id IN ({placeholders}) AND j.active = 1
    """
    
    params = list(job_ids)
    conditions = []
    
    # Apply filters
    if filters.get("location"):
        conditions.append("v.location LIKE ?")
        params.append(f"%{filters['location']}%")
    
    if filters.get("remote") is not None:
        conditions.append("v.remote = ?")
        params.append(1 if filters["remote"] else 0)
    
    if filters.get("company"):
        company_ids = filters["company"]
        if isinstance(company_ids, list) and company_ids:
            placeholders_c = ",".join("?" * len(company_ids))
            conditions.append(f"c.id IN ({placeholders_c})")
            params.extend(company_ids)
    
    if filters.get("sector"):
        sectors = filters["sector"]
        if isinstance(sectors, list):
            sectors = [s for s in sectors if s]
        elif isinstance(sectors, str):
            sectors = [s.strip() for s in sectors.split(",") if s.strip()]
        if sectors:
            placeholders_s = ",".join("?" * len(sectors))
            conditions.append(f"v.sector IN ({placeholders_s})")
            params.extend(sectors)
    
    if filters.get("keywords"):
        keyword_pattern = f"%{filters['keywords']}%"
        conditions.append("(v.title LIKE ? OR v.extra LIKE ?)")
        params.extend([keyword_pattern, keyword_pattern])
    
    if filters.get("new_grad"):
        # This would require joining with snapshot_jobs, simplified for now
        pass
    
    if conditions:
        query += " AND " + " AND ".join(conditions)
    
    rows = cur.execute(query, params).fetchall()
    
    return [
        {
            "job_id": row["job_id"],
            "company": row["company"],
            "title": row["title"],
            "first_seen": row["first_seen"]
        }
        for row in rows
    ]
