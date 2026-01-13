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
    timestamp TIMESTAMP NOT NULL
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

    def _ensure_schema(self) -> None:
        """Initialize the database schema if not present."""
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

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
    def insert_snapshot(self, timestamp: datetime) -> int:
        cur = self.conn.cursor()
        cur.execute(
            "INSERT INTO snapshots (timestamp) VALUES (?)", (timestamp,)
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
