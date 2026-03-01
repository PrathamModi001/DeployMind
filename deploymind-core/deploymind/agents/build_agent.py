"""Build Agent - Dockerfile generation and Docker image building."""

import os
from pathlib import Path

from crewai import Agent
from crewai.tools import tool

from deploymind.shared.secure_logging import get_logger

logger = get_logger(__name__)


@tool("Detect Language")
def detect_language(repo_path: str) -> str:
    """Detect the programming language and framework of a repository.

    Args:
        repo_path: Absolute path to the repository root directory.

    Returns:
        Human-readable summary string of the detected language, framework,
        entry point, package manager, and whether a Dockerfile already exists.
    """
    from deploymind.infrastructure.build.language_detector import LanguageDetector
    try:
        result = LanguageDetector().detect(repo_path)
        logger.info("Language detected", language=result.language, framework=str(result.framework))
        return result.to_summary()
    except Exception as e:
        logger.error("Language detection failed", error=str(e))
        return f"Detection failed: {e}"


@tool("Generate Dockerfile")
def generate_dockerfile(repo_path: str, language: str) -> str:
    """Generate an optimized multi-stage Dockerfile for the detected language/framework.

    Args:
        repo_path: Absolute path to the repository root directory.
        language: Language string returned by detect_language (used as hint).

    Returns:
        Path to the generated Dockerfile and a preview of its contents.
    """
    from deploymind.infrastructure.build.language_detector import LanguageDetector, DetectionResult
    from deploymind.infrastructure.build.dockerfile_generator import DockerfileGenerator
    try:
        detection = LanguageDetector().detect(repo_path)
        generated = DockerfileGenerator().generate(detection)

        dockerfile_path = Path(repo_path) / "Dockerfile"
        dockerignore_path = Path(repo_path) / ".dockerignore"

        dockerfile_path.write_text(generated.content, encoding="utf-8")
        if not dockerignore_path.exists():
            dockerignore_path.write_text(generated.dockerignore_content, encoding="utf-8")

        logger.info(
            "Dockerfile generated",
            language=generated.language,
            multi_stage=generated.is_multi_stage,
            port=generated.exposed_port,
        )
        preview = generated.content[:500] + "..." if len(generated.content) > 500 else generated.content
        return (
            f"Dockerfile written to: {dockerfile_path}\n"
            f"Language: {generated.language} | Multi-stage: {generated.is_multi_stage} | Port: {generated.exposed_port}\n\n"
            f"Preview:\n{preview}"
        )
    except Exception as e:
        logger.error("Dockerfile generation failed", error=str(e))
        return f"Dockerfile generation failed: {e}"


@tool("Build Docker Image")
def build_docker_image(dockerfile_path: str, image_tag: str) -> str:
    """Build a Docker image from a Dockerfile using the local Docker daemon.

    Args:
        dockerfile_path: Absolute path to the Dockerfile.
        image_tag: Tag for the resulting image (e.g. 'myapp:v1.0').

    Returns:
        Build result summary including success status, image size, and duration.
    """
    from deploymind.infrastructure.build.docker_builder import DockerBuilder
    try:
        context_path = str(Path(dockerfile_path).parent)
        result = DockerBuilder().build(
            image_tag=image_tag,
            dockerfile_path=dockerfile_path,
            context_path=context_path,
        )
        if result.success:
            return (
                f"Build SUCCEEDED\n"
                f"Image: {image_tag}\n"
                f"Size: {result.image_size_mb} MB\n"
                f"Layers: {result.layers}\n"
                f"Duration: {result.duration_seconds:.1f}s\n"
                f"ID: {result.image_id}"
            )
        else:
            return (
                f"Build FAILED\n"
                f"Image: {image_tag}\n"
                f"Error: {result.error_message}\n"
                f"Log (last 20 lines):\n" + "\n".join(result.build_log.splitlines()[-20:])
            )
    except Exception as e:
        logger.error("Docker build tool failed", error=str(e))
        return f"Docker build failed: {e}"


@tool("Optimize Docker Image")
def optimize_docker_image(dockerfile_content: str) -> str:
    """Analyze a Dockerfile for security issues and optimization opportunities.

    Args:
        dockerfile_content: The full text content of the Dockerfile to analyze.

    Returns:
        Scored report of findings with severity (error/warning/info) and suggestions.
    """
    from deploymind.infrastructure.build.dockerfile_optimizer import DockerfileOptimizer
    try:
        optimizer = DockerfileOptimizer()
        findings = optimizer.analyze(dockerfile_content)
        score = optimizer.get_score(findings)

        if not findings:
            return f"Dockerfile score: 100/100 — No issues found."

        lines = [f"Dockerfile score: {score}/100\n"]
        for f in findings:
            lines.append(f"[{f.severity.value.upper()}] {f.rule_id}: {f.message}")
            lines.append(f"  → {f.suggestion}")
        return "\n".join(lines)
    except Exception as e:
        logger.error("Dockerfile optimization analysis failed", error=str(e))
        return f"Optimization analysis failed: {e}"


def create_build_agent(llm: str = "groq/llama-3.1-70b-versatile") -> Agent:
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
