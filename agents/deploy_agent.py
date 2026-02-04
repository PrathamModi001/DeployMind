"""Deploy Agent - Rolling deployment, health checks, and automatic rollback."""

from crewai import Agent
from crewai.tools import tool

from core.logger import get_logger

logger = get_logger(__name__)


@tool("Deploy Container")
def deploy_container(instance_id: str, image_tag: str, port: int = 8080) -> str:
    """Deploy a Docker container to an EC2 instance."""
    raise NotImplementedError("Will be implemented on Day 4")


@tool("Health Check")
def health_check(instance_id: str, port: int = 8080, path: str = "/health") -> str:
    """Run health checks against a deployed application."""
    raise NotImplementedError("Will be implemented on Day 4")


@tool("Rollback Deployment")
def rollback_deployment(instance_id: str, previous_image_tag: str) -> str:
    """Rollback to a previous deployment version."""
    raise NotImplementedError("Will be implemented on Day 4")


@tool("Check Deployment Status")
def check_deployment_status(deployment_id: str) -> str:
    """Check the current status of a deployment."""
    raise NotImplementedError("Will be implemented on Day 4")


def create_deploy_agent(llm: str = "claude-3-5-sonnet-20241022") -> Agent:
    """Create the Deploy Agent with its tools.

    The Deploy Agent is responsible for:
    - Rolling deployments to EC2 instances
    - Post-deployment health checking
    - Automatic rollback on failure
    - Deployment status reporting
    """
    return Agent(
        role="Deployment Specialist",
        goal="Execute reliable rolling deployments to AWS EC2, monitor health, "
        "and automatically rollback on failure.",
        backstory=(
            "You are an expert in deployment automation and reliability "
            "engineering. You execute rolling deployments, monitor application "
            "health post-deployment for 1-5 minutes, and automatically trigger "
            "rollbacks when health checks fail. You prioritize zero-downtime "
            "deployments and fast recovery from failures."
        ),
        tools=[deploy_container, health_check, rollback_deployment, check_deployment_status],
        llm=llm,
        verbose=True,
        allow_delegation=False,
    )
