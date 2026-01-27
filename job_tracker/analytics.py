"""
Analytics calculation engine for company hiring patterns.

Provides functions to calculate and analyze company hiring behavior,
including posting patterns, reliability scores, and new grad friendliness.
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional
from job_tracker.db import Database
import json
import sqlite3


def calculate_company_analytics(
    db: Database, 
    company_id: int, 
    snapshot_date: Optional[datetime] = None
) -> Dict[str, any]:
    """
    Calculate hiring pattern analytics for a company.
    
    Args:
        db: Database instance
        company_id: Company ID to analyze
        snapshot_date: Optional date for snapshot (defaults to today)
        
    Returns:
        Dictionary containing analytics metrics
    """
    if snapshot_date is None:
        snapshot_date = datetime.now()
    
    cur = db.conn.cursor()
    
    # Get job posting stats (last 90 days)
    cur.execute(
        """
        SELECT 
            COUNT(*) as total_posted,
            COUNT(CASE WHEN removed_at IS NOT NULL THEN 1 END) as total_removed,
            AVG(JULIANDAY(removed_at) - JULIANDAY(first_seen)) as avg_duration
        FROM jobs
        WHERE company_id = ? AND first_seen >= date('now', '-90 days')
        """,
        (company_id,)
    )
    stats = cur.fetchone()
    
    # Calculate ghost posting rate (jobs removed within 7 days)
    cur.execute(
        """
        SELECT COUNT(*) as ghost_count
        FROM jobs
        WHERE company_id = ?
          AND removed_at IS NOT NULL
          AND JULIANDAY(removed_at) - JULIANDAY(first_seen) <= 7
          AND first_seen >= date('now', '-90 days')
        """,
        (company_id,)
    )
    ghost_result = cur.fetchone()
    ghost_count = ghost_result["ghost_count"] if ghost_result else 0
    
    total_posted = stats["total_posted"] if stats and stats["total_posted"] else 0
    total_removed = stats["total_removed"] if stats and stats["total_removed"] else 0
    avg_duration = stats["avg_duration"] if stats and stats["avg_duration"] else 0
    
    ghost_posting_rate = (ghost_count / total_posted * 100) if total_posted > 0 else 0
    
    # Calculate posting frequency (per month)
    cur.execute(
        """
        SELECT COUNT(*) as count
        FROM jobs
        WHERE company_id = ? AND first_seen >= date('now', '-30 days')
        """,
        (company_id,)
    )
    monthly_result = cur.fetchone()
    monthly_postings = monthly_result["count"] if monthly_result else 0
    
    # Calculate removal frequency
    cur.execute(
        """
        SELECT COUNT(*) as count
        FROM jobs
        WHERE company_id = ? AND removed_at >= date('now', '-30 days')
        """,
        (company_id,)
    )
    removal_result = cur.fetchone()
    monthly_removals = removal_result["count"] if removal_result else 0
    
    # Job churn rate
    churn_rate = (monthly_removals / monthly_postings * 100) if monthly_postings > 0 else 0
    
    # Reliability score (0-100)
    # Higher score = more reliable (longer postings, lower ghost rate, lower churn)
    reliability_score = 100.0
    reliability_score -= min(ghost_posting_rate * 2, 50)  # Penalize ghost postings
    reliability_score -= min(churn_rate, 30)  # Penalize high churn
    if avg_duration < 14:
        reliability_score -= 20  # Penalize short postings
    reliability_score = max(0.0, min(100.0, reliability_score))
    
    # New grad friendly score
    cur.execute(
        """
        SELECT 
            COUNT(DISTINCT CASE WHEN sj.is_new_grad = 1 THEN j.job_id END) as new_grad_count,
            COUNT(DISTINCT j.job_id) as total_count
        FROM jobs j
        JOIN snapshot_jobs sj ON sj.job_id = j.job_id
        JOIN snapshots s ON s.snapshot_id = sj.snapshot_id
        WHERE j.company_id = ?
          AND s.timestamp >= date('now', '-90 days')
        """,
        (company_id,)
    )
    ng_result = cur.fetchone()
    if ng_result and ng_result["total_count"] and ng_result["total_count"] > 0:
        new_grad_rate = (ng_result["new_grad_count"] / ng_result["total_count"] * 100)
    else:
        new_grad_rate = 0.0
    
    return {
        "total_jobs_posted": int(total_posted),
        "total_jobs_removed": int(total_removed),
        "avg_posting_duration_days": round(float(avg_duration), 1) if avg_duration else 0.0,
        "ghost_posting_rate": round(ghost_posting_rate, 1),
        "posting_frequency_per_month": int(monthly_postings),
        "removal_frequency_per_month": int(monthly_removals),
        "job_churn_rate": round(churn_rate, 1),
        "reliability_score": round(reliability_score, 1),
        "new_grad_friendly_score": round(new_grad_rate, 1)
    }


def update_company_analytics(db: Database, company_id: int) -> None:
    """
    Calculate and store company analytics in the database.
    
    Args:
        db: Database instance
        company_id: Company ID to analyze
    """
    analytics = calculate_company_analytics(db, company_id)
    snapshot_date = datetime.now().date()
    
    cur = db.conn.cursor()
    cur.execute(
        """
        INSERT OR REPLACE INTO company_analytics
        (company_id, snapshot_date, total_jobs_posted, total_jobs_removed, 
         avg_posting_duration_days, ghost_posting_rate, posting_frequency_per_month,
         removal_frequency_per_month, job_churn_rate, reliability_score, 
         new_grad_friendly_score, metrics_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            company_id,
            snapshot_date,
            analytics["total_jobs_posted"],
            analytics["total_jobs_removed"],
            analytics["avg_posting_duration_days"],
            analytics["ghost_posting_rate"],
            analytics["posting_frequency_per_month"],
            analytics["removal_frequency_per_month"],
            analytics["job_churn_rate"],
            analytics["reliability_score"],
            analytics["new_grad_friendly_score"],
            json.dumps(analytics)
        )
    )
    db.conn.commit()


def calculate_user_analytics(db: Database, user_id: int) -> Dict:
    """Calculate personal analytics for a user"""
    cur = db.conn.cursor()
    
    # Application stats
    cur.execute(
        """
        SELECT 
            COUNT(*) as total,
            COUNT(CASE WHEN status = 'applied' THEN 1 END) as applied,
            COUNT(CASE WHEN status = 'offer' THEN 1 END) as offers,
            COUNT(CASE WHEN status = 'rejected' THEN 1 END) as rejected
        FROM applications
        WHERE user_id = ?
        """,
        (user_id,)
    )
    app_stats = cur.fetchone()
    
    total = app_stats["total"] if app_stats and app_stats["total"] else 0
    offers = app_stats["offers"] if app_stats and app_stats["offers"] else 0
    success_rate = (offers / total * 100) if total > 0 else 0
    
    # Saved jobs
    cur.execute("SELECT COUNT(*) as count FROM saved_jobs WHERE user_id = ?", (user_id,))
    saved_result = cur.fetchone()
    saved_count = saved_result["count"] if saved_result and saved_result["count"] else 0
    
    # Top companies
    cur.execute(
        """
        SELECT c.name, COUNT(*) as count
        FROM applications a
        JOIN jobs j ON j.job_id = a.job_id
        JOIN companies c ON c.id = j.company_id
        WHERE a.user_id = ?
        GROUP BY c.id
        ORDER BY count DESC
        LIMIT 5
        """,
        (user_id,)
    )
    top_companies = [{"name": row["name"], "count": row["count"]} for row in cur.fetchall()]
    
    # Top sectors
    cur.execute(
        """
        SELECT v.sector, COUNT(*) as count
        FROM applications a
        JOIN jobs j ON j.job_id = a.job_id
        JOIN job_versions v ON v.job_id = j.job_id
        JOIN (
            SELECT job_id, MAX(timestamp) AS max_ts
            FROM job_versions
            GROUP BY job_id
        ) latest ON latest.job_id = v.job_id AND latest.max_ts = v.timestamp
        WHERE a.user_id = ? AND v.sector IS NOT NULL
        GROUP BY v.sector
        ORDER BY count DESC
        LIMIT 5
        """,
        (user_id,)
    )
    top_sectors = [{"sector": row["sector"], "count": row["count"]} for row in cur.fetchall()]
    
    return {
        "total_applications": total,
        "total_saved_jobs": saved_count,
        "applications_by_status": {
            "applied": app_stats["applied"] if app_stats and app_stats["applied"] else 0,
            "offers": offers,
            "rejected": app_stats["rejected"] if app_stats and app_stats["rejected"] else 0
        },
        "success_rate": round(success_rate, 1),
        "top_companies": top_companies,
        "top_sectors": top_sectors
    }


def calculate_market_analytics(db: Database) -> Dict:
    """Calculate market-wide analytics"""
    cur = db.conn.cursor()
    
    # Sector trends
    cur.execute(
        """
        SELECT v.sector, COUNT(DISTINCT j.job_id) as job_count
        FROM jobs j
        JOIN job_versions v ON v.job_id = j.job_id
        JOIN (
            SELECT job_id, MAX(timestamp) AS max_ts
            FROM job_versions
            GROUP BY job_id
        ) latest ON latest.job_id = v.job_id AND latest.max_ts = v.timestamp
        WHERE j.active = 1 AND v.sector IS NOT NULL
        GROUP BY v.sector
        ORDER BY job_count DESC
        """
    )
    sector_trends = [{"sector": row["sector"], "count": row["job_count"]} for row in cur.fetchall()]
    
    # Company reliability
    cur.execute(
        """
        SELECT c.name, ca.reliability_score
        FROM companies c
        JOIN company_analytics ca ON ca.company_id = c.id
        ORDER BY ca.reliability_score DESC
        LIMIT 20
        """
    )
    company_reliability = [{"name": row["name"], "score": row["reliability_score"]} for row in cur.fetchall()]
    
    return {
        "sector_trends": sector_trends,
        "company_reliability": company_reliability
    }
