"""Build Agent - Dockerfile generation and Docker image building."""

from crewai import Agent
from crewai.tools import tool

from core.logger import get_logger

logger = get_logger(__name__)


@tool("Detect Language")
def detect_language(repo_path: str) -> str:
    """Detect the programming language and framework of a repository."""
    raise NotImplementedError("Will be implemented on Day 3")


@tool("Generate Dockerfile")
def generate_dockerfile(repo_path: str, language: str) -> str:
    """Generate an optimized Dockerfile for the detected language/framework."""
    raise NotImplementedError("Will be implemented on Day 3")


@tool("Build Docker Image")
def build_docker_image(dockerfile_path: str, image_tag: str) -> str:
    """Build a Docker image from a Dockerfile."""
    raise NotImplementedError("Will be implemented on Day 3")


@tool("Optimize Docker Image")
def optimize_docker_image(dockerfile_content: str) -> str:
    """Suggest optimizations for a Dockerfile (multi-stage builds, layer caching)."""
    raise NotImplementedError("Will be implemented on Day 3")


def create_build_agent(llm: str = "claude-3-5-sonnet-20241022") -> Agent:
    """Create the Build Agent with its tools.

    The Build Agent is responsible for:
    - Detecting project language and framework
    - Generating optimized Dockerfiles
    - Building Docker images
    - Suggesting image size optimizations
    """
    return Agent(
        role="Build Specialist",
        goal="Generate optimized Dockerfiles and build efficient Docker images "
        "for any supported language (Node.js, Python, Go).",
        backstory=(
            "You are an expert in containerization and Docker best practices. "
            "You can detect project languages and frameworks, generate "
            "production-ready Dockerfiles with multi-stage builds, and optimize "
            "images for minimal size and fast startup. You support Node.js, "
            "Python, and Go applications."
        ),
        tools=[detect_language, generate_dockerfile, build_docker_image, optimize_docker_image],
        llm=llm,
        verbose=True,
        allow_delegation=False,
    )
