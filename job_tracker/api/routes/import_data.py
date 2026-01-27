"""
Import API endpoints for CSV import of applications.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Body, UploadFile, File
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from datetime import datetime
import csv
import io
import json

from job_tracker.api.dependencies import get_db, require_auth
from job_tracker.db import Database

router = APIRouter(prefix="/api/import", tags=["import"])


class ColumnMapping(BaseModel):
    """Schema for CSV column mapping."""
    csv_column: str
    field: str  # 'job_title', 'company', 'status', 'applied_at', 'notes', etc.


class ImportRequest(BaseModel):
    """Schema for import request with column mappings."""
    mappings: List[ColumnMapping]
    skip_header: bool = True


@router.post("/applications/csv")
async def import_applications_csv(
    file: UploadFile = File(...),
    mappings: str = Body(...),  # JSON string of mappings
    user_id: int = Depends(require_auth),
    db: Database = Depends(get_db)
):
    """
    Import applications from CSV file.
    
    Requires a column mapping JSON string that maps CSV columns to application fields.
    """
    try:
        # Parse mappings
        mapping_data = json.loads(mappings)
        column_map = {m['csv_column']: m['field'] for m in mapping_data.get('mappings', [])}
        
        # Read CSV file
        contents = await file.read()
        csv_text = contents.decode('utf-8')
        csv_reader = csv.DictReader(io.StringIO(csv_text))
        
        imported = 0
        errors = []
        
        for row_num, row in enumerate(csv_reader, start=2):  # Start at 2 (row 1 is header)
            try:
                # Map CSV columns to application fields
                app_data = {}
                
                # Required: job_title and company (to find job_id)
                job_title = None
                company_name = None
                
                for csv_col, field in column_map.items():
                    if csv_col in row and row[csv_col]:
                        value = row[csv_col].strip()
                        
                        if field == 'job_title':
                            job_title = value
                        elif field == 'company':
                            company_name = value
                        elif field == 'status':
                            app_data['status'] = value.lower()
                        elif field == 'applied_at':
                            # Try to parse date
                            try:
                                app_data['applied_at'] = datetime.fromisoformat(value.replace('Z', '+00:00'))
                            except:
                                # Try other formats
                                try:
                                    app_data['applied_at'] = datetime.strptime(value, '%Y-%m-%d')
                                except:
                                    app_data['applied_at'] = None
                        elif field == 'application_method':
                            app_data['application_method'] = value
                        elif field == 'application_url':
                            app_data['application_url'] = value
                        elif field == 'notes':
                            app_data['notes'] = value
                        elif field == 'priority':
                            try:
                                app_data['priority'] = int(value)
                            except:
                                app_data['priority'] = 0
                
                if not job_title or not company_name:
                    errors.append(f"Row {row_num}: Missing job_title or company")
                    continue
                
                # Find job_id by title and company
                cur = db.conn.cursor()
                job_query = """
                    SELECT j.job_id
                    FROM jobs j
                    JOIN companies c ON j.company_id = c.id
                    JOIN job_versions v ON v.job_id = j.job_id
                    JOIN (
                        SELECT job_id, MAX(timestamp) AS max_ts
                        FROM job_versions
                        GROUP BY job_id
                    ) latest ON latest.job_id = v.job_id AND latest.max_ts = v.timestamp
                    WHERE LOWER(c.name) = LOWER(?) AND LOWER(v.title) = LOWER(?)
                    LIMIT 1
                """
                job_row = cur.execute(job_query, (company_name, job_title)).fetchone()
                
                if not job_row:
                    errors.append(f"Row {row_num}: Job not found: {company_name} - {job_title}")
                    continue
                
                job_id = job_row['job_id']
                
                # Check if application already exists
                existing = cur.execute(
                    "SELECT application_id FROM applications WHERE user_id = ? AND job_id = ?",
                    (user_id, job_id)
                ).fetchone()
                
                if existing:
                    # Update existing application
                    update_fields = []
                    update_params = []
                    
                    if 'status' in app_data:
                        update_fields.append("status = ?")
                        update_params.append(app_data['status'])
                    if 'applied_at' in app_data and app_data['applied_at']:
                        update_fields.append("applied_at = ?")
                        update_params.append(app_data['applied_at'])
                    if 'application_method' in app_data:
                        update_fields.append("application_method = ?")
                        update_params.append(app_data['application_method'])
                    if 'application_url' in app_data:
                        update_fields.append("application_url = ?")
                        update_params.append(app_data['application_url'])
                    if 'notes' in app_data:
                        update_fields.append("notes = ?")
                        update_params.append(app_data['notes'])
                    if 'priority' in app_data:
                        update_fields.append("priority = ?")
                        update_params.append(app_data['priority'])
                    
                    if update_fields:
                        update_fields.append("updated_at = ?")
                        update_params.append(datetime.now())
                        update_params.append(existing['application_id'])
                        
                        cur.execute(
                            f"UPDATE applications SET {', '.join(update_fields)} WHERE application_id = ?",
                            update_params
                        )
                else:
                    # Create new application
                    cur.execute(
                        """
                        INSERT INTO applications (
                            user_id, job_id, status, applied_at, application_method,
                            application_url, notes, priority, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            user_id,
                            job_id,
                            app_data.get('status', 'applied'),
                            app_data.get('applied_at'),
                            app_data.get('application_method'),
                            app_data.get('application_url'),
                            app_data.get('notes'),
                            app_data.get('priority', 0),
                            datetime.now(),
                            datetime.now()
                        )
                    )
                
                imported += 1
                
            except Exception as e:
                errors.append(f"Row {row_num}: {str(e)}")
        
        db.conn.commit()
        
        return {
            "imported": imported,
            "errors": errors[:10],  # Limit errors returned
            "total_errors": len(errors)
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Import failed: {str(e)}"
        )


@router.post("/applications/preview")
async def preview_csv_import(
    file: UploadFile = File(...),
    user_id: int = Depends(require_auth),
    db: Database = Depends(get_db)
):
    """
    Preview CSV file and return first few rows with column names.
    Helps users map columns before importing.
    """
    try:
        contents = await file.read()
        csv_text = contents.decode('utf-8')
        csv_reader = csv.DictReader(io.StringIO(csv_text))
        
        # Get first 5 rows
        preview_rows = []
        for i, row in enumerate(csv_reader):
            if i >= 5:
                break
            preview_rows.append(row)
        
        # Get column names
        columns = list(preview_rows[0].keys()) if preview_rows else []
        
        return {
            "columns": columns,
            "preview": preview_rows,
            "row_count": len(preview_rows)
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to preview CSV: {str(e)}"
        )
