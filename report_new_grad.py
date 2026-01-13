#!/usr/bin/env python3
"""
Report new-grad jobs since the previous snapshot.

Works with the current SQLite schema:
- snapshots(snapshot_id, timestamp)
- snapshot_jobs(snapshot_id, job_id, version_id, is_new_grad)
- job_versions(version_id, job_id, timestamp, title, location, remote, extra)
- jobs(job_id, company_id, url, source, first_seen, last_seen, removed_at, active)
- companies(id, slug, name, source)

Usage:
  python report_new_grad.py --db live_jobs.db
  python report_new_grad.py --db live_jobs.db --limit 50
  python report_new_grad.py --db live_jobs.db --snapshots-back 2
"""

from __future__ import annotations

from job_tracker.diff_engine import classify_new_grad
from job_tracker.models import Job

import argparse
import json
import sqlite3
from typing import Any, Dict, List, Optional, Tuple


def _connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def _get_latest_snapshots(conn: sqlite3.Connection, snapshots_back: int = 1) -> Tuple[int, int]:
    """
    Returns (latest_snapshot_id, previous_snapshot_id) where previous is N back.

    snapshots_back=1 -> previous = immediately prior snapshot
    snapshots_back=2 -> previous = two snapshots back, etc.
    """
    rows = conn.execute(
        "SELECT snapshot_id FROM snapshots ORDER BY snapshot_id DESC LIMIT ?",
        (snapshots_back + 1,),
    ).fetchall()

    if len(rows) < 2:
        raise RuntimeError(
            "Need at least 2 snapshots to compute deltas. Run live collection at least twice."
        )

    latest = int(rows[0]["snapshot_id"])
    previous = int(rows[snapshots_back]["snapshot_id"])
    return latest, previous


def _fetch_new_grad_map(conn: sqlite3.Connection, snapshot_id: int) -> Dict[str, int]:
    """
    job_id -> version_id for jobs that are marked is_new_grad=1 in the given snapshot.
    """
    rows = conn.execute(
        """
        SELECT job_id, version_id
        FROM snapshot_jobs
        WHERE snapshot_id = ? AND is_new_grad = 1
        """,
        (snapshot_id,),
    ).fetchall()
    return {str(r["job_id"]): int(r["version_id"]) for r in rows}


def _fetch_job_details_by_job_ids(
    conn: sqlite3.Connection,
    snapshot_id: int,
    job_ids: List[str],
) -> List[sqlite3.Row]:
    """
    Fetch job details for a list of job_ids at a given snapshot_id.
    Pulls title/location/remote/extra from the job_versions linked by snapshot_jobs,
    plus company name + url.
    """
    if not job_ids:
        return []

    # SQLite has a variable limit; chunk to be safe.
    CHUNK = 500
    out: List[sqlite3.Row] = []

    base_sql = """
    SELECT
        c.name AS company_name,
        j.url  AS url,
        j.source AS source,
        j.first_seen AS first_seen,
        j.last_seen  AS last_seen,
        v.title AS title,
        v.location AS location,
        v.remote AS remote,
        v.extra AS extra
    FROM snapshot_jobs sj
    JOIN job_versions v ON v.version_id = sj.version_id
    JOIN jobs j         ON j.job_id = sj.job_id
    JOIN companies c    ON c.id = j.company_id
    WHERE sj.snapshot_id = ?
      AND sj.job_id IN ({placeholders})
    ORDER BY c.name ASC, v.title ASC
    """

    for i in range(0, len(job_ids), CHUNK):
        chunk = job_ids[i : i + CHUNK]
        placeholders = ",".join(["?"] * len(chunk))
        sql = base_sql.format(placeholders=placeholders)
        params = [snapshot_id] + chunk
        out.extend(conn.execute(sql, params).fetchall())

    return out


def _pretty_remote(remote_val: Any) -> str:
    if remote_val is None:
        return "Unknown"
    try:
        return "Remote" if int(remote_val) == 1 else "Not remote"
    except Exception:
        return "Unknown"


def _why_new_grad(row):
    # rebuild a Job object from the row so we can reuse the classifier
    extra = None
    if row["extra"]:
        try:
            extra = json.loads(row["extra"])
        except Exception:
            extra = {"raw_extra": row["extra"]}

    job = Job(
        job_id="report",
        company=row["company_name"],
        title=row["title"],
        location=row["location"] or "",
        url=row["url"],
        source=row["source"] or "",
        remote=row["remote"],
        extra=extra,
    )
    ok, reasons = classify_new_grad(job)
    if not ok:
        return "NOT new-grad by strict rules: " + "; ".join(reasons)
    return "; ".join(reasons)


def _print_section(title: str, rows: List[sqlite3.Row], limit: int) -> None:
    print("\n" + "=" * 80)
    print(title)
    print("=" * 80)

    if not rows:
        print("(none)")
        return

    shown = rows[:limit] if limit > 0 else rows
    for r in shown:
        company = r["company_name"]
        job_title = r["title"]
        loc = r["location"] or ""
        remote = _pretty_remote(r["remote"])
        url = r["url"]
        why = _why_new_grad(r)

        line1 = f"[{company}] {job_title}"
        if loc:
            line1 += f" — {loc}"
        line1 += f" ({remote})"
        print(line1)
        print(f"  {url}")
        print(f"  Why: {why}")
        print("")

    if limit > 0 and len(rows) > limit:
        print(f"... ({len(rows) - limit} more)\n")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="live_jobs.db", help="Path to SQLite DB (default: live_jobs.db)")
    ap.add_argument("--limit", type=int, default=50, help="Max jobs per section to print (default: 50, 0=all)")
    ap.add_argument(
        "--snapshots-back",
        type=int,
        default=1,
        help="Compare latest snapshot to N-back snapshot (default: 1 = previous snapshot)",
    )
    args = ap.parse_args()

    conn = _connect(args.db)
    latest_id, prev_id = _get_latest_snapshots(conn, snapshots_back=args.snapshots_back)

    latest_ts = conn.execute("SELECT timestamp FROM snapshots WHERE snapshot_id=?", (latest_id,)).fetchone()["timestamp"]
    prev_ts = conn.execute("SELECT timestamp FROM snapshots WHERE snapshot_id=?", (prev_id,)).fetchone()["timestamp"]

    latest_map = _fetch_new_grad_map(conn, latest_id)  # job_id -> version_id
    prev_map = _fetch_new_grad_map(conn, prev_id)

    latest_job_ids = set(latest_map.keys())
    prev_job_ids = set(prev_map.keys())

    new_ids = sorted(list(latest_job_ids - prev_job_ids))
    removed_ids = sorted(list(prev_job_ids - latest_job_ids))

    # UPDATED = present in both, but version changed
    updated_ids = sorted(
        [jid for jid in (latest_job_ids & prev_job_ids) if latest_map[jid] != prev_map[jid]]
    )

    print(f"Comparing snapshots: latest={latest_id} ({latest_ts}) vs previous={prev_id} ({prev_ts})")
    print(f"NEW: {len(new_ids)} | UPDATED: {len(updated_ids)} | REMOVED: {len(removed_ids)}")

    new_rows = _fetch_job_details_by_job_ids(conn, latest_id, new_ids)
    updated_rows = _fetch_job_details_by_job_ids(conn, latest_id, updated_ids)
    removed_rows = _fetch_job_details_by_job_ids(conn, prev_id, removed_ids)

    _print_section("NEW (new-grad)", new_rows, args.limit)
    _print_section("UPDATED (new-grad)", updated_rows, args.limit)
    _print_section("REMOVED (new-grad)", removed_rows, args.limit)


if __name__ == "__main__":
    main()
