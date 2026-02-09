"""Full deployment workflow orchestrating Security, Build, and Deploy phases.

This use case coordinates the complete deployment pipeline:
1. Clone GitHub repository
2. Security scan with Trivy
3. Build Docker image
4. Deploy to EC2 with health checks
5. Rollback on failure
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional
import uuid

from config.settings import Settings
from infrastructure.vcs.github.github_client import GitHubClient
from infrastructure.cache.redis_client import RedisClient
from application.use_cases.scan_security import SecurityScanUseCase, SecurityScanRequest
from application.use_cases.build_application import BuildApplicationUseCase, BuildRequest
from application.use_cases.deploy_application import DeployApplicationUseCase, DeployRequest
from shared.validators import SecurityValidator
from shared.exceptions import ValidationError, SecurityScanError, BuildError, DeploymentError
from core.logger import get_logger

logger = get_logger(__name__)


@dataclass
class FullDeploymentRequest:
    """Request for full deployment workflow."""
    repository: str  # owner/repo
    instance_id: str  # EC2 instance ID
    port: int = 8080
    strategy: str = "rolling"
    health_check_path: str = "/health"
    environment: str = "production"


@dataclass
class FullDeploymentResponse:
    """Response from full deployment workflow."""
    success: bool
    deployment_id: str
    repository: str
    commit_sha: Optional[str] = None

    # Security phase
    security_passed: bool = False
    security_scan_id: Optional[str] = None
    vulnerabilities_found: int = 0

    # Build phase
    build_successful: bool = False
    image_tag: Optional[str] = None
    image_size_mb: Optional[float] = None

    # Deploy phase
    deployment_successful: bool = False
    container_id: Optional[str] = None
    health_check_passed: bool = False
    application_url: Optional[str] = None

    # Error handling
    error_phase: Optional[str] = None  # security, build, deploy
    error_message: Optional[str] = None
    rollback_performed: bool = False

    # Timing
    duration_seconds: Optional[float] = None


class FullDeploymentWorkflow:
    """Orchestrates the complete deployment pipeline."""

    def __init__(self, settings: Settings):
        """Initialize workflow with all required use cases.

        Args:
            settings: Application settings with API keys and configuration
        """
        self.settings = settings
        self.validator = SecurityValidator()

        # Infrastructure clients
        self.github_client = GitHubClient(settings)
        self.redis_client = RedisClient(settings.redis_url)

        # Use cases
        self.security_scan_use_case = SecurityScanUseCase(settings)
        self.build_use_case = BuildApplicationUseCase(settings)
        self.deploy_use_case = DeployApplicationUseCase(settings)

        logger.info("FullDeploymentWorkflow initialized")

    def execute(self, request: FullDeploymentRequest) -> FullDeploymentResponse:
        """Execute the full deployment workflow.

        Pipeline stages:
        1. Validate inputs
        2. Clone repository
        3. Security scan (BLOCKING - fail = stop)
        4. Build Docker image
        5. Deploy to EC2 with health checks
        6. Rollback on failure

        Args:
            request: Deployment request with repository and instance details

        Returns:
            Deployment response with results from all phases

        Raises:
            ValidationError: If inputs are invalid
            SecurityScanError: If security scan fails critically
            BuildError: If Docker build fails
            DeploymentError: If deployment fails
        """
        deployment_id = str(uuid.uuid4())[:8]
        start_time = datetime.now()

        logger.info(
            "Starting full deployment workflow",
            extra={
                "deployment_id": deployment_id,
                "repository": request.repository,
                "instance_id": request.instance_id
            }
        )

        # Publish start event
        self._publish_event("deployment_started", {
            "deployment_id": deployment_id,
            "repository": request.repository,
            "instance_id": request.instance_id,
            "timestamp": start_time.isoformat()
        })

        response = FullDeploymentResponse(
            success=False,
            deployment_id=deployment_id,
            repository=request.repository
        )

        try:
            # Stage 1: Validate inputs
            self._validate_request(request)

            # Stage 2: Clone repository and get commit SHA
            logger.info("Cloning repository", extra={"repository": request.repository})
            commit_sha, clone_path = self._clone_repository(request.repository)
            response.commit_sha = commit_sha

            # Stage 3: Security scan (BLOCKING)
            logger.info("Starting security scan phase", extra={"deployment_id": deployment_id})
            security_result = self._execute_security_scan(
                deployment_id, request.repository, commit_sha, clone_path
            )
            response.security_passed = security_result["passed"]
            response.security_scan_id = security_result["scan_id"]
            response.vulnerabilities_found = security_result["vulnerabilities"]

            if not security_result["passed"]:
                response.error_phase = "security"
                response.error_message = security_result["error"]
                self._publish_event("deployment_failed", {
                    "deployment_id": deployment_id,
                    "phase": "security",
                    "reason": response.error_message
                })
                return response

            # Stage 4: Build Docker image
            logger.info("Starting build phase", extra={"deployment_id": deployment_id})
            build_result = self._execute_build(
                deployment_id, request.repository, commit_sha, clone_path
            )
            response.build_successful = build_result["success"]
            response.image_tag = build_result["image_tag"]
            response.image_size_mb = build_result["image_size_mb"]

            if not build_result["success"]:
                response.error_phase = "build"
                response.error_message = build_result["error"]
                self._publish_event("deployment_failed", {
                    "deployment_id": deployment_id,
                    "phase": "build",
                    "reason": response.error_message
                })
                return response

            # Stage 5: Deploy to EC2
            logger.info("Starting deploy phase", extra={"deployment_id": deployment_id})

            # Read generated Dockerfile for building on instance
            import os
            dockerfile_path = os.path.join(clone_path, "Dockerfile")
            dockerfile_content = None
            if os.path.exists(dockerfile_path):
                with open(dockerfile_path, 'r') as f:
                    dockerfile_content = f.read()

            deploy_result = self._execute_deployment(
                deployment_id,
                request.instance_id,
                response.image_tag,
                request.port,
                request.health_check_path,
                request.repository,
                dockerfile_content
            )
            response.deployment_successful = deploy_result["success"]
            response.container_id = deploy_result.get("container_id")
            response.health_check_passed = deploy_result.get("health_check_passed", False)
            response.application_url = deploy_result.get("application_url")
            response.rollback_performed = deploy_result.get("rollback_performed", False)

            if not deploy_result["success"]:
                response.error_phase = "deploy"
                response.error_message = deploy_result["error"]
                self._publish_event("deployment_failed", {
                    "deployment_id": deployment_id,
                    "phase": "deploy",
                    "reason": response.error_message,
                    "rollback_performed": response.rollback_performed
                })
                return response

            # Success!
            response.success = True
            duration = (datetime.now() - start_time).total_seconds()
            response.duration_seconds = duration

            logger.info(
                "Deployment completed successfully",
                extra={
                    "deployment_id": deployment_id,
                    "duration_seconds": duration,
                    "image_tag": response.image_tag,
                    "application_url": response.application_url
                }
            )

            self._publish_event("deployment_completed", {
                "deployment_id": deployment_id,
                "success": True,
                "duration_seconds": duration,
                "image_tag": response.image_tag,
                "application_url": response.application_url
            })

            return response

        except ValidationError as e:
            response.error_phase = "validation"
            response.error_message = str(e)
            logger.error("Validation error", extra={"error": str(e)}, exc_info=True)
            return response

        except Exception as e:
            response.error_phase = "unknown"
            response.error_message = f"Unexpected error: {str(e)}"
            logger.error(
                "Unexpected error in deployment workflow",
                extra={"error": str(e)},
                exc_info=True
            )
            self._publish_event("deployment_failed", {
                "deployment_id": deployment_id,
                "phase": "unknown",
                "reason": str(e)
            })
            return response

    def _validate_request(self, request: FullDeploymentRequest) -> None:
        """Validate all inputs before starting workflow.

        Args:
            request: Deployment request to validate

        Raises:
            ValidationError: If any validation fails
        """
        # Validate repository format
        self.validator.validate_repository(request.repository)

        # Validate instance ID
        self.validator.validate_instance_id(request.instance_id)

        # Validate deployment strategy
        self.validator.validate_deployment_strategy(request.strategy)

        # Validate environment
        self.validator.validate_environment(request.environment)

        # Validate port
        self.validator.validate_port(request.port)

        # Validate health check path
        if not request.health_check_path.startswith("/"):
            raise ValidationError("Health check path must start with /")

        logger.info("Request validation passed")

    def _clone_repository(self, repository: str) -> tuple[str, str]:
        """Clone GitHub repository and get latest commit SHA.

        Args:
            repository: Repository in format owner/repo

        Returns:
            Tuple of (commit_sha, clone_path)

        Raises:
            Exception: If repository cannot be cloned
        """
        try:
            # Get repository details from GitHub API
            repo = self.github_client.get_repository(repository)
            default_branch = repo.default_branch

            # Clone repository to temp directory with unique ID
            import uuid
            import tempfile
            import os
            unique_id = str(uuid.uuid4())[:8]

            # Use cross-platform temp directory
            temp_base = tempfile.gettempdir()
            clone_path = os.path.join(temp_base, "deploymind", f"{repository.replace('/', '_')}_{unique_id}")

            self.github_client.clone_repository(repository, clone_path)

            # Get latest commit SHA from default branch
            commit_sha = repo.get_branch(default_branch).commit.sha

            logger.info(
                "Repository cloned successfully",
                extra={
                    "repository": repository,
                    "commit_sha": commit_sha,
                    "branch": default_branch,
                    "clone_path": clone_path
                }
            )

            return commit_sha, clone_path

        except Exception as e:
            logger.error(
                "Failed to clone repository",
                extra={"repository": repository, "error": str(e)},
                exc_info=True
            )
            raise

    def _execute_security_scan(
        self, deployment_id: str, repository: str, commit_sha: str, clone_path: str
    ) -> dict:
        """Execute security scan phase.

        Args:
            deployment_id: Unique deployment ID
            repository: Repository name
            commit_sha: Commit SHA to scan
            clone_path: Path to cloned repository

        Returns:
            Dictionary with scan results
        """
        self._publish_event("security_scan_started", {
            "deployment_id": deployment_id,
            "repository": repository
        })

        try:
            # Scan the cloned repository filesystem
            scan_request = SecurityScanRequest(
                deployment_id=deployment_id,
                target=clone_path,
                scan_type="filesystem",
                policy="strict"
            )

            scan_response = self.security_scan_use_case.execute(scan_request)

            # Extract results from response
            result = {
                "passed": scan_response.success,
                "scan_id": deployment_id,  # Use deployment_id as scan_id
                "vulnerabilities": scan_response.scan_result.total_vulnerabilities if scan_response.scan_result else 0,
                "error": scan_response.message if not scan_response.success else None
            }

            self._publish_event("security_scan_completed", {
                "deployment_id": deployment_id,
                "passed": result["passed"],
                "vulnerabilities": result["vulnerabilities"]
            })

            return result

        except Exception as e:
            logger.error(
                "Security scan failed",
                extra={"deployment_id": deployment_id, "error": str(e)},
                exc_info=True
            )
            return {
                "passed": False,
                "scan_id": None,
                "vulnerabilities": 0,
                "error": f"Security scan error: {str(e)}"
            }

    def _execute_build(
        self, deployment_id: str, repository: str, commit_sha: str, clone_path: str
    ) -> dict:
        """Execute Docker build phase.

        Args:
            deployment_id: Unique deployment ID
            repository: Repository name
            commit_sha: Commit SHA to build
            clone_path: Path to cloned repository

        Returns:
            Dictionary with build results
        """
        self._publish_event("build_started", {
            "deployment_id": deployment_id,
            "repository": repository
        })

        try:
            # Generate image tag from repository and commit (lowercase for Docker)
            image_tag = f"{repository.replace('/', '-')}:{commit_sha[:8]}".lower()

            build_request = BuildRequest(
                deployment_id=deployment_id,
                project_path=clone_path,
                image_tag=image_tag,
                analyze_with_ai=False  # Skip AI analysis for speed
            )

            build_response = self.build_use_case.execute(build_request)

            # Calculate image size (approximate from build result or default)
            image_size_mb = None
            if build_response.build_result and hasattr(build_response.build_result, 'image_size_mb'):
                image_size_mb = build_response.build_result.image_size_mb
            elif build_response.success:
                # Default estimate if not available
                image_size_mb = 150.0

            result = {
                "success": build_response.success,
                "image_tag": build_response.image_tag,
                "image_size_mb": image_size_mb,
                "error": build_response.message if not build_response.success else None
            }

            self._publish_event("build_completed", {
                "deployment_id": deployment_id,
                "success": result["success"],
                "image_tag": result["image_tag"],
                "image_size_mb": result["image_size_mb"]
            })

            return result

        except Exception as e:
            logger.error(
                "Build failed",
                extra={"deployment_id": deployment_id, "error": str(e)},
                exc_info=True
            )
            return {
                "success": False,
                "image_tag": None,
                "image_size_mb": None,
                "error": f"Build error: {str(e)}"
            }

    def _execute_deployment(
        self,
        deployment_id: str,
        instance_id: str,
        image_tag: str,
        port: int,
        health_check_path: str,
        repository: str = None,
        dockerfile_content: str = None
    ) -> dict:
        """Execute deployment to EC2 phase.

        Args:
            deployment_id: Unique deployment ID
            instance_id: EC2 instance ID
            image_tag: Docker image tag to deploy
            port: Application port
            health_check_path: Health check endpoint path
            repository: GitHub repository for building on instance
            dockerfile_content: Dockerfile content for building on instance

        Returns:
            Dictionary with deployment results
        """
        self._publish_event("deployment_started", {
            "deployment_id": deployment_id,
            "instance_id": instance_id,
            "image_tag": image_tag
        })

        try:
            deploy_request = DeployRequest(
                deployment_id=deployment_id,
                instance_id=instance_id,
                image_tag=image_tag,
                port=port,
                health_check_path=health_check_path,
                repository=repository,
                dockerfile_content=dockerfile_content,
                build_on_instance=True  # Always build on instance for now
            )

            deploy_response = self.deploy_use_case.execute(deploy_request)

            result = {
                "success": deploy_response.success,
                "container_id": deploy_response.container_id,
                "health_check_passed": deploy_response.health_check_passed,
                "application_url": deploy_response.application_url,
                "rollback_performed": deploy_response.rollback_performed,
                "error": deploy_response.error_message if not deploy_response.success else None
            }

            self._publish_event("deployment_completed", {
                "deployment_id": deployment_id,
                "success": result["success"],
                "container_id": result["container_id"],
                "health_check_passed": result["health_check_passed"],
                "rollback_performed": result["rollback_performed"]
            })

            return result

        except Exception as e:
            logger.error(
                "Deployment failed",
                extra={"deployment_id": deployment_id, "error": str(e)},
                exc_info=True
            )
            return {
                "success": False,
                "container_id": None,
                "health_check_passed": False,
                "application_url": None,
                "rollback_performed": False,
                "error": f"Deployment error: {str(e)}"
            }

    def _publish_event(self, event_type: str, data: dict) -> None:
        """Publish event to Redis for real-time tracking.

        Args:
            event_type: Type of event (deployment_started, security_scan_completed, etc.)
            data: Event data dictionary
        """
        try:
            event = {
                "event_type": event_type,
                "timestamp": datetime.now().isoformat(),
                **data
            }

            self.redis_client.publish_event("deploymind:events", event)

            logger.debug(
                "Event published",
                extra={"event_type": event_type, "data": data}
            )

        except Exception as e:
            # Don't fail the deployment if event publishing fails
            logger.warning(
                "Failed to publish event",
                extra={"event_type": event_type, "error": str(e)}
            )
