"""Build application use case.

Application layer orchestration for building Docker images.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from config.settings import Settings
from config.logging import get_logger
from infrastructure.build.language_detector import LanguageDetector, ProjectInfo
from infrastructure.build.dockerfile_optimizer import DockerfileOptimizer
from infrastructure.build.docker_builder import DockerBuilder, BuildResult
from agents.build.build_agent import BuildAgent, BuildAgentResult

logger = get_logger(__name__)


@dataclass
class BuildRequest:
    """Request to build Docker image."""

    deployment_id: str
    project_path: str
    image_tag: str | None = None
    analyze_with_ai: bool = True


@dataclass
class BuildResponse:
    """Response from build operation."""

    deployment_id: str
    success: bool
    image_name: str | None
    image_tag: str | None
    project_info: ProjectInfo | None
    build_result: BuildResult | None
    ai_analysis: BuildAgentResult | None
    message: str


class BuildApplicationUseCase:
    """Use case for building Docker images with AI assistance.

    Orchestrates:
    1. Language/framework detection
    2. Dockerfile generation/optimization
    3. Docker image building
    4. AI-powered analysis and recommendations
    """

    def __init__(self, settings: Settings):
        """Initialize build use case.

        Args:
            settings: Application settings
        """
        self.settings = settings
        self.language_detector = LanguageDetector()
        self.dockerfile_optimizer = DockerfileOptimizer()
        self.docker_builder = DockerBuilder()
        self.build_agent = BuildAgent(settings.groq_api_key)

    def execute(self, request: BuildRequest) -> BuildResponse:
        """Execute build workflow.

        Args:
            request: Build request with project path and options

        Returns:
            BuildResponse with build results and AI analysis
        """
        logger.info(
            "Starting build workflow",
            extra={
                "deployment_id": request.deployment_id,
                "project_path": request.project_path,
                "analyze_with_ai": request.analyze_with_ai
            }
        )

        project_path = Path(request.project_path)

        try:
            # Step 1: Detect language and framework
            logger.info("Detecting project language and framework")
            project_info = self.language_detector.detect(project_path)

            if not project_info:
                raise ValueError(f"Could not detect project type for {project_path}")

            logger.info(
                "Project detected",
                extra={
                    "language": project_info.language,
                    "framework": project_info.framework,
                    "package_manager": project_info.package_manager
                }
            )

            # Step 2: Generate or optimize Dockerfile
            dockerfile_path = project_path / "Dockerfile"

            if not dockerfile_path.exists():
                logger.info("Dockerfile not found, generating optimized Dockerfile")
                dockerfile_content = self.dockerfile_optimizer.optimize(
                    project_path=str(project_path),
                    project_info=project_info,
                    existing_dockerfile=None
                )
                logger.info("Dockerfile generated successfully")
            else:
                logger.info("Dockerfile exists, reading existing file")
                with open(dockerfile_path, 'r') as f:
                    dockerfile_content = f.read()

            # Step 3: Build Docker image
            logger.info("Building Docker image")

            # Determine image tag
            if request.image_tag:
                image_tag = request.image_tag
            else:
                # Auto-generate tag
                import time
                timestamp = int(time.time())
                image_tag = f"deploymind-{project_info.language}-{timestamp}"

            build_result = self.docker_builder.build(
                context_path=str(project_path),
                project_info=project_info,
                dockerfile_content=dockerfile_content,
                tag=image_tag
            )

            if not build_result.success:
                raise RuntimeError(f"Docker build failed: {build_result.error_message}")

            logger.info(
                "Docker image built successfully",
                extra={
                    "image_id": build_result.image_id,
                    "tag": image_tag,
                    "build_time": build_result.build_time_seconds
                }
            )

            # Step 4: AI-powered analysis (optional)
            ai_analysis = None
            if request.analyze_with_ai:
                try:
                    logger.info("Running AI-powered build analysis")
                    ai_analysis = self.build_agent.analyze_and_build(str(project_path))

                    logger.info(
                        "AI analysis complete",
                        extra={"recommendations_count": len(ai_analysis.recommendations)}
                    )
                except Exception as e:
                    logger.warning(
                        "AI analysis failed, continuing without it",
                        extra={"error": str(e)}
                    )

            # Step 5: Build response
            return BuildResponse(
                deployment_id=request.deployment_id,
                success=True,
                image_name=image_tag,
                image_tag=image_tag,
                project_info=project_info,
                build_result=build_result,
                ai_analysis=ai_analysis,
                message=(
                    f"✅ Successfully built {project_info.language} application. "
                    f"Image: {image_tag}, Build time: {build_result.build_time_seconds:.1f}s"
                )
            )

        except Exception as e:
            logger.error(
                "Build workflow failed",
                extra={
                    "deployment_id": request.deployment_id,
                    "error": str(e)
                },
                exc_info=True
            )

            return BuildResponse(
                deployment_id=request.deployment_id,
                success=False,
                image_name=None,
                image_tag=None,
                project_info=None,
                build_result=None,
                ai_analysis=None,
                message=f"❌ Build failed: {str(e)}"
            )
