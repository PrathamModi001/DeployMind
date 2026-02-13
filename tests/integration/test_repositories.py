"""Integration tests for repository implementations.

Tests all repository persistence operations with real database.
"""

import pytest
from datetime import datetime
from domain.entities.deployment import Deployment
from infrastructure.database.repositories.deployment_repo_impl import DeploymentRepositoryImpl
from infrastructure.database.repositories.security_scan_repo_impl import SecurityScanRepositoryImpl
from infrastructure.database.repositories.build_result_repo_impl import BuildResultRepositoryImpl
from infrastructure.database.repositories.health_check_repo_impl import HealthCheckRepositoryImpl
from infrastructure.database.connection import get_db_session, init_db


@pytest.fixture(scope="module")
def db_session():
    """Create a test database session."""
    # Initialize database
    init_db()
    session = get_db_session()
    yield session
    session.close()


@pytest.fixture
def deployment_repo(db_session):
    """Create DeploymentRepository instance."""
    return DeploymentRepositoryImpl(db=db_session)


@pytest.fixture
def security_scan_repo(db_session):
    """Create SecurityScanRepository instance."""
    return SecurityScanRepositoryImpl(db=db_session)


@pytest.fixture
def build_result_repo(db_session):
    """Create BuildResultRepository instance."""
    return BuildResultRepositoryImpl(db=db_session)


@pytest.fixture
def health_check_repo(db_session):
    """Create HealthCheckRepository instance."""
    return HealthCheckRepositoryImpl(db=db_session)


@pytest.fixture
def sample_deployment():
    """Create a sample deployment entity with unique ID."""
    import uuid
    deployment = Deployment(
        id=f"test-{str(uuid.uuid4())[:8]}",  # Unique ID for each test
        repository="testuser/testrepo",
        instance_id="i-1234567890abcdef0",
        status="pending",
        created_at=datetime.now(),
        updated_at=datetime.now(),
        image_tag="testrepo:abc123"
    )
    # Add optional fields
    deployment.commit_sha = "abc1234567890"
    deployment.branch = "main"
    deployment.region = "us-east-1"
    deployment.strategy = "rolling"
    deployment.triggered_by = "manual"
    deployment.trigger_type = "manual"
    return deployment


class TestDeploymentRepository:
    """Test DeploymentRepository implementation."""

    def test_create_deployment(self, deployment_repo, sample_deployment):
        """Test creating a new deployment."""
        # Create deployment
        created = deployment_repo.create(sample_deployment)

        # Verify created deployment
        assert created.id == sample_deployment.id
        assert created.repository == sample_deployment.repository
        assert created.instance_id == sample_deployment.instance_id
        assert created.status == sample_deployment.status
        assert created.image_tag == sample_deployment.image_tag
        assert created.commit_sha == sample_deployment.commit_sha
        assert created.branch == sample_deployment.branch

    def test_get_by_id(self, deployment_repo, sample_deployment):
        """Test retrieving deployment by ID."""
        # Create deployment
        deployment_repo.create(sample_deployment)

        # Retrieve by ID
        retrieved = deployment_repo.get_by_id(sample_deployment.id)

        # Verify retrieved deployment
        assert retrieved is not None
        assert retrieved.id == sample_deployment.id
        assert retrieved.repository == sample_deployment.repository
        assert retrieved.instance_id == sample_deployment.instance_id

    def test_update_deployment(self, deployment_repo, sample_deployment):
        """Test updating an existing deployment."""
        # Create deployment
        created = deployment_repo.create(sample_deployment)

        # Update status
        created.status = "deployed"
        created.updated_at = datetime.now()
        updated = deployment_repo.update(created)

        # Verify update
        assert updated.status == "deployed"
        assert updated.id == sample_deployment.id

    def test_list_all_deployments(self, deployment_repo):
        """Test listing all deployments with pagination."""
        # List deployments (limit=10)
        deployments = deployment_repo.list_all(limit=10)

        # Verify list
        assert isinstance(deployments, list)
        assert len(deployments) <= 10

    def test_get_by_repository(self, deployment_repo, sample_deployment):
        """Test getting deployments by repository name."""
        # Create deployment
        deployment_repo.create(sample_deployment)

        # Get by repository
        deployments = deployment_repo.get_by_repository(sample_deployment.repository)

        # Verify results
        assert isinstance(deployments, list)
        assert len(deployments) >= 1
        assert any(d.repository == sample_deployment.repository for d in deployments)

    def test_get_by_status(self, deployment_repo, sample_deployment):
        """Test getting deployments by status."""
        # Create deployment
        deployment_repo.create(sample_deployment)

        # Get by status
        deployments = deployment_repo.get_by_status("pending")

        # Verify results
        assert isinstance(deployments, list)
        assert all(d.status == "pending" for d in deployments)

    def test_count(self, deployment_repo):
        """Test counting all deployments."""
        count = deployment_repo.count()
        assert isinstance(count, int)
        assert count >= 0


class TestSecurityScanRepository:
    """Test SecurityScanRepository implementation."""

    def test_create_security_scan(self, security_scan_repo, sample_deployment, deployment_repo):
        """Test creating a security scan record."""
        # Create deployment first
        deployment_repo.create(sample_deployment)

        # Create security scan
        scan_data = {
            "scan_type": "filesystem",
            "scanner": "trivy",
            "scan_started_at": datetime.now(),
            "scan_completed_at": datetime.now(),
            "passed": True,
            "total_vulnerabilities": 5,
            "critical_count": 0,
            "high_count": 1,
            "medium_count": 2,
            "low_count": 2,
            "vulnerabilities": [],
            "agent_decision": "pass",
            "agent_reasoning": "No critical vulnerabilities found"
        }

        created_scan = security_scan_repo.create(sample_deployment.id, scan_data)

        # Verify created scan
        assert created_scan["deployment_id"] == sample_deployment.id
        assert created_scan["scan_type"] == "filesystem"
        assert created_scan["scanner"] == "trivy"
        assert created_scan["passed"] is True
        assert created_scan["total_vulnerabilities"] == 5
        assert created_scan["critical_count"] == 0
        assert created_scan["high_count"] == 1

    def test_get_by_deployment(self, security_scan_repo, sample_deployment, deployment_repo):
        """Test retrieving security scans by deployment ID."""
        # Create deployment first
        deployment_repo.create(sample_deployment)

        # Create security scan
        scan_data = {
            "scan_type": "filesystem",
            "scanner": "trivy",
            "passed": True,
            "total_vulnerabilities": 0
        }
        security_scan_repo.create(sample_deployment.id, scan_data)

        # Retrieve scans
        scans = security_scan_repo.get_by_deployment(sample_deployment.id)

        # Verify results
        assert isinstance(scans, list)
        assert len(scans) >= 1
        assert all(scan["deployment_id"] == sample_deployment.id for scan in scans)

    def test_get_latest_for_deployment(self, security_scan_repo, sample_deployment, deployment_repo):
        """Test getting the latest security scan for a deployment."""
        # Create deployment first
        deployment_repo.create(sample_deployment)

        # Create security scan
        scan_data = {
            "scan_type": "filesystem",
            "scanner": "trivy",
            "passed": True,
            "total_vulnerabilities": 0
        }
        security_scan_repo.create(sample_deployment.id, scan_data)

        # Get latest scan
        latest = security_scan_repo.get_latest_for_deployment(sample_deployment.id)

        # Verify result
        assert latest is not None
        assert latest["deployment_id"] == sample_deployment.id


class TestBuildResultRepository:
    """Test BuildResultRepository implementation."""

    def test_create_build_result(self, build_result_repo, sample_deployment, deployment_repo):
        """Test creating a build result record."""
        # Create deployment first
        deployment_repo.create(sample_deployment)

        # Create build result
        build_data = {
            "build_started_at": datetime.now(),
            "build_completed_at": datetime.now(),
            "build_duration_seconds": 45.5,
            "success": True,
            "exit_code": 0,
            "dockerfile_path": "Dockerfile",
            "dockerfile_generated": False,
            "detected_language": "python",
            "detected_framework": "fastapi",
            "image_id": "sha256:abc123",
            "image_tag": "testrepo:latest",
            "image_size_bytes": 157286400,  # 150 MB
            "layer_count": 12
        }

        created_build = build_result_repo.create(sample_deployment.id, build_data)

        # Verify created build
        assert created_build["deployment_id"] == sample_deployment.id
        assert created_build["success"] is True
        assert created_build["detected_language"] == "python"
        assert created_build["detected_framework"] == "fastapi"
        assert created_build["image_size_bytes"] == 157286400
        assert created_build["layer_count"] == 12

    def test_get_by_deployment(self, build_result_repo, sample_deployment, deployment_repo):
        """Test retrieving build results by deployment ID."""
        # Create deployment first
        deployment_repo.create(sample_deployment)

        # Create build result
        build_data = {
            "success": True,
            "image_tag": "testrepo:latest"
        }
        build_result_repo.create(sample_deployment.id, build_data)

        # Retrieve builds
        builds = build_result_repo.get_by_deployment(sample_deployment.id)

        # Verify results
        assert isinstance(builds, list)
        assert len(builds) >= 1
        assert all(build["deployment_id"] == sample_deployment.id for build in builds)


class TestHealthCheckRepository:
    """Test HealthCheckRepository implementation."""

    def test_create_health_check(self, health_check_repo, sample_deployment, deployment_repo):
        """Test creating a health check record."""
        # Create deployment first
        deployment_repo.create(sample_deployment)

        # Create health check
        check_data = {
            "check_type": "http",
            "check_url": "http://54.123.45.67:8080/health",
            "healthy": True,
            "status_code": 200,
            "response_time_ms": 45,
            "check_time": datetime.now(),
            "attempt_number": 1,
            "max_attempts": 5
        }

        created_check = health_check_repo.create(sample_deployment.id, check_data)

        # Verify created check
        assert created_check["deployment_id"] == sample_deployment.id
        assert created_check["check_type"] == "http"
        assert created_check["healthy"] is True
        assert created_check["status_code"] == 200
        assert created_check["response_time_ms"] == 45
        assert created_check["attempt_number"] == 1

    def test_get_by_deployment(self, health_check_repo, sample_deployment, deployment_repo):
        """Test retrieving health checks by deployment ID."""
        # Create deployment first
        deployment_repo.create(sample_deployment)

        # Create health check
        check_data = {
            "check_type": "http",
            "healthy": True,
            "status_code": 200
        }
        health_check_repo.create(sample_deployment.id, check_data)

        # Retrieve checks
        checks = health_check_repo.get_by_deployment(sample_deployment.id)

        # Verify results
        assert isinstance(checks, list)
        assert len(checks) >= 1
        assert all(check["deployment_id"] == sample_deployment.id for check in checks)

    def test_get_failed_checks(self, health_check_repo, sample_deployment, deployment_repo):
        """Test retrieving failed health checks."""
        # Create deployment first
        deployment_repo.create(sample_deployment)

        # Create failed health check
        check_data = {
            "check_type": "http",
            "healthy": False,
            "status_code": 503,
            "error_message": "Connection refused"
        }
        health_check_repo.create(sample_deployment.id, check_data)

        # Get failed checks
        failed_checks = health_check_repo.get_failed_checks(sample_deployment.id)

        # Verify results
        assert isinstance(failed_checks, list)
        assert all(check["healthy"] is False for check in failed_checks)
