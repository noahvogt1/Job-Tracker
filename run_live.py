#!/usr/bin/env python3
"""
Run live job collection using companies.yaml as the source of truth.

This loads enabled companies from companies.yaml, builds CompanyConfig objects
(for supported ATS types), and runs the scheduler to collect + persist snapshots.

Usage:
  python run_live.py
  python run_live.py --once
  python run_live.py --interval-seconds 21600
"""

from __future__ import annotations

import argparse
from pathlib import Path

from job_tracker.scheduler import load_company_configs_from_yaml, run_scheduler


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--db", default="live_jobs.db", help="SQLite DB path")
    p.add_argument("--companies", default="companies.yaml", help="YAML config path")
    p.add_argument("--interval-seconds", type=int, default=6 * 3600, help="Seconds between runs")
    p.add_argument("--iterations", type=int, default=0, help="0 = infinite, 1 = run once, N = run N times")
    p.add_argument("--once", action="store_true", help="Run exactly one collection (iterations=1)")
    p.add_argument("--allow-remote", action="store_true", default=True, help="Include remote roles")
    args = p.parse_args()

    yaml_path = Path(args.companies)
    db_path = Path(args.db)

    companies = load_company_configs_from_yaml(yaml_path)

    iterations = 1 if args.once else args.iterations

    run_scheduler(
        db_path=db_path,
        companies=companies,
        interval_seconds=args.interval_seconds,
        iterations=iterations,
        allow_remote=args.allow_remote,
    )


if __name__ == "__main__":
    main()
