"""
Analytics API routes for personal and market analytics.
"""

from fastapi import APIRouter, Depends
from job_tracker.api.dependencies import get_db, get_current_user
from job_tracker.db import Database
from job_tracker.analytics import calculate_user_analytics, calculate_market_analytics

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get("/personal")
async def get_personal_analytics(
    user_id: int = Depends(get_current_user),
    db: Database = Depends(get_db)
):
    """Get personal analytics"""
    return calculate_user_analytics(db, user_id)


@router.get("/market")
async def get_market_analytics(db: Database = Depends(get_db)):
    """Get market-wide analytics"""
    return calculate_market_analytics(db)


@router.get("/sectors")
async def get_sector_analytics(db: Database = Depends(get_db)):
    """Get sector trends"""
    analytics = calculate_market_analytics(db)
    return {"sectors": analytics["sector_trends"]}


@router.get("/companies")
async def get_company_analytics_summary(db: Database = Depends(get_db)):
    """Get company analytics summary"""
    analytics = calculate_market_analytics(db)
    return {"companies": analytics["company_reliability"]}
