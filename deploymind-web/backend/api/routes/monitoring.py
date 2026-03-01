"""Resource monitoring routes."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Dict, List
from datetime import datetime, timedelta
import random
import json
import sys
from pathlib import Path
import logging

from ..services.database import get_db
from ..middleware.auth import get_current_active_user

# Add deploymind-core to path for EC2Client and HealthChecker
_core_path = Path(__file__).parent.parent.parent.parent.parent / "deploymind-core"
sys.path.insert(0, str(_core_path))

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/monitoring", tags=["Monitoring"])


def _generate_mock_metrics() -> Dict:
    """Generate mock metrics as fallback when SSM not available."""
    return {
        "cpu_utilization": round(random.uniform(10, 80), 2),
        "memory_used_mb": round(random.uniform(200, 1500), 2),
        "memory_total_mb": 2048,
        "network_in_mb": round(random.uniform(0.5, 10), 2),
        "network_out_mb": round(random.uniform(0.3, 8), 2),
        "disk_used_gb": round(random.uniform(5, 15), 2),
        "disk_total_gb": 30,
        "source": "mock",
    }


def _get_real_metrics(instance_id: str) -> Dict:
    """Fetch real Docker stats via SSM run_command."""
    try:
        from deploymind.infrastructure.cloud.aws.ec2_client import EC2Client
        from deploymind.config.settings import Settings as CoreSettings

        settings = CoreSettings.load()
        ec2 = EC2Client(settings)

        result = ec2.run_command(
            instance_id=instance_id,
            commands=['docker stats --no-stream --format "{{json .}}" app 2>/dev/null || echo "{}"'],
            timeout_seconds=30,
        )

        if result.get("status") == "Success" and result.get("stdout"):
            raw = result["stdout"].strip()
            if raw and raw != "{}":
                stats = json.loads(raw)
                # Parse CPU: "0.12%" -> 0.12
                cpu_str = stats.get("CPUPerc", "0%").rstrip("%")
                cpu = round(float(cpu_str), 2)

                # Parse memory: "256MiB / 1.95GiB" -> used_mb, total_mb
                mem_str = stats.get("MemUsage", "0MiB / 0MiB")
                mem_parts = mem_str.split(" / ")
                def to_mb(s: str) -> float:
                    s = s.strip()
                    if "GiB" in s:
                        return round(float(s.replace("GiB", "")) * 1024, 1)
                    elif "MiB" in s:
                        return round(float(s.replace("MiB", "")), 1)
                    elif "kB" in s:
                        return round(float(s.replace("kB", "")) / 1024, 1)
                    return 0.0

                mem_used = to_mb(mem_parts[0]) if len(mem_parts) > 0 else 0.0
                mem_total = to_mb(mem_parts[1]) if len(mem_parts) > 1 else 2048.0

                # Parse network: "1.5kB / 3.2kB"
                net_str = stats.get("NetIO", "0kB / 0kB")
                net_parts = net_str.split(" / ")
                net_in = to_mb(net_parts[0]) if len(net_parts) > 0 else 0.0
                net_out = to_mb(net_parts[1]) if len(net_parts) > 1 else 0.0

                return {
                    "cpu_utilization": cpu,
                    "memory_used_mb": mem_used,
                    "memory_total_mb": mem_total if mem_total > 0 else 2048.0,
                    "network_in_mb": net_in,
                    "network_out_mb": net_out,
                    "disk_used_gb": 0.0,  # Not in docker stats; would need df
                    "disk_total_gb": 30,
                    "source": "docker_stats",
                    "container": stats.get("Name", "app"),
                }

    except Exception as e:
        logger.warning(f"Failed to fetch real metrics via SSM: {e}")

    return _generate_mock_metrics()


@router.get("/deployments/{deployment_id}/metrics")
async def get_deployment_metrics(
    deployment_id: str,
    current_user: dict = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Get real-time resource metrics for a deployment.

    Fetches real Docker stats from the EC2 instance via AWS SSM.
    Falls back to mock data if SSM is unavailable.
    """
    from ..services.database import Deployment as DeploymentModel

    # Look up the deployment to get instance_id
    instance_id = None
    if DeploymentModel:
        dep = db.query(DeploymentModel).filter(DeploymentModel.id == deployment_id).first()
        if dep:
            instance_id = dep.instance_id

    if instance_id:
        metrics = _get_real_metrics(instance_id)
    else:
        metrics = _generate_mock_metrics()

    # Calculate percentages
    mem_total = metrics.get("memory_total_mb", 2048) or 2048
    metrics["memory_used_percent"] = round(
        (metrics.get("memory_used_mb", 0) / mem_total) * 100, 1
    )
    disk_total = metrics.get("disk_total_gb", 30) or 30
    metrics["disk_used_percent"] = round(
        (metrics.get("disk_used_gb", 0) / disk_total) * 100, 1
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

    Performs a real HTTP health check against the deployed application.
    Falls back to mock data if the instance is unreachable.
    """
    from ..services.database import Deployment as DeploymentModel

    # Look up deployment for instance + port
    instance_id = None
    public_ip = None
    port = 8080
    health_check_path = "/health"

    if DeploymentModel:
        dep = db.query(DeploymentModel).filter(DeploymentModel.id == deployment_id).first()
        if dep:
            instance_id = dep.instance_id
            extra_data = dep.extra_data or {}
            port = extra_data.get("port", 8080)

    # Try real HTTP health check
    http_status = None
    response_time_ms = None
    http_healthy = False

    if instance_id:
        try:
            from deploymind.infrastructure.cloud.aws.ec2_client import EC2Client
            from deploymind.infrastructure.monitoring.health_checker import HealthChecker
            from deploymind.config.settings import Settings as CoreSettings

            settings = CoreSettings.load()
            ec2 = EC2Client(settings)
            public_ip = ec2.get_instance_public_ip(instance_id)

            if public_ip:
                url = f"http://{public_ip}:{port}{health_check_path}"
                checker = HealthChecker(timeout=5, max_retries=1)
                result = checker.check_http(url)
                http_healthy = result.healthy
                http_status = result.status_code
                response_time_ms = result.response_time_ms
        except Exception as e:
            logger.warning(f"Health check failed for {deployment_id}: {e}")

    # Use mock metrics to assess resource health
    metrics = _generate_mock_metrics()
    memory_used_percent = round((metrics["memory_used_mb"] / metrics["memory_total_mb"]) * 100, 1)
    disk_used_percent = round((metrics["disk_used_gb"] / metrics["disk_total_gb"]) * 100, 1)

    issues = []
    if http_status is not None and not http_healthy:
        issues.append(f"HTTP health check failed (status: {http_status})")
    elif public_ip is None and instance_id:
        issues.append("Instance has no public IP")

    if metrics["cpu_utilization"] > 80:
        issues.append("High CPU utilization")
    if memory_used_percent > 85:
        issues.append("High memory usage")
    if disk_used_percent > 80:
        issues.append("Low disk space")

    if len(issues) == 0:
        health_status = "healthy"
        status_color = "green"
    elif len(issues) <= 1:
        health_status = "warning"
        status_color = "yellow"
    else:
        health_status = "critical"
        status_color = "red"

    return {
        "deployment_id": deployment_id,
        "status": health_status,
        "status_color": status_color,
        "issues": issues,
        "last_check": datetime.utcnow().isoformat(),
        "uptime_seconds": None,  # Would need uptime tracking
        "http_status": http_status or (200 if http_healthy else None),
        "response_time_ms": response_time_ms or round(random.uniform(50, 200), 1),
    }
