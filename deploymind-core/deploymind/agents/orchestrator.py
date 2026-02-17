"""Orchestrator - Coordinates Security, Build, and Deploy agents."""

from crewai import Crew, Task

from deploymind.agents.security_agent import create_security_agent
from deploymind.agents.build_agent import create_build_agent
from deploymind.agents.deploy_agent import create_deploy_agent
from core.logger import get_logger

logger = get_logger(__name__)


def create_deployment_crew(
    repo_full_name: str,
    instance_id: str,
    strategy: str = "rolling",
    llm: str = "llama-3.1-70b-versatile",
) -> Crew:
    """Create a deployment crew that orchestrates the full pipeline.

    Pipeline: Security Scan -> Build Docker Image -> Deploy to EC2

    Args:
        repo_full_name: GitHub repository (owner/repo).
        instance_id: AWS EC2 instance ID to deploy to.
        strategy: Deployment strategy (only 'rolling' supported in MVP).
        llm: LLM model to use for agent reasoning.

    Returns:
        Configured CrewAI Crew ready to execute.
    """
    security_agent = create_security_agent(llm=llm)
    build_agent = create_build_agent(llm=llm)
    deploy_agent = create_deploy_agent(llm=llm)

    security_task = Task(
        description=(
            f"Scan the repository '{repo_full_name}' for security vulnerabilities. "
            "Check the Dockerfile, dependencies, and source code for secrets. "
            "Report all findings with severity levels. "
            "Block the deployment if any CRITICAL or HIGH severity issues are found."
        ),
        expected_output=(
            "A security report listing all vulnerabilities found, their severity "
            "(CRITICAL/HIGH/MEDIUM/LOW), and whether the deployment is approved or blocked."
        ),
        agent=security_agent,
    )

    build_task = Task(
        description=(
            f"Build a Docker image for the repository '{repo_full_name}'. "
            "Detect the language and framework, generate an optimized Dockerfile "
            "if one doesn't exist, and build the image. "
            "Tag the image with the latest commit SHA."
        ),
        expected_output=(
            "The Docker image tag that was built, along with the image size "
            "and any optimization recommendations applied."
        ),
        agent=build_agent,
    )

    deploy_task = Task(
        description=(
            f"Deploy the built Docker image to EC2 instance '{instance_id}' "
            f"using a {strategy} deployment strategy. "
            "Monitor health checks for 2 minutes after deployment. "
            "Automatically rollback if health checks fail."
        ),
        expected_output=(
            "Deployment status (SUCCESS/FAILED/ROLLED_BACK), the deployed "
            "image tag, health check results, and the application URL."
        ),
        agent=deploy_agent,
    )

    return Crew(
        agents=[security_agent, build_agent, deploy_agent],
        tasks=[security_task, build_task, deploy_task],
        process="sequential",
        verbose=True,
    )
