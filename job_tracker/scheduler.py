#!/usr/bin/env python3
"""
Scheduler for the job tracker.

Runs: load companies -> collect jobs -> persist snapshot -> sleep -> repeat

Key point: this defines run_scheduler(), which run_live.py expects.
It also includes a YAML -> CompanyConfig adapter for supported ATS types.

Supported sources:
- greenhouse (expects endpoint like https://boards.greenhouse.io/<token>)
- lever (expects endpoint like https://jobs.lever.co/<slug>)
- ashby (expects endpoint like https://jobs.ashbyhq.com/<board> OR api.ashbyhq.com/.../<board>)
- smartrecruiters (expects endpoint like https://jobs.smartrecruiters.com/<company_identifier>)

Anything else is skipped (e.g., source: custom).
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple
from urllib.parse import urlparse

import yaml

from job_tracker.collector import collect_jobs
from job_tracker.db import Database
from job_tracker.persistence import persist_snapshot


@dataclass(frozen=True)
class CompanyConfig:
    slug: str
    name: str
    ats: str
    json_path: Optional[str] = None


def _load_yaml_companies(path: Path) -> Tuple[List[dict], dict]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if isinstance(data, dict):
        defaults = data.get("defaults") or {}
        companies = data.get("companies") or []
        if not isinstance(companies, list):
            raise ValueError("Expected 'companies:' to be a YAML list.")
        return companies, defaults
    if isinstance(data, list):
        return data, {}
    raise ValueError(f"Unsupported YAML structure: {type(data).__name__}")


def _derive_slug(source: str, endpoint: str) -> Optional[str]:
    """
    Convert a human endpoint URL into the identifier our fetchers need.
    Returns None if we can't derive one.
    """
    if not endpoint:
        return None

    u = urlparse(endpoint)
    host = (u.netloc or "").lower()
    parts = [p for p in (u.path or "").split("/") if p]

    source = (source or "").lower()

    if source == "greenhouse":
        # https://boards.greenhouse.io/<token>
        # sometimes people paste https://boards.greenhouse.io/<token>?gh_jid=...
        if parts:
            return parts[0]
        return None

    if source == "lever":
        # https://jobs.lever.co/<slug>
        if "lever.co" in host and parts:
            return parts[0]
        return None

    if source == "ashby":
        # https://jobs.ashbyhq.com/<board>
        # OR https://api.ashbyhq.com/posting-api/job-board/<board>
        if "ashbyhq.com" in host:
            if parts and parts[0] == "posting-api" and len(parts) >= 3 and parts[1] == "job-board":
                return parts[2]
            if parts:
                return parts[0]
        return None

    if source == "smartrecruiters":
        # https://jobs.smartrecruiters.com/<company_identifier>
        if "smartrecruiters.com" in host and parts:
            return parts[0]
        return None

    return None


def load_company_configs_from_yaml(yaml_path: Path) -> List[CompanyConfig]:
    companies, defaults = _load_yaml_companies(yaml_path)
    default_enabled = bool(defaults.get("enabled", True))

    out: List[CompanyConfig] = []
    skipped = 0

    for entry in companies:
        if not isinstance(entry, dict):
            skipped += 1
            continue
        enabled = bool(entry.get("enabled", default_enabled))
        if not enabled:
            continue

        name = entry.get("name") or "<unknown>"
        source = (entry.get("source") or "custom").lower()
        endpoint = entry.get("endpoint") or ""
        json_path = entry.get("json_path")

        # Only handle ATS we can collect today
        if source not in {"greenhouse", "lever", "ashby", "smartrecruiters"}:
            skipped += 1
            continue

        slug = entry.get("slug") or _derive_slug(source, endpoint)
        if not slug:
            skipped += 1
            continue

        out.append(CompanyConfig(slug=slug, name=name, ats=source, json_path=json_path))

    if not out:
        raise ValueError(
            "No collectable companies found in YAML. "
            "You need entries with source in {greenhouse, lever, ashby, smartrecruiters} "
            "and either slug: or a derivable endpoint."
        )

    if skipped:
        print(f"[scheduler] Skipped {skipped} YAML entries (custom/unsupported/missing slug).")

    return out


def run_scheduler(
    db_path: Path,
    companies: List[CompanyConfig],
    interval_seconds: int = 6 * 3600,
    iterations: int = 0,
    allow_remote: bool = True,
) -> None:
    """
    Main loop. iterations=0 means infinite.
    """
    i = 0
    while True:
        i += 1
        print(f"[scheduler] Run {i} collecting from {len(companies)} companies...")

        ts = datetime.now(timezone.utc)

        jobs, errors = collect_jobs(companies=companies, allow_remote=allow_remote, return_errors=True)
        succeeded = len(companies) - len(errors)

        with Database(db_path) as db:
            run_id = db.insert_run(started_at=ts, companies_total=len(companies))
            for err in errors:
                db.insert_run_error(
                    run_id=run_id,
                    created_at=ts,
                    company_slug=err.get("company_slug"),
                    company_name=err.get("company_name"),
                    ats=err.get("ats"),
                    error=err.get("error") or "unknown error",
                )

            snapshot_id = persist_snapshot(
                db=db,
                timestamp=ts,
                jobs=jobs,
                company_configs=companies,
                run_id=run_id,
            )

            status = "ok" if not errors else "error"
            db.finish_run(
                run_id=run_id,
                finished_at=datetime.now(timezone.utc),
                status=status,
                companies_succeeded=succeeded,
                companies_failed=len(errors),
                jobs_collected=len(jobs),
                notes=None if not errors else f"{len(errors)} company fetch failures",
            )

        print(
            f"[scheduler] Persisted snapshot_id={snapshot_id} jobs={len(jobs)} "
            f"companies_ok={succeeded} companies_failed={len(errors)}"
        )

        if iterations and i >= iterations:
            break

        print(f"[scheduler] Sleeping {interval_seconds} seconds...")
        time.sleep(interval_seconds)
