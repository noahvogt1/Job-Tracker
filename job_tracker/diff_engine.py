"""
Diff engine for job snapshots.

This module provides functions to compute differences between two
``JobSnapshot`` instances. It identifies new jobs, removed jobs, and
changes to existing jobs. For changed jobs, it can also record which
fields have been modified.

The diff engine operates purely in-memory on lists of ``Job`` objects,
which makes it easy to plug into a database or other storage backend.
"""

from __future__ import annotations

import re
from typing import Dict, List, Tuple

from .models import Job, JobSnapshot


class JobDiff:
    """Container for a changed job and the fields that were modified."""

    def __init__(self, job_id: str, old: Job, new: Job, changes: Dict[str, Tuple] = None):
        self.job_id = job_id
        self.old = old
        self.new = new
        # changes maps field name to a tuple of (old_value, new_value)
        self.changes = changes or {}

    def __repr__(self) -> str:
        return f"JobDiff(job_id={self.job_id}, changes={self.changes})"


def compute_diff(old_snapshot: JobSnapshot, new_snapshot: JobSnapshot) -> Dict[str, List]:
    """Compute differences between two job snapshots.

    Args:
        old_snapshot: The previous snapshot of jobs.
        new_snapshot: The current snapshot of jobs.

    Returns:
        A dictionary with keys ``new``, ``removed``, and ``changed``. Each
        value is a list of ``Job`` (for ``new`` and ``removed``) or
        ``JobDiff`` (for ``changed``).
    """
    old_index = old_snapshot.index_by_id()
    new_index = new_snapshot.index_by_id()

    # Determine new jobs.
    new_jobs: List[Job] = []
    removed_jobs: List[Job] = []
    changed_jobs: List[JobDiff] = []

    for job_id, new_job in new_index.items():
        if job_id not in old_index:
            new_jobs.append(new_job)
        else:
            old_job = old_index[job_id]
            changes: Dict[str, Tuple] = {}
            # Compare fields of interest.
            for field in ["title", "location", "remote", "extra"]:
                old_val = getattr(old_job, field)
                new_val = getattr(new_job, field)
                if old_val != new_val:
                    changes[field] = (old_val, new_val)
            if changes:
                changed_jobs.append(JobDiff(job_id, old_job, new_job, changes))

    for job_id, old_job in old_index.items():
        if job_id not in new_index:
            removed_jobs.append(old_job)

    return {
        "new": new_jobs,
        "removed": removed_jobs,
        "changed": changed_jobs,
    }


# -------------------------
# New-grad classification
# -------------------------

_POSITIVE_TITLE_KEYWORDS = [
    # explicit early-career signals
    "new grad",
    "new graduate",
    "early career",
    "university",
    "campus",
    "graduate program",
    "campus hire",
    "rotational",
    "university grad",
    "university graduate",
    "early in career",
    "campus recruiting",
    "college graduate",
    # entry/junior patterns
    "entry level",
    "entry-level",
    "junior",
    "jr",
    "associate",
    # common level-1 signals
    "engineer i",
    "software engineer i",
    "developer i",
    "analyst i",
    "engineer 1",
    "software engineer 1",
    "level 1",
    # undergrad-associated roles
    "intern",
    "internship",
    "co-op",
    "coop",
]

# Hard negatives (title)
_NEGATIVE_TITLE_KEYWORDS = [
    "senior",
    "sr",
    "staff",
    "principal",
    "lead",
    "manager",
    "director",
    "vice president",
    "vp",
    "head of",
    "architect",
    "contract",
    "contractor",
    "temporary",
    "temp",
    "consultant",
]

# Research roles are often not new-grad unless explicitly stated
_RESEARCH_TITLE_KEYWORDS = [
    "research scientist",
    "research engineer",
    "researcher",
]

# Hard negatives (requirements / description / metadata)
_NEGATIVE_TEXT_PATTERNS = [
    r"\b[3-9]\+?\s*(?:years|yrs)\b",
    r"\b\d{2}\+?\s*(?:years|yrs)\b",
    r"\bminimum\s+\d+\s*(?:years|yrs)\b",
    r"\b\d+\+?\s*(?:years|yrs)\s+of experience\b",
    r"\bphd\b",
    r"\bpostdoc\b",
    r"\bmasters\s+required\b",
    r"\bms\s+required\b",
]

# Positive patterns for new-grad suitability (<=2 YOE)
_POSITIVE_TEXT_PATTERNS = [
    r"\b0\s*[-–to]+\s*2\s*(?:years|yrs)\b",
    r"\b0\s*[-–to]+\s*1\s*(?:years|yrs)\b",
    r"\b1\s*[-–to]+\s*2\s*(?:years|yrs)\b",
    r"\bno prior experience\b",
    r"\brecent graduate\b",
    r"\bnew graduate\b",
]


def _collect_text_blobs(job: Job) -> List[str]:
    """Collect likely text fields from job.extra for scanning."""
    blobs: List[str] = []
    if not job.extra:
        return blobs

    # Common description keys across ATSes
    for key in [
        "description",
        "descriptionPlain",
        "openingPlain",
        "jobDescription",
        "job_description",
        "qualifications",
        "requirements",
        "responsibilities",
        "content",
    ]:
        val = job.extra.get(key)
        if val:
            blobs.append(str(val))

    # Also flatten values (best-effort) without going too deep
    for v in job.extra.values():
        if isinstance(v, list):
            blobs.extend(str(item) for item in v if item is not None)
        elif isinstance(v, dict):
            blobs.extend(str(val) for val in v.values() if val is not None)
        elif v is not None:
            # scalar
            blobs.append(str(v))

    return blobs


def classify_new_grad(job: Job) -> Tuple[bool, List[str]]:
    """
    Strict classifier:
    - Reject strong seniority signals
    - Reject >=3 YOE / PhD / postdoc requirements
    - Require at least one positive new-grad signal to return True
    - Research roles require explicit positive signal
    Returns (is_new_grad, reasons)
    """
    reasons: List[str] = []
    title = (job.title or "").lower()

    # Title hard negatives
    for bad in _NEGATIVE_TITLE_KEYWORDS:
        if bad in title:
            return False, [f'title contains "{bad}" (seniority)']

    is_research_role = any(bad in title for bad in _RESEARCH_TITLE_KEYWORDS)

    # Build text to scan
    text_blobs = [title] + [b.lower() for b in _collect_text_blobs(job)]
    full_text = "\n".join(text_blobs)

    # Hard negative requirement patterns
    for pat in _NEGATIVE_TEXT_PATTERNS:
        if re.search(pat, full_text):
            return False, [f"matched negative requirement pattern: {pat}"]

    # Positive evidence
    positive_hits: List[str] = []

    for good in _POSITIVE_TITLE_KEYWORDS:
        if good in title:
            positive_hits.append(f'title contains "{good}"')
            break

    for pat in _POSITIVE_TEXT_PATTERNS:
        if re.search(pat, full_text):
            positive_hits.append(f"matched positive requirement pattern: {pat}")
            break

    # Metadata signals (best-effort)
    if job.extra:
        for key in ["experienceLevel", "experience_level", "seniority", "level", "typeOfEmployment", "employmentType"]:
            val = job.extra.get(key)
            if isinstance(val, dict):
                lab = (val.get("label") or val.get("name") or "").lower()
            else:
                lab = str(val).lower() if val is not None else ""

            if not lab:
                continue

            if any(t in lab for t in ["senior", "staff", "principal", "lead", "manager", "director"]):
                return False, [f'extra.{key}="{val}" (seniority)']

            if any(t in lab for t in ["entry", "junior", "intern", "graduate", "early", "new grad"]):
                positive_hits.append(f'extra.{key}="{val}"')
                break

    # Research roles require explicit positive signal
    if is_research_role and not positive_hits:
        return False, ["research role with no explicit new-grad signals"]

    # Strict: require at least one positive signal
    if not positive_hits:
        return False, ["no positive new-grad signals found"]

    reasons.extend(positive_hits)
    return True, reasons


def is_new_grad(job: Job) -> bool:
    """Backwards-compatible boolean wrapper."""
    return classify_new_grad(job)[0]
