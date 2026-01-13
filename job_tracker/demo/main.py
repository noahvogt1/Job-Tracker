"""
Entry point for running job collectors and diff engine.

This script demonstrates how to use the job tracker modules to fetch
jobs from Greenhouse, compute diffs between snapshots, and filter for
new graduate positions. It can operate in two modes:

1. **Sample mode** using bundled JSON files under ``job_tracker/testdata``.
   This mode is useful when network access is unavailable. It loads two
   sample snapshots from ``sample1.json`` and ``sample2.json`` and
   demonstrates the diff computation and new graduate filtering.

2. **Live mode** attempting to fetch jobs from specified board tokens.
   Note: due to environment restrictions, live mode may fail to fetch
   remote data. It is included here for completeness.
"""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
from typing import List

from ..fetchers import fetch_greenhouse_jobs
from ..models import JobSnapshot
from ..diff_engine import compute_diff, is_new_grad


def run_sample_demo() -> None:
    """Run a demonstration using sample JSON files bundled with the package."""
    base_dir = Path(__file__).resolve().parent / "testdata"
    sample1 = base_dir / "sample1.json"
    sample2 = base_dir / "sample2.json"
    company_name = "ExampleCo"

    # First snapshot from sample1.json
    jobs1 = fetch_greenhouse_jobs(
        board_token="exampleco", company_name=company_name, json_path=sample1
    )
    snapshot1 = JobSnapshot(timestamp=datetime(2026, 1, 1), jobs=jobs1)

    # Second snapshot from sample2.json
    jobs2 = fetch_greenhouse_jobs(
        board_token="exampleco", company_name=company_name, json_path=sample2
    )
    snapshot2 = JobSnapshot(timestamp=datetime(2026, 1, 2), jobs=jobs2)

    diff = compute_diff(snapshot1, snapshot2)
    print("=== Demo: Snapshot Diff ===")
    print(f"New jobs: {len(diff['new'])}")
    for job in diff["new"]:
        print(f"  NEW: {job.title} at {job.company} [{job.location}] -> {job.url}")

    print(f"Removed jobs: {len(diff['removed'])}")
    for job in diff["removed"]:
        print(f"  REMOVED: {job.title} at {job.company}")

    print(f"Changed jobs: {len(diff['changed'])}")
    for jobdiff in diff["changed"]:
        changes_str = ", ".join(
            f"{field}: '{old_val}' -> '{new_val}'" for field, (old_val, new_val) in jobdiff.changes.items()
        )
        print(f"  CHANGED: {jobdiff.old.title} | {changes_str}")

    # Filter new graduate jobs from the second snapshot
    new_grad_jobs = [job for job in snapshot2.jobs if is_new_grad(job)]
    print("\n=== New Graduate Jobs in Second Snapshot ===")
    for job in new_grad_jobs:
        print(f"  {job.title} at {job.company} [{job.location}] -> {job.url}")


def run_live(board_tokens: List[str], company_names: List[str]) -> None:
    """Attempt to fetch live jobs from Greenhouse for the specified boards.

    Args:
        board_tokens: List of Greenhouse board slugs.
        company_names: Corresponding human-friendly company names.
    """
    from ..models import Job
    from ..fetchers import fetch_greenhouse_jobs

    snapshots = []
    now = datetime.utcnow()
    for token, company in zip(board_tokens, company_names):
        jobs = fetch_greenhouse_jobs(board_token=token, company_name=company)
        print(f"Fetched {len(jobs)} jobs for {company} ({token})")
        snapshots.append(JobSnapshot(timestamp=now, jobs=jobs))

    # Merge all snapshots into one for diff demonstration
    all_jobs = [job for snap in snapshots for job in snap.jobs]
    combined_snapshot = JobSnapshot(timestamp=now, jobs=all_jobs)
    print("Total jobs across companies:", len(combined_snapshot.jobs))
    new_grad_jobs = [job for job in combined_snapshot.jobs if is_new_grad(job)]
    print("New grad jobs across companies:", len(new_grad_jobs))
    for job in new_grad_jobs:
        print(f"  {job.title} at {job.company} -> {job.url}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Job tracker demonstration script")
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Run the offline demo using sample JSON files",
    )
    parser.add_argument(
        "--boards",
        nargs="*",
        help="Greenhouse board tokens to fetch from in live mode",
    )
    parser.add_argument(
        "--companies",
        nargs="*",
        help="Company names corresponding to the board tokens",
    )
    args = parser.parse_args()

    if args.demo or not args.boards:
        # Default to demo mode if no boards provided.
        run_sample_demo()
    else:
        if not args.companies or len(args.companies) != len(args.boards):
            raise ValueError("You must specify the same number of companies as boards")
        run_live(args.boards, args.companies)


if __name__ == "__main__":
    main()