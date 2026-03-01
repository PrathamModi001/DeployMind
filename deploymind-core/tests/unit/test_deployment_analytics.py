"""Unit tests for deployment analytics."""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
from deploymind.domain.entities.deployment import Deployment

from deploymind.application.analytics.deployment_analytics import (
    DeploymentAnalytics,
    DeploymentMetrics,
    RepositoryStats,
    TimeSeriesData
)


@pytest.fixture
def mock_repos():
    """Create mock repositories."""
    with patch('deploymind.application.analytics.deployment_analytics.container') as mock_container:
        mock_container.deployment_repo = Mock()
        mock_container.security_scan_repo = Mock()
        mock_container.build_result_repo = Mock()
        mock_container.health_check_repo = Mock()
        yield mock_container


@pytest.fixture
def sample_deployments():
    """Create sample deployment data."""
    now = datetime.now()

    deployments = [
        Mock(
            id=f"deploy-{i}",
            repository="user/repo1" if i % 2 == 0 else "user/repo2",
            status="deployed" if i % 3 != 0 else "failed",
            created_at=now - timedelta(days=i),
            duration_seconds=float(100 + i * 10) if i % 3 != 0 else None
        )
        for i in range(10)
    ]

    return deployments


class TestDeploymentAnalytics:
    """Test DeploymentAnalytics class."""

    def test_get_overall_metrics_empty(self, mock_repos):
        """Test metrics with no deployments."""
        mock_repos.deployment_repo.list_all.return_value = []

        analytics = DeploymentAnalytics()
        metrics = analytics.get_overall_metrics()

        assert metrics.total_deployments == 0
        assert metrics.success_rate == 0.0
        assert metrics.average_duration_seconds is None

    def test_get_overall_metrics_basic(self, mock_repos, sample_deployments):
        """Test basic overall metrics calculation."""
        mock_repos.deployment_repo.list_all.return_value = sample_deployments
        mock_repos.security_scan_repo.get_by_deployment.return_value = []
        mock_repos.build_result_repo.get_by_deployment.return_value = []

        analytics = DeploymentAnalytics()
        metrics = analytics.get_overall_metrics(days=30)

        assert metrics.total_deployments == 10
        # 10 deployments, i % 3 == 0 fails = 4 failed, 6 successful
        assert metrics.successful_deployments == 6
        assert metrics.failed_deployments == 4
        assert metrics.success_rate == 60.0

    def test_get_overall_metrics_with_durations(self, mock_repos, sample_deployments):
        """Test metrics with duration calculations."""
        mock_repos.deployment_repo.list_all.return_value = sample_deployments
        mock_repos.security_scan_repo.get_by_deployment.return_value = []
        mock_repos.build_result_repo.get_by_deployment.return_value = []

        analytics = DeploymentAnalytics()
        metrics = analytics.get_overall_metrics()

        assert metrics.average_duration_seconds is not None
        assert metrics.fastest_deployment_seconds is not None
        assert metrics.slowest_deployment_seconds is not None
        assert metrics.total_duration_seconds > 0

    def test_get_overall_metrics_repository_filter(self, mock_repos, sample_deployments):
        """Test metrics filtered by repository."""
        # Filter to only repo1 deployments (every even index)
        repo1_deployments = [d for d in sample_deployments if d.repository == "user/repo1"]
        mock_repos.deployment_repo.get_by_repository.return_value = repo1_deployments
        mock_repos.security_scan_repo.get_by_deployment.return_value = []
        mock_repos.build_result_repo.get_by_deployment.return_value = []

        analytics = DeploymentAnalytics()
        metrics = analytics.get_overall_metrics(repository="user/repo1")

        assert metrics.total_deployments == 5  # Half of 10
        assert "user/repo2" not in metrics.deployments_by_repository or \
               metrics.deployments_by_repository["user/repo2"] == 0

    def test_get_overall_metrics_repository_breakdown(self, mock_repos, sample_deployments):
        """Test repository breakdown in metrics."""
        mock_repos.deployment_repo.list_all.return_value = sample_deployments
        mock_repos.security_scan_repo.get_by_deployment.return_value = []
        mock_repos.build_result_repo.get_by_deployment.return_value = []

        analytics = DeploymentAnalytics()
        metrics = analytics.get_overall_metrics()

        assert len(metrics.deployments_by_repository) == 2
        assert "user/repo1" in metrics.deployments_by_repository
        assert "user/repo2" in metrics.deployments_by_repository

    def test_get_overall_metrics_time_breakdown(self, mock_repos, sample_deployments):
        """Test time-based breakdown in metrics."""
        mock_repos.deployment_repo.list_all.return_value = sample_deployments
        mock_repos.security_scan_repo.get_by_deployment.return_value = []
        mock_repos.build_result_repo.get_by_deployment.return_value = []

        analytics = DeploymentAnalytics()
        metrics = analytics.get_overall_metrics()

        assert metrics.deployments_by_hour is not None
        assert metrics.deployments_by_day is not None
        assert len(metrics.deployments_by_day) <= 10  # Max 10 days

    def test_get_repository_stats_empty(self, mock_repos):
        """Test repository stats with no deployments."""
        mock_repos.deployment_repo.get_by_repository.return_value = []

        analytics = DeploymentAnalytics()
        # Clear cache to avoid interference from other tests
        analytics.get_repository_stats.clear_cache()
        stats = analytics.get_repository_stats("user/repo")

        assert stats.repository == "user/repo"
        assert stats.total_deployments == 0
        assert stats.success_rate == 0.0
        assert stats.last_deployment_at is None

    def test_get_repository_stats_with_data(self, mock_repos):
        """Test repository stats with deployment data."""
        deployments = [
            Mock(
                id="deploy-1",
                repository="user/repo",
                status="deployed",
                created_at=datetime.now(),
                duration_seconds=100.0
            ),
            Mock(
                id="deploy-2",
                repository="user/repo",
                status="deployed",
                created_at=datetime.now() - timedelta(hours=1),
                duration_seconds=120.0
            ),
            Mock(
                id="deploy-3",
                repository="user/repo",
                status="failed",
                created_at=datetime.now() - timedelta(hours=2),
                duration_seconds=None
            )
        ]
        mock_repos.deployment_repo.get_by_repository.return_value = deployments

        analytics = DeploymentAnalytics()
        # Clear cache to avoid interference from other tests
        analytics.get_repository_stats.clear_cache()
        stats = analytics.get_repository_stats("user/repo")

        assert stats.total_deployments == 3
        assert stats.successful_deployments == 2
        assert stats.failed_deployments == 1
        assert stats.success_rate == pytest.approx(66.67, rel=0.1)
        assert stats.average_duration_seconds == 110.0  # (100 + 120) / 2
        assert stats.last_deployment_status == "deployed"

    def test_get_top_repositories(self, mock_repos):
        """Test getting top repositories by deployment count."""
        deployments = []
        for i in range(15):
            # Create more deployments for repo1 than repo2
            repo = "user/repo1" if i < 10 else "user/repo2"
            deployments.append(Mock(
                id=f"deploy-{i}",
                repository=repo,
                status="deployed" if i % 2 == 0 else "failed",
                created_at=datetime.now() - timedelta(days=i),
                duration_seconds=float(100 + i)
            ))

        mock_repos.deployment_repo.list_all.return_value = deployments

        analytics = DeploymentAnalytics()
        top_repos = analytics.get_top_repositories(limit=5)

        assert len(top_repos) <= 5
        assert top_repos[0].repository == "user/repo1"  # Should be first (10 deployments)
        assert top_repos[0].total_deployments == 10
        assert top_repos[1].repository == "user/repo2"  # Should be second (5 deployments)
        assert top_repos[1].total_deployments == 5

    def test_get_time_series_daily(self, mock_repos):
        """Test daily time series data."""
        now = datetime.now()
        deployments = [
            Mock(
                id=f"deploy-{i}",
                repository="user/repo",
                status="deployed" if i % 2 == 0 else "failed",
                created_at=now - timedelta(days=i),
                duration_seconds=float(100 + i * 10)
            )
            for i in range(7)  # One week
        ]

        mock_repos.deployment_repo.list_all.return_value = deployments

        analytics = DeploymentAnalytics()
        time_series = analytics.get_time_series(days=7, interval_hours=24)

        assert len(time_series) <= 7  # Up to 7 days
        for data_point in time_series:
            assert isinstance(data_point, TimeSeriesData)
            assert data_point.total_count > 0
            assert data_point.success_count + data_point.failure_count == data_point.total_count

    def test_get_time_series_hourly(self, mock_repos):
        """Test hourly time series data."""
        now = datetime.now()
        deployments = [
            Mock(
                id=f"deploy-{i}",
                repository="user/repo",
                status="deployed",
                created_at=now - timedelta(hours=i),
                duration_seconds=100.0
            )
            for i in range(24)  # 24 hours
        ]

        mock_repos.deployment_repo.list_all.return_value = deployments

        analytics = DeploymentAnalytics()
        time_series = analytics.get_time_series(days=1, interval_hours=1)

        assert len(time_series) <= 24  # Up to 24 hours

    def test_get_failure_analysis_empty(self, mock_repos):
        """Test failure analysis with no failures."""
        mock_repos.deployment_repo.get_by_status.return_value = []

        analytics = DeploymentAnalytics()
        analysis = analytics.get_failure_analysis()

        assert analysis["total_failures"] == 0
        assert len(analysis["failure_by_phase"]) == 0
        assert len(analysis["common_errors"]) == 0

    def test_get_failure_analysis_with_failures(self, mock_repos):
        """Test failure analysis with failed deployments."""
        now = datetime.now()
        failures = [
            Mock(
                id=f"deploy-{i}",
                repository="user/repo1" if i < 2 else "user/repo2",
                status="failed",
                created_at=now - timedelta(days=i),
                rollback_reason="Health check failed" if i % 2 == 0 else "Build failed"
            )
            for i in range(5)
        ]

        mock_repos.deployment_repo.get_by_status.return_value = failures

        analytics = DeploymentAnalytics()
        analysis = analytics.get_failure_analysis(days=30)

        assert analysis["total_failures"] == 5
        assert "failure_by_phase" in analysis
        assert "failure_by_repository" in analysis
        assert len(analysis["most_recent_failures"]) == 5

    def test_calculate_security_pass_rate(self, mock_repos, sample_deployments):
        """Test security scan pass rate calculation."""
        mock_repos.deployment_repo.list_all.return_value = sample_deployments[:3]

        # Mock security scans - 2 passed, 1 failed
        def mock_get_scans(deployment_id):
            if deployment_id == "deploy-0":
                return [{"passed": True}]
            elif deployment_id == "deploy-1":
                return [{"passed": True}]
            elif deployment_id == "deploy-2":
                return [{"passed": False}]
            return []

        mock_repos.security_scan_repo.get_by_deployment = mock_get_scans
        mock_repos.build_result_repo.get_by_deployment.return_value = []

        analytics = DeploymentAnalytics()
        metrics = analytics.get_overall_metrics()

        # 2 passed out of 3 = 66.67%
        assert metrics.security_scan_pass_rate == pytest.approx(66.67, rel=0.1)

    def test_calculate_build_success_rate(self, mock_repos, sample_deployments):
        """Test build success rate calculation."""
        mock_repos.deployment_repo.list_all.return_value = sample_deployments[:3]
        mock_repos.security_scan_repo.get_by_deployment.return_value = []

        # Mock build results - 2 successful, 1 failed
        def mock_get_builds(deployment_id):
            if deployment_id == "deploy-0":
                return [{"success": True}]
            elif deployment_id == "deploy-1":
                return [{"success": True}]
            elif deployment_id == "deploy-2":
                return [{"success": False}]
            return []

        mock_repos.build_result_repo.get_by_deployment = mock_get_builds

        analytics = DeploymentAnalytics()
        metrics = analytics.get_overall_metrics()

        # 2 successful out of 3 = 66.67%
        assert metrics.build_success_rate == pytest.approx(66.67, rel=0.1)


class TestDeploymentMetrics:
    """Test DeploymentMetrics dataclass."""

    def test_create_metrics(self):
        """Test creating DeploymentMetrics."""
        metrics = DeploymentMetrics(
            total_deployments=100,
            successful_deployments=85,
            failed_deployments=15,
            success_rate=85.0,
            average_duration_seconds=120.5,
            fastest_deployment_seconds=45.0,
            slowest_deployment_seconds=300.0,
            total_duration_seconds=12050.0
        )

        assert metrics.total_deployments == 100
        assert metrics.success_rate == 85.0
        assert metrics.average_duration_seconds == 120.5


class TestRepositoryStats:
    """Test RepositoryStats dataclass."""

    def test_create_repository_stats(self):
        """Test creating RepositoryStats."""
        now = datetime.now()
        stats = RepositoryStats(
            repository="user/repo",
            total_deployments=50,
            successful_deployments=45,
            failed_deployments=5,
            success_rate=90.0,
            average_duration_seconds=100.0,
            last_deployment_at=now,
            last_deployment_status="deployed"
        )

        assert stats.repository == "user/repo"
        assert stats.success_rate == 90.0
        assert stats.last_deployment_status == "deployed"


class TestTimeSeriesData:
    """Test TimeSeriesData dataclass."""

    def test_create_time_series_data(self):
        """Test creating TimeSeriesData."""
        now = datetime.now()
        data = TimeSeriesData(
            timestamp=now,
            total_count=10,
            success_count=8,
            failure_count=2,
            average_duration=120.0
        )

        assert data.total_count == 10
        assert data.success_count == 8
        assert data.failure_count == 2
        assert data.average_duration == 120.0
