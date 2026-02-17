"""Deploy Agent - Rolling deployment, health checks, and automatic rollback.

This agent is responsible for executing deployments to AWS EC2 instances,
performing health checks, and triggering automatic rollbacks on failure.
"""

from crewai import Agent
from crewai.tools import tool

from deploymind.config.settings import Settings
from deploymind.infrastructure.cloud.aws.ec2_client import EC2Client
from deploymind.infrastructure.monitoring.health_checker import HealthChecker
from deploymind.infrastructure.deployment.rolling_deployer import RollingDeployer
from deploymind.shared.secure_logging import get_logger

logger = get_logger(__name__)

# Global instances (initialized when agent is created)
_rolling_deployer: RollingDeployer | None = None
_ec2_client: EC2Client | None = None
_health_checker: HealthChecker | None = None


def _get_deployer() -> RollingDeployer:
    """Get global RollingDeployer instance."""
    global _rolling_deployer
    if _rolling_deployer is None:
        settings = Settings.load()
        _initialize_deployer(settings)
    return _rolling_deployer


def _initialize_deployer(settings: Settings) -> None:
    """Initialize global deployer instances."""
    global _rolling_deployer, _ec2_client, _health_checker
    _ec2_client = EC2Client(settings)
    _health_checker = HealthChecker(timeout=30, max_retries=5, retry_delay=10)
    _rolling_deployer = RollingDeployer(
        ec2_client=_ec2_client,
        health_checker=_health_checker,
        health_check_duration=120,
        health_check_interval=10
    )
    logger.info("Deploy agent infrastructure initialized")


@tool("Deploy Container")
def deploy_container(
    deployment_id: str,
    instance_id: str,
    image_tag: str,
    container_name: str = "app",
    port: int = 8080,
    health_check_path: str = "/health",
    previous_image_tag: str = None
) -> str:
    """Deploy a Docker container to an EC2 instance using rolling deployment.

    Performs zero-downtime deployment with automatic health checking and rollback.

    Args:
        deployment_id: Unique deployment identifier
        instance_id: AWS EC2 instance ID (e.g., 'i-1234567890abcdef0')
        image_tag: Docker image tag to deploy (e.g., 'myrepo/myapp:v1.0')
        container_name: Name for the container (default: 'app')
        port: Application port (default: 8080)
        health_check_path: Health check endpoint path (default: '/health')
        previous_image_tag: Previous image tag for rollback (optional)

    Returns:
        String describing deployment outcome (success or failure with details)
    """
    logger.info(
        f"Deploy container tool called",
        extra={
            "deployment_id": deployment_id,
            "instance_id": instance_id,
            "image_tag": image_tag
        }
    )

    try:
        deployer = _get_deployer()
        result = deployer.deploy(
            deployment_id=deployment_id,
            instance_id=instance_id,
            image_tag=image_tag,
            container_name=container_name,
            port=port,
            health_check_path=health_check_path,
            previous_image_tag=previous_image_tag
        )

        if result.success:
            return (
                f"✓ Deployment successful!\n"
                f"Deployment ID: {deployment_id}\n"
                f"Container ID: {result.container_id}\n"
                f"Image: {image_tag}\n"
                f"Instance: {instance_id}\n"
                f"Health checks: PASSED\n"
                f"Duration: {result.deployment_duration_seconds}s"
            )
        else:
            rollback_msg = " (rollback performed)" if result.rollback_performed else ""
            return (
                f"✗ Deployment failed{rollback_msg}\n"
                f"Deployment ID: {deployment_id}\n"
                f"Image: {image_tag}\n"
                f"Instance: {instance_id}\n"
                f"Error: {result.error_message}\n"
                f"Duration: {result.deployment_duration_seconds}s"
            )

    except Exception as e:
        logger.error(f"Deploy container tool failed", extra={"error": str(e)})
        return f"✗ Deployment failed: {str(e)}"


@tool("Health Check")
def health_check(
    instance_id: str,
    port: int = 8080,
    path: str = "/health",
    check_type: str = "http"
) -> str:
    """Run health checks against a deployed application.

    Supports HTTP, TCP, and command-based health checks.

    Args:
        instance_id: AWS EC2 instance ID
        port: Application port (default: 8080)
        path: Health check endpoint path (default: '/health')
        check_type: Type of check - 'http', 'tcp', or 'command' (default: 'http')

    Returns:
        String describing health check results
    """
    logger.info(
        f"Health check tool called",
        extra={"instance_id": instance_id, "port": port, "path": path, "check_type": check_type}
    )

    try:
        deployer = _get_deployer()
        ec2_client = deployer.ec2_client
        health_checker = deployer.health_checker

        # Get instance public IP
        public_ip = ec2_client.get_instance_public_ip(instance_id)
        if not public_ip:
            return f"✗ Health check failed: Instance {instance_id} has no public IP"

        if check_type == "http":
            url = f"http://{public_ip}:{port}{path}"
            result = health_checker.check_http(url)
        elif check_type == "tcp":
            result = health_checker.check_tcp(public_ip, port)
        else:
            return f"✗ Unsupported check type: {check_type}"

        if result.healthy:
            return (
                f"✓ Health check PASSED\n"
                f"Type: {check_type.upper()}\n"
                f"Instance: {instance_id}\n"
                f"Target: {public_ip}:{port}{path if check_type == 'http' else ''}\n"
                f"Status Code: {result.status_code}\n"
                f"Response Time: {result.response_time_ms}ms"
            )
        else:
            return (
                f"✗ Health check FAILED\n"
                f"Type: {check_type.upper()}\n"
                f"Instance: {instance_id}\n"
                f"Target: {public_ip}:{port}{path if check_type == 'http' else ''}\n"
                f"Error: {result.error_message}\n"
                f"Attempts: {result.attempt_number}/{result.max_attempts}"
            )

    except Exception as e:
        logger.error(f"Health check tool failed", extra={"error": str(e)})
        return f"✗ Health check failed: {str(e)}"


@tool("Rollback Deployment")
def rollback_deployment(
    deployment_id: str,
    instance_id: str,
    previous_image_tag: str,
    container_name: str = "app",
    port: int = 8080
) -> str:
    """Rollback to a previous deployment version.

    Stops the current container and redeploys the previous working version.

    Args:
        deployment_id: Deployment ID being rolled back
        instance_id: AWS EC2 instance ID
        previous_image_tag: Previous Docker image tag to restore
        container_name: Name of the container (default: 'app')
        port: Application port (default: 8080)

    Returns:
        String describing rollback outcome
    """
    logger.info(
        f"Rollback tool called",
        extra={
            "deployment_id": deployment_id,
            "instance_id": instance_id,
            "previous_image_tag": previous_image_tag
        }
    )

    try:
        deployer = _get_deployer()
        result = deployer.rollback(
            deployment_id=deployment_id,
            instance_id=instance_id,
            container_name=container_name,
            previous_image_tag=previous_image_tag,
            port=port
        )

        if result.success:
            return (
                f"✓ Rollback successful!\n"
                f"Deployment ID: {deployment_id}\n"
                f"Instance: {instance_id}\n"
                f"Restored Image: {previous_image_tag}\n"
                f"Duration: {result.deployment_duration_seconds}s"
            )
        else:
            return (
                f"✗ Rollback failed\n"
                f"Deployment ID: {deployment_id}\n"
                f"Instance: {instance_id}\n"
                f"Error: {result.error_message}\n"
                f"Duration: {result.deployment_duration_seconds}s"
            )

    except Exception as e:
        logger.error(f"Rollback tool failed", extra={"error": str(e)})
        return f"✗ Rollback failed: {str(e)}"


@tool("Check Deployment Status")
def check_deployment_status(instance_id: str, container_name: str = "app") -> str:
    """Check the current status of a deployment by checking container status.

    Args:
        instance_id: AWS EC2 instance ID
        container_name: Name of the container to check (default: 'app')

    Returns:
        String describing container status
    """
    logger.info(
        f"Check deployment status tool called",
        extra={"instance_id": instance_id, "container_name": container_name}
    )

    try:
        deployer = _get_deployer()
        ec2_client = deployer.ec2_client

        # Get container status
        status = ec2_client.get_container_status(instance_id, container_name)

        if status.get("running"):
            return (
                f"✓ Container RUNNING\n"
                f"Instance: {instance_id}\n"
                f"Container: {container_name}\n"
                f"Container ID: {status.get('container_id', 'N/A')}\n"
                f"Status: {status.get('status')}\n"
                f"Started At: {status.get('started_at', 'N/A')}"
            )
        else:
            return (
                f"✗ Container NOT RUNNING\n"
                f"Instance: {instance_id}\n"
                f"Container: {container_name}\n"
                f"Status: {status.get('status', 'not_found')}"
            )

    except Exception as e:
        logger.error(f"Check deployment status tool failed", extra={"error": str(e)})
        return f"✗ Status check failed: {str(e)}"


def create_deploy_agent(groq_api_key: str) -> Agent:
    """Create the Deploy Agent with its tools.

    The Deploy Agent is responsible for:
    - Rolling deployments to EC2 instances
    - Post-deployment health checking (2 minutes)
    - Automatic rollback on failure
    - Deployment status reporting

    Args:
        groq_api_key: Groq API key for LLM

    Returns:
        CrewAI Agent configured for deployment operations
    """
    from groq import Groq

    llm = Groq(api_key=groq_api_key, model="llama-3.1-70b-versatile")

    return Agent(
        role="Deployment Specialist",
        goal="Execute reliable rolling deployments to AWS EC2, monitor health, "
        "and automatically rollback on failure.",
        backstory=(
            "You are an expert in deployment automation and reliability "
            "engineering. You execute rolling deployments, monitor application "
            "health post-deployment for 2 minutes, and automatically trigger "
            "rollbacks when health checks fail. You prioritize zero-downtime "
            "deployments and fast recovery from failures. You understand Docker "
            "containers, AWS EC2, health check strategies, and rollback procedures."
        ),
        tools=[deploy_container, health_check, rollback_deployment, check_deployment_status],
        llm=llm,
        verbose=True,
        allow_delegation=False,
    )
