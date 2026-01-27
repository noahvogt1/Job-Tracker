"""
Pydantic schemas for API request/response models.

These schemas define the structure of data sent to and received from
the API endpoints, providing validation and serialization.
"""

from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Optional, List, Dict, Any
from datetime import datetime, date


# ============================================================================
# User Schemas
# ============================================================================

class UserCreate(BaseModel):
    """Schema for creating a new user."""
    username: str = Field(..., min_length=3, max_length=50, pattern="^[a-zA-Z0-9_]+$")
    email: Optional[EmailStr] = None
    password: str = Field(..., min_length=8, max_length=72)  # Bcrypt has 72-byte limit


class UserLogin(BaseModel):
    """Schema for user login."""
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=1)
    remember_me: bool = False


class UserResponse(BaseModel):
    """Schema for user information in responses."""
    user_id: int
    username: str
    email: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class UserProfile(BaseModel):
    """Schema for user profile information."""
    full_name: Optional[str] = None
    degree_type: Optional[str] = None
    graduation_year: Optional[int] = None
    skills: Optional[List[str]] = None
    location_preference: Optional[str] = None
    remote_preference: Optional[int] = None  # 0 = no, 1 = yes, 2 = flexible
    target_sectors: Optional[List[str]] = None


class UserProfileResponse(UserProfile):
    """Schema for user profile response."""
    profile_id: int
    user_id: int
    resume_url: Optional[str] = None
    notes: Optional[str] = None


# ============================================================================
# Job Schemas
# ============================================================================

class JobFilter(BaseModel):
    """Schema for filtering job searches."""
    location: Optional[str] = None
    remote: Optional[bool] = None
    company: Optional[List[int]] = None
    sector: Optional[List[str]] = None
    department: Optional[str] = None
    experience_level: Optional[str] = None
    keywords: Optional[str] = None
    new_grad: Optional[bool] = None
    posted_since: Optional[date] = None


class JobResponse(BaseModel):
    """Schema for job information in responses."""
    job_id: str
    company: str
    company_id: int
    title: str
    location: str
    remote: Optional[bool]
    url: str
    source: str
    sector: Optional[str]
    posted_at: Optional[datetime]
    is_new_grad: bool


class JobDetailResponse(JobResponse):
    """Extended job information with additional details."""
    extra: Optional[Dict[str, Any]] = None
    description: Optional[str] = None


# ============================================================================
# Application Schemas
# ============================================================================

class ApplicationCreate(BaseModel):
    """Schema for creating a new application."""
    job_id: str
    status: str = "applied"
    application_method: Optional[str] = None
    application_url: Optional[str] = None
    notes: Optional[str] = None
    tags: Optional[List[str]] = None
    priority: int = 0


class ApplicationUpdate(BaseModel):
    """Schema for updating an application."""
    status: Optional[str] = None
    notes: Optional[str] = None
    priority: Optional[int] = None
    tags: Optional[List[str]] = None


class ApplicationResponse(BaseModel):
    """Schema for application information in responses."""
    application_id: int
    user_id: int
    job_id: str
    status: str
    applied_at: Optional[datetime]
    application_method: Optional[str]
    application_url: Optional[str]
    notes: Optional[str]
    tags: Optional[str]  # JSON string
    priority: int
    created_at: datetime
    updated_at: datetime


# ============================================================================
# Interview Schemas
# ============================================================================

class InterviewCreate(BaseModel):
    """Schema for creating a new interview."""
    interview_type: str
    scheduled_at: Optional[datetime] = None
    duration_minutes: Optional[int] = None
    interviewer_name: Optional[str] = None
    interviewer_email: Optional[str] = None
    location: Optional[str] = None
    notes: Optional[str] = None
    preparation_notes: Optional[str] = None
    
    @field_validator('scheduled_at', mode='before')
    @classmethod
    def parse_datetime(cls, v):
        """Parse datetime from ISO string or return None."""
        if v == '' or v is None:
            return None
        if isinstance(v, str):
            try:
                # Handle ISO format with or without timezone
                if v.endswith('Z'):
                    v = v[:-1] + '+00:00'
                return datetime.fromisoformat(v)
            except (ValueError, AttributeError):
                return None
        return v


class InterviewUpdate(BaseModel):
    """Schema for updating an interview."""
    interview_type: Optional[str] = None
    scheduled_at: Optional[datetime] = None
    duration_minutes: Optional[int] = None
    interviewer_name: Optional[str] = None
    interviewer_email: Optional[str] = None
    location: Optional[str] = None
    notes: Optional[str] = None
    preparation_notes: Optional[str] = None
    status: Optional[str] = None
    
    @field_validator('scheduled_at', mode='before')
    @classmethod
    def parse_datetime(cls, v):
        """Parse datetime from ISO string or return None."""
        if v == '' or v is None:
            return None
        if isinstance(v, str):
            try:
                if v.endswith('Z'):
                    v = v[:-1] + '+00:00'
                return datetime.fromisoformat(v)
            except (ValueError, AttributeError):
                return None
        return v


class InterviewResponse(BaseModel):
    """Schema for interview information in responses."""
    interview_id: int
    application_id: int
    interview_type: str
    scheduled_at: Optional[datetime]
    duration_minutes: Optional[int]
    interviewer_name: Optional[str]
    interviewer_email: Optional[str]
    location: Optional[str]
    notes: Optional[str]
    preparation_notes: Optional[str]
    status: str
    created_at: datetime


# ============================================================================
# Offer Schemas
# ============================================================================

class OfferCreate(BaseModel):
    """Schema for creating a new offer."""
    offer_date: date
    salary_amount: Optional[float] = None
    salary_currency: str = "USD"
    salary_period: Optional[str] = None  # 'hourly', 'monthly', 'yearly'
    equity: Optional[str] = None
    benefits: Optional[str] = None
    start_date: Optional[date] = None
    decision_deadline: Optional[date] = None
    notes: Optional[str] = None
    
    @field_validator('start_date', 'decision_deadline', mode='before')
    @classmethod
    def empty_str_to_none(cls, v):
        """Convert empty strings to None for optional date fields."""
        if v == '' or v is None:
            return None
        return v


class OfferUpdate(BaseModel):
    """Schema for updating an offer."""
    offer_date: Optional[date] = None
    salary_amount: Optional[float] = None
    salary_currency: Optional[str] = None
    salary_period: Optional[str] = None
    equity: Optional[str] = None
    benefits: Optional[str] = None
    start_date: Optional[date] = None
    decision_deadline: Optional[date] = None
    status: Optional[str] = None
    notes: Optional[str] = None
    
    @field_validator('start_date', 'decision_deadline', 'offer_date', mode='before')
    @classmethod
    def empty_str_to_none(cls, v):
        """Convert empty strings to None for optional date fields."""
        if v == '' or v is None:
            return None
        return v


class OfferResponse(BaseModel):
    """Schema for offer information in responses."""
    offer_id: int
    application_id: int
    offer_date: date
    salary_amount: Optional[float]
    salary_currency: str
    salary_period: Optional[str]
    equity: Optional[str]
    benefits: Optional[str]
    start_date: Optional[date]
    decision_deadline: Optional[date]
    status: str
    notes: Optional[str]
    created_at: datetime


# ============================================================================
# Company Schemas
# ============================================================================

class CompanyProfileResponse(BaseModel):
    """Schema for company profile information."""
    company_id: int
    name: str
    website: Optional[str] = None
    description: Optional[str] = None
    industry: Optional[str] = None
    size: Optional[str] = None
    headquarters: Optional[str] = None
    founded_year: Optional[int] = None
    employee_count: Optional[int] = None
    linkedin_url: Optional[str] = None
    glassdoor_url: Optional[str] = None


class CompanyNoteCreate(BaseModel):
    """Schema for creating a company note."""
    company_id: int
    note_text: str
    rating: Optional[int] = Field(None, ge=1, le=5)


class CompanyNoteResponse(BaseModel):
    """Schema for company note in responses."""
    note_id: int
    user_id: int
    company_id: int
    note_text: str
    rating: Optional[int]
    created_at: datetime
    updated_at: datetime


# ============================================================================
# Tag Schemas
# ============================================================================

class TagCreate(BaseModel):
    """Schema for creating a tag."""
    name: str
    color: Optional[str] = None


class TagResponse(BaseModel):
    """Schema for tag information in responses."""
    tag_id: int
    user_id: int
    name: str
    color: Optional[str]
    created_at: datetime


# ============================================================================
# Saved Search Schemas
# ============================================================================

class SavedSearchCreate(BaseModel):
    """Schema for creating a saved search."""
    name: str
    filters: Dict[str, Any]  # JSON-serializable filters
    notification_enabled: bool = True


class SavedSearchResponse(BaseModel):
    """Schema for saved search in responses."""
    search_id: int
    user_id: int
    name: str
    filters: str  # JSON string
    created_at: datetime
    last_run_at: Optional[datetime]
    notification_enabled: bool


# ============================================================================
# Notification Schemas
# ============================================================================

class NotificationResponse(BaseModel):
    """Schema for notification in responses."""
    notification_id: int
    user_id: int
    type: str
    title: str
    message: str
    related_job_id: Optional[str]
    related_application_id: Optional[int]
    read: bool
    created_at: datetime


class NotificationPreferences(BaseModel):
    """Schema for notification preferences."""
    email_enabled: bool = True
    job_alerts: bool = True
    status_changes: bool = True
    reminders: bool = True
    deadlines: bool = True
    weekly_digest: bool = True


# ============================================================================
# Company Schemas
# ============================================================================

class CompanyProfileUpdate(BaseModel):
    """Schema for updating company profile."""
    website: Optional[str] = None
    description: Optional[str] = None
    industry: Optional[str] = None
    size: Optional[str] = None
    headquarters: Optional[str] = None
    founded_year: Optional[int] = None
    employee_count: Optional[int] = None
    linkedin_url: Optional[str] = None
    glassdoor_url: Optional[str] = None
    notes: Optional[str] = None


class CompanyNoteCreate(BaseModel):
    """Schema for creating a company note."""
    note_text: str = Field(..., min_length=1, max_length=5000)
    rating: Optional[int] = Field(None, ge=1, le=5)


class CompanyNoteUpdate(BaseModel):
    """Schema for updating a company note."""
    note_text: Optional[str] = Field(None, min_length=1, max_length=5000)
    rating: Optional[int] = Field(None, ge=1, le=5)


class CompanyNoteResponse(BaseModel):
    """Schema for company note in responses."""
    note_id: int
    user_id: int
    username: Optional[str]
    company_id: int
    note_text: str
    rating: Optional[int]
    created_at: datetime
    updated_at: datetime


class CompanyResponse(BaseModel):
    """Schema for company information in responses."""
    id: int
    slug: str
    name: str
    source: str
    website: Optional[str] = None
    description: Optional[str] = None
    industry: Optional[str] = None
    size: Optional[str] = None
    headquarters: Optional[str] = None
    founded_year: Optional[int] = None
    employee_count: Optional[int] = None
    linkedin_url: Optional[str] = None
    glassdoor_url: Optional[str] = None
    profile_notes: Optional[str] = None


class CompanyAnalyticsResponse(BaseModel):
    """Schema for company analytics in responses."""
    analytics_id: Optional[int] = None
    company_id: int
    snapshot_date: Optional[date] = None
    total_jobs_posted: int
    total_jobs_removed: int
    avg_posting_duration_days: float
    ghost_posting_rate: float
    posting_frequency_per_month: int
    removal_frequency_per_month: int
    job_churn_rate: float
    reliability_score: float
    new_grad_friendly_score: float
