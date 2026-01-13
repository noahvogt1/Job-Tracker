#!/usr/bin/env python3
"""
Validate company definitions in ``companies.yaml``.

Supports YAML shaped like:

version: 1
defaults:
  enabled: true
companies:
  - name: ...
    source: ...
    endpoint: ...

This script loads the YAML, checks each enabled entry has a reachable endpoint,
and verifies that the URL roughly matches the declared ATS source.
Exits non-zero if any checks fail.

Usage::

    python validate_companies.py --file companies.yaml
"""

from __future__ import annotations

import argparse
import sys
from urllib.parse import urlparse

import requests
import yaml


def load_companies(path: str) -> tuple[list[dict], dict]:
    """
    Returns (companies, defaults)

    Accepts:
      - top-level dict with 'companies' list (recommended)
      - top-level list of company dicts (legacy)
    """
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    # Recommended shape: dict with companies + defaults
    if isinstance(data, dict):
        defaults = data.get("defaults") or {}
        companies = data.get("companies") or []
        if not isinstance(companies, list):
            raise ValueError("Expected 'companies:' to be a YAML list.")
        if not isinstance(defaults, dict):
            defaults = {}
        return companies, defaults

    # Legacy: list at top-level
    if isinstance(data, list):
        return data, {}

    raise ValueError(f"Unsupported YAML structure: {type(data).__name__}")


def check_url_reachable(url: str, timeout: int = 10) -> bool:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    }

    try:
        resp = requests.head(url, allow_redirects=True, timeout=timeout, headers=headers)
        if resp.status_code >= 400:
            resp = requests.get(url, allow_redirects=True, timeout=timeout, headers=headers)

        # Consider "blocked but alive" as reachable
        if resp.status_code in (401, 403):
            return True

        return resp.status_code < 400
    except Exception:
        return False



def matches_source(url: str, source: str) -> bool:
    host = urlparse(url).netloc.lower()
    source = (source or "custom").lower()

    if source == "lever":
        return "lever.co" in host
    if source == "greenhouse":
        return "greenhouse.io" in host
    if source == "workday":
        return ("myworkdayjobs" in host) or ("workday" in host)
    # For custom or other sources we don't enforce
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate companies.yaml")
    parser.add_argument("--file", default="companies.yaml", help="Path to YAML file")
    parser.add_argument("--timeout", type=int, default=10, help="Timeout in seconds for HTTP requests")
    args = parser.parse_args()

    try:
        companies, defaults = load_companies(args.file)
    except Exception as e:
        print(f"Failed to load companies: {e}")
        sys.exit(2)

    default_enabled = bool(defaults.get("enabled", True))

    failures: list[tuple[str, str]] = []
    enabled_count = 0

    for entry in companies:
        if not isinstance(entry, dict):
            failures.append(("<unknown>", f"non-dict company entry: {entry!r}"))
            continue

        enabled = bool(entry.get("enabled", default_enabled))
        if not enabled:
            continue
        enabled_count += 1

        name = entry.get("name") or "<unknown>"
        source = (entry.get("source") or "custom").lower()
        endpoint = entry.get("endpoint")

        if not endpoint:
            failures.append((name, "missing endpoint"))
            continue

        reachable = check_url_reachable(endpoint, timeout=args.timeout)
        if not reachable:
            failures.append((name, f"endpoint unreachable: {endpoint}"))
            continue

        if not matches_source(endpoint, source):
            failures.append((name, f"endpoint does not match source '{source}': {endpoint}"))

    if failures:
        print("Validation failures:")
        for name, reason in failures:
            print(f"- {name}: {reason}")
        sys.exit(1)

    print(f"All {enabled_count} enabled companies validated successfully.")


if __name__ == "__main__":
    main()
