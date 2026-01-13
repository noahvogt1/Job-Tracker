#!/usr/bin/env python3
"""
CLI script to report job changes between snapshots.

This tool compares two snapshots of job postings stored in a SQLite database and
prints lists of NEW, UPDATED and REMOVED jobs.  By default it compares the
latest snapshot to the previous snapshot.  Use the ``--since-hours`` flag to
compare the latest snapshot to the snapshot taken at or before a given number
of hours ago.  This allows you to generate a report covering an arbitrary
time window (e.g. the last 24 hours).

Usage::

    python report_new_grad.py [--db-path live_jobs.db] [--since-hours 24]

The output is written to stdout in a human‑readable format.  It is intended
for local inspection; the daily email digest uses similar logic to build
email content.
"""

from __future__ import annotations

import argparse
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, Tuple, List, Any

from job_tracker.normalize import canonicalize_url


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Report job changes between snapshots")
    parser.add_argument("--db-path", default="live_jobs.db", help="Path to SQLite database")
    parser.add_argument("--since-hours", type=float, default=None,
                        help="Number of hours back to compare against (default: previous snapshot)")
    return parser.parse_args()


def pick_snapshot_range(conn: sqlite3.Connection, since_hours: float | None) -> Tuple[int, int]:
    """Select start and end snapshot IDs based on ``since_hours``.

    Args:
        conn: open SQLite connection
        since_hours: hours back to compare; if None, use previous snapshot

    Returns:
        (start_snapshot_id, end_snapshot_id)

    Raises:
        RuntimeError: if there are fewer than two snapshots when ``since_hours`` is None.
    """
    cur = conn.cursor()
    cur.execute("SELECT id, created_at FROM snapshots ORDER BY created_at")
    rows = cur.fetchall()
    if not rows:
        raise RuntimeError("No snapshots found in database")
    # Latest snapshot
    end_id = rows[-1][0]
    if since_hours is None:
        if len(rows) < 2:
            # If only one snapshot exists, compare it to itself
            start_id = end_id
        else:
            start_id = rows[-2][0]
        return start_id, end_id
    # Determine cutoff time
    now = datetime.utcnow()
    cutoff = now - timedelta(hours=since_hours)
    start_id = rows[0][0]
    # Find the snapshot with created_at <= cutoff, choose the latest one before cutoff
    for sid, created_at_str in reversed(rows):
        try:
            created_at = datetime.fromisoformat(created_at_str)
        except ValueError:
            # Fallback: parse as naive timestamp
            created_at = datetime.strptime(created_at_str.split(".")[0], "%Y-%m-%d %H:%M:%S")
        if created_at <= cutoff:
            start_id = sid
            break
    return start_id, end_id


def fetch_jobs_by_snapshot(conn: sqlite3.Connection, snapshot_id: int) -> Dict[str, Dict[str, Any]]:
    """Return a mapping of canonical job key to job record for a snapshot."""
    cur = conn.cursor()
    query = """
    SELECT j.id, j.job_id, j.company, j.title, j.location, j.url,
           j.normal_title, j.normal_location, j.canonical_url
    FROM job_versions j
    JOIN snapshot_jobs sj ON j.id = sj.job_version_id
    WHERE sj.snapshot_id = ?
    """
    cur.execute(query, (snapshot_id,))
    rows = cur.fetchall()
    jobs: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        (jid, job_id, company, title, location, url,
         normal_title, normal_location, canonical_url) = row
        # Build canonical key
        # Use normalized title and location when available, else fall back to raw
        norm_title = (normal_title or title or "").strip().lower()
        norm_loc = (normal_location or location or "").strip().lower()
        canon_url = canonical_url or canonicalize_url(url)
        key = "|".join([company.strip().lower() if company else "",
                         norm_title, norm_loc, canon_url])
        jobs[key] = {
            "id": jid,
            "job_id": job_id,
            "company": company,
            "title": title,
            "location": location,
            "url": url,
            "normal_title": normal_title,
            "normal_location": normal_location,
            "canonical_url": canon_url,
        }
    return jobs


def diff_jobs(start_jobs: Dict[str, Dict[str, Any]],
              end_jobs: Dict[str, Dict[str, Any]]) -> Tuple[List[Dict[str, Any]],
                                                          List[Dict[str, Any]],
                                                          List[Dict[str, Any]]]:
    """Compute new, updated and removed jobs between two job mappings.

    Args:
        start_jobs: mapping from canonical key to job dict at start snapshot
        end_jobs: mapping from canonical key to job dict at end snapshot

    Returns:
        (new_jobs, updated_jobs, removed_jobs)
    """
    new_jobs = []
    removed_jobs = []
    updated_jobs = []

    start_keys = set(start_jobs)
    end_keys = set(end_jobs)
    # New keys in end snapshot
    for key in sorted(end_keys - start_keys):
        new_jobs.append(end_jobs[key])
    # Removed keys present in start but not in end
    for key in sorted(start_keys - end_keys):
        removed_jobs.append(start_jobs[key])
    # Keys present in both; check for updates
    for key in sorted(start_keys & end_keys):
        s = start_jobs[key]
        e = end_jobs[key]
        # Compare selected fields
        diffs = {}
        if (s.get("title") or "").strip() != (e.get("title") or "").strip():
            diffs["title"] = (s.get("title"), e.get("title"))
        if (s.get("location") or "").strip() != (e.get("location") or "").strip():
            diffs["location"] = (s.get("location"), e.get("location"))
        # Compare canonical URL in case job is rehosted under different tracking link
        if (s.get("canonical_url") or "").strip() != (e.get("canonical_url") or "").strip():
            diffs["canonical_url"] = (s.get("canonical_url"), e.get("canonical_url"))
        if diffs:
            updated_entry = dict(e)  # use end version as base
            updated_entry["diffs"] = diffs
            updated_jobs.append(updated_entry)
    return new_jobs, updated_jobs, removed_jobs


def print_report(new_jobs: List[Dict[str, Any]],
                 updated_jobs: List[Dict[str, Any]],
                 removed_jobs: List[Dict[str, Any]]) -> None:
    """Pretty‑print the diff results to stdout."""
    def print_section(title: str, jobs: List[Dict[str, Any]], show_diffs: bool = False) -> None:
        print(f"\n{title} ({len(jobs)})")
        print("=" * (len(title) + len(str(len(jobs))) + 3))
        for j in jobs:
            company = j.get("company") or ""
            title = j.get("title") or ""
            location = j.get("location") or ""
            url = j.get("url") or j.get("canonical_url") or ""
            print(f"- {company} — {title}")
            print(f"  {location} | {url}")
            if show_diffs and j.get("diffs"):
                for field, (old, new) in j["diffs"].items():
                    print(f"    updated {field}: {old!r} → {new!r}")
        if not jobs:
            print("(none)")
    print_section("NEW", new_jobs)
    print_section("UPDATED", updated_jobs, show_diffs=True)
    print_section("REMOVED", removed_jobs)


def main() -> None:
    args = parse_arguments()
    conn = sqlite3.connect(args.db_path)
    try:
        start_id, end_id = pick_snapshot_range(conn, args.since_hours)
        start_jobs = fetch_jobs_by_snapshot(conn, start_id)
        end_jobs = fetch_jobs_by_snapshot(conn, end_id)
        new_jobs, updated_jobs, removed_jobs = diff_jobs(start_jobs, end_jobs)
        print(f"Comparing snapshots: start={start_id}, end={end_id}\n")
        print_report(new_jobs, updated_jobs, removed_jobs)
    finally:
        conn.close()


if __name__ == "__main__":
    main()