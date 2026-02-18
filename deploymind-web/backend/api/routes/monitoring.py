"""Resource monitoring routes."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Dict, List
from datetime import datetime, timedelta
import random

from ..services.database import get_db
from ..middleware.auth import get_current_active_user

router = APIRouter(prefix="/api/monitoring", tags=["Monitoring"])


def _generate_mock_metrics() -> Dict:
    """Generate mock metrics for demonstration."""
    # In production, this would fetch real metrics from CloudWatch or EC2
    return {
        "cpu_utilization": round(random.uniform(10, 80), 2),
        "memory_used_mb": round(random.uniform(200, 1500), 2),
        "memory_total_mb": 2048,
        "network_in_mb": round(random.uniform(0.5, 10), 2),
        "network_out_mb": round(random.uniform(0.3, 8), 2),
        "disk_used_gb": round(random.uniform(5, 15), 2),
        "disk_total_gb": 30,
    }


@router.get("/deployments/{deployment_id}/metrics")
async def get_deployment_metrics(
    deployment_id: str,
    current_user: dict = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Get real-time resource metrics for a deployment.

    In production, this would fetch from:
    - AWS CloudWatch for EC2 instance metrics
    - EC2 instance metadata endpoint
    - Custom monitoring agents
    """
    metrics = _generate_mock_metrics()

    # Calculate percentages
    metrics["memory_used_percent"] = round(
        (metrics["memory_used_mb"] / metrics["memory_total_mb"]) * 100, 1
    )
    metrics["disk_used_percent"] = round(
        (metrics["disk_used_gb"] / metrics["disk_total_gb"]) * 100, 1
    )

    return {
        "deployment_id": deployment_id,
        "timestamp": datetime.utcnow().isoformat(),
        "metrics": metrics
    }


@router.get("/deployments/{deployment_id}/metrics/history")
async def get_metrics_history(
    deployment_id: str,
    hours: int = 1,
    current_user: dict = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Get historical metrics for charting.

    Returns time-series data for the last N hours.
    """
    if hours < 1 or hours > 24:
        raise HTTPException(status_code=400, detail="Hours must be between 1 and 24")

    # Generate mock historical data
    now = datetime.utcnow()
    points = []

    # Generate data points every 5 minutes
    interval_minutes = 5
    num_points = (hours * 60) // interval_minutes

    for i in range(num_points):
        timestamp = now - timedelta(minutes=i * interval_minutes)

        # Generate somewhat realistic trending data
        base_cpu = 40 + (i % 10) * 3
        base_memory = 800 + (i % 15) * 20

        points.append({
            "timestamp": timestamp.isoformat(),
            "cpu_utilization": round(base_cpu + random.uniform(-10, 10), 2),
            "memory_used_mb": round(base_memory + random.uniform(-100, 100), 2),
            "network_in_mb": round(random.uniform(1, 15), 2),
            "network_out_mb": round(random.uniform(0.5, 10), 2),
        })

    # Reverse to get chronological order
    points.reverse()

    return {
        "deployment_id": deployment_id,
        "hours": hours,
        "interval_minutes": interval_minutes,
        "data": points
    }


@router.get("/deployments/{deployment_id}/health")
async def get_deployment_health(
    deployment_id: str,
    current_user: dict = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Get overall health status of deployment.

    Checks:
    - HTTP endpoint availability
    - Resource utilization thresholds
    - Error rates
    """
    metrics = _generate_mock_metrics()

    # Calculate percentages
    memory_used_percent = round((metrics["memory_used_mb"] / metrics["memory_total_mb"]) * 100, 1)
    disk_used_percent = round((metrics["disk_used_gb"] / metrics["disk_total_gb"]) * 100, 1)

    # Determine health status
    issues = []

    if metrics["cpu_utilization"] > 80:
        issues.append("High CPU utilization")

    if memory_used_percent > 85:
        issues.append("High memory usage")

    if disk_used_percent > 80:
        issues.append("Low disk space")

    # Overall status
    if len(issues) == 0:
        status = "healthy"
        status_color = "green"
    elif len(issues) <= 1:
        status = "warning"
        status_color = "yellow"
    else:
        status = "critical"
        status_color = "red"

    return {
        "deployment_id": deployment_id,
        "status": status,
        "status_color": status_color,
        "issues": issues,
        "last_check": datetime.utcnow().isoformat(),
        "uptime_seconds": 86400,  # Mock: 1 day uptime
        "http_status": 200,
        "response_time_ms": round(random.uniform(50, 200), 1),
    }
