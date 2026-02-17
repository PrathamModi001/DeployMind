"""Analytics routes."""
from fastapi import APIRouter, Depends, Query
from typing import Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from ..middleware.auth import get_current_active_user
from ..services.database import get_db
from ..services.analytics_service import AnalyticsService

router = APIRouter(prefix="/api/analytics", tags=["Analytics"])


@router.get("/overview")
async def get_analytics_overview(
    days: int = Query(7, ge=1, le=90, description="Number of days to analyze"),
    current_user: dict = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Get deployment analytics overview.

    Returns key metrics:
    - Total deployments
    - Success rate
    - Average duration
    - Cost saved
    """
    service = AnalyticsService(db)
    return service.get_overview(days)


@router.get("/timeline")
async def get_deployment_timeline(
    days: int = Query(30, ge=1, le=365, description="Number of days"),
    current_user: dict = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Get deployment timeline data for charts.

    Returns daily deployment counts and success rates.
    """
    service = AnalyticsService(db)
    return service.get_timeline(days)


@router.get("/performance")
async def get_performance_metrics(
    current_user: dict = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Get performance metrics.

    Returns:
    - Build times by language
    - Deployment times by strategy
    - Health check response times
    """
    service = AnalyticsService(db)
    return service.get_performance()
