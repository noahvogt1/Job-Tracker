"""
Data models for the job tracking application.

The primary entity is ``Job`` which represents a job posting at a given
company. Each job has a stable identifier derived from the company
identifier and the URL of the posting. Additional fields include the
title, location, remote flag and source (Greenhouse, Lever, etc.).

The ``JobSnapshot`` class encapsulates a collection of jobs at a single
point in time. Snapshots are used by the diff engine to detect
additions, removals and updates between runs.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Optional


def stable_job_id(company: str, url: str) -> str:
    """Return a stable, deterministic identifier for a job.

    The job ID is derived from the company identifier and the job URL via
    SHA256 hashing. Only the first 24 characters of the hex digest are
    retained to keep the identifier compact while minimizing collisions.

    Args:
        company: Normalized company name or slug.
        url: Absolute URL for the job posting.

    Returns:
        A 24-character hexadecimal string.
    """
    return hashlib.sha256(f"{company}|{url}".encode("utf-8")).hexdigest()[:24]


@dataclass
class Job:
    """Represents a single job posting.

    Attributes:
        job_id: Stable identifier derived from company name and URL.
        company: Human friendly company name.
        title: Job title.
        location: Location string, e.g. "New York, NY" or "Remote".
        url: Absolute URL to the job posting.
        source: Name of the source system (e.g. greenhouse, lever).
        remote: Optional boolean flag indicating if the job is remote.
        posted_at: Optional ISO timestamp when the job was first seen.
        extra: Optional dictionary for additional fields (e.g. salary range).
    """

    job_id: str
    company: str
    title: str
    location: str
    url: str
    source: str
    remote: Optional[bool] = None
    posted_at: Optional[str] = None
    extra: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Optional[str]]:
        """Serialize the job to a dictionary.

        This method produces a plain dictionary representation of the job
        which can be stored in JSON or a database.

        Returns:
            A dictionary containing all job fields.
        """
        return {
            "job_id": self.job_id,
            "company": self.company,
            "title": self.title,
            "location": self.location,
            "url": self.url,
            "source": self.source,
            "remote": self.remote,
            "posted_at": self.posted_at,
            "extra": self.extra,
        }


@dataclass
class JobSnapshot:
    """Collection of jobs at a single timestamp.

    A snapshot is taken each time the collector runs. Snapshots are
    compared against previous snapshots to produce diffs.

    Attributes:
        timestamp: Datetime when the snapshot was taken.
        jobs: List of jobs present at the snapshot time.
    """

    timestamp: datetime
    jobs: List[Job]

    def index_by_id(self) -> Dict[str, Job]:
        """Return a mapping of job_id to Job for quick lookups."""
        return {job.job_id: job for job in self.jobs}

    def filter(self, predicate) -> "JobSnapshot":
        """Return a new snapshot containing only jobs matching predicate.

        Args:
            predicate: A callable receiving a Job and returning a boolean.

        Returns:
            A new ``JobSnapshot`` containing only jobs for which
            ``predicate(job)`` returns True.
        """
        filtered_jobs = [job for job in self.jobs if predicate(job)]
        return JobSnapshot(timestamp=self.timestamp, jobs=filtered_jobs)