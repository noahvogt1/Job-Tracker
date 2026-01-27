"""
Greenhouse company board discovery module.

This module provides functionality to automatically discover Greenhouse company
boards by trying common patterns, scraping known sources, and validating
board tokens.
"""

from __future__ import annotations

import logging
import re
import time
from typing import List, Dict, Set, Optional, Tuple
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from .fetchers import fetch_greenhouse_jobs

logger = logging.getLogger(__name__)


def discover_greenhouse_boards(
    max_boards: int = 500,
    timeout: int = 10,
    polite_delay: float = 0.5,
    known_companies: Optional[List[str]] = None,
) -> List[Dict[str, str]]:
    """Discover Greenhouse company boards automatically.
    
    This function attempts to discover Greenhouse boards through multiple methods:
    1. Try common company name patterns
    2. Scrape known job board aggregators
    3. Validate discovered boards
    
    Args:
        max_boards: Maximum number of boards to discover
        timeout: Request timeout in seconds
        polite_delay: Delay between requests in seconds
        known_companies: Optional list of known company names to try
        
    Returns:
        List of dictionaries with 'slug', 'name', and 'url' keys
    """
    discovered: List[Dict[str, str]] = []
    seen_slugs: Set[str] = set()
    
    # Method 1: Try common company name patterns
    logger.info("Discovering Greenhouse boards via common patterns...")
    common_companies = known_companies or _get_common_company_names()
    pattern_discovered = _discover_via_patterns(common_companies, seen_slugs, timeout, polite_delay)
    discovered.extend(pattern_discovered)
    logger.info(f"Found {len(pattern_discovered)} boards via patterns")
    
    # Method 2: Scrape known sources
    logger.info("Discovering Greenhouse boards via web scraping...")
    scraped_discovered = _discover_via_scraping(seen_slugs, max_boards - len(discovered), timeout, polite_delay)
    discovered.extend(scraped_discovered)
    logger.info(f"Found {len(scraped_discovered)} boards via scraping")
    
    return discovered[:max_boards]


def _get_common_company_names() -> List[str]:
    """Get a list of common company names to try."""
    return [
        # Tech companies
        "stripe", "airbnb", "uber", "lyft", "doordash", "instacart",
        "coinbase", "robinhood", "plaid", "square", "shopify",
        "databricks", "snowflake", "mongodb", "elastic", "confluent",
        "palantir", "databricks", "snowflake", "datadog", "newrelic",
        "twilio", "sendgrid", "mailchimp", "hubspot", "salesforce",
        "atlassian", "slack", "zoom", "dropbox", "box",
        "reddit", "pinterest", "snapchat", "tiktok", "discord",
        "netflix", "spotify", "hulu", "disney", "warner",
        "nvidia", "amd", "intel", "qualcomm", "broadcom",
        # Finance
        "janestreet", "citadel", "twosigma", "hrt", "imc", "optiver",
        "jump", "drw", "sig", "akuna", "flow",
        # Startups
        "figma", "notion", "linear", "vercel", "vercel",
        "anthropic", "openai", "cohere", "stability", "huggingface",
        "anthropic", "openai", "cohere", "stability", "huggingface",
        # Add more common names
        "github", "gitlab", "bitbucket", "circleci", "travis",
        "docker", "kubernetes", "terraform", "ansible", "chef",
    ]


def _discover_via_patterns(
    company_names: List[str],
    seen_slugs: Set[str],
    timeout: int,
    delay: float,
) -> List[Dict[str, str]]:
    """Try common company name patterns to find Greenhouse boards."""
    discovered = []
    headers = {"User-Agent": "Mozilla/5.0 (compatible; job-tracker/1.0)"}
    
    for name in company_names:
        if len(discovered) >= 200:  # Limit per method
            break
            
        # Try variations of the company name
        slugs_to_try = [
            name.lower().replace(" ", ""),
            name.lower().replace(" ", "-"),
            name.lower().replace(" ", "_"),
            name.lower(),
        ]
        
        for slug in slugs_to_try:
            if slug in seen_slugs:
                continue
                
            # Validate board exists
            if _validate_greenhouse_board(slug, timeout, headers):
                seen_slugs.add(slug)
                discovered.append({
                    "slug": slug,
                    "name": name.title(),
                    "url": f"https://boards.greenhouse.io/{slug}",
                })
                logger.debug(f"Discovered Greenhouse board: {slug}")
            
            time.sleep(delay)
    
    return discovered


def _discover_via_scraping(
    seen_slugs: Set[str],
    max_count: int,
    timeout: int,
    delay: float,
) -> List[Dict[str, str]]:
    """Scrape known sources to find Greenhouse board links."""
    discovered = []
    headers = {"User-Agent": "Mozilla/5.0 (compatible; job-tracker/1.0)"}
    
    # Sources that might link to Greenhouse boards
    sources = [
        "https://www.greenhouse.io/customers",
        "https://www.greenhouse.io/case-studies",
    ]
    
    for source_url in sources:
        if len(discovered) >= max_count:
            break
            
        try:
            resp = requests.get(source_url, headers=headers, timeout=timeout)
            resp.raise_for_status()
            
            soup = BeautifulSoup(resp.text, "html.parser")
            
            # Find all links to boards.greenhouse.io
            for link in soup.find_all("a", href=True):
                href = link.get("href", "")
                if "boards.greenhouse.io" in href:
                    # Extract slug from URL
                    match = re.search(r"boards\.greenhouse\.io/([^/?#]+)", href)
                    if match:
                        slug = match.group(1).lower()
                        if slug not in seen_slugs and _validate_greenhouse_board(slug, timeout, headers):
                            seen_slugs.add(slug)
                            company_name = link.text.strip() or slug.title()
                            discovered.append({
                                "slug": slug,
                                "name": company_name,
                                "url": f"https://boards.greenhouse.io/{slug}",
                            })
                            logger.debug(f"Discovered Greenhouse board via scraping: {slug}")
            
            time.sleep(delay)
        except Exception as e:
            logger.warning(f"Failed to scrape {source_url}: {e}")
            continue
    
    return discovered


def _validate_greenhouse_board(slug: str, timeout: int, headers: Dict[str, str]) -> bool:
    """Validate that a Greenhouse board exists and has jobs."""
    try:
        # Try the API endpoint
        api_url = f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs"
        resp = requests.get(api_url, headers=headers, timeout=timeout)
        
        if resp.status_code == 200:
            data = resp.json()
            # Check if board has jobs
            if data.get("jobs"):
                return True
        
        return False
    except Exception:
        return False


def discover_and_add_to_yaml(
    yaml_path: str,
    max_boards: int = 500,
    merge_existing: bool = True,
) -> int:
    """Discover Greenhouse boards and add them to companies.yaml.
    
    Args:
        yaml_path: Path to companies.yaml file
        max_boards: Maximum number of boards to discover
        merge_existing: If True, merge with existing entries
        
    Returns:
        Number of new companies added
    """
    import yaml
    from pathlib import Path
    
    yaml_file = Path(yaml_path)
    
    # Load existing companies
    existing_slugs = set()
    existing_companies = []
    
    if yaml_file.exists() and merge_existing:
        with yaml_file.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
            existing_companies = data.get("companies", [])
            for comp in existing_companies:
                if isinstance(comp, dict) and comp.get("source") == "greenhouse":
                    slug = comp.get("slug") or _extract_slug_from_endpoint(comp.get("endpoint", ""))
                    if slug:
                        existing_slugs.add(slug)
    
    # Discover new boards
    discovered = discover_greenhouse_boards(max_boards=max_boards)
    
    # Filter out existing
    new_companies = [
        comp for comp in discovered
        if comp["slug"] not in existing_slugs
    ]
    
    # Add to YAML
    for comp in new_companies:
        existing_companies.append({
            "name": comp["name"],
            "source": "greenhouse",
            "endpoint": comp["url"],
            "slug": comp["slug"],
            "enabled": True,
        })
    
    # Write back
    data = {
        "version": 1,
        "defaults": {
            "enabled": True,
            "track_new_grad": True,
        },
        "companies": existing_companies,
    }
    
    with yaml_file.open("w", encoding="utf-8") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
    
    return len(new_companies)


def _extract_slug_from_endpoint(endpoint: str) -> Optional[str]:
    """Extract slug from Greenhouse endpoint URL."""
    if not endpoint:
        return None
    match = re.search(r"boards\.greenhouse\.io/([^/?#]+)", endpoint)
    return match.group(1).lower() if match else None
