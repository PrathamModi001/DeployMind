"""Analytics service for deployment metrics calculation."""
from typing import Dict, List
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func, case
import sys
from pathlib import Path

# Import deploymind-core models
core_path = Path(__file__).parent.parent.parent.parent / "deploymind-core"
sys.path.insert(0, str(core_path))

try:
    from deploymind.infrastructure.database.models import (
        Deployment,
        BuildResult,
        HealthCheck,
        DeploymentStatusEnum,
    )
except ImportError:
    Deployment = None
    BuildResult = None
    HealthCheck = None
    DeploymentStatusEnum = None


class AnalyticsService:
    """Service for calculating analytics from database."""

    def __init__(self, db: Session):
        """Initialize with database session."""
        self.db = db

    def get_overview(self, days: int = 7) -> Dict:
        """
        Get deployment analytics overview.

        Args:
            days: Number of days to analyze (default: 7)

        Returns:
            Dictionary with overview metrics
        """
        if not Deployment:
            return self._mock_overview(days)

        # Calculate date range
        start_date = datetime.utcnow() - timedelta(days=days)

        # Query deployments in date range
        deployments = (
            self.db.query(Deployment)
            .filter(Deployment.created_at >= start_date)
            .all()
        )

        if not deployments:
            return self._empty_overview(days)

        # Calculate metrics
        total = len(deployments)
        successful = sum(
            1 for d in deployments
            if d.status in [DeploymentStatusEnum.DEPLOYED, "deployed"]
        )
        failed = sum(
            1 for d in deployments
            if d.status in [DeploymentStatusEnum.FAILED, "failed", DeploymentStatusEnum.SECURITY_FAILED, "security_failed", DeploymentStatusEnum.BUILD_FAILED, "build_failed"]
        )
        success_rate = (successful / total * 100) if total > 0 else 0.0

        # Calculate duration stats
        durations = [d.duration_seconds for d in deployments if d.duration_seconds]
        avg_duration = sum(durations) / len(durations) if durations else 0.0
        total_duration = sum(durations) if durations else 0.0

        # Group by status
        status_counts = {}
        for d in deployments:
            status_key = d.status.value if hasattr(d.status, 'value') else d.status
            status_counts[status_key] = status_counts.get(status_key, 0) + 1

        # Group by environment (from extra_data JSON)
        env_counts = {}
        for d in deployments:
            env = (d.extra_data or {}).get("environment", "production")
            env_counts[env] = env_counts.get(env, 0) + 1

        # Estimate cost saved (rough calculation: $0.50 per successful deployment)
        cost_saved = successful * 0.50

        return {
            "period_days": days,
            "total_deployments": total,
            "successful_deployments": successful,
            "failed_deployments": failed,
            "success_rate": round(success_rate, 2),
            "average_duration_seconds": round(avg_duration, 2),
            "total_duration_seconds": round(total_duration, 2),
            "cost_saved_usd": round(cost_saved, 2),
            "deployments_by_status": status_counts,
            "deployments_by_environment": env_counts,
        }

    def get_timeline(self, days: int = 30) -> Dict:
        """
        Get deployment timeline data for charts.

        Args:
            days: Number of days to include

        Returns:
            Dictionary with timeline data
        """
        if not Deployment:
            return self._mock_timeline(days)

        start_date = datetime.utcnow() - timedelta(days=days)

        # Query deployments
        deployments = (
            self.db.query(Deployment)
            .filter(Deployment.created_at >= start_date)
            .all()
        )

        # Group by date
        timeline_data = {}
        for i in range(days):
            date = (datetime.utcnow() - timedelta(days=days-i-1)).date()
            timeline_data[date] = {
                "total": 0,
                "successful": 0,
                "failed": 0,
                "durations": [],
            }

        # Populate with deployment data
        for d in deployments:
            date = d.created_at.date()
            if date in timeline_data:
                timeline_data[date]["total"] += 1
                if d.status in [DeploymentStatusEnum.DEPLOYED, "deployed"]:
                    timeline_data[date]["successful"] += 1
                elif d.status in [DeploymentStatusEnum.FAILED, "failed", DeploymentStatusEnum.SECURITY_FAILED, "security_failed", DeploymentStatusEnum.BUILD_FAILED, "build_failed"]:
                    timeline_data[date]["failed"] += 1
                if d.duration_seconds:
                    timeline_data[date]["durations"].append(d.duration_seconds)

        # Format timeline
        timeline = []
        for date in sorted(timeline_data.keys()):
            data = timeline_data[date]
            avg_duration = (
                sum(data["durations"]) / len(data["durations"])
                if data["durations"]
                else 0.0
            )
            timeline.append({
                "date": date.strftime("%Y-%m-%d"),
                "total_deployments": data["total"],
                "successful": data["successful"],
                "failed": data["failed"],
                "avg_duration_seconds": round(avg_duration, 2),
            })

        return {"timeline": timeline}

    def get_performance(self) -> Dict:
        """
        Get performance metrics.

        Returns:
            Dictionary with performance data
        """
        if not BuildResult or not HealthCheck:
            return self._mock_performance()

        # Build times by language
        build_results = self.db.query(BuildResult).all()
        build_by_lang = {}
        for br in build_results:
            lang = br.detected_language or "unknown"
            if lang not in build_by_lang:
                build_by_lang[lang] = []
            # Estimate build time from deployment duration (rough approximation)
            # In real scenario, you'd track build_duration separately
            if br.deployment and br.deployment.duration_seconds:
                build_by_lang[lang].append(br.deployment.duration_seconds / 3)  # Assume build is 1/3 of total

        build_times = {}
        for lang, times in build_by_lang.items():
            if times:
                build_times[lang] = {
                    "avg": round(sum(times) / len(times), 2),
                    "min": round(min(times), 2),
                    "max": round(max(times), 2),
                    "count": len(times),
                }

        # Deployment times by strategy
        deployments = self.db.query(Deployment).filter(
            Deployment.duration_seconds.isnot(None)
        ).all()

        deploy_by_strategy = {}
        for d in deployments:
            strategy = d.strategy.value if hasattr(d.strategy, 'value') else str(d.strategy)
            if strategy not in deploy_by_strategy:
                deploy_by_strategy[strategy] = []
            deploy_by_strategy[strategy].append(d.duration_seconds)

        deployment_times = {}
        for strategy, times in deploy_by_strategy.items():
            if times:
                deployment_times[strategy] = {
                    "avg": round(sum(times) / len(times), 2),
                    "min": round(min(times), 2),
                    "max": round(max(times), 2),
                    "count": len(times),
                }

        # Health check response times
        health_checks = self.db.query(HealthCheck).filter(
            HealthCheck.response_time_ms.isnot(None)
        ).all()

        response_times = [hc.response_time_ms for hc in health_checks]
        if response_times:
            response_times_sorted = sorted(response_times)
            avg_ms = sum(response_times) / len(response_times)
            p50_ms = response_times_sorted[len(response_times_sorted) // 2]
            p95_ms = response_times_sorted[int(len(response_times_sorted) * 0.95)]
            p99_ms = response_times_sorted[int(len(response_times_sorted) * 0.99)]
        else:
            avg_ms = p50_ms = p95_ms = p99_ms = 0.0

        return {
            "build_times_by_language": build_times,
            "deployment_times_by_strategy": deployment_times,
            "health_check_response_times": {
                "avg_ms": round(avg_ms, 2),
                "p50_ms": round(p50_ms, 2),
                "p95_ms": round(p95_ms, 2),
                "p99_ms": round(p99_ms, 2),
            },
        }

    def _empty_overview(self, days: int) -> Dict:
        """Return empty overview when no data."""
        return {
            "period_days": days,
            "total_deployments": 0,
            "successful_deployments": 0,
            "failed_deployments": 0,
            "success_rate": 0.0,
            "average_duration_seconds": 0.0,
            "total_duration_seconds": 0.0,
            "cost_saved_usd": 0.0,
            "deployments_by_status": {},
            "deployments_by_environment": {},
        }

    def _mock_overview(self, days: int) -> Dict:
        """Fallback mock data."""
        return {
            "period_days": days,
            "total_deployments": 0,
            "successful_deployments": 0,
            "failed_deployments": 0,
            "success_rate": 0.0,
            "average_duration_seconds": 0.0,
            "total_duration_seconds": 0.0,
            "cost_saved_usd": 0.0,
            "deployments_by_status": {},
            "deployments_by_environment": {},
        }

    def _mock_timeline(self, days: int) -> Dict:
        """Fallback mock timeline."""
        return {"timeline": []}

    def _mock_performance(self) -> Dict:
        """Fallback mock performance."""
        return {
            "build_times_by_language": {},
            "deployment_times_by_strategy": {},
            "health_check_response_times": {
                "avg_ms": 0.0,
                "p50_ms": 0.0,
                "p95_ms": 0.0,
                "p99_ms": 0.0,
            },
        }
