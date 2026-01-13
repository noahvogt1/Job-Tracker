"""
Demonstration of persistence across multiple ATS providers.

This script demonstrates collecting jobs from both Greenhouse and Lever
using local sample JSON files, persisting them into the database, and
tracking updates across snapshots. It runs two consecutive snapshots
for two companies: ExampleCo on Greenhouse and ExampleLever on Lever.
"""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

from ..collector import CompanyConfig, collect_jobs
from ..db import Database
from ..persistence import persist_snapshot


def print_db_summary(db: Database, title: str) -> None:
    print(f"\n=== {title} ===")
    active = db.list_active_jobs()
    removed = db.list_removed_jobs()
    print(f"Active jobs: {len(active)}")
    for row in active:
        print(
            f"  {row['job_id']}: {row['company_name']} (active since {row['first_seen']}, last seen {row['last_seen']})"
        )
    print(f"Removed jobs: {len(removed)}")
    for row in removed:
        print(
            f"  {row['job_id']}: {row['company_name']} removed at {row['removed_at']}"
        )


def demo_multi(db_path: Path) -> None:
    if db_path.exists():
        os.remove(db_path)
    db = Database(db_path)
    try:
        # Configure two companies: ExampleCo (Greenhouse) and ExampleLever (Lever)
        base = Path(__file__).resolve().parent / "testdata"
        companies = [
            CompanyConfig(
                slug="exampleco",
                name="ExampleCo",
                ats="greenhouse",
                json_path=base / "sample1.json",
            ),
            CompanyConfig(
                slug="example-lever",
                name="ExampleLever",
                ats="lever",
                json_path=base / "sample_lever1.json",
            ),
        ]
        # First snapshot
        jobs1 = collect_jobs(companies, allow_remote=False)
        snapshot_time1 = datetime(2026, 1, 1, 0, 0, 0)
        persist_snapshot(db, snapshot_time1, jobs1, companies)
        print_db_summary(db, "After first snapshot (two companies)")

        # Update JSON paths for second snapshot
        companies = [
            CompanyConfig(
                slug="exampleco",
                name="ExampleCo",
                ats="greenhouse",
                json_path=base / "sample2.json",
            ),
            CompanyConfig(
                slug="example-lever",
                name="ExampleLever",
                ats="lever",
                json_path=base / "sample_lever2.json",
            ),
        ]
        jobs2 = collect_jobs(companies, allow_remote=False)
        snapshot_time2 = datetime(2026, 1, 2, 0, 0, 0)
        persist_snapshot(db, snapshot_time2, jobs2, companies)
        print_db_summary(db, "After second snapshot (two companies)")
    finally:
        db.close()


if __name__ == "__main__":
    demo_multi(Path("demo_multi.db"))