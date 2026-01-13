"""
Data normalization utilities for the Job Tracker project.

This module contains helper functions to normalize job attributes.  It provides
two main functions:

* ``normalize_location`` – convert a raw location string into a structured
  object with country, region, city and remote/hybrid flags.
* ``canonicalize_url`` – strip tracking parameters and normalize URLs so
  duplicate postings across different sources can be identified.

The heuristics implemented here are deliberately simple to keep noise low.
You can refine them over time as you encounter more edge cases.
"""

from __future__ import annotations

import re
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode

STATE_ABBREVIATIONS = {
    "alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR",
    "california": "CA", "colorado": "CO", "connecticut": "CT",
    "delaware": "DE", "district of columbia": "DC", "florida": "FL",
    "georgia": "GA", "hawaii": "HI", "idaho": "ID", "illinois": "IL",
    "indiana": "IN", "iowa": "IA", "kansas": "KS", "kentucky": "KY",
    "louisiana": "LA", "maine": "ME", "maryland": "MD", "massachusetts": "MA",
    "michigan": "MI", "minnesota": "MN", "mississippi": "MS",
    "missouri": "MO", "montana": "MT", "nebraska": "NE", "nevada": "NV",
    "new hampshire": "NH", "new jersey": "NJ", "new mexico": "NM",
    "new york": "NY", "north carolina": "NC", "north dakota": "ND",
    "ohio": "OH", "oklahoma": "OK", "oregon": "OR", "pennsylvania": "PA",
    "rhode island": "RI", "south carolina": "SC", "south dakota": "SD",
    "tennessee": "TN", "texas": "TX", "utah": "UT", "vermont": "VT",
    "virginia": "VA", "washington": "WA", "west virginia": "WV",
    "wisconsin": "WI", "wyoming": "WY"
}

REMOTE_KEYWORDS = {"remote", "remotely", "wfh", "work from home", "anywhere"}


def normalize_location(raw: str) -> dict:
    """Normalize a raw location string.

    Args:
        raw: The location string exactly as scraped.

    Returns:
        A dictionary with the following keys:
        - raw: original string
        - country: guessed country code (default "US")
        - region: two‑letter state code or None
        - city: city name or None
        - is_remote: True if the job is remote
        - is_hybrid: True if the job is hybrid (remote + onsite)
    """
    if raw is None:
        return {
            "raw": None,
            "country": None,
            "region": None,
            "city": None,
            "is_remote": False,
            "is_hybrid": False,
        }
    text = raw.strip().lower()
    is_remote = any(keyword in text for keyword in REMOTE_KEYWORDS)
    # Hybrid detection: contains both remote and a city/state
    is_hybrid = is_remote and any(
        state in text for state in STATE_ABBREVIATIONS.keys()
    )

    country = "US"
    region = None
    city = None

    # Try to parse "City, State" patterns
    parts = [p.strip() for p in re.split(r",|/|\|", text) if p.strip()]
    if parts:
        # Find a state name or abbreviation in parts
        for part in parts:
            part_lower = part.lower()
            if part_lower in STATE_ABBREVIATIONS.values():
                region = part_lower.upper()
                break
            elif part_lower in STATE_ABBREVIATIONS:
                region = STATE_ABBREVIATIONS[part_lower]
                break
        # City is typically the first part if we found a region
        if region and parts[0].lower() != region.lower():
            city_part = parts[0]
            # Capitalize each word in city
            city = " ".join(w.capitalize() for w in city_part.split())

    return {
        "raw": raw,
        "country": country,
        "region": region,
        "city": city,
        "is_remote": is_remote,
        "is_hybrid": is_hybrid,
    }


def canonicalize_url(url: str) -> str:
    """Canonicalize a job URL.

    Removes tracking parameters and normalizes the scheme and hostname.  If the
    URL is malformed, returns it unchanged.

    Args:
        url: The original URL as scraped.

    Returns:
        A canonical URL string.
    """
    if not url:
        return url
    try:
        parsed = urlparse(url)
    except Exception:
        return url

    # Lowercase scheme and hostname
    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.lower()

    # Remove trailing slash from path
    path = parsed.path.rstrip('/')

    # Filter query parameters: drop tracking keys
    tracking_keys = {
        "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
        "ref", "referrer", "gh_src", "gh_jid", "source", "src"
    }
    query_params = parse_qsl(parsed.query, keep_blank_values=True)
    cleaned_params = [(k, v) for k, v in query_params if k.lower() not in tracking_keys]
    query = urlencode(cleaned_params)

    # Reconstruct the URL
    canonical = urlunparse((scheme, netloc, path, '', query, ''))
    return canonical