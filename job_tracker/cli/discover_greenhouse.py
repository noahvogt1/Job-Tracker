#!/usr/bin/env python3
"""
Discover Greenhouse company boards and add them to companies.yaml.

This script automatically discovers Greenhouse company boards by trying
common patterns and scraping known sources, then adds them to the
companies.yaml configuration file.

Usage:
    python -m job_tracker.cli.discover_greenhouse
    python -m job_tracker.cli.discover_greenhouse --max-boards 1000
    python -m job_tracker.cli.discover_greenhouse --dry-run
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from job_tracker.greenhouse_discovery import discover_and_add_to_yaml, discover_greenhouse_boards


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Discover Greenhouse company boards and add to companies.yaml"
    )
    parser.add_argument(
        "--yaml",
        default="companies.yaml",
        help="Path to companies.yaml file (default: companies.yaml)",
    )
    parser.add_argument(
        "--max-boards",
        type=int,
        default=500,
        help="Maximum number of boards to discover (default: 500)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Discover boards but don't write to YAML (just print results)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=10,
        help="Request timeout in seconds (default: 10)",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.5,
        help="Delay between requests in seconds (default: 0.5)",
    )
    
    args = parser.parse_args()
    
    yaml_path = Path(args.yaml)
    
    if not yaml_path.parent.exists():
        print(f"Error: Directory {yaml_path.parent} does not exist")
        sys.exit(1)
    
    print(f"Discovering Greenhouse company boards...")
    print(f"Max boards: {args.max_boards}")
    print(f"Timeout: {args.timeout}s, Delay: {args.delay}s")
    print()
    
    if args.dry_run:
        # Just discover and print
        discovered = discover_greenhouse_boards(
            max_boards=args.max_boards,
            timeout=args.timeout,
            polite_delay=args.delay,
        )
        print(f"\nDiscovered {len(discovered)} Greenhouse boards:")
        for comp in discovered[:50]:  # Show first 50
            print(f"  - {comp['name']} ({comp['slug']})")
        if len(discovered) > 50:
            print(f"  ... and {len(discovered) - 50} more")
    else:
        # Discover and add to YAML
        try:
            count = discover_and_add_to_yaml(
                str(yaml_path),
                max_boards=args.max_boards,
                merge_existing=True,
            )
            print(f"\nSuccessfully added {count} new Greenhouse companies to {yaml_path}")
            print(f"Run the job collector to fetch jobs from these companies.")
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    main()
