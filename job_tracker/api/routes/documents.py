"""
Resume and Cover Letter management API endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Body, UploadFile, File
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

from job_tracker.api.dependencies import get_db, require_auth
from job_tracker.db import Database

router = APIRouter(prefix="/api/documents", tags=["documents"])


class ResumeCreate(BaseModel):
    name: str
    file_url: Optional[str] = None
    version: Optional[str] = None
    notes: Optional[str] = None
    is_default: bool = False


class ResumeUpdate(BaseModel):
    name: Optional[str] = None
    file_url: Optional[str] = None
    version: Optional[str] = None
    notes: Optional[str] = None
    is_default: Optional[bool] = None


class ResumeResponse(BaseModel):
    resume_id: int
    user_id: int
    name: str
    file_url: Optional[str] = None
    version: Optional[str] = None
    notes: Optional[str] = None
    is_default: bool
    created_at: datetime
    updated_at: datetime


class CoverLetterCreate(BaseModel):
    name: str
    content: Optional[str] = None
    file_url: Optional[str] = None
    version: Optional[str] = None
    notes: Optional[str] = None
    is_default: bool = False


class CoverLetterUpdate(BaseModel):
    name: Optional[str] = None
    content: Optional[str] = None
    file_url: Optional[str] = None
    version: Optional[str] = None
    notes: Optional[str] = None
    is_default: Optional[bool] = None


class CoverLetterResponse(BaseModel):
    cover_letter_id: int
    user_id: int
    name: str
    content: Optional[str] = None
    file_url: Optional[str] = None
    version: Optional[str] = None
    notes: Optional[str] = None
    is_default: bool
    created_at: datetime
    updated_at: datetime


@router.get("/resumes", response_model=List[ResumeResponse])
async def list_resumes(
    user_id: int = Depends(require_auth),
    db: Database = Depends(get_db)
):
    """List all resumes for the authenticated user."""
    cur = db.conn.cursor()
    rows = cur.execute(
        "SELECT * FROM resumes WHERE user_id = ? ORDER BY is_default DESC, created_at DESC",
        (user_id,)
    ).fetchall()
    
    return [
        ResumeResponse(
            resume_id=row["resume_id"],
            user_id=row["user_id"],
            name=row["name"],
            file_url=row["file_url"],
            version=row["version"],
            notes=row["notes"],
            is_default=bool(row["is_default"]),
            created_at=datetime.fromisoformat(row["created_at"]) if isinstance(row["created_at"], str) else row["created_at"],
            updated_at=datetime.fromisoformat(row["updated_at"]) if isinstance(row["updated_at"], str) else row["updated_at"]
        )
        for row in rows
    ]


@router.post("/resumes", response_model=ResumeResponse, status_code=status.HTTP_201_CREATED)
async def create_resume(
    resume: ResumeCreate = Body(...),
    user_id: int = Depends(require_auth),
    db: Database = Depends(get_db)
):
    """Create a new resume."""
    cur = db.conn.cursor()
    now = datetime.now()
    
    # If setting as default, unset other defaults
    if resume.is_default:
        cur.execute(
            "UPDATE resumes SET is_default = 0 WHERE user_id = ?",
            (user_id,)
        )
    
    cur.execute(
        """
        INSERT INTO resumes (user_id, name, file_url, version, notes, is_default, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            user_id,
            resume.name,
            resume.file_url,
            resume.version,
            resume.notes,
            1 if resume.is_default else 0,
            now,
            now
        )
    )
    db.conn.commit()
    
    resume_id = cur.lastrowid
    row = cur.execute("SELECT * FROM resumes WHERE resume_id = ?", (resume_id,)).fetchone()
    
    return ResumeResponse(
        resume_id=row["resume_id"],
        user_id=row["user_id"],
        name=row["name"],
        file_url=row["file_url"],
        version=row["version"],
        notes=row["notes"],
        is_default=bool(row["is_default"]),
        created_at=datetime.fromisoformat(row["created_at"]) if isinstance(row["created_at"], str) else row["created_at"],
        updated_at=datetime.fromisoformat(row["updated_at"]) if isinstance(row["updated_at"], str) else row["updated_at"]
    )


@router.put("/resumes/{resume_id}", response_model=ResumeResponse)
async def update_resume(
    resume_id: int,
    resume: ResumeUpdate = Body(...),
    user_id: int = Depends(require_auth),
    db: Database = Depends(get_db)
):
    """Update a resume."""
    cur = db.conn.cursor()
    
    # Verify ownership
    existing = cur.execute(
        "SELECT resume_id FROM resumes WHERE resume_id = ? AND user_id = ?",
        (resume_id, user_id)
    ).fetchone()
    
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resume not found")
    
    # If setting as default, unset other defaults
    if resume.is_default:
        cur.execute(
            "UPDATE resumes SET is_default = 0 WHERE user_id = ? AND resume_id != ?",
            (user_id, resume_id)
        )
    
    # Build update query
    updates = []
    params = []
    
    if resume.name is not None:
        updates.append("name = ?")
        params.append(resume.name)
    if resume.file_url is not None:
        updates.append("file_url = ?")
        params.append(resume.file_url)
    if resume.version is not None:
        updates.append("version = ?")
        params.append(resume.version)
    if resume.notes is not None:
        updates.append("notes = ?")
        params.append(resume.notes)
    if resume.is_default is not None:
        updates.append("is_default = ?")
        params.append(1 if resume.is_default else 0)
    
    if updates:
        updates.append("updated_at = ?")
        params.append(datetime.now())
        params.extend([resume_id, user_id])
        
        cur.execute(
            f"UPDATE resumes SET {', '.join(updates)} WHERE resume_id = ? AND user_id = ?",
            params
        )
        db.conn.commit()
    
    row = cur.execute("SELECT * FROM resumes WHERE resume_id = ?", (resume_id,)).fetchone()
    return ResumeResponse(
        resume_id=row["resume_id"],
        user_id=row["user_id"],
        name=row["name"],
        file_url=row["file_url"],
        version=row["version"],
        notes=row["notes"],
        is_default=bool(row["is_default"]),
        created_at=datetime.fromisoformat(row["created_at"]) if isinstance(row["created_at"], str) else row["created_at"],
        updated_at=datetime.fromisoformat(row["updated_at"]) if isinstance(row["updated_at"], str) else row["updated_at"]
    )


@router.delete("/resumes/{resume_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_resume(
    resume_id: int,
    user_id: int = Depends(require_auth),
    db: Database = Depends(get_db)
):
    """Delete a resume."""
    cur = db.conn.cursor()
    
    existing = cur.execute(
        "SELECT resume_id FROM resumes WHERE resume_id = ? AND user_id = ?",
        (resume_id, user_id)
    ).fetchone()
    
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resume not found")
    
    cur.execute("DELETE FROM resumes WHERE resume_id = ? AND user_id = ?", (resume_id, user_id))
    db.conn.commit()
    return None


@router.get("/cover-letters", response_model=List[CoverLetterResponse])
async def list_cover_letters(
    user_id: int = Depends(require_auth),
    db: Database = Depends(get_db)
):
    """List all cover letters for the authenticated user."""
    cur = db.conn.cursor()
    rows = cur.execute(
        "SELECT * FROM cover_letters WHERE user_id = ? ORDER BY is_default DESC, created_at DESC",
        (user_id,)
    ).fetchall()
    
    return [
        CoverLetterResponse(
            cover_letter_id=row["cover_letter_id"],
            user_id=row["user_id"],
            name=row["name"],
            content=row["content"],
            file_url=row["file_url"],
            version=row["version"],
            notes=row["notes"],
            is_default=bool(row["is_default"]),
            created_at=datetime.fromisoformat(row["created_at"]) if isinstance(row["created_at"], str) else row["created_at"],
            updated_at=datetime.fromisoformat(row["updated_at"]) if isinstance(row["updated_at"], str) else row["updated_at"]
        )
        for row in rows
    ]


@router.post("/cover-letters", response_model=CoverLetterResponse, status_code=status.HTTP_201_CREATED)
async def create_cover_letter(
    cover_letter: CoverLetterCreate = Body(...),
    user_id: int = Depends(require_auth),
    db: Database = Depends(get_db)
):
    """Create a new cover letter."""
    cur = db.conn.cursor()
    now = datetime.now()
    
    if cover_letter.is_default:
        cur.execute(
            "UPDATE cover_letters SET is_default = 0 WHERE user_id = ?",
            (user_id,)
        )
    
    cur.execute(
        """
        INSERT INTO cover_letters (user_id, name, content, file_url, version, notes, is_default, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            user_id,
            cover_letter.name,
            cover_letter.content,
            cover_letter.file_url,
            cover_letter.version,
            cover_letter.notes,
            1 if cover_letter.is_default else 0,
            now,
            now
        )
    )
    db.conn.commit()
    
    cover_letter_id = cur.lastrowid
    row = cur.execute("SELECT * FROM cover_letters WHERE cover_letter_id = ?", (cover_letter_id,)).fetchone()
    
    return CoverLetterResponse(
        cover_letter_id=row["cover_letter_id"],
        user_id=row["user_id"],
        name=row["name"],
        content=row["content"],
        file_url=row["file_url"],
        version=row["version"],
        notes=row["notes"],
        is_default=bool(row["is_default"]),
        created_at=datetime.fromisoformat(row["created_at"]) if isinstance(row["created_at"], str) else row["created_at"],
        updated_at=datetime.fromisoformat(row["updated_at"]) if isinstance(row["updated_at"], str) else row["updated_at"]
    )


@router.put("/cover-letters/{cover_letter_id}", response_model=CoverLetterResponse)
async def update_cover_letter(
    cover_letter_id: int,
    cover_letter: CoverLetterUpdate = Body(...),
    user_id: int = Depends(require_auth),
    db: Database = Depends(get_db)
):
    """Update a cover letter."""
    cur = db.conn.cursor()
    
    existing = cur.execute(
        "SELECT cover_letter_id FROM cover_letters WHERE cover_letter_id = ? AND user_id = ?",
        (cover_letter_id, user_id)
    ).fetchone()
    
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cover letter not found")
    
    if cover_letter.is_default:
        cur.execute(
            "UPDATE cover_letters SET is_default = 0 WHERE user_id = ? AND cover_letter_id != ?",
            (user_id, cover_letter_id)
        )
    
    updates = []
    params = []
    
    if cover_letter.name is not None:
        updates.append("name = ?")
        params.append(cover_letter.name)
    if cover_letter.content is not None:
        updates.append("content = ?")
        params.append(cover_letter.content)
    if cover_letter.file_url is not None:
        updates.append("file_url = ?")
        params.append(cover_letter.file_url)
    if cover_letter.version is not None:
        updates.append("version = ?")
        params.append(cover_letter.version)
    if cover_letter.notes is not None:
        updates.append("notes = ?")
        params.append(cover_letter.notes)
    if cover_letter.is_default is not None:
        updates.append("is_default = ?")
        params.append(1 if cover_letter.is_default else 0)
    
    if updates:
        updates.append("updated_at = ?")
        params.append(datetime.now())
        params.extend([cover_letter_id, user_id])
        
        cur.execute(
            f"UPDATE cover_letters SET {', '.join(updates)} WHERE cover_letter_id = ? AND user_id = ?",
            params
        )
        db.conn.commit()
    
    row = cur.execute("SELECT * FROM cover_letters WHERE cover_letter_id = ?", (cover_letter_id,)).fetchone()
    return CoverLetterResponse(
        cover_letter_id=row["cover_letter_id"],
        user_id=row["user_id"],
        name=row["name"],
        content=row["content"],
        file_url=row["file_url"],
        version=row["version"],
        notes=row["notes"],
        is_default=bool(row["is_default"]),
        created_at=datetime.fromisoformat(row["created_at"]) if isinstance(row["created_at"], str) else row["created_at"],
        updated_at=datetime.fromisoformat(row["updated_at"]) if isinstance(row["updated_at"], str) else row["updated_at"]
    )


@router.delete("/cover-letters/{cover_letter_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_cover_letter(
    cover_letter_id: int,
    user_id: int = Depends(require_auth),
    db: Database = Depends(get_db)
):
    """Delete a cover letter."""
    cur = db.conn.cursor()
    
    existing = cur.execute(
        "SELECT cover_letter_id FROM cover_letters WHERE cover_letter_id = ? AND user_id = ?",
        (cover_letter_id, user_id)
    ).fetchone()
    
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cover letter not found")
    
    cur.execute("DELETE FROM cover_letters WHERE cover_letter_id = ? AND user_id = ?", (cover_letter_id, user_id))
    db.conn.commit()
    return None
