"""Example: Deploy a GitHub repository to AWS EC2 using DeployMind.

This example demonstrates how to use the DeployMind orchestrator
to run a full deployment pipeline:
  1. Security scan (Trivy + secrets check)
  2. Docker image build (auto-detect language, generate Dockerfile)
  3. Rolling deployment to EC2 (health checks + auto-rollback)

Prerequisites:
  - Set up .env with API keys (see .env.example)
  - Start local services: docker-compose up -d
  - AWS EC2 instance running with Docker installed

Usage:
  python -m examples.example_deploy
"""

from core.config import Config
from core.logger import get_logger
from agents.orchestrator import create_deployment_crew

logger = get_logger(__name__)


def main():
    # Load configuration
    config = Config.load()
    missing = config.validate()
    if missing:
        logger.error("Missing required config", extra={"missing": missing})
        print(f"Missing required environment variables: {', '.join(missing)}")
        print("Copy .env.example to .env and fill in your values.")
        return

    # Create the deployment crew
    crew = create_deployment_crew(
        repo_full_name="example-org/my-python-app",
        instance_id="i-0123456789abcdef0",
        strategy="rolling",
        llm=config.default_llm,
    )

    # Execute the pipeline (security -> build -> deploy)
    logger.info("Starting deployment pipeline")
    result = crew.kickoff()

    logger.info("Deployment complete", extra={"result": str(result)})
    print(f"\nDeployment result:\n{result}")


if __name__ == "__main__":
    main()
