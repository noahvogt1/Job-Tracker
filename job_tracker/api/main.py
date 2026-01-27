"""
Main FastAPI application for the Job Tracker platform.

This module sets up the FastAPI app with CORS, static file serving,
and route registration.
"""

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pathlib import Path
import os

# Determine the project root directory
PROJECT_ROOT = Path(__file__).parent.parent.parent
WEB_DIR = PROJECT_ROOT / "web"

app = FastAPI(
    title="Job Tracker API",
    description="Comprehensive job management platform API",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc"
)

# CORS middleware - configure appropriately for production
# Configure CORS with safer defaults.
# In development we allow common local origins; in production we
# expect explicit origins via JOBTRACKER_ALLOWED_ORIGINS.
environment = os.getenv("JOBTRACKER_ENV", "development").lower()

if environment == "production":
    raw_origins = os.getenv("JOBTRACKER_ALLOWED_ORIGINS", "")
    allowed_origins = [
        origin.strip()
        for origin in raw_origins.split(",")
        if origin.strip()
    ]
    # Fallback to no wildcard in production; if nothing is configured we
    # still mount CORS but with an empty list so misconfiguration is obvious.
else:
    # Reasonable defaults for local development and preview tooling
    allowed_origins = [
        "http://localhost",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files (web UI) if web directory exists
if WEB_DIR.exists():
    static_dir = WEB_DIR / "static"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
    
    # Mount web directory to serve HTML files
    app.mount("/web", StaticFiles(directory=str(WEB_DIR), html=True), name="web")

# Import routes
from .routes import jobs, applications, auth, companies, analytics, notifications, settings, dashboard, searches, export, import_data, documents, templates, sharing, search, tags

@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "ok",
        "version": "1.0.0"
    }

@app.get("/api")
async def api_info():
    """API information endpoint."""
    return {
        "name": "Job Tracker API",
        "version": "1.0.0",
        "docs": "/api/docs",
        "health": "/api/health"
    }

# Serve HTML files from web directory
@app.get("/{filename}.html")
async def serve_html(filename: str):
    """Serve HTML files from the web directory."""
    html_file = WEB_DIR / f"{filename}.html"
    if html_file.exists() and html_file.is_file():
        return FileResponse(str(html_file))
    raise HTTPException(status_code=404, detail=f"Page {filename}.html not found")

# Root redirect to web UI or API info
@app.get("/")
async def root():
    """Root endpoint - serves web UI if available, otherwise API info."""
    web_index = WEB_DIR / "index.html"
    if web_index.exists():
        return FileResponse(str(web_index))
    return {
        "message": "Job Tracker API",
        "docs": "/api/docs",
        "health": "/api/health"
    }

# Include route modules
app.include_router(jobs.router)
app.include_router(applications.router)
app.include_router(auth.router)
app.include_router(companies.router)
app.include_router(analytics.router)
app.include_router(notifications.router)
app.include_router(settings.router)
app.include_router(dashboard.router)
app.include_router(searches.router)
app.include_router(export.router)
app.include_router(import_data.router)
app.include_router(documents.router)
app.include_router(templates.router)
app.include_router(sharing.router)
app.include_router(search.router)
app.include_router(tags.router)
