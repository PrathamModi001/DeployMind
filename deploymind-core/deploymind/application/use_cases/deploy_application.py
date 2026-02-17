"""Deploy application use case - Day 4 implementation.

This use case orchestrates the full deployment workflow:
1. Validate inputs
2. Create deployment record
3. Execute rolling deployment
4. Run health checks
5. Handle failures and rollback
6. Update deployment status
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from deploymind.config.settings import Settings
from deploymind.infrastructure.deployment.rolling_deployer import RollingDeployer, DeploymentResult
from deploymind.infrastructure.cloud.aws.ec2_client import EC2Client
from deploymind.infrastructure.monitoring.health_checker import HealthChecker
from deploymind.shared.validators import SecurityValidator
from deploymind.shared.secure_logging import get_logger
from deploymind.shared.exceptions import ValidationError, DeploymentError

logger = get_logger(__name__)


@dataclass
class DeployRequest:
    """Deployment request parameters."""

    deployment_id: str
    instance_id: str
    image_tag: str
    container_name: str = "app"
    port: int = 8080
    health_check_path: str = "/health"
    previous_image_tag: Optional[str] = None
    env_vars: Optional[dict[str, str]] = None
    repository: Optional[str] = None
    dockerfile_content: Optional[str] = None
    build_on_instance: bool = False


@dataclass
class DeployResponse:
    """Deployment response with results."""

    success: bool
    deployment_id: str
    instance_id: str
    image_tag: str
    container_id: Optional[str] = None
    error_message: Optional[str] = None
    rollback_performed: bool = False
    deployment_duration_seconds: Optional[int] = None
    health_check_passed: bool = False
    application_url: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class DeployApplicationUseCase:
    """Use case for deploying applications to AWS EC2 with rolling deployment strategy.

    Features:
    - Input validation (instance ID, image tag, port, etc.)
    - Rolling deployment with zero downtime
    - Automatic health checking (2 minutes)
    - Automatic rollback on failure
    - Detailed logging and error handling
    """

    def __init__(self, settings: Settings):
        """Initialize use case with required dependencies.

        Args:
            settings: Application settings
        """
        self.settings = settings
        self.validator = SecurityValidator()

        # Initialize infrastructure components
        self.ec2_client = EC2Client(settings)
        self.health_checker = HealthChecker(
            timeout=30,
            max_retries=5,
            retry_delay=10
        )
        self.rolling_deployer = RollingDeployer(
            ec2_client=self.ec2_client,
            health_checker=self.health_checker,
            health_check_duration=120,  # 2 minutes
            health_check_interval=10     # 10 seconds
        )

        logger.info("DeployApplicationUseCase initialized")

    def execute(self, request: DeployRequest) -> DeployResponse:
        """Execute deployment workflow.

        Args:
            request: DeployRequest with deployment parameters

        Returns:
            DeployResponse with deployment results

        Raises:
            ValidationError: If inputs are invalid
            DeploymentError: If deployment fails critically
        """
        start_time = datetime.utcnow()
        logger.info(
            "Starting deployment workflow",
            extra={
                "deployment_id": request.deployment_id,
                "instance_id": request.instance_id,
                "image_tag": request.image_tag
            }
        )

        # Step 1: Validate inputs
        self._validate_request(request)

        # Step 2: Execute rolling deployment
        deployment_result = self.rolling_deployer.deploy(
            deployment_id=request.deployment_id,
            instance_id=request.instance_id,
            image_tag=request.image_tag,
            container_name=request.container_name,
            port=request.port,
            health_check_path=request.health_check_path,
            env_vars=request.env_vars,
            previous_image_tag=request.previous_image_tag,
            repository=request.repository,
            dockerfile_content=request.dockerfile_content,
            build_on_instance=request.build_on_instance
        )

        # Step 3: Build response
        response = self._build_response(request, deployment_result, start_time)

        # Step 4: Log final outcome
        if response.success:
            logger.info(
                "Deployment workflow completed successfully",
                extra={
                    "deployment_id": request.deployment_id,
                    "duration_seconds": response.deployment_duration_seconds
                }
            )
        else:
            logger.error(
                "Deployment workflow failed",
                extra={
                    "deployment_id": request.deployment_id,
                    "error": response.error_message,
                    "rollback_performed": response.rollback_performed
                }
            )

        return response

    def _validate_request(self, request: DeployRequest) -> None:
        """Validate deployment request parameters.

        Args:
            request: DeployRequest to validate

        Raises:
            ValidationError: If any validation fails
        """
        logger.info("Validating deployment request")

        # Validate instance ID format
        if not self.validator.validate_instance_id(request.instance_id):
            raise ValidationError(
                f"Invalid instance ID format: {request.instance_id}. "
                f"Expected format: i-[a-f0-9]{{8,17}}"
            )

        # Validate Docker tag
        sanitized_tag = self.validator.sanitize_docker_tag(request.image_tag)
        if sanitized_tag != request.image_tag:
            raise ValidationError(
                f"Invalid characters in image tag: {request.image_tag}"
            )

        # Validate port range
        if not (1 <= request.port <= 65535):
            raise ValidationError(
                f"Invalid port number: {request.port}. Must be 1-65535"
            )

        # Validate health check path
        if not request.health_check_path.startswith("/"):
            raise ValidationError(
                f"Health check path must start with /: {request.health_check_path}"
            )

        # Validate container name (alphanumeric and hyphens only)
        if not request.container_name.replace("-", "").replace("_", "").isalnum():
            raise ValidationError(
                f"Invalid container name: {request.container_name}. "
                f"Use only alphanumeric characters, hyphens, and underscores"
            )

        # Validate environment variables (check for secrets in keys)
        if request.env_vars:
            for key in request.env_vars.keys():
                if any(
                    secret in key.lower()
                    for secret in ["password", "secret", "key", "token"]
                ):
                    logger.warning(
                        f"Environment variable name contains secret-like term",
                        extra={"key": key}
                    )

        logger.info("Request validation passed")

    def _build_response(
        self,
        request: DeployRequest,
        deployment_result: DeploymentResult,
        start_time: datetime
    ) -> DeployResponse:
        """Build deployment response from results.

        Args:
            request: Original deployment request
            deployment_result: Result from RollingDeployer
            start_time: Workflow start time

        Returns:
            DeployResponse with all details
        """
        # Construct application URL from instance public IP and port
        application_url = None
        if deployment_result.success:
            try:
                public_ip = self.ec2_client.get_instance_public_ip(request.instance_id)
                if public_ip:
                    application_url = f"http://{public_ip}:{request.port}"
            except Exception as e:
                logger.warning(f"Failed to get public IP for application URL: {e}")

        return DeployResponse(
            success=deployment_result.success,
            deployment_id=request.deployment_id,
            instance_id=request.instance_id,
            image_tag=request.image_tag,
            container_id=deployment_result.container_id,
            error_message=deployment_result.error_message,
            rollback_performed=deployment_result.rollback_performed,
            deployment_duration_seconds=deployment_result.deployment_duration_seconds,
            health_check_passed=(
                deployment_result.health_check_result.healthy
                if deployment_result.health_check_result
                else False
            ),
            application_url=application_url,
            started_at=start_time,
            completed_at=datetime.utcnow()
        )


class DeployApplication(DeployApplicationUseCase):
    """Alias for backward compatibility."""

    pass
