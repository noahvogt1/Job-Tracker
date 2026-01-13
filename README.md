# Job Tracker (MVP)

Backend-only job tracker that:

1. Loads a company universe from `companies.yaml`
2. Collects jobs from supported ATS providers (Greenhouse, Lever, Ashby, SmartRecruiters)
3. Persists periodic **snapshots** into `live_jobs.db`
4. Produces diffs and a **new-grad** filtered report
5. Sends an email digest via SMTP

## What is "supported" right now

- `source: greenhouse` (board token/slug)
- `source: lever` (company slug)
- `source: ashby` (board name)
- `source: smartrecruiters` (company identifier)

Entries marked `source: custom` are kept in YAML but **skipped** by collection until a custom scraper exists.

## Quick start

### 1) Validate company config

```bash
python -m job_tracker.cli.validate_companies --file companies.yaml
```

### 2) Collect snapshots

Run once:

```bash
python run_live.py --once
```

Run continuously (6h interval by default):

```bash
python run_live.py
```

### 3) View diffs (new-grad focused)

```bash
python -m job_tracker.cli.report_new_grad --db-path live_jobs.db
python -m job_tracker.cli.report_new_grad --db-path live_jobs.db --since-hours 24
```

### 4) Email digest

Dry run (prints body):

```bash
python -m job_tracker.cli.email_digest --db live_jobs.db --dry-run
```

Send for real (set env vars first):

- `DIGEST_TO`
- `SMTP_HOST`
- `SMTP_PORT` (default 587)
- `SMTP_USER`
- `SMTP_PASS` (Gmail: use an app password)

```bash
python -m job_tracker.cli.email_digest --db live_jobs.db
```

## Production-safety features

- Per-company fetch failures no longer stop a run.
- Each scheduler iteration records a `runs` row and detailed `run_errors` rows.
- Snapshots are linked to the `run_id` (when available).

## Scheduling (recommended)

### Windows Task Scheduler

Create **two** tasks:

1) **Collect** (every 6–12 hours)

Action (Program/script):
- `python`

Arguments:
- `run_live.py --once --db live_jobs.db --companies companies.yaml`

Start in:
- your repo folder (where `run_live.py` lives)

2) **Digest** (daily, or after collection)

Action (Program/script):
- `python`

Arguments:
- `-m job_tracker.cli.email_digest --db live_jobs.db`

Set the SMTP environment variables in the task configuration.

## Notes

- Prefer explicit `slug:` for ATS-backed companies to avoid inference mistakes.
- Custom scrapers are the next expansion path (Workday is usually the biggest ROI).
