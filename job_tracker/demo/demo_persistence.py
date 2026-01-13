"""
Demonstration of persistence and diff recording using the job tracker.

This script simulates two consecutive runs of the collector using the
sample Greenhouse JSON files bundled with the repository. It writes
results into a SQLite database and prints out summaries after each
snapshot. This demonstrates how new jobs are inserted, changes are
recorded, and removed jobs are marked inactive.
"""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

from .collector import CompanyConfig, collect_jobs
from .db import Database
from .persistence import persist_snapshot


def print_db_summary(db: Database, title: str) -> None:
    print(f"\n=== {title} ===")
    active = db.list_active_jobs()
    removed = db.list_removed_jobs()
    print(f"Active jobs: {len(active)}")
    for row in active:
        print(
            f"  {row['job_id']}: {row['company_name']} - {row['job_id']} - {row['last_seen']}"
        )
    print(f"Removed jobs: {len(removed)}")
    for row in removed:
        print(
            f"  {row['job_id']}: {row['company_name']} removed at {row['removed_at']}"
        )


def demo_persistence(db_path: Path) -> None:
    # Ensure database file is clean
    if db_path.exists():
        os.remove(db_path)
    db = Database(db_path)
    try:
        # Sample company configuration
        companies = [
            CompanyConfig(
                slug="exampleco",
                name="ExampleCo",
                ats="greenhouse",
                json_path=Path(__file__).resolve().parent / "testdata" / "sample1.json",
            )
        ]
        # First snapshot using sample1.json
        jobs1 = collect_jobs(companies, allow_remote=False)
        snapshot_time1 = datetime(2026, 1, 1, 0, 0, 0)
        persist_snapshot(db, snapshot_time1, jobs1, companies)
        print_db_summary(db, "After first snapshot")

        # Modify company config to point to sample2.json for second run
        companies[0] = CompanyConfig(
            slug="exampleco",
            name="ExampleCo",
            ats="greenhouse",
            json_path=Path(__file__).resolve().parent / "testdata" / "sample2.json",
        )
        jobs2 = collect_jobs(companies, allow_remote=False)
        snapshot_time2 = datetime(2026, 1, 2, 0, 0, 0)
        persist_snapshot(db, snapshot_time2, jobs2, companies)
        print_db_summary(db, "After second snapshot")
    finally:
        db.close()


if __name__ == "__main__":
    demo_db_path = Path("demo_persistence.db")
    demo_persistence(demo_db_path)