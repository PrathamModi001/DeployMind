"""Deployment analytics and metrics tracking.

Provides insights into deployment patterns, success rates, and performance.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
from collections import defaultdict

from deploymind.config.dependencies import container
from core.logger import get_logger
from deploymind.shared.cache import cached

logger = get_logger(__name__)


@dataclass
class DeploymentMetrics:
    """Aggregated deployment metrics."""
    total_deployments: int
    successful_deployments: int
    failed_deployments: int
    success_rate: float
    average_duration_seconds: Optional[float]
    fastest_deployment_seconds: Optional[float]
    slowest_deployment_seconds: Optional[float]
    total_duration_seconds: float

    # Phase-specific metrics
    security_scan_pass_rate: float = 0.0
    build_success_rate: float = 0.0
    deployment_success_rate: float = 0.0

    # Repository breakdown
    deployments_by_repository: Dict[str, int] = None
    success_by_repository: Dict[str, int] = None

    # Time-based metrics
    deployments_by_hour: Dict[int, int] = None
    deployments_by_day: Dict[str, int] = None


@dataclass
class RepositoryStats:
    """Statistics for a specific repository."""
    repository: str
    total_deployments: int
    successful_deployments: int
    failed_deployments: int
    success_rate: float
    average_duration_seconds: Optional[float]
    last_deployment_at: Optional[datetime]
    last_deployment_status: Optional[str]


@dataclass
class TimeSeriesData:
    """Time-series deployment data."""
    timestamp: datetime
    total_count: int
    success_count: int
    failure_count: int
    average_duration: Optional[float]


class DeploymentAnalytics:
    """Analytics service for deployment metrics."""

    def __init__(self):
        """Initialize analytics service."""
        self.deployment_repo = container.deployment_repo
        self.security_scan_repo = container.security_scan_repo
        self.build_result_repo = container.build_result_repo
        self.health_check_repo = container.health_check_repo

    @cached(ttl_seconds=300, prefix="analytics:overall", use_redis=False)
    def get_overall_metrics(
        self,
        days: int = 30,
        repository: Optional[str] = None
    ) -> DeploymentMetrics:
        """Get overall deployment metrics.

        Args:
            days: Number of days to look back (default: 30)
            repository: Optional repository filter

        Returns:
            DeploymentMetrics object with aggregated statistics
        """
        # Get deployments
        if repository:
            deployments = self.deployment_repo.get_by_repository(repository, limit=1000)
        else:
            deployments = self.deployment_repo.list_all(limit=1000)

        # Filter by date range
        cutoff_date = datetime.now() - timedelta(days=days)
        deployments = [d for d in deployments if d.created_at >= cutoff_date]

        if not deployments:
            return self._empty_metrics()

        # Calculate basic metrics
        total = len(deployments)
        successful = sum(1 for d in deployments if d.status == "deployed")
        failed = sum(1 for d in deployments if d.status == "failed")
        success_rate = (successful / total * 100) if total > 0 else 0.0

        # Calculate duration metrics
        durations = [d.duration_seconds for d in deployments if d.duration_seconds is not None]
        avg_duration = sum(durations) / len(durations) if durations else None
        fastest = min(durations) if durations else None
        slowest = max(durations) if durations else None
        total_duration = sum(durations) if durations else 0.0

        # Repository breakdown
        repo_counts = defaultdict(int)
        repo_success = defaultdict(int)
        for d in deployments:
            repo_counts[d.repository] += 1
            if d.status == "deployed":
                repo_success[d.repository] += 1

        # Time-based breakdown
        hour_counts = defaultdict(int)
        day_counts = defaultdict(int)
        for d in deployments:
            hour_counts[d.created_at.hour] += 1
            day_counts[d.created_at.strftime("%Y-%m-%d")] += 1

        # Phase-specific metrics
        security_pass_rate = self._calculate_security_pass_rate(deployments)
        build_success_rate = self._calculate_build_success_rate(deployments)
        deployment_success_rate = success_rate

        return DeploymentMetrics(
            total_deployments=total,
            successful_deployments=successful,
            failed_deployments=failed,
            success_rate=success_rate,
            average_duration_seconds=avg_duration,
            fastest_deployment_seconds=fastest,
            slowest_deployment_seconds=slowest,
            total_duration_seconds=total_duration,
            security_scan_pass_rate=security_pass_rate,
            build_success_rate=build_success_rate,
            deployment_success_rate=deployment_success_rate,
            deployments_by_repository=dict(repo_counts),
            success_by_repository=dict(repo_success),
            deployments_by_hour=dict(hour_counts),
            deployments_by_day=dict(day_counts)
        )

    @cached(ttl_seconds=300, prefix="analytics:repo", use_redis=False)
    def get_repository_stats(self, repository: str) -> RepositoryStats:
        """Get statistics for a specific repository.

        Args:
            repository: Repository name (owner/repo)

        Returns:
            RepositoryStats object
        """
        deployments = self.deployment_repo.get_by_repository(repository, limit=1000)

        if not deployments:
            return RepositoryStats(
                repository=repository,
                total_deployments=0,
                successful_deployments=0,
                failed_deployments=0,
                success_rate=0.0,
                average_duration_seconds=None,
                last_deployment_at=None,
                last_deployment_status=None
            )

        total = len(deployments)
        successful = sum(1 for d in deployments if d.status == "deployed")
        failed = sum(1 for d in deployments if d.status == "failed")
        success_rate = (successful / total * 100) if total > 0 else 0.0

        durations = [d.duration_seconds for d in deployments if d.duration_seconds is not None]
        avg_duration = sum(durations) / len(durations) if durations else None

        latest = deployments[0]  # Already sorted by created_at desc

        return RepositoryStats(
            repository=repository,
            total_deployments=total,
            successful_deployments=successful,
            failed_deployments=failed,
            success_rate=success_rate,
            average_duration_seconds=avg_duration,
            last_deployment_at=latest.created_at,
            last_deployment_status=latest.status
        )

    def get_top_repositories(self, limit: int = 10) -> List[RepositoryStats]:
        """Get top repositories by deployment count.

        Args:
            limit: Number of repositories to return

        Returns:
            List of RepositoryStats sorted by deployment count
        """
        # Get all deployments
        deployments = self.deployment_repo.list_all(limit=10000)

        # Group by repository
        repo_map = defaultdict(list)
        for d in deployments:
            repo_map[d.repository].append(d)

        # Calculate stats for each repository
        repo_stats = []
        for repo, repo_deployments in repo_map.items():
            total = len(repo_deployments)
            successful = sum(1 for d in repo_deployments if d.status == "deployed")
            failed = sum(1 for d in repo_deployments if d.status == "failed")
            success_rate = (successful / total * 100) if total > 0 else 0.0

            durations = [d.duration_seconds for d in repo_deployments if d.duration_seconds is not None]
            avg_duration = sum(durations) / len(durations) if durations else None

            latest = repo_deployments[0]  # Already sorted

            repo_stats.append(RepositoryStats(
                repository=repo,
                total_deployments=total,
                successful_deployments=successful,
                failed_deployments=failed,
                success_rate=success_rate,
                average_duration_seconds=avg_duration,
                last_deployment_at=latest.created_at,
                last_deployment_status=latest.status
            ))

        # Sort by deployment count
        repo_stats.sort(key=lambda x: x.total_deployments, reverse=True)

        return repo_stats[:limit]

    def get_time_series(
        self,
        days: int = 7,
        interval_hours: int = 24
    ) -> List[TimeSeriesData]:
        """Get time-series deployment data.

        Args:
            days: Number of days to look back
            interval_hours: Time interval in hours (default: 24 = daily)

        Returns:
            List of TimeSeriesData objects
        """
        # Get deployments
        deployments = self.deployment_repo.list_all(limit=10000)

        # Filter by date range
        cutoff_date = datetime.now() - timedelta(days=days)
        deployments = [d for d in deployments if d.created_at >= cutoff_date]

        # Group by time interval
        interval_map = defaultdict(list)
        for d in deployments:
            # Round timestamp to interval
            timestamp = d.created_at.replace(minute=0, second=0, microsecond=0)
            if interval_hours > 1:
                hours_since_midnight = timestamp.hour
                interval_start = hours_since_midnight // interval_hours * interval_hours
                timestamp = timestamp.replace(hour=interval_start)

            interval_map[timestamp].append(d)

        # Calculate metrics for each interval
        time_series = []
        for timestamp, interval_deployments in sorted(interval_map.items()):
            total = len(interval_deployments)
            successful = sum(1 for d in interval_deployments if d.status == "deployed")
            failed = sum(1 for d in interval_deployments if d.status == "failed")

            durations = [d.duration_seconds for d in interval_deployments if d.duration_seconds is not None]
            avg_duration = sum(durations) / len(durations) if durations else None

            time_series.append(TimeSeriesData(
                timestamp=timestamp,
                total_count=total,
                success_count=successful,
                failure_count=failed,
                average_duration=avg_duration
            ))

        return time_series

    def get_failure_analysis(self, days: int = 30) -> Dict[str, Any]:
        """Analyze deployment failures.

        Args:
            days: Number of days to look back

        Returns:
            Dictionary with failure analysis data
        """
        # Get failed deployments
        deployments = self.deployment_repo.get_by_status("failed", limit=1000)

        # Filter by date range
        cutoff_date = datetime.now() - timedelta(days=days)
        deployments = [d for d in deployments if d.created_at >= cutoff_date]

        if not deployments:
            return {
                "total_failures": 0,
                "failure_by_phase": {},
                "failure_by_repository": {},
                "common_errors": []
            }

        # Analyze failure phases
        phase_failures = defaultdict(int)
        repo_failures = defaultdict(int)

        for d in deployments:
            # Note: Would need error_phase field in deployment to track this
            # For now, use rollback_reason as proxy
            if hasattr(d, 'rollback_reason') and d.rollback_reason:
                phase_failures[d.rollback_reason] += 1

            repo_failures[d.repository] += 1

        return {
            "total_failures": len(deployments),
            "failure_by_phase": dict(phase_failures),
            "failure_by_repository": dict(repo_failures),
            "most_recent_failures": [
                {
                    "deployment_id": d.id,
                    "repository": d.repository,
                    "created_at": d.created_at.isoformat(),
                    "rollback_reason": getattr(d, 'rollback_reason', None)
                }
                for d in deployments[:5]  # Last 5 failures
            ]
        }

    def _calculate_security_pass_rate(self, deployments: List) -> float:
        """Calculate security scan pass rate.

        Args:
            deployments: List of deployments

        Returns:
            Pass rate as percentage
        """
        total_scans = 0
        passed_scans = 0

        for d in deployments:
            scans = self.security_scan_repo.get_by_deployment(d.id)
            if scans:
                total_scans += len(scans)
                passed_scans += sum(1 for s in scans if s.get('passed', False))

        return (passed_scans / total_scans * 100) if total_scans > 0 else 0.0

    def _calculate_build_success_rate(self, deployments: List) -> float:
        """Calculate build success rate.

        Args:
            deployments: List of deployments

        Returns:
            Success rate as percentage
        """
        total_builds = 0
        successful_builds = 0

        for d in deployments:
            builds = self.build_result_repo.get_by_deployment(d.id)
            if builds:
                total_builds += len(builds)
                successful_builds += sum(1 for b in builds if b.get('success', False))

        return (successful_builds / total_builds * 100) if total_builds > 0 else 0.0

    def _empty_metrics(self) -> DeploymentMetrics:
        """Return empty metrics object."""
        return DeploymentMetrics(
            total_deployments=0,
            successful_deployments=0,
            failed_deployments=0,
            success_rate=0.0,
            average_duration_seconds=None,
            fastest_deployment_seconds=None,
            slowest_deployment_seconds=None,
            total_duration_seconds=0.0,
            deployments_by_repository={},
            success_by_repository={},
            deployments_by_hour={},
            deployments_by_day={}
        )
