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
from pathlib import Path
from datetime import datetime
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
"""


class Database:
    """Wrapper around sqlite3 connection.

    Provides helper methods for common operations and ensures the
    connection uses row_factory for named access.
    """

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.conn = sqlite3.connect(str(db_path))
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
        # 1) Add snapshots.run_id if missing.
        cur = self.conn.cursor()
        cur.execute("PRAGMA table_info(snapshots)")
        cols = {row[1] for row in cur.fetchall()}  # type: ignore[index]
        if "run_id" not in cols:
            cur.execute("ALTER TABLE snapshots ADD COLUMN run_id INTEGER")

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

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()
        return False
