"""
Database layer for the job tracker.

This module defines the SQLite schema used for persisting jobs, snapshots
and versions of jobs over time. It provides helper functions for
initializing the database and performing common operations such as
inserting jobs, updating existing jobs, recording versions and
associating jobs with snapshots. SQLite is used as the backend to keep
the demonstration self-contained; replacing it with another database
(e.g. PostgreSQL) would primarily require adjusting connection
handling and SQL dialect.
"""

from __future__ import annotations

import sqlite3
import json
from pathlib import Path
from datetime import datetime, date
from typing import Dict, Any, List, Optional, Tuple


SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS runs (
    run_id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TIMESTAMP NOT NULL,
    finished_at TIMESTAMP,
    status TEXT NOT NULL, -- 'running' | 'ok' | 'error'
    companies_total INTEGER NOT NULL DEFAULT 0,
    companies_succeeded INTEGER NOT NULL DEFAULT 0,
    companies_failed INTEGER NOT NULL DEFAULT 0,
    jobs_collected INTEGER NOT NULL DEFAULT 0,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS run_errors (
    error_id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL,
    created_at TIMESTAMP NOT NULL,
    company_slug TEXT,
    company_name TEXT,
    ats TEXT,
    error TEXT NOT NULL,
    FOREIGN KEY(run_id) REFERENCES runs(run_id)
);

CREATE TABLE IF NOT EXISTS companies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    slug TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    source TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS jobs (
    job_id TEXT PRIMARY KEY,
    company_id INTEGER NOT NULL,
    url TEXT NOT NULL,
    source TEXT NOT NULL,
    first_seen TIMESTAMP NOT NULL,
    last_seen TIMESTAMP NOT NULL,
    removed_at TIMESTAMP,
    active INTEGER NOT NULL DEFAULT 1,
    FOREIGN KEY(company_id) REFERENCES companies(id)
);

CREATE TABLE IF NOT EXISTS job_versions (
    version_id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    title TEXT NOT NULL,
    location TEXT,
    remote INTEGER,
    extra TEXT,
    FOREIGN KEY(job_id) REFERENCES jobs(job_id)
);

CREATE TABLE IF NOT EXISTS snapshots (
    snapshot_id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TIMESTAMP NOT NULL,
    run_id INTEGER,
    FOREIGN KEY(run_id) REFERENCES runs(run_id)
);

CREATE TABLE IF NOT EXISTS snapshot_jobs (
    snapshot_id INTEGER NOT NULL,
    job_id TEXT NOT NULL,
    version_id INTEGER NOT NULL,
    is_new_grad INTEGER NOT NULL,
    PRIMARY KEY(snapshot_id, job_id),
    FOREIGN KEY(snapshot_id) REFERENCES snapshots(snapshot_id),
    FOREIGN KEY(job_id) REFERENCES jobs(job_id),
    FOREIGN KEY(version_id) REFERENCES job_versions(version_id)
);

-- Users
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    email TEXT UNIQUE,
    password_hash TEXT,
    created_at TIMESTAMP NOT NULL,
    last_login TIMESTAMP,
    preferences TEXT
);

-- User profiles
CREATE TABLE IF NOT EXISTS user_profiles (
    profile_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL UNIQUE,
    full_name TEXT,
    degree_type TEXT,
    graduation_year INTEGER,
    skills TEXT,
    location_preference TEXT,
    remote_preference INTEGER,
    target_sectors TEXT,
    resume_url TEXT,
    notes TEXT,
    FOREIGN KEY(user_id) REFERENCES users(user_id)
);

-- User sessions
CREATE TABLE IF NOT EXISTS user_sessions (
    session_id TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    created_at TIMESTAMP NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    FOREIGN KEY(user_id) REFERENCES users(user_id)
);

-- Saved jobs
CREATE TABLE IF NOT EXISTS saved_jobs (
    saved_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    job_id TEXT NOT NULL,
    saved_at TIMESTAMP NOT NULL,
    notes TEXT,
    tags TEXT,
    priority INTEGER DEFAULT 0,
    deadline DATE,
    FOREIGN KEY(user_id) REFERENCES users(user_id),
    FOREIGN KEY(job_id) REFERENCES jobs(job_id),
    UNIQUE(user_id, job_id)
);

-- Applications
CREATE TABLE IF NOT EXISTS applications (
    application_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    job_id TEXT NOT NULL,
    status TEXT NOT NULL,
    applied_at TIMESTAMP,
    application_method TEXT,
    application_url TEXT,
    notes TEXT,
    tags TEXT,
    priority INTEGER DEFAULT 0,
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL,
    FOREIGN KEY(user_id) REFERENCES users(user_id),
    FOREIGN KEY(job_id) REFERENCES jobs(job_id)
);

-- Application events
CREATE TABLE IF NOT EXISTS application_events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    application_id INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    event_data TEXT,
    created_at TIMESTAMP NOT NULL,
    FOREIGN KEY(application_id) REFERENCES applications(application_id)
);

-- Interviews
CREATE TABLE IF NOT EXISTS interviews (
    interview_id INTEGER PRIMARY KEY AUTOINCREMENT,
    application_id INTEGER NOT NULL,
    interview_type TEXT NOT NULL,
    scheduled_at TIMESTAMP,
    duration_minutes INTEGER,
    interviewer_name TEXT,
    interviewer_email TEXT,
    location TEXT,
    notes TEXT,
    preparation_notes TEXT,
    follow_up_required INTEGER DEFAULT 0,
    follow_up_date DATE,
    status TEXT DEFAULT 'scheduled',
    created_at TIMESTAMP NOT NULL,
    FOREIGN KEY(application_id) REFERENCES applications(application_id)
);

-- Offers
CREATE TABLE IF NOT EXISTS offers (
    offer_id INTEGER PRIMARY KEY AUTOINCREMENT,
    application_id INTEGER NOT NULL UNIQUE,
    offer_date DATE NOT NULL,
    salary_amount REAL,
    salary_currency TEXT DEFAULT 'USD',
    salary_period TEXT,
    equity TEXT,
    benefits TEXT,
    start_date DATE,
    decision_deadline DATE,
    status TEXT DEFAULT 'pending',
    notes TEXT,
    created_at TIMESTAMP NOT NULL,
    FOREIGN KEY(application_id) REFERENCES applications(application_id)
);

-- Tags
CREATE TABLE IF NOT EXISTS tags (
    tag_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    color TEXT,
    created_at TIMESTAMP NOT NULL,
    FOREIGN KEY(user_id) REFERENCES users(user_id),
    UNIQUE(user_id, name)
);

-- Job tags
CREATE TABLE IF NOT EXISTS job_tags (
    job_id TEXT NOT NULL,
    tag_id INTEGER NOT NULL,
    PRIMARY KEY(job_id, tag_id),
    FOREIGN KEY(job_id) REFERENCES jobs(job_id),
    FOREIGN KEY(tag_id) REFERENCES tags(tag_id)
);

-- Saved searches
CREATE TABLE IF NOT EXISTS saved_searches (
    search_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    filters TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL,
    last_run_at TIMESTAMP,
    notification_enabled INTEGER DEFAULT 1,
    FOREIGN KEY(user_id) REFERENCES users(user_id)
);

-- Job recommendations
CREATE TABLE IF NOT EXISTS job_recommendations (
    recommendation_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    job_id TEXT NOT NULL,
    score REAL NOT NULL,
    reason TEXT,
    created_at TIMESTAMP NOT NULL,
    FOREIGN KEY(user_id) REFERENCES users(user_id),
    FOREIGN KEY(job_id) REFERENCES jobs(job_id)
);

-- Company profiles
CREATE TABLE IF NOT EXISTS company_profiles (
    company_id INTEGER PRIMARY KEY,
    website TEXT,
    description TEXT,
    industry TEXT,
    size TEXT,
    headquarters TEXT,
    founded_year INTEGER,
    employee_count INTEGER,
    linkedin_url TEXT,
    glassdoor_url TEXT,
    notes TEXT,
    FOREIGN KEY(company_id) REFERENCES companies(id)
);

-- Company notes
CREATE TABLE IF NOT EXISTS company_notes (
    note_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    company_id INTEGER NOT NULL,
    note_text TEXT NOT NULL,
    rating INTEGER,
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL,
    FOREIGN KEY(user_id) REFERENCES users(user_id),
    FOREIGN KEY(company_id) REFERENCES companies(id)
);

-- Company analytics
CREATE TABLE IF NOT EXISTS company_analytics (
    analytics_id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER NOT NULL,
    snapshot_date DATE NOT NULL,
    total_jobs_posted INTEGER DEFAULT 0,
    total_jobs_removed INTEGER DEFAULT 0,
    avg_posting_duration_days REAL,
    ghost_posting_rate REAL,
    posting_frequency_per_month REAL,
    removal_frequency_per_month REAL,
    job_churn_rate REAL,
    reliability_score REAL,
    new_grad_friendly_score REAL,
    metrics_json TEXT,
    FOREIGN KEY(company_id) REFERENCES companies(id),
    UNIQUE(company_id, snapshot_date)
);

-- User analytics
CREATE TABLE IF NOT EXISTS user_analytics (
    analytics_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    computed_at TIMESTAMP NOT NULL,
    total_applications INTEGER DEFAULT 0,
    total_saved_jobs INTEGER DEFAULT 0,
    applications_by_status TEXT,
    success_rate REAL,
    avg_response_time_days REAL,
    top_companies TEXT,
    top_sectors TEXT,
    insights_json TEXT,
    FOREIGN KEY(user_id) REFERENCES users(user_id)
);

-- Market analytics
CREATE TABLE IF NOT EXISTS market_analytics (
    analytics_id INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_date DATE NOT NULL,
    sector_trends TEXT,
    degree_compatibility TEXT,
    company_reliability TEXT,
    hiring_velocity TEXT,
    insights_json TEXT
);

-- Notifications
CREATE TABLE IF NOT EXISTS notifications (
    notification_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    type TEXT NOT NULL,
    title TEXT NOT NULL,
    message TEXT NOT NULL,
    related_job_id TEXT,
    related_application_id INTEGER,
    read INTEGER DEFAULT 0,
    created_at TIMESTAMP NOT NULL,
    FOREIGN KEY(user_id) REFERENCES users(user_id),
    FOREIGN KEY(related_job_id) REFERENCES jobs(job_id),
    FOREIGN KEY(related_application_id) REFERENCES applications(application_id)
);

-- Notification preferences
CREATE TABLE IF NOT EXISTS notification_preferences (
    user_id INTEGER PRIMARY KEY,
    email_enabled INTEGER DEFAULT 1,
    job_alerts INTEGER DEFAULT 1,
    status_changes INTEGER DEFAULT 1,
    reminders INTEGER DEFAULT 1,
    deadlines INTEGER DEFAULT 1,
    weekly_digest INTEGER DEFAULT 1,
    FOREIGN KEY(user_id) REFERENCES users(user_id)
);
"""


class Database:
    """Wrapper around sqlite3 connection.

    Provides helper methods for common operations and ensures the
    connection uses row_factory for named access.
    """

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._ensure_schema()

    def __enter__(self) -> "Database":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        self.close()
        return False

    def _ensure_schema(self) -> None:
        """Initialize the database schema and apply lightweight migrations."""
        self.conn.executescript(SCHEMA)

        # Lightweight migrations for existing DBs.
        cur = self.conn.cursor()
        
        # 1) Add snapshots.run_id if missing.
        cur.execute("PRAGMA table_info(snapshots)")
        cols = {row[1] for row in cur.fetchall()}  # type: ignore[index]
        if "run_id" not in cols:
            cur.execute("ALTER TABLE snapshots ADD COLUMN run_id INTEGER")
        
        # 2) Add sector column to job_versions if missing.
        cur.execute("PRAGMA table_info(job_versions)")
        cols = {row[1] for row in cur.fetchall()}  # type: ignore[index]
        if "sector" not in cols:
            cur.execute("ALTER TABLE job_versions ADD COLUMN sector TEXT")

        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    # --- run operations ---
    def insert_run(self, started_at: datetime, companies_total: int) -> int:
        cur = self.conn.cursor()
        cur.execute(
            "INSERT INTO runs (started_at, status, companies_total) VALUES (?, 'running', ?)",
            (started_at, companies_total),
        )
        run_id = cur.lastrowid
        self.conn.commit()
        return int(run_id)

    def finish_run(
        self,
        run_id: int,
        finished_at: datetime,
        status: str,
        companies_succeeded: int,
        companies_failed: int,
        jobs_collected: int,
        notes: str | None = None,
    ) -> None:
        cur = self.conn.cursor()
        cur.execute(
            """
            UPDATE runs
            SET finished_at=?, status=?, companies_succeeded=?, companies_failed=?, jobs_collected=?, notes=?
            WHERE run_id=?
            """,
            (finished_at, status, companies_succeeded, companies_failed, jobs_collected, notes, run_id),
        )
        self.conn.commit()

    def insert_run_error(
        self,
        run_id: int,
        created_at: datetime,
        company_slug: str | None,
        company_name: str | None,
        ats: str | None,
        error: str,
    ) -> None:
        cur = self.conn.cursor()
        cur.execute(
            """
            INSERT INTO run_errors (run_id, created_at, company_slug, company_name, ats, error)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (run_id, created_at, company_slug, company_name, ats, error),
        )
        self.conn.commit()

    # --- company operations ---
    def upsert_company(self, slug: str, name: str, source: str) -> int:
        """Insert or update a company and return its id."""
        cur = self.conn.cursor()
        cur.execute(
            "INSERT OR IGNORE INTO companies (slug, name, source) VALUES (?, ?, ?)",
            (slug, name, source),
        )
        # If it already existed, update the name/source if changed
        cur.execute(
            "UPDATE companies SET name=?, source=? WHERE slug=?",
            (name, source, slug),
        )
        self.conn.commit()
        cur.execute("SELECT id FROM companies WHERE slug=?", (slug,))
        return int(cur.fetchone()["id"])

    # --- job operations ---
    def get_job(self, job_id: str) -> Optional[sqlite3.Row]:
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM jobs WHERE job_id=?", (job_id,))
        return cur.fetchone()

    def insert_job(
        self,
        job_id: str,
        company_id: int,
        url: str,
        source: str,
        first_seen: datetime,
        last_seen: datetime,
    ) -> None:
        cur = self.conn.cursor()
        cur.execute(
            "INSERT INTO jobs (job_id, company_id, url, source, first_seen, last_seen, active) "
            "VALUES (?, ?, ?, ?, ?, ?, 1)",
            (job_id, company_id, url, source, first_seen, last_seen),
        )
        self.conn.commit()

    def update_job_seen(self, job_id: str, last_seen: datetime) -> None:
        cur = self.conn.cursor()
        cur.execute(
            "UPDATE jobs SET last_seen=?, active=1, removed_at=NULL WHERE job_id=?",
            (last_seen, job_id),
        )
        self.conn.commit()

    def mark_jobs_removed(self, job_ids: List[str], removed_at: datetime) -> None:
        if not job_ids:
            return
        cur = self.conn.cursor()
        # Use placeholders for variable length
        placeholders = ",".join("?" for _ in job_ids)
        sql = f"UPDATE jobs SET active=0, removed_at=? WHERE job_id IN ({placeholders})"
        cur.execute(sql, (removed_at, *job_ids))
        self.conn.commit()

    # --- version operations ---
    def insert_job_version(
        self,
        job_id: str,
        timestamp: datetime,
        title: str,
        location: str,
        remote: Optional[bool],
        extra_json: str,
    ) -> int:
        cur = self.conn.cursor()
        cur.execute(
            "INSERT INTO job_versions (job_id, timestamp, title, location, remote, extra) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                job_id,
                timestamp,
                title,
                location,
                1 if remote is True else 0 if remote is False else None,
                extra_json,
            ),
        )
        version_id = cur.lastrowid
        self.conn.commit()
        return version_id

    def get_latest_job_version(self, job_id: str) -> Optional[sqlite3.Row]:
        cur = self.conn.cursor()
        cur.execute(
            "SELECT * FROM job_versions WHERE job_id=? ORDER BY timestamp DESC LIMIT 1",
            (job_id,),
        )
        return cur.fetchone()

    # --- snapshot operations ---
    def insert_snapshot(self, timestamp: datetime, run_id: int | None = None) -> int:
        cur = self.conn.cursor()
        cur.execute(
            "INSERT INTO snapshots (timestamp, run_id) VALUES (?, ?)",
            (timestamp, run_id),
        )
        snapshot_id = cur.lastrowid
        self.conn.commit()
        return snapshot_id

    def insert_snapshot_job(
        self,
        snapshot_id: int,
        job_id: str,
        version_id: int,
        is_new_grad: bool,
    ) -> None:
        cur = self.conn.cursor()
        cur.execute(
            "INSERT INTO snapshot_jobs (snapshot_id, job_id, version_id, is_new_grad) "
            "VALUES (?, ?, ?, ?)",
            (snapshot_id, job_id, version_id, 1 if is_new_grad else 0),
        )
        self.conn.commit()

    # Query helpers for demonstration
    def list_active_jobs(self) -> List[sqlite3.Row]:
        cur = self.conn.cursor()
        cur.execute(
            "SELECT j.*, c.name AS company_name FROM jobs j "
            "JOIN companies c ON j.company_id=c.id WHERE j.active=1"
        )
        return cur.fetchall()

    def list_removed_jobs(self) -> List[sqlite3.Row]:
        cur = self.conn.cursor()
        cur.execute(
            "SELECT j.*, c.name AS company_name FROM jobs j "
            "JOIN companies c ON j.company_id=c.id WHERE j.active=0"
        )
        return cur.fetchall()

    # --- application operations ---
    def create_application(
        self,
        user_id: int,
        job_id: str,
        status: str = "applied",
        applied_at: Optional[datetime] = None,
        application_method: Optional[str] = None,
        application_url: Optional[str] = None,
        notes: Optional[str] = None,
        tags: Optional[List[str]] = None,
        priority: int = 0,
    ) -> int:
        """Create a new application and return its ID."""
        cur = self.conn.cursor()
        now = datetime.now()
        tags_json = json.dumps(tags) if tags else None
        
        cur.execute(
            """
            INSERT INTO applications 
            (user_id, job_id, status, applied_at, application_method, application_url, notes, tags, priority, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (user_id, job_id, status, applied_at or now, application_method, application_url, notes, tags_json, priority, now, now)
        )
        application_id = cur.lastrowid
        
        # Create initial event
        cur.execute(
            """
            INSERT INTO application_events (application_id, event_type, event_data, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (application_id, "created", json.dumps({"status": status}), now)
        )
        
        self.conn.commit()
        return int(application_id)

    def get_application(self, application_id: int, user_id: Optional[int] = None) -> Optional[sqlite3.Row]:
        """Get an application by ID, optionally filtered by user_id."""
        cur = self.conn.cursor()
        if user_id:
            cur.execute(
                "SELECT * FROM applications WHERE application_id = ? AND user_id = ?",
                (application_id, user_id)
            )
        else:
            cur.execute("SELECT * FROM applications WHERE application_id = ?", (application_id,))
        return cur.fetchone()

    def update_application(
        self,
        application_id: int,
        user_id: int,
        status: Optional[str] = None,
        notes: Optional[str] = None,
        tags: Optional[List[str]] = None,
        priority: Optional[int] = None,
        application_method: Optional[str] = None,
        application_url: Optional[str] = None,
    ) -> bool:
        """Update an application. Returns True if updated, False if not found."""
        cur = self.conn.cursor()
        
        # Get current status to track changes
        current = cur.execute(
            "SELECT status FROM applications WHERE application_id = ? AND user_id = ?",
            (application_id, user_id)
        ).fetchone()
        
        if not current:
            return False
        
        current_status = current["status"]
        updates = []
        params = []
        
        if status is not None:
            updates.append("status = ?")
            params.append(status)
        if notes is not None:
            updates.append("notes = ?")
            params.append(notes)
        if tags is not None:
            updates.append("tags = ?")
            params.append(json.dumps(tags))
        if priority is not None:
            updates.append("priority = ?")
            params.append(priority)
        if application_method is not None:
            updates.append("application_method = ?")
            params.append(application_method)
        if application_url is not None:
            updates.append("application_url = ?")
            params.append(application_url)
        
        if not updates:
            return True  # Nothing to update
        
        updates.append("updated_at = ?")
        params.extend([datetime.now(), application_id, user_id])
        
        cur.execute(
            f"UPDATE applications SET {', '.join(updates)} WHERE application_id = ? AND user_id = ?",
            params
        )
        
        # Track status change event
        if status is not None and status != current_status:
            cur.execute(
                """
                INSERT INTO application_events (application_id, event_type, event_data, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (application_id, "status_changed", json.dumps({"old_status": current_status, "new_status": status}), datetime.now())
            )
        
        self.conn.commit()
        return True

    def delete_application(self, application_id: int, user_id: int) -> bool:
        """Delete an application. Returns True if deleted, False if not found."""
        cur = self.conn.cursor()
        cur.execute(
            "DELETE FROM applications WHERE application_id = ? AND user_id = ?",
            (application_id, user_id)
        )
        deleted = cur.rowcount > 0
        self.conn.commit()
        return deleted

    def list_applications(
        self,
        user_id: int,
        status: Optional[str] = None,
        job_id: Optional[str] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> List[sqlite3.Row]:
        """List applications for a user with optional filters."""
        cur = self.conn.cursor()
        query = "SELECT * FROM applications WHERE user_id = ?"
        params: List[Any] = [user_id]
        
        if status:
            query += " AND status = ?"
            params.append(status)
        if job_id:
            query += " AND job_id = ?"
            params.append(job_id)
        
        query += " ORDER BY updated_at DESC"
        
        if limit:
            query += " LIMIT ?"
            params.append(limit)
        if offset:
            query += " OFFSET ?"
            params.append(offset)
        
        cur.execute(query, params)
        return cur.fetchall()

    def get_application_events(self, application_id: int) -> List[sqlite3.Row]:
        """Get all events for an application, ordered by creation time."""
        cur = self.conn.cursor()
        cur.execute(
            "SELECT * FROM application_events WHERE application_id = ? ORDER BY created_at ASC",
            (application_id,)
        )
        return cur.fetchall()

    def add_application_event(
        self,
        application_id: int,
        event_type: str,
        event_data: Optional[Dict[str, Any]] = None,
    ) -> int:
        """Add an event to an application's timeline."""
        cur = self.conn.cursor()
        cur.execute(
            """
            INSERT INTO application_events (application_id, event_type, event_data, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (application_id, event_type, json.dumps(event_data) if event_data else None, datetime.now())
        )
        event_id = cur.lastrowid
        self.conn.commit()
        return int(event_id)

    # --- interview operations ---
    def create_interview(
        self,
        application_id: int,
        interview_type: str,
        scheduled_at: Optional[datetime] = None,
        duration_minutes: Optional[int] = None,
        interviewer_name: Optional[str] = None,
        interviewer_email: Optional[str] = None,
        location: Optional[str] = None,
        notes: Optional[str] = None,
        preparation_notes: Optional[str] = None,
        follow_up_required: bool = False,
        follow_up_date: Optional[date] = None,
        status: str = "scheduled",
    ) -> int:
        """Create a new interview and return its ID."""
        cur = self.conn.cursor()
        cur.execute(
            """
            INSERT INTO interviews 
            (application_id, interview_type, scheduled_at, duration_minutes, interviewer_name, 
             interviewer_email, location, notes, preparation_notes, follow_up_required, 
             follow_up_date, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                application_id, interview_type, scheduled_at, duration_minutes,
                interviewer_name, interviewer_email, location, notes, preparation_notes,
                1 if follow_up_required else 0, follow_up_date, status, datetime.now()
            )
        )
        interview_id = cur.lastrowid
        self.conn.commit()
        
        # Add event to application timeline
        self.add_application_event(
            application_id,
            "interview_scheduled",
            {"interview_id": interview_id, "interview_type": interview_type, "scheduled_at": scheduled_at.isoformat() if scheduled_at else None}
        )
        
        return int(interview_id)

    def get_interview(self, interview_id: int) -> Optional[sqlite3.Row]:
        """Get an interview by ID."""
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM interviews WHERE interview_id = ?", (interview_id,))
        return cur.fetchone()

    def update_interview(
        self,
        interview_id: int,
        interview_type: Optional[str] = None,
        scheduled_at: Optional[datetime] = None,
        duration_minutes: Optional[int] = None,
        interviewer_name: Optional[str] = None,
        interviewer_email: Optional[str] = None,
        location: Optional[str] = None,
        notes: Optional[str] = None,
        preparation_notes: Optional[str] = None,
        follow_up_required: Optional[bool] = None,
        follow_up_date: Optional[date] = None,
        status: Optional[str] = None,
    ) -> bool:
        """Update an interview. Returns True if updated, False if not found."""
        cur = self.conn.cursor()
        updates = []
        params = []
        
        if interview_type is not None:
            updates.append("interview_type = ?")
            params.append(interview_type)
        if scheduled_at is not None:
            updates.append("scheduled_at = ?")
            params.append(scheduled_at)
        if duration_minutes is not None:
            updates.append("duration_minutes = ?")
            params.append(duration_minutes)
        if interviewer_name is not None:
            updates.append("interviewer_name = ?")
            params.append(interviewer_name)
        if interviewer_email is not None:
            updates.append("interviewer_email = ?")
            params.append(interviewer_email)
        if location is not None:
            updates.append("location = ?")
            params.append(location)
        if notes is not None:
            updates.append("notes = ?")
            params.append(notes)
        if preparation_notes is not None:
            updates.append("preparation_notes = ?")
            params.append(preparation_notes)
        if follow_up_required is not None:
            updates.append("follow_up_required = ?")
            params.append(1 if follow_up_required else 0)
        if follow_up_date is not None:
            updates.append("follow_up_date = ?")
            params.append(follow_up_date)
        if status is not None:
            updates.append("status = ?")
            params.append(status)
        
        if not updates:
            return True
        
        params.append(interview_id)
        cur.execute(f"UPDATE interviews SET {', '.join(updates)} WHERE interview_id = ?", params)
        updated = cur.rowcount > 0
        self.conn.commit()
        return updated

    def delete_interview(self, interview_id: int) -> bool:
        """Delete an interview. Returns True if deleted, False if not found."""
        cur = self.conn.cursor()
        # Get application_id before deleting for event tracking
        interview = cur.execute("SELECT application_id FROM interviews WHERE interview_id = ?", (interview_id,)).fetchone()
        
        cur.execute("DELETE FROM interviews WHERE interview_id = ?", (interview_id,))
        deleted = cur.rowcount > 0
        
        if deleted and interview:
            self.add_application_event(
                interview["application_id"],
                "interview_cancelled",
                {"interview_id": interview_id}
            )
        
        self.conn.commit()
        return deleted

    def list_interviews(
        self,
        application_id: Optional[int] = None,
        user_id: Optional[int] = None,
        status: Optional[str] = None,
        upcoming_only: bool = False,
    ) -> List[sqlite3.Row]:
        """List interviews with optional filters."""
        cur = self.conn.cursor()
        
        if user_id:
            # Join with applications to filter by user
            query = """
                SELECT i.* FROM interviews i
                JOIN applications a ON i.application_id = a.application_id
                WHERE a.user_id = ?
            """
            params: List[Any] = [user_id]
        elif application_id:
            query = "SELECT * FROM interviews WHERE application_id = ?"
            params = [application_id]
        else:
            query = "SELECT * FROM interviews WHERE 1=1"
            params = []
        
        if status:
            query += " AND i.status = ?" if user_id or application_id else " AND status = ?"
            params.append(status)
        
        if upcoming_only:
            query += " AND i.scheduled_at > ?" if user_id or application_id else " AND scheduled_at > ?"
            params.append(datetime.now())
        
        query += " ORDER BY scheduled_at ASC" if user_id or application_id else " ORDER BY scheduled_at ASC"
        
        cur.execute(query, params)
        return cur.fetchall()

    # --- offer operations ---
    def create_offer(
        self,
        application_id: int,
        offer_date: date,
        salary_amount: Optional[float] = None,
        salary_currency: str = "USD",
        salary_period: Optional[str] = None,
        equity: Optional[str] = None,
        benefits: Optional[str] = None,
        start_date: Optional[date] = None,
        decision_deadline: Optional[date] = None,
        status: str = "pending",
        notes: Optional[str] = None,
    ) -> int:
        """Create a new offer and return its ID."""
        cur = self.conn.cursor()
        cur.execute(
            """
            INSERT INTO offers 
            (application_id, offer_date, salary_amount, salary_currency, salary_period, 
             equity, benefits, start_date, decision_deadline, status, notes, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                application_id, offer_date, salary_amount, salary_currency, salary_period,
                equity, benefits, start_date, decision_deadline, status, notes, datetime.now()
            )
        )
        offer_id = cur.lastrowid
        self.conn.commit()
        
        # Add event to application timeline
        self.add_application_event(
            application_id,
            "offer_received",
            {"offer_id": offer_id, "offer_date": offer_date.isoformat(), "salary_amount": salary_amount}
        )
        
        return int(offer_id)

    def get_offer(self, application_id: int) -> Optional[sqlite3.Row]:
        """Get an offer by application_id (one-to-one relationship)."""
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM offers WHERE application_id = ?", (application_id,))
        return cur.fetchone()

    def update_offer(
        self,
        application_id: int,
        offer_date: Optional[date] = None,
        salary_amount: Optional[float] = None,
        salary_currency: Optional[str] = None,
        salary_period: Optional[str] = None,
        equity: Optional[str] = None,
        benefits: Optional[str] = None,
        start_date: Optional[date] = None,
        decision_deadline: Optional[date] = None,
        status: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> bool:
        """Update an offer. Returns True if updated, False if not found."""
        cur = self.conn.cursor()
        updates = []
        params = []
        
        if offer_date is not None:
            updates.append("offer_date = ?")
            params.append(offer_date)
        if salary_amount is not None:
            updates.append("salary_amount = ?")
            params.append(salary_amount)
        if salary_currency is not None:
            updates.append("salary_currency = ?")
            params.append(salary_currency)
        if salary_period is not None:
            updates.append("salary_period = ?")
            params.append(salary_period)
        if equity is not None:
            updates.append("equity = ?")
            params.append(equity)
        if benefits is not None:
            updates.append("benefits = ?")
            params.append(benefits)
        if start_date is not None:
            updates.append("start_date = ?")
            params.append(start_date)
        if decision_deadline is not None:
            updates.append("decision_deadline = ?")
            params.append(decision_deadline)
        if status is not None:
            updates.append("status = ?")
            params.append(status)
        if notes is not None:
            updates.append("notes = ?")
            params.append(notes)
        
        if not updates:
            return True
        
        params.append(application_id)
        cur.execute(f"UPDATE offers SET {', '.join(updates)} WHERE application_id = ?", params)
        updated = cur.rowcount > 0
        self.conn.commit()
        return updated

    def list_offers(self, user_id: int, status: Optional[str] = None) -> List[sqlite3.Row]:
        """List offers for a user, optionally filtered by status."""
        cur = self.conn.cursor()
        query = """
            SELECT o.* FROM offers o
            JOIN applications a ON o.application_id = a.application_id
            WHERE a.user_id = ?
        """
        params: List[Any] = [user_id]
        
        if status:
            query += " AND o.status = ?"
            params.append(status)
        
        query += " ORDER BY o.offer_date DESC"
        
        cur.execute(query, params)
        return cur.fetchall()

    # --- user operations ---
    def create_user(
        self,
        username: str,
        password_hash: str,
        email: Optional[str] = None,
    ) -> int:
        """Create a new user and return user_id."""
        cur = self.conn.cursor()
        now = datetime.now()
        
        cur.execute(
            """
            INSERT INTO users (username, email, password_hash, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (username, email, password_hash, now)
        )
        user_id = cur.lastrowid
        
        # Create default notification preferences
        cur.execute(
            """
            INSERT INTO notification_preferences (user_id, email_enabled, job_alerts, status_changes, reminders, deadlines, weekly_digest)
            VALUES (?, 1, 1, 1, 1, 1, 1)
            """,
            (user_id,)
        )
        
        self.conn.commit()
        return int(user_id)

    def get_user_by_username(self, username: str) -> Optional[sqlite3.Row]:
        """Get a user by username."""
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM users WHERE username = ?", (username,))
        return cur.fetchone()

    def get_user_by_email(self, email: str) -> Optional[sqlite3.Row]:
        """Get a user by email."""
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM users WHERE email = ?", (email,))
        return cur.fetchone()

    def get_user_by_id(self, user_id: int) -> Optional[sqlite3.Row]:
        """Get a user by ID."""
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        return cur.fetchone()

    def update_last_login(self, user_id: int) -> None:
        """Update the last_login timestamp for a user."""
        cur = self.conn.cursor()
        cur.execute(
            "UPDATE users SET last_login = ? WHERE user_id = ?",
            (datetime.now(), user_id)
        )
        self.conn.commit()

    def delete_user_session(self, session_id: str) -> bool:
        """Delete a user session (for logout)."""
        cur = self.conn.cursor()
        cur.execute("DELETE FROM user_sessions WHERE session_id = ?", (session_id,))
        deleted = cur.rowcount > 0
        self.conn.commit()
        return deleted

    def delete_user_sessions(self, user_id: int) -> int:
        """Delete all sessions for a user."""
        cur = self.conn.cursor()
        cur.execute("DELETE FROM user_sessions WHERE user_id = ?", (user_id,))
        count = cur.rowcount
        self.conn.commit()
        return count

    def update_user_preferences(self, user_id: int, preferences: dict) -> bool:
        """Update user preferences."""
        cur = self.conn.cursor()
        preferences_json = json.dumps(preferences)
        cur.execute(
            "UPDATE users SET preferences = ? WHERE user_id = ?",
            (preferences_json, user_id)
        )
        self.conn.commit()
        return cur.rowcount > 0

    def get_user_preferences(self, user_id: int) -> dict:
        """Get user preferences."""
        cur = self.conn.cursor()
        row = cur.execute(
            "SELECT preferences FROM users WHERE user_id = ?",
            (user_id,)
        ).fetchone()
        if row and row["preferences"]:
            return json.loads(row["preferences"])
        return {}

    # ============================================================================
    # Company Operations
    # ============================================================================

    def get_company_profile(self, company_id: int) -> Optional[sqlite3.Row]:
        """Get company profile with extended information."""
        cur = self.conn.cursor()
        cur.execute(
            """
            SELECT c.*, cp.website, cp.description, cp.industry, cp.size, 
                   cp.headquarters, cp.founded_year, cp.employee_count,
                   cp.linkedin_url, cp.glassdoor_url, cp.notes as profile_notes
            FROM companies c
            LEFT JOIN company_profiles cp ON cp.company_id = c.id
            WHERE c.id = ?
            """,
            (company_id,)
        )
        return cur.fetchone()

    def upsert_company_profile(
        self,
        company_id: int,
        website: Optional[str] = None,
        description: Optional[str] = None,
        industry: Optional[str] = None,
        size: Optional[str] = None,
        headquarters: Optional[str] = None,
        founded_year: Optional[int] = None,
        employee_count: Optional[int] = None,
        linkedin_url: Optional[str] = None,
        glassdoor_url: Optional[str] = None,
        notes: Optional[str] = None
    ) -> None:
        """Create or update company profile."""
        cur = self.conn.cursor()
        cur.execute(
            """
            INSERT OR REPLACE INTO company_profiles
            (company_id, website, description, industry, size, headquarters, 
             founded_year, employee_count, linkedin_url, glassdoor_url, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (company_id, website, description, industry, size, headquarters,
             founded_year, employee_count, linkedin_url, glassdoor_url, notes)
        )
        self.conn.commit()

    def add_company_note(
        self,
        user_id: int,
        company_id: int,
        note_text: str,
        rating: Optional[int] = None
    ) -> int:
        """Add a note about a company."""
        cur = self.conn.cursor()
        cur.execute(
            """
            INSERT INTO company_notes (user_id, company_id, note_text, rating, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (user_id, company_id, note_text, rating, datetime.now(), datetime.now())
        )
        self.conn.commit()
        return cur.lastrowid

    def get_company_notes(self, company_id: int, user_id: Optional[int] = None) -> List[sqlite3.Row]:
        """Get notes for a company, optionally filtered by user."""
        query = "SELECT cn.*, u.username FROM company_notes cn LEFT JOIN users u ON cn.user_id = u.user_id WHERE cn.company_id = ?"
        params: List[Any] = [company_id]
        
        if user_id:
            query += " AND cn.user_id = ?"
            params.append(user_id)
        
        query += " ORDER BY cn.created_at DESC"
        
        cur = self.conn.cursor()
        return cur.execute(query, params).fetchall()

    def update_company_note(
        self,
        note_id: int,
        user_id: int,
        note_text: Optional[str] = None,
        rating: Optional[int] = None
    ) -> bool:
        """Update a company note."""
        cur = self.conn.cursor()
        
        # Verify note belongs to user
        cur.execute("SELECT user_id FROM company_notes WHERE note_id = ?", (note_id,))
        note = cur.fetchone()
        if not note or note["user_id"] != user_id:
            return False
        
        updates = []
        params: List[Any] = []
        
        if note_text is not None:
            updates.append("note_text = ?")
            params.append(note_text)
        
        if rating is not None:
            updates.append("rating = ?")
            params.append(rating)
        
        if updates:
            updates.append("updated_at = ?")
            params.append(datetime.now())
            params.append(note_id)
            
            cur.execute(
                f"UPDATE company_notes SET {', '.join(updates)} WHERE note_id = ?",
                params
            )
            self.conn.commit()
            return cur.rowcount > 0
        
        return False

    def delete_company_note(self, note_id: int, user_id: int) -> bool:
        """Delete a company note."""
        cur = self.conn.cursor()
        
        # Verify note belongs to user
        cur.execute("SELECT user_id FROM company_notes WHERE note_id = ?", (note_id,))
        note = cur.fetchone()
        if not note or note["user_id"] != user_id:
            return False
        
        cur.execute("DELETE FROM company_notes WHERE note_id = ?", (note_id,))
        deleted = cur.rowcount > 0
        self.conn.commit()
        return deleted

    def get_company_analytics(self, company_id: int) -> Optional[sqlite3.Row]:
        """Get latest company analytics snapshot."""
        cur = self.conn.cursor()
        cur.execute(
            """
            SELECT * FROM company_analytics
            WHERE company_id = ?
            ORDER BY snapshot_date DESC
            LIMIT 1
            """,
            (company_id,)
        )
        return cur.fetchone()

    def get_all_companies(self) -> List[sqlite3.Row]:
        """Get all companies ordered by name."""
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM companies ORDER BY name ASC")
        return cur.fetchall()

    def get_company_jobs(self, company_id: int, active_only: bool = True) -> List[sqlite3.Row]:
        """Get all jobs for a company."""
        cur = self.conn.cursor()
        query = """
            SELECT j.*, v.title, v.location, v.remote, v.sector
            FROM jobs j
            JOIN job_versions v ON v.job_id = j.job_id
            JOIN (
                SELECT job_id, MAX(timestamp) AS max_ts
                FROM job_versions
                GROUP BY job_id
            ) latest ON latest.job_id = v.job_id AND latest.max_ts = v.timestamp
            WHERE j.company_id = ?
        """
        params: List[Any] = [company_id]
        
        if active_only:
            query += " AND j.active = 1"
        
        query += " ORDER BY j.last_seen DESC"
        
        return cur.execute(query, params).fetchall()

    # --- Notification operations ---
    def create_notification(
        self,
        user_id: int,
        notification_type: str,
        title: str,
        message: str,
        related_job_id: Optional[str] = None,
        related_application_id: Optional[int] = None
    ) -> int:
        """Create a notification"""
        cur = self.conn.cursor()
        cur.execute(
            """
            INSERT INTO notifications 
            (user_id, type, title, message, related_job_id, related_application_id, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (user_id, notification_type, title, message, related_job_id, related_application_id, datetime.now())
        )
        self.conn.commit()
        return cur.lastrowid

    def get_notifications(
        self,
        user_id: int,
        unread_only: bool = False,
        limit: int = 50
    ) -> List[sqlite3.Row]:
        """Get notifications for user"""
        query = "SELECT * FROM notifications WHERE user_id = ?"
        params: List[Any] = [user_id]
        
        if unread_only:
            query += " AND read = 0"
        
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        
        cur = self.conn.cursor()
        return cur.execute(query, params).fetchall()

    def mark_notification_read(self, notification_id: int, user_id: int) -> None:
        """Mark notification as read"""
        cur = self.conn.cursor()
        cur.execute(
            "UPDATE notifications SET read = 1 WHERE notification_id = ? AND user_id = ?",
            (notification_id, user_id)
        )
        self.conn.commit()

    def mark_all_notifications_read(self, user_id: int) -> None:
        """Mark all notifications as read"""
        cur = self.conn.cursor()
        cur.execute(
            "UPDATE notifications SET read = 1 WHERE user_id = ? AND read = 0",
            (user_id,)
        )
        self.conn.commit()

    def get_notification_preferences(self, user_id: int) -> sqlite3.Row:
        """Get notification preferences"""
        cur = self.conn.cursor()
        cur.execute(
            "SELECT * FROM notification_preferences WHERE user_id = ?",
            (user_id,)
        )
        row = cur.fetchone()
        if not row:
            # Create default preferences
            cur.execute(
                """
                INSERT INTO notification_preferences (user_id) VALUES (?)
                """,
                (user_id,)
            )
            self.conn.commit()
            cur.execute(
                "SELECT * FROM notification_preferences WHERE user_id = ?",
                (user_id,)
            )
            row = cur.fetchone()
        return row

    def update_notification_preferences(
        self,
        user_id: int,
        email_enabled: Optional[bool] = None,
        job_alerts: Optional[bool] = None,
        status_changes: Optional[bool] = None,
        reminders: Optional[bool] = None,
        deadlines: Optional[bool] = None,
        weekly_digest: Optional[bool] = None
    ) -> None:
        """Update notification preferences"""
        updates = []
        params: List[Any] = []
        
        if email_enabled is not None:
            updates.append("email_enabled = ?")
            params.append(1 if email_enabled else 0)
        if job_alerts is not None:
            updates.append("job_alerts = ?")
            params.append(1 if job_alerts else 0)
        if status_changes is not None:
            updates.append("status_changes = ?")
            params.append(1 if status_changes else 0)
        if reminders is not None:
            updates.append("reminders = ?")
            params.append(1 if reminders else 0)
        if deadlines is not None:
            updates.append("deadlines = ?")
            params.append(1 if deadlines else 0)
        if weekly_digest is not None:
            updates.append("weekly_digest = ?")
            params.append(1 if weekly_digest else 0)
        
        if not updates:
            return
        
        params.append(user_id)
        
        cur = self.conn.cursor()
        cur.execute(
            f"UPDATE notification_preferences SET {', '.join(updates)} WHERE user_id = ?",
            params
        )
        self.conn.commit()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()
        return False
