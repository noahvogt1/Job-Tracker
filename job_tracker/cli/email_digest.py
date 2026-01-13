#!/usr/bin/env python3
"""
Send an email digest of new-grad job changes.

Works with current schema:
- snapshots(snapshot_id, timestamp)
- snapshot_jobs(snapshot_id, job_id, version_id, is_new_grad)
- job_versions(version_id, job_id, timestamp, title, location, remote, extra)
- jobs(job_id, company_id, url, source, ...)
- companies(id, slug, name, source)

Adds a tiny digests table to checkpoint the last snapshot emailed.
"""

from __future__ import annotations

import argparse
import os
import smtplib
import sqlite3
from datetime import datetime, timezone
from email.message import EmailMessage
from typing import List, Tuple


def ensure_digest_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS digests (
            digest_id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TIMESTAMP NOT NULL,
            start_snapshot_id INTEGER,
            end_snapshot_id INTEGER NOT NULL
        );
        """
    )
    conn.commit()


def get_last_digest_end_snapshot(conn: sqlite3.Connection) -> int | None:
    row = conn.execute(
        "SELECT end_snapshot_id FROM digests ORDER BY digest_id DESC LIMIT 1"
    ).fetchone()
    return int(row[0]) if row else None


def get_latest_snapshot(conn: sqlite3.Connection) -> Tuple[int, str]:
    row = conn.execute(
        "SELECT snapshot_id, timestamp FROM snapshots ORDER BY snapshot_id DESC LIMIT 1"
    ).fetchone()
    if not row:
        raise SystemExit("No snapshots found. Run collection at least once.")
    return int(row[0]), str(row[1])


def get_previous_snapshot(conn: sqlite3.Connection, snapshot_id: int) -> int | None:
    row = conn.execute(
        "SELECT snapshot_id FROM snapshots WHERE snapshot_id < ? ORDER BY snapshot_id DESC LIMIT 1",
        (snapshot_id,),
    ).fetchone()
    return int(row[0]) if row else None


def diff_snapshot_job_ids(conn: sqlite3.Connection, prev_id: int, cur_id: int):
    prev = {r[0]: r[1] for r in conn.execute(
        "SELECT job_id, version_id FROM snapshot_jobs WHERE snapshot_id=?",
        (prev_id,),
    ).fetchall()}
    cur = {r[0]: r[1] for r in conn.execute(
        "SELECT job_id, version_id FROM snapshot_jobs WHERE snapshot_id=?",
        (cur_id,),
    ).fetchall()}

    new_ids = sorted([jid for jid in cur.keys() if jid not in prev])
    removed_ids = sorted([jid for jid in prev.keys() if jid not in cur])
    updated_ids = sorted([jid for jid in cur.keys() if jid in prev and cur[jid] != prev[jid]])

    return new_ids, updated_ids, removed_ids


def fetch_new_grad_rows(conn: sqlite3.Connection, snapshot_id: int, job_ids: List[str]):
    if not job_ids:
        return []

    placeholders = ",".join(["?"] * len(job_ids))
    query = f"""
    SELECT
        c.name as company,
        v.title as title,
        v.location as location,
        v.remote as remote,
        j.url as url,
        v.timestamp as version_ts
    FROM snapshot_jobs sj
    JOIN job_versions v ON v.version_id = sj.version_id
    JOIN jobs j ON j.job_id = sj.job_id
    JOIN companies c ON c.id = j.company_id
    WHERE sj.snapshot_id = ?
      AND sj.is_new_grad = 1
      AND sj.job_id IN ({placeholders})
    ORDER BY c.name, v.title
    """
    return conn.execute(query, (snapshot_id, *job_ids)).fetchall()


def format_digest(new_rows, updated_rows, removed_rows, prev_id, cur_id, cur_ts: str) -> str:
    lines = []
    lines.append(f"Job Tracker Digest")
    lines.append(f"Snapshots: {prev_id} -> {cur_id}   (latest at {cur_ts})")
    lines.append("")
    lines.append(f"NEW (new-grad): {len(new_rows)}")
    for company, title, location, remote, url, _ in new_rows:
        rflag = " [remote]" if remote else ""
        lines.append(f"  + {company} — {title} — {location}{rflag}")
        lines.append(f"    {url}")
    lines.append("")
    lines.append(f"UPDATED (new-grad): {len(updated_rows)}")
    for company, title, location, remote, url, _ in updated_rows:
        rflag = " [remote]" if remote else ""
        lines.append(f"  ~ {company} — {title} — {location}{rflag}")
        lines.append(f"    {url}")
    lines.append("")
    lines.append(f"REMOVED (new-grad): {len(removed_rows)}")
    for company, title, location, remote, url, _ in removed_rows:
        rflag = " [remote]" if remote else ""
        lines.append(f"  - {company} — {title} — {location}{rflag}")
        lines.append(f"    {url}")

    return "\n".join(lines).strip() + "\n"


def send_email(subject: str, body: str) -> None:
    to_addr = os.environ.get("DIGEST_TO")
    host = os.environ.get("SMTP_HOST")
    port = int(os.environ.get("SMTP_PORT", "587"))
    user = os.environ.get("SMTP_USER")
    pwd = os.environ.get("SMTP_PASS")

    if not (to_addr and host and user and pwd):
        raise SystemExit("Missing SMTP env vars. Need DIGEST_TO, SMTP_HOST, SMTP_USER, SMTP_PASS (and optionally SMTP_PORT).")

    msg = EmailMessage()
    msg["From"] = user
    msg["To"] = to_addr
    msg["Subject"] = subject
    msg.set_content(body)

    with smtplib.SMTP(host, port) as s:
        s.starttls()
        s.login(user, pwd)
        s.send_message(msg)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--db", default=os.environ.get("DB_PATH", "live_jobs.db"))
    p.add_argument("--dry-run", action="store_true", help="Print digest instead of sending email")
    args = p.parse_args()

    conn = sqlite3.connect(args.db)
    ensure_digest_table(conn)

    latest_id, latest_ts = get_latest_snapshot(conn)
    prev_id = get_previous_snapshot(conn, latest_id)
    if prev_id is None:
        raise SystemExit("Need at least 2 snapshots before emailing a digest.")

    # Resume from last emailed snapshot if available
    last_end = get_last_digest_end_snapshot(conn)
    if last_end is not None and last_end < latest_id:
        # Compare last_end -> latest
        prev_id = last_end

    new_ids, updated_ids, removed_ids = diff_snapshot_job_ids(conn, prev_id, latest_id)

    new_rows = fetch_new_grad_rows(conn, latest_id, new_ids)
    updated_rows = fetch_new_grad_rows(conn, latest_id, updated_ids)
    removed_rows = fetch_new_grad_rows(conn, prev_id, removed_ids)

    body = format_digest(new_rows, updated_rows, removed_rows, prev_id, latest_id, latest_ts)
    subject = f"Job Tracker Digest: {len(new_rows)} new-grad new / {len(updated_rows)} updated / {len(removed_rows)} removed"

    if args.dry_run:
        print(body)
    else:
        send_email(subject, body)

    # Record checkpoint
    conn.execute(
        "INSERT INTO digests(created_at, start_snapshot_id, end_snapshot_id) VALUES (?, ?, ?)",
        (datetime.now(timezone.utc).isoformat(), prev_id, latest_id),
    )
    conn.commit()
    conn.close()


if __name__ == "__main__":
    main()
