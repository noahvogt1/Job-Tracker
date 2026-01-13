"""
Collector to fetch jobs across multiple companies and ATS providers.

The collector module defines functions to fetch jobs from different
Applicant Tracking Systems (ATS) given a configuration of companies to
monitor. Each company record includes identifying information such as
the ATS type, board token or site slug, and a human-friendly name.

The main entry point is ``collect_jobs`` which returns a list of
``Job`` objects for all configured companies. The caller can then
persist these jobs to the database and compute diffs or other
analytics.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Dict, Optional
from pathlib import Path

from .fetchers import (
    fetch_greenhouse_jobs,
    fetch_lever_jobs,
    fetch_ashby_jobs,
    fetch_smartrecruiters_jobs,
)
from .models import Job


@dataclass
class CompanyConfig:
    """Configuration for a company to collect jobs for."""

    slug: str  # Board token or site slug for the ATS
    name: str  # Human friendly name
    ats: str  # 'greenhouse', 'lever', 'ashby', or 'smartrecruiters'
    # Optional path to a local JSON file for offline testing
    json_path: Optional[Path] = None


def collect_jobs(
    companies: List[CompanyConfig],
    allow_remote: bool = True,
    polite_delay: float = 0.0,
    return_errors: bool = False,
) -> List[Job] | tuple[List[Job], List[Dict[str, str]]]:
    """Fetch jobs for all configured companies.

    Args:
        companies: List of company configurations.
        allow_remote: If False, skip network calls and expect `json_path`
            on each company for offline testing.

    Returns:
        Combined list of ``Job`` objects from all companies.
    """
    all_jobs: List[Job] = []
    errors: List[Dict[str, str]] = []
    for company in companies:
        ats_type = company.ats.lower()
        try:
            if ats_type == "greenhouse":
                jobs = fetch_greenhouse_jobs(
                    board_token=company.slug,
                    company_name=company.name,
                    json_path=company.json_path,
                    allow_remote=allow_remote,
                )
            elif ats_type == "lever":
                if company.json_path is not None:
                    api_url = ""
                else:
                    api_url = f"https://api.lever.co/v0/postings/{company.slug}?mode=json"
                jobs = fetch_lever_jobs(
                    api_url=api_url,
                    company_name=company.name,
                    json_path=company.json_path,
                    allow_remote=allow_remote,
                )
            elif ats_type == "ashby":
                jobs = fetch_ashby_jobs(
                    board_name=company.slug,
                    company_name=company.name,
                    json_path=company.json_path,
                    allow_remote=allow_remote,
                )
            elif ats_type == "smartrecruiters":
                jobs = fetch_smartrecruiters_jobs(
                    company_identifier=company.slug,
                    company_name=company.name,
                    json_path=company.json_path,
                    allow_remote=allow_remote,
                )
            else:
                raise ValueError(f"Unsupported ATS type: {company.ats}")

            all_jobs.extend(jobs)
        except Exception as e:
            errors.append(
                {
                    "company_slug": company.slug,
                    "company_name": company.name,
                    "ats": company.ats,
                    "error": f"{type(e).__name__}: {e}",
                }
            )
        # Delay between calls to be polite to remote servers
        if polite_delay > 0:
            import time as _time  # import locally to avoid overhead if not needed
            _time.sleep(polite_delay)
    if return_errors:
        return all_jobs, errors

    return all_jobs