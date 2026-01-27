"""
Application templates API endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Body
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

from job_tracker.api.dependencies import get_db, require_auth
from job_tracker.db import Database

router = APIRouter(prefix="/api/templates", tags=["templates"])


class ApplicationTemplateCreate(BaseModel):
    name: str
    application_method: Optional[str] = None
    default_notes: Optional[str] = None
    url_pattern: Optional[str] = None
    resume_id: Optional[int] = None
    cover_letter_id: Optional[int] = None
    is_default: bool = False


class ApplicationTemplateUpdate(BaseModel):
    name: Optional[str] = None
    application_method: Optional[str] = None
    default_notes: Optional[str] = None
    url_pattern: Optional[str] = None
    resume_id: Optional[int] = None
    cover_letter_id: Optional[int] = None
    is_default: Optional[bool] = None


class ApplicationTemplateResponse(BaseModel):
    template_id: int
    user_id: int
    name: str
    application_method: Optional[str] = None
    default_notes: Optional[str] = None
    url_pattern: Optional[str] = None
    resume_id: Optional[int] = None
    cover_letter_id: Optional[int] = None
    is_default: bool
    created_at: datetime
    updated_at: datetime


@router.get("", response_model=List[ApplicationTemplateResponse])
async def list_templates(
    user_id: int = Depends(require_auth),
    db: Database = Depends(get_db)
):
    """List all application templates for the authenticated user."""
    cur = db.conn.cursor()
    rows = cur.execute(
        "SELECT * FROM application_templates WHERE user_id = ? ORDER BY is_default DESC, created_at DESC",
        (user_id,)
    ).fetchall()
    
    return [
        ApplicationTemplateResponse(
            template_id=row["template_id"],
            user_id=row["user_id"],
            name=row["name"],
            application_method=row["application_method"],
            default_notes=row["default_notes"],
            url_pattern=row["url_pattern"],
            resume_id=row["resume_id"],
            cover_letter_id=row["cover_letter_id"],
            is_default=bool(row["is_default"]),
            created_at=datetime.fromisoformat(row["created_at"]) if isinstance(row["created_at"], str) else row["created_at"],
            updated_at=datetime.fromisoformat(row["updated_at"]) if isinstance(row["updated_at"], str) else row["updated_at"]
        )
        for row in rows
    ]


@router.post("", response_model=ApplicationTemplateResponse, status_code=status.HTTP_201_CREATED)
async def create_template(
    template: ApplicationTemplateCreate = Body(...),
    user_id: int = Depends(require_auth),
    db: Database = Depends(get_db)
):
    """Create a new application template."""
    cur = db.conn.cursor()
    now = datetime.now()
    
    if template.is_default:
        cur.execute(
            "UPDATE application_templates SET is_default = 0 WHERE user_id = ?",
            (user_id,)
        )
    
    cur.execute(
        """
        INSERT INTO application_templates (
            user_id, name, application_method, default_notes, url_pattern,
            resume_id, cover_letter_id, is_default, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            user_id,
            template.name,
            template.application_method,
            template.default_notes,
            template.url_pattern,
            template.resume_id,
            template.cover_letter_id,
            1 if template.is_default else 0,
            now,
            now
        )
    )
    db.conn.commit()
    
    template_id = cur.lastrowid
    row = cur.execute("SELECT * FROM application_templates WHERE template_id = ?", (template_id,)).fetchone()
    
    return ApplicationTemplateResponse(
        template_id=row["template_id"],
        user_id=row["user_id"],
        name=row["name"],
        application_method=row["application_method"],
        default_notes=row["default_notes"],
        url_pattern=row["url_pattern"],
        resume_id=row["resume_id"],
        cover_letter_id=row["cover_letter_id"],
        is_default=bool(row["is_default"]),
        created_at=datetime.fromisoformat(row["created_at"]) if isinstance(row["created_at"], str) else row["created_at"],
        updated_at=datetime.fromisoformat(row["updated_at"]) if isinstance(row["updated_at"], str) else row["updated_at"]
    )


@router.put("/{template_id}", response_model=ApplicationTemplateResponse)
async def update_template(
    template_id: int,
    template: ApplicationTemplateUpdate = Body(...),
    user_id: int = Depends(require_auth),
    db: Database = Depends(get_db)
):
    """Update an application template."""
    cur = db.conn.cursor()
    
    existing = cur.execute(
        "SELECT template_id FROM application_templates WHERE template_id = ? AND user_id = ?",
        (template_id, user_id)
    ).fetchone()
    
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")
    
    if template.is_default:
        cur.execute(
            "UPDATE application_templates SET is_default = 0 WHERE user_id = ? AND template_id != ?",
            (user_id, template_id)
        )
    
    updates = []
    params = []
    
    if template.name is not None:
        updates.append("name = ?")
        params.append(template.name)
    if template.application_method is not None:
        updates.append("application_method = ?")
        params.append(template.application_method)
    if template.default_notes is not None:
        updates.append("default_notes = ?")
        params.append(template.default_notes)
    if template.url_pattern is not None:
        updates.append("url_pattern = ?")
        params.append(template.url_pattern)
    if template.resume_id is not None:
        updates.append("resume_id = ?")
        params.append(template.resume_id)
    if template.cover_letter_id is not None:
        updates.append("cover_letter_id = ?")
        params.append(template.cover_letter_id)
    if template.is_default is not None:
        updates.append("is_default = ?")
        params.append(1 if template.is_default else 0)
    
    if updates:
        updates.append("updated_at = ?")
        params.append(datetime.now())
        params.extend([template_id, user_id])
        
        cur.execute(
            f"UPDATE application_templates SET {', '.join(updates)} WHERE template_id = ? AND user_id = ?",
            params
        )
        db.conn.commit()
    
    row = cur.execute("SELECT * FROM application_templates WHERE template_id = ?", (template_id,)).fetchone()
    return ApplicationTemplateResponse(
        template_id=row["template_id"],
        user_id=row["user_id"],
        name=row["name"],
        application_method=row["application_method"],
        default_notes=row["default_notes"],
        url_pattern=row["url_pattern"],
        resume_id=row["resume_id"],
        cover_letter_id=row["cover_letter_id"],
        is_default=bool(row["is_default"]),
        created_at=datetime.fromisoformat(row["created_at"]) if isinstance(row["created_at"], str) else row["created_at"],
        updated_at=datetime.fromisoformat(row["updated_at"]) if isinstance(row["updated_at"], str) else row["updated_at"]
    )


@router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_template(
    template_id: int,
    user_id: int = Depends(require_auth),
    db: Database = Depends(get_db)
):
    """Delete an application template."""
    cur = db.conn.cursor()
    
    existing = cur.execute(
        "SELECT template_id FROM application_templates WHERE template_id = ? AND user_id = ?",
        (template_id, user_id)
    ).fetchone()
    
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")
    
    cur.execute("DELETE FROM application_templates WHERE template_id = ? AND user_id = ?", (template_id, user_id))
    db.conn.commit()
    return None


@router.get("/default", response_model=Optional[ApplicationTemplateResponse])
async def get_default_template(
    user_id: int = Depends(require_auth),
    db: Database = Depends(get_db)
):
    """Get the default application template for the user."""
    cur = db.conn.cursor()
    row = cur.execute(
        "SELECT * FROM application_templates WHERE user_id = ? AND is_default = 1 LIMIT 1",
        (user_id,)
    ).fetchone()
    
    if not row:
        return None
    
    return ApplicationTemplateResponse(
        template_id=row["template_id"],
        user_id=row["user_id"],
        name=row["name"],
        application_method=row["application_method"],
        default_notes=row["default_notes"],
        url_pattern=row["url_pattern"],
        resume_id=row["resume_id"],
        cover_letter_id=row["cover_letter_id"],
        is_default=bool(row["is_default"]),
        created_at=datetime.fromisoformat(row["created_at"]) if isinstance(row["created_at"], str) else row["created_at"],
        updated_at=datetime.fromisoformat(row["updated_at"]) if isinstance(row["updated_at"], str) else row["updated_at"]
    )
