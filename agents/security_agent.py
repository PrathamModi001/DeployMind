"""Security Agent - Trivy-based vulnerability scanning and CVE analysis."""

from crewai import Agent
from crewai.tools import tool

from core.logger import get_logger

logger = get_logger(__name__)


@tool("Scan Dockerfile")
def scan_dockerfile(dockerfile_path: str) -> str:
    """Scan a Dockerfile for security issues using Trivy."""
    raise NotImplementedError("Will be implemented on Day 2")


@tool("Scan Dependencies")
def scan_dependencies(requirements_path: str) -> str:
    """Scan project dependencies for known vulnerabilities."""
    raise NotImplementedError("Will be implemented on Day 2")


@tool("Check Secrets")
def check_secrets(repo_path: str) -> str:
    """Scan repository for accidentally committed secrets."""
    raise NotImplementedError("Will be implemented on Day 2")


def create_security_agent(llm: str = "claude-3-5-sonnet-20241022") -> Agent:
    """Create the Security Agent with its tools.

    The Security Agent is responsible for:
    - Scanning Dockerfiles for misconfigurations
    - Checking dependencies for known CVEs
    - Detecting accidentally committed secrets
    - Providing severity assessments and fix recommendations
    """
    return Agent(
        role="Security Specialist",
        goal="Ensure all deployments are secure by scanning for vulnerabilities, "
        "misconfigurations, and secrets before any code is deployed.",
        backstory=(
            "You are an expert in application security and container security. "
            "You use Trivy and other tools to identify CVEs, Dockerfile "
            "misconfigurations, and leaked secrets. You provide clear severity "
            "ratings and actionable fix recommendations. You block deployments "
            "that have critical or high severity vulnerabilities."
        ),
        tools=[scan_dockerfile, scan_dependencies, check_secrets],
        llm=llm,
        verbose=True,
        allow_delegation=False,
    )
