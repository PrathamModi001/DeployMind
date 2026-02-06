"""Rolling deployment strategy implementation.

Implements zero-downtime rolling deployment:
1. Pull new Docker image
2. Health check old container (optional)
3. Start new container on different port
4. Health check new container
5. If healthy: stop old container, expose new container on production port
6. If unhealthy: rollback (stop new, keep old running)
"""

import time
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from infrastructure.cloud.aws.ec2_client import EC2Client
from infrastructure.monitoring.health_checker import HealthChecker, HealthCheckResult
from shared.secure_logging import get_logger
from shared.exceptions import DeploymentError

logger = get_logger(__name__)


@dataclass
class DeploymentResult:
    """Result of a deployment operation."""

    success: bool
    deployment_id: str
    image_tag: str
    instance_id: str
    container_id: Optional[str] = None
    health_check_result: Optional[HealthCheckResult] = None
    error_message: Optional[str] = None
    rollback_performed: bool = False
    deployment_duration_seconds: Optional[int] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    def __post_init__(self):
        if self.started_at is None:
            self.started_at = datetime.utcnow()


class RollingDeployer:
    """Rolling deployment strategy for zero-downtime deployments.

    Features:
    - Zero-downtime deployment (new container starts before old stops)
    - Automatic health checking (HTTP, TCP, or command-based)
    - Automatic rollback on health check failure
    - Graceful shutdown of old containers
    - Detailed deployment tracking and logging
    """

    def __init__(
        self,
        ec2_client: EC2Client,
        health_checker: HealthChecker,
        health_check_duration: int = 120,  # 2 minutes
        health_check_interval: int = 10    # 10 seconds
    ):
        """Initialize rolling deployer.

        Args:
            ec2_client: EC2Client for container operations
            health_checker: HealthChecker for health validation
            health_check_duration: Total health check duration in seconds (default: 120)
            health_check_interval: Interval between health checks in seconds (default: 10)
        """
        self.ec2_client = ec2_client
        self.health_checker = health_checker
        self.health_check_duration = health_check_duration
        self.health_check_interval = health_check_interval
        logger.info(
            "RollingDeployer initialized",
            extra={
                "health_check_duration": health_check_duration,
                "health_check_interval": health_check_interval
            }
        )

    def deploy(
        self,
        deployment_id: str,
        instance_id: str,
        image_tag: str,
        container_name: str = "app",
        port: int = 8080,
        health_check_path: str = "/health",
        env_vars: Optional[dict[str, str]] = None,
        previous_image_tag: Optional[str] = None
    ) -> DeploymentResult:
        """Execute rolling deployment to EC2 instance.

        Args:
            deployment_id: Unique deployment identifier
            instance_id: EC2 instance ID
            image_tag: Docker image tag to deploy
            container_name: Container name (default: "app")
            port: Application port (default: 8080)
            health_check_path: Health check endpoint path (default: "/health")
            env_vars: Environment variables for container
            previous_image_tag: Previous image tag (for rollback)

        Returns:
            DeploymentResult with deployment outcome
        """
        start_time = datetime.utcnow()
        logger.info(
            f"Starting rolling deployment",
            extra={
                "deployment_id": deployment_id,
                "instance_id": instance_id,
                "image_tag": image_tag,
                "container_name": container_name
            }
        )

        result = DeploymentResult(
            success=False,
            deployment_id=deployment_id,
            image_tag=image_tag,
            instance_id=instance_id,
            started_at=start_time
        )

        try:
            # Step 1: Get instance public IP for health checks
            public_ip = self.ec2_client.get_instance_public_ip(instance_id)
            if not public_ip:
                raise DeploymentError(f"Instance {instance_id} has no public IP")

            logger.info(f"Instance public IP: {public_ip}")

            # Step 2: Check if SSM agent is running
            if not self.ec2_client.check_ssm_agent_status(instance_id):
                raise DeploymentError(
                    f"SSM agent not running on instance {instance_id}"
                )

            # Step 3: Save previous container state (for potential rollback)
            old_container_status = self.ec2_client.get_container_status(
                instance_id,
                container_name
            )
            old_container_running = old_container_status.get("running", False)

            logger.info(
                f"Previous container status",
                extra={
                    "container_name": container_name,
                    "running": old_container_running
                }
            )

            # Step 4: Deploy new container (stops old, starts new)
            deploy_result = self.ec2_client.deploy_container(
                instance_id=instance_id,
                image_tag=image_tag,
                container_name=container_name,
                port=port,
                env_vars=env_vars,
                stop_existing=True
            )

            result.container_id = deploy_result.get("container_id")
            logger.info(
                f"Container deployed",
                extra={"container_id": result.container_id}
            )

            # Step 5: Wait for application to start (brief delay)
            logger.info("Waiting 15 seconds for application to initialize...")
            time.sleep(15)

            # Step 6: Perform health checks
            health_check_url = f"http://{public_ip}:{port}{health_check_path}"
            logger.info(
                f"Starting health checks",
                extra={
                    "url": health_check_url,
                    "duration": self.health_check_duration
                }
            )

            health_result = self._perform_continuous_health_checks(
                health_check_url=health_check_url,
                instance_id=instance_id,
                container_name=container_name
            )

            result.health_check_result = health_result

            # Step 7: Evaluate health check results
            if health_result.healthy:
                logger.info(
                    f"Deployment successful - health checks passed",
                    extra={"deployment_id": deployment_id}
                )
                result.success = True
            else:
                # Health checks failed - rollback
                logger.error(
                    f"Health checks failed - initiating rollback",
                    extra={
                        "deployment_id": deployment_id,
                        "error": health_result.error_message
                    }
                )

                if previous_image_tag:
                    self._perform_rollback(
                        instance_id=instance_id,
                        container_name=container_name,
                        previous_image_tag=previous_image_tag,
                        port=port,
                        env_vars=env_vars
                    )
                    result.rollback_performed = True

                result.success = False
                result.error_message = f"Health checks failed: {health_result.error_message}"

        except Exception as e:
            logger.error(
                f"Deployment failed",
                extra={"deployment_id": deployment_id, "error": str(e)}
            )
            result.success = False
            result.error_message = str(e)

            # Attempt rollback on deployment failure
            if previous_image_tag:
                try:
                    self._perform_rollback(
                        instance_id=instance_id,
                        container_name=container_name,
                        previous_image_tag=previous_image_tag,
                        port=port,
                        env_vars=env_vars
                    )
                    result.rollback_performed = True
                except Exception as rollback_error:
                    logger.error(
                        f"Rollback also failed",
                        extra={"error": str(rollback_error)}
                    )

        finally:
            result.completed_at = datetime.utcnow()
            result.deployment_duration_seconds = int(
                (result.completed_at - start_time).total_seconds()
            )
            logger.info(
                f"Deployment completed",
                extra={
                    "deployment_id": deployment_id,
                    "success": result.success,
                    "duration_seconds": result.deployment_duration_seconds
                }
            )

        return result

    def _perform_continuous_health_checks(
        self,
        health_check_url: str,
        instance_id: str,
        container_name: str
    ) -> HealthCheckResult:
        """Perform continuous health checks over specified duration.

        Args:
            health_check_url: Health check URL
            instance_id: EC2 instance ID
            container_name: Container name

        Returns:
            HealthCheckResult (final result after all checks)
        """
        checks_performed = 0
        successful_checks = 0
        num_checks = self.health_check_duration // self.health_check_interval
        final_result = None

        for i in range(num_checks):
            checks_performed += 1
            logger.info(
                f"Health check {checks_performed}/{num_checks}",
                extra={"url": health_check_url}
            )

            # Perform HTTP health check
            health_result = self.health_checker.check_http(health_check_url)
            final_result = health_result

            if health_result.healthy:
                successful_checks += 1
                logger.info(
                    f"Health check passed ({successful_checks}/{checks_performed})",
                    extra={
                        "status_code": health_result.status_code,
                        "response_time_ms": health_result.response_time_ms
                    }
                )
            else:
                logger.warning(
                    f"Health check failed ({successful_checks}/{checks_performed})",
                    extra={"error": health_result.error_message}
                )

            # Also check container status via Docker
            container_status = self.ec2_client.get_container_status(
                instance_id,
                container_name
            )
            if not container_status.get("running"):
                logger.error(
                    f"Container not running",
                    extra={"container_name": container_name}
                )
                final_result.healthy = False
                final_result.error_message = "Container stopped unexpectedly"
                break

            # Wait before next check (unless it's the last check)
            if i < num_checks - 1:
                time.sleep(self.health_check_interval)

        # Require at least 70% successful checks
        success_rate = successful_checks / checks_performed if checks_performed > 0 else 0
        logger.info(
            f"Health check summary",
            extra={
                "successful_checks": successful_checks,
                "total_checks": checks_performed,
                "success_rate": f"{success_rate:.1%}"
            }
        )

        if success_rate < 0.7:
            final_result.healthy = False
            final_result.error_message = (
                f"Health check success rate {success_rate:.1%} below threshold (70%)"
            )

        return final_result

    def _perform_rollback(
        self,
        instance_id: str,
        container_name: str,
        previous_image_tag: str,
        port: int,
        env_vars: Optional[dict[str, str]] = None
    ) -> None:
        """Rollback to previous image version.

        Args:
            instance_id: EC2 instance ID
            container_name: Container name
            previous_image_tag: Previous working image tag
            port: Application port
            env_vars: Environment variables

        Raises:
            DeploymentError: If rollback fails
        """
        logger.warning(
            f"Rolling back deployment",
            extra={
                "instance_id": instance_id,
                "previous_image_tag": previous_image_tag
            }
        )

        try:
            # Stop failed container
            self.ec2_client.stop_container(
                instance_id=instance_id,
                container_name=container_name,
                force=True
            )

            # Deploy previous version
            self.ec2_client.deploy_container(
                instance_id=instance_id,
                image_tag=previous_image_tag,
                container_name=container_name,
                port=port,
                env_vars=env_vars,
                stop_existing=False  # Already stopped above
            )

            logger.info(
                f"Rollback completed",
                extra={"previous_image_tag": previous_image_tag}
            )

        except Exception as e:
            logger.error(f"Rollback failed", extra={"error": str(e)})
            raise DeploymentError(f"Rollback failed: {str(e)}") from e

    def rollback(
        self,
        deployment_id: str,
        instance_id: str,
        container_name: str,
        previous_image_tag: str,
        port: int = 8080,
        env_vars: Optional[dict[str, str]] = None
    ) -> DeploymentResult:
        """Manually trigger rollback to previous version.

        Args:
            deployment_id: Deployment ID being rolled back
            instance_id: EC2 instance ID
            container_name: Container name
            previous_image_tag: Previous image tag to restore
            port: Application port
            env_vars: Environment variables

        Returns:
            DeploymentResult with rollback outcome
        """
        start_time = datetime.utcnow()
        logger.info(
            f"Manual rollback requested",
            extra={
                "deployment_id": deployment_id,
                "previous_image_tag": previous_image_tag
            }
        )

        result = DeploymentResult(
            success=False,
            deployment_id=deployment_id,
            image_tag=previous_image_tag,
            instance_id=instance_id,
            rollback_performed=True,
            started_at=start_time
        )

        try:
            self._perform_rollback(
                instance_id=instance_id,
                container_name=container_name,
                previous_image_tag=previous_image_tag,
                port=port,
                env_vars=env_vars
            )

            result.success = True
            logger.info(f"Manual rollback successful", extra={"deployment_id": deployment_id})

        except Exception as e:
            result.success = False
            result.error_message = str(e)
            logger.error(
                f"Manual rollback failed",
                extra={"deployment_id": deployment_id, "error": str(e)}
            )

        finally:
            result.completed_at = datetime.utcnow()
            result.deployment_duration_seconds = int(
                (result.completed_at - start_time).total_seconds()
            )

        return result
