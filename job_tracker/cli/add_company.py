#!/usr/bin/env python3
"""
Add a new company entry to ``companies.yaml``.

This script appends a new company to the YAML configuration without
introducing duplicates.  You can supply required fields via command‑line
arguments or interactively when running the script.  It preserves existing
entries and formatting by using PyYAML for parsing and dumping.

Usage examples::

    python add_company.py --file companies.yaml --name Stripe --source greenhouse --endpoint https://boards.greenhouse.io/stripe

    python add_company.py  # prompts for missing fields

Optional arguments include ``--tags`` (comma‑separated) and ``--disable`` to
add the company as disabled.
"""

from __future__ import annotations

import argparse
import os
import sys
import yaml


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Append a company to companies.yaml")
    parser.add_argument("--file", default="companies.yaml", help="Path to YAML file")
    parser.add_argument("--name", help="Company name")
    parser.add_argument("--source", choices=["lever", "greenhouse", "workday", "custom"],
                        help="ATS source (lever, greenhouse, workday, custom)")
    parser.add_argument("--endpoint", help="URL of the careers page or API endpoint")
    parser.add_argument("--tags", help="Comma‑separated tags (optional)")
    parser.add_argument("--disable", action="store_true", help="Add company as disabled")
    return parser.parse_args()


def load_companies(path: str) -> list:
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
        return data or []


def save_companies(path: str, companies: list) -> None:
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(companies, f, sort_keys=False)


def prompt_if_missing(args: argparse.Namespace, attr: str, prompt_text: str) -> str:
    value = getattr(args, attr)
    if value:
        return value
    try:
        return input(f"{prompt_text}: ").strip()
    except EOFError:
        return ""


def main() -> None:
    args = parse_args()
    companies = load_companies(args.file)
    # Prompt for missing fields interactively
    name = prompt_if_missing(args, "name", "Company name")
    source = prompt_if_missing(args, "source", "ATS source (lever/greenhouse/workday/custom)")
    endpoint = prompt_if_missing(args, "endpoint", "Endpoint URL")
    tags_str = args.tags
    tags = [t.strip() for t in tags_str.split(",") if t.strip()] if tags_str else []
    enabled = not args.disable
    if not name or not source or not endpoint:
        print("Name, source and endpoint are required.")
        sys.exit(1)
    # Normalize name
    norm_name = " ".join(word.capitalize() for word in name.split())
    # Check duplicates
    for comp in companies:
        if comp.get("name", "").strip().lower() == norm_name.strip().lower():
            print(f"Company with name '{norm_name}' already exists. Aborting.")
            sys.exit(1)
        if comp.get("endpoint", "").strip().lower() == endpoint.strip().lower():
            print(f"Company with endpoint '{endpoint}' already exists. Aborting.")
            sys.exit(1)
    new_entry = {
        "name": norm_name,
        "source": source.lower(),
        "endpoint": endpoint,
    }
    if tags:
        new_entry["tags"] = tags
    if not enabled:
        new_entry["enabled"] = False
    companies.append(new_entry)
    save_companies(args.file, companies)
    print(f"Added {norm_name} to {args.file} (enabled={enabled}).")


if __name__ == "__main__":
    main()