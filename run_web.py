#!/usr/bin/env python3
"""
Run the job tracker web application.

This script starts the FastAPI server with uvicorn, serving both the API
and the web UI.

Usage:
    python run_web.py
    python run_web.py --port 8000
    python run_web.py --db live_jobs.db
    python run_web.py --host 0.0.0.0 --port 8000
    python run_web.py --reload  # Enable auto-reload for development
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

try:
    import uvicorn
except ImportError:
    print("Error: uvicorn is not installed. Please install dependencies:")
    print("  pip install -r requirements.txt")
    sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run Job Tracker Web Application",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_web.py
  python run_web.py --port 8000
  python run_web.py --db live_jobs.db
  python run_web.py --host 0.0.0.0 --port 8000
  python run_web.py --reload
        """
    )
    
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to run on (default: 8000)"
    )
    
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host to bind to (default: 127.0.0.1)"
    )
    
    parser.add_argument(
        "--db",
        default="live_jobs.db",
        help="Database path (default: live_jobs.db)"
    )
    
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload for development (watch for file changes)"
    )
    
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Number of worker processes (default: 1)"
    )
    
    args = parser.parse_args()
    
    # Set environment variable for database path
    os.environ["DB_PATH"] = str(Path(args.db).absolute())
    
    # Verify database exists (or will be created on first connection)
    db_path = Path(args.db)
    if not db_path.exists() and not db_path.parent.exists():
        print(f"Warning: Database directory does not exist: {db_path.parent}")
        print("The database will be created on first connection.")
    
    print("=" * 60)
    print("Job Tracker Web Application")
    print("=" * 60)
    print(f"Database: {db_path.absolute()}")
    print(f"Server: http://{args.host}:{args.port}")
    print(f"API Docs: http://{args.host}:{args.port}/api/docs")
    print(f"Reload: {'Enabled' if args.reload else 'Disabled'}")
    print("=" * 60)
    print()
    
    try:
        uvicorn.run(
            "job_tracker.api.main:app",
            host=args.host,
            port=args.port,
            reload=args.reload,
            workers=args.workers if not args.reload else 1,  # Reload doesn't work with multiple workers
            log_level="info"
        )
    except KeyboardInterrupt:
        print("\nShutting down server...")
    except Exception as e:
        print(f"Error starting server: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
