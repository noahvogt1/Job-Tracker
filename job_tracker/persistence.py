"""
Persistence utilities to ingest collected jobs into the database.

This module takes the list of jobs produced by the collector and writes
them into the database schema defined in ``db.py``. It handles
insertion of companies, jobs, versions, and snapshot associations. It
also updates the ``active`` and ``removed_at`` flags on jobs that are
no longer present in the latest snapshot.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import List, Dict

from .models import Job
from .db import Database
from .diff_engine import is_new_grad
from .collector import CompanyConfig


def persist_snapshot(
    db: Database,
    timestamp: datetime,
    jobs: List[Job],
    company_configs: List[CompanyConfig],
) -> int:
    """Persist a snapshot of jobs into the database.

    Args:
        db: Database instance.
        timestamp: Datetime of the snapshot.
        jobs: List of jobs collected.
        company_configs: Configuration list to resolve company ids.

    Returns:
        The snapshot_id of the newly inserted snapshot.
    """
    # Build mapping from company name to (slug, ats)
    name_to_config: Dict[str, CompanyConfig] = {
        cfg.name: cfg for cfg in company_configs
    }

    # Step 1: Insert snapshot row
    snapshot_id = db.insert_snapshot(timestamp)

    # Collect job_ids from snapshot to detect removals later
    snapshot_job_ids = set()

    # Step 2: Upsert companies and jobs, insert versions, snapshot_jobs
    for job in jobs:
        snapshot_job_ids.add(job.job_id)
        # Resolve company config by name; fallback to None
        cfg = name_to_config.get(job.company)
        if cfg is None:
            raise ValueError(
                f"No company configuration found for company '{job.company}'."
            )
        # Upsert company and get id
        company_id = db.upsert_company(slug=cfg.slug, name=cfg.name, source=cfg.ats)
        existing = db.get_job(job.job_id)
        if existing is None:
            # Insert new job row
            db.insert_job(
                job_id=job.job_id,
                company_id=company_id,
                url=job.url,
                source=job.source,
                first_seen=timestamp,
                last_seen=timestamp,
            )
        else:
            # Update existing job's last_seen and reactivate if necessary
            db.update_job_seen(job.job_id, last_seen=timestamp)
        # Insert job version record
        # Serialize extra dictionary to JSON string
        extra_json = json.dumps(job.extra, ensure_ascii=False) if job.extra else "{}"
        version_id = db.insert_job_version(
            job_id=job.job_id,
            timestamp=timestamp,
            title=job.title,
            location=job.location or "",
            remote=job.remote,
            extra_json=extra_json,
        )
        # Determine new grad status
        new_grad_flag = is_new_grad(job)
        # Record snapshot-job association
        db.insert_snapshot_job(
            snapshot_id=snapshot_id,
            job_id=job.job_id,
            version_id=version_id,
            is_new_grad=new_grad_flag,
        )

    # Step 3: Mark removed jobs (jobs previously active but not present now)
    # Get list of active jobs in DB
    active_jobs = db.list_active_jobs()
    # Determine which active job_ids are not in current snapshot
    removed_ids = [row["job_id"] for row in active_jobs if row["job_id"] not in snapshot_job_ids]
    db.mark_jobs_removed(removed_ids, removed_at=timestamp)

    return snapshot_id