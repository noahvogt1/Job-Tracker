"""
Functions to fetch job postings from various applicant tracking systems (ATS).

Currently supported sources include Greenhouse, Lever, Ashby and
SmartRecruiters. Each fetcher returns a list of ``Job`` objects defined
in ``job_tracker.models``. If
network access is unavailable or calls fail, fetchers can also load
pre-recorded JSON from files for local testing.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import List, Optional, Dict

import requests

from .models import Job, stable_job_id

logger = logging.getLogger(__name__)


def _load_json_from_file(path: Path) -> Dict:
    """Load JSON from a local file for offline testing.

    Args:
        path: Path to JSON file.

    Returns:
        Parsed JSON dictionary.
    """
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def fetch_greenhouse_jobs(
    board_token: str,
    company_name: str,
    json_path: Optional[Path] = None,
    timeout: int = 20,
    allow_remote: bool = True,
) -> List[Job]:
    """Fetch published jobs from a Greenhouse job board.

    If ``json_path`` is provided, the function will load the JSON from the
    specified file instead of performing a network request. This makes it
    easy to test the collector without internet access.

    Args:
        board_token: The Greenhouse board slug (e.g. "stripe", "airbnb").
        company_name: Human-friendly company name to store on each job.
        json_path: Optional path to a local JSON file containing the
            response structure returned by the Greenhouse API.
        timeout: Timeout in seconds for the HTTP request.
        allow_remote: Whether to attempt a remote call if ``json_path`` is
            not provided.

    Returns:
        A list of ``Job`` instances.
    """
    data: Dict
    if json_path is not None:
        data = _load_json_from_file(json_path)
    else:
        # Attempt remote fetch only if allowed. Requests may fail due to
        # environment restrictions; exceptions are logged and result in an
        # empty list.
        if not allow_remote:
            logger.warning(
                "Remote fetching disabled and no JSON file provided; returning empty list"
            )
            return []
        endpoint = f"https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs"
        try:
            # Include a generic User-Agent header to avoid some provider rate limits/403s
            headers = {"User-Agent": "Mozilla/5.0 (compatible; job-tracker/1.0)"}
            resp = requests.get(endpoint, headers=headers, timeout=timeout)
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            logger.error(
                "Failed to fetch Greenhouse jobs for board %s: %s", board_token, exc
            )
            return []

    jobs: List[Job] = []
    for j in data.get("jobs", []):
        title = (j.get("title") or "").strip()
        url = (j.get("absolute_url") or "").strip()
        location_dict = j.get("location") or {}
        location = (location_dict.get("name") or "").strip()
        # Determine remote flag from location keywords.
        remote_flag: Optional[bool] = None
        loc_lower = location.lower()
        if "remote" in loc_lower or "anywhere" in loc_lower:
            remote_flag = True
        elif location:
            remote_flag = False
        else:
            remote_flag = None

        if not url:
            continue
        job_id = stable_job_id(company_name, url)
        # Additional fields may be nested under custom fields; store all
        # key-value pairs except for location and title.
        # For simplicity, include departments and office names if present.
        extra = {}
        for key in ["departments", "offices", "metadata", "custom_fields"]:
            if key in j and j[key]:
                extra[key] = j[key]

        jobs.append(
            Job(
                job_id=job_id,
                company=company_name,
                title=title,
                location=location or "",
                url=url,
                source="greenhouse",
                remote=remote_flag,
                posted_at=None,
                extra=extra,
            )
        )
    return jobs


def fetch_ashby_jobs(
    board_name: str,
    company_name: str,
    json_path: Optional[Path] = None,
    timeout: int = 20,
    allow_remote: bool = True,
) -> List[Job]:
    """Fetch published jobs from an Ashby job board.

    Ashby exposes a simple Job Posting API at
    ``https://api.ashbyhq.com/posting-api/job-board/{JOB_BOARD_NAME}``. The
    endpoint returns a JSON payload with a top-level ``jobs`` array, where
    each entry contains fields such as ``title``, ``location``,
    ``secondaryLocations``, ``isRemote``, ``descriptionPlain`` and URLs
    ``jobUrl`` / ``applyUrl``. The board name is the slug used in the
    hosted Ashby careers site URL (e.g. ``jobs.ashbyhq.com/notion`` →
    ``notion``). The API is unauthenticated and documented in Ashby's
    developer docs【749797653657086†L61-L112】【749797653657086†L184-L189】.

    Args:
        board_name: The Ashby job board name (slug).
        company_name: Human-friendly company name.
        json_path: Optional path to a JSON file for offline testing.
        timeout: Request timeout in seconds.
        allow_remote: If False and ``json_path`` is None, returns empty list.

    Returns:
        List of ``Job`` objects.
    """
    data: Dict
    if json_path is not None:
        data = _load_json_from_file(json_path)
    else:
        if not allow_remote:
            logger.warning(
                "Remote fetching disabled and no JSON file provided; returning empty list"
            )
            return []
        endpoint = f"https://api.ashbyhq.com/posting-api/job-board/{board_name}"
        try:
            headers = {"User-Agent": "Mozilla/5.0 (compatible; job-tracker/1.0)"}
            resp = requests.get(endpoint, headers=headers, timeout=timeout)
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            logger.error(
                "Failed to fetch Ashby jobs for board %s: %s", board_name, exc
            )
            return []

    jobs: List[Job] = []
    for j in data.get("jobs", []):
        title = (j.get("title") or "").strip()
        # Combine location and secondary locations into a single string
        location = ""
        loc_obj = j.get("location")
        if loc_obj and isinstance(loc_obj, str):
            location = loc_obj.strip()
        elif loc_obj and isinstance(loc_obj, dict):
            # Ashby uses address object under location
            parts = [
                loc_obj.get("addressCountry"),
                loc_obj.get("addressRegion"),
                loc_obj.get("addressLocality"),
            ]
            location = ", ".join(filter(None, parts))
        # Append secondary locations if present
        sec_locs = j.get("secondaryLocations") or []
        if sec_locs:
            # Each entry is a dict like main location
            sec_strings = []
            for loc in sec_locs:
                if isinstance(loc, str):
                    sec_strings.append(loc.strip())
                elif isinstance(loc, dict):
                    parts = [
                        loc.get("addressCountry"),
                        loc.get("addressRegion"),
                        loc.get("addressLocality"),
                    ]
                        
                    sec_strings.append(", ".join(filter(None, parts)))
            if location:
                location += "; " + "; ".join(sec_strings)
            else:
                location = "; ".join(sec_strings)
        url = (j.get("jobUrl") or j.get("applyUrl") or "").strip()
        if not url:
            continue
        # Determine remote flag from isRemote boolean or location keywords
        remote_flag: Optional[bool] = None
        if isinstance(j.get("isRemote"), bool):
            remote_flag = j["isRemote"]
        else:
            loc_lower = location.lower()
            if any(word in loc_lower for word in ["remote", "anywhere"]):
                remote_flag = True
            elif location:
                remote_flag = False
        job_id = stable_job_id(company_name, url)
        extra = {
            "descriptionPlain": j.get("descriptionPlain"),
            "jobUrl": url,
            "applyUrl": j.get("applyUrl"),
        }
        jobs.append(
            Job(
                job_id=job_id,
                company=company_name,
                title=title,
                location=location or "",
                url=url,
                source="ashby",
                remote=remote_flag,
                posted_at=None,
                extra=extra,
            )
        )
    return jobs


def fetch_smartrecruiters_jobs(
    company_identifier: str,
    company_name: str,
    json_path: Optional[Path] = None,
    timeout: int = 20,
    allow_remote: bool = True,
) -> List[Job]:
    """Fetch published jobs from the SmartRecruiters Posting API.

    SmartRecruiters provides a public Posting API endpoint that lists active
    job postings for a company: ``/v1/companies/{companyIdentifier}/postings``.
    The response contains a ``content`` array of ``Posting`` objects. Each
    posting includes fields such as ``name`` (job title), ``location``,
    ``postingUrl``, ``applyUrl``, and nested objects for ``typeOfEmployment``,
    ``experienceLevel`` etc. An example ``Posting`` object shows these
    properties【697270942559925†L160-L218】. This function extracts the
    essentials and converts them into ``Job`` objects.

    Args:
        company_identifier: Slug/identifier used in the SmartRecruiters API
            (e.g. "smartrecruiters" or "databricks").
        company_name: Human friendly company name.
        json_path: Optional path to a JSON file containing a list of postings
            for offline testing.
        timeout: Request timeout in seconds.
        allow_remote: If False and no json_path is provided, returns empty list.

    Returns:
        List of ``Job`` objects.
    """
    data: Dict
    if json_path is not None:
        data = _load_json_from_file(json_path)
    else:
        if not allow_remote:
            logger.warning(
                "Remote fetching disabled and no JSON file provided; returning empty list"
            )
            return []
        endpoint = f"https://api.smartrecruiters.com/v1/companies/{company_identifier}/postings"
        try:
            headers = {"User-Agent": "Mozilla/5.0 (compatible; job-tracker/1.0)"}
            resp = requests.get(endpoint, headers=headers, timeout=timeout)
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            logger.error(
                "Failed to fetch SmartRecruiters jobs for company %s: %s",
                company_identifier,
                exc,
            )
            return []
    # The response may have 'content' field (for API returning ListResult) or
    # be a plain list of postings depending on SmartRecruiters API version.
    postings = data.get("content") if isinstance(data, dict) else data
    if postings is None:
        postings = []
    jobs: List[Job] = []
    for p in postings:
        # Title is called 'name'
        title = (p.get("name") or p.get("title") or "").strip()
        # Location details may be nested under 'location'
        loc_obj = p.get("location") or {}
        location_parts = []
        city = loc_obj.get("city") or loc_obj.get("addressLocality")
        region = loc_obj.get("region") or loc_obj.get("addressRegion")
        country = loc_obj.get("country") or loc_obj.get("addressCountry")
        if city:
            location_parts.append(city)
        if region:
            location_parts.append(region)
        if country:
            location_parts.append(country.upper() if isinstance(country, str) else country)
        location = ", ".join(location_parts)
        # Job URL: prefer postingUrl or applyUrl
        url = (
            p.get("postingUrl")
            or p.get("applyUrl")
            or p.get("ref")  # fallback to ref field
            or ""
        ).strip()
        if not url:
            continue
        # Determine remote flag from location or 'remote' boolean
        remote_flag: Optional[bool] = None
        if isinstance(loc_obj.get("remote"), bool):
            remote_flag = loc_obj["remote"]
        else:
            loc_lower = location.lower()
            if any(word in loc_lower for word in ["remote", "anywhere"]):
                remote_flag = True
            elif location:
                remote_flag = False
        job_id = stable_job_id(company_name, url)
        extra = {
            "typeOfEmployment": p.get("typeOfEmployment"),
            "experienceLevel": p.get("experienceLevel"),
            "industry": p.get("industry"),
            "department": p.get("department"),
            "function": p.get("function"),
            "postingUrl": url,
            "applyUrl": p.get("applyUrl"),
        }
        jobs.append(
            Job(
                job_id=job_id,
                company=company_name,
                title=title,
                location=location or "",
                url=url,
                source="smartrecruiters",
                remote=remote_flag,
                posted_at=None,
                extra=extra,
            )
        )
    return jobs


def fetch_lever_jobs(
    api_url: str,
    company_name: str,
    json_path: Optional[Path] = None,
    timeout: int = 20,
    allow_remote: bool = True,
) -> List[Job]:
    """Fetch published jobs from a Lever job site.

    Lever has a public endpoint that returns jobs in JSON format. The URL
    often looks like ``https://api.lever.co/v0/postings/{company}?mode=published``.
    See Lever's documentation for details.

    Args:
        api_url: Full URL to the Lever API for the company.
        company_name: Human-friendly company name.
        json_path: Optional path to a local JSON file for offline testing.
        timeout: Request timeout.
        allow_remote: If False and ``json_path`` is None, returns empty list.

    Returns:
        List of ``Job`` objects.
    """
    data: List[Dict]
    if json_path is not None:
        data = _load_json_from_file(json_path)
    else:
        if not allow_remote:
            logger.warning(
                "Remote fetching disabled and no JSON file provided; returning empty list"
            )
            return []
        try:
            headers = {"User-Agent": "Mozilla/5.0 (compatible; job-tracker/1.0)"}
            resp = requests.get(api_url, headers=headers, timeout=timeout)
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            logger.error(
                "Failed to fetch Lever jobs from %s: %s", api_url, exc
            )
            return []

    jobs: List[Job] = []
    for item in data:
        title = (item.get("text") or "").strip()
        # Lever returns a list of categories; location may be under categories.
        location = ""
        categories = item.get("categories") or {}
        if categories.get("location"):
            location = categories["location"].strip()
        url = (item.get("hostedUrl") or "").strip() or (item.get("applyUrl") or "").strip()
        if not url:
            continue
        job_id = stable_job_id(company_name, url)
        # Determine remote flag based on location.
        remote_flag: Optional[bool] = None
        loc_lower = location.lower()
        if "remote" in loc_lower or "anywhere" in loc_lower:
            remote_flag = True
        elif location:
            remote_flag = False
        else:
            remote_flag = None

        extra = {
            "categories": categories,
            "department": item.get("department"),
            "description": item.get("description"),
            "listedAt": item.get("listedAt"),
        }

        jobs.append(
            Job(
                job_id=job_id,
                company=company_name,
                title=title,
                location=location,
                url=url,
                source="lever",
                remote=remote_flag,
                posted_at=None,
                extra=extra,
            )
        )
    return jobs