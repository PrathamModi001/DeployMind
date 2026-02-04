"""Environment configuration loader for DeployMind."""

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv


@dataclass
class Config:
    """Application configuration loaded from environment variables."""

    # Anthropic
    anthropic_api_key: str = ""

    # AWS
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    aws_region: str = "us-east-1"

    # GitHub
    github_token: str = ""

    # Database
    database_url: str = "postgresql://admin:password@localhost:5432/deploymind"

    # Redis
    redis_url: str = "redis://localhost:6379"

    # Application
    environment: str = "development"
    log_level: str = "INFO"
    log_format: str = "json"

    # Agent configuration
    default_llm: str = "claude-3-5-sonnet-20241022"
    cost_saving_llm: str = "claude-3-haiku-20240307"
    max_deployment_time_seconds: int = 300
    health_check_interval_seconds: int = 10

    @classmethod
    def load(cls, env_file: str | None = None) -> "Config":
        """Load configuration from environment variables and optional .env file."""
        if env_file:
            load_dotenv(env_file)
        else:
            load_dotenv()

        return cls(
            anthropic_api_key=os.getenv("ANTHROPIC_API_KEY", ""),
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID", ""),
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY", ""),
            aws_region=os.getenv("AWS_REGION", "us-east-1"),
            github_token=os.getenv("GITHUB_TOKEN", ""),
            database_url=os.getenv(
                "DATABASE_URL",
                "postgresql://admin:password@localhost:5432/deploymind",
            ),
            redis_url=os.getenv("REDIS_URL", "redis://localhost:6379"),
            environment=os.getenv("ENVIRONMENT", "development"),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            log_format=os.getenv("LOG_FORMAT", "json"),
            default_llm=os.getenv("DEFAULT_LLM", "claude-3-5-sonnet-20241022"),
            cost_saving_llm=os.getenv("COST_SAVING_LLM", "claude-3-haiku-20240307"),
            max_deployment_time_seconds=int(
                os.getenv("MAX_DEPLOYMENT_TIME_SECONDS", "300")
            ),
            health_check_interval_seconds=int(
                os.getenv("HEALTH_CHECK_INTERVAL_SECONDS", "10")
            ),
        )

    def validate(self) -> list[str]:
        """Validate configuration, returning a list of missing required variables."""
        required = {
            "ANTHROPIC_API_KEY": self.anthropic_api_key,
            "AWS_ACCESS_KEY_ID": self.aws_access_key_id,
            "AWS_SECRET_ACCESS_KEY": self.aws_secret_access_key,
            "GITHUB_TOKEN": self.github_token,
        }
        return [name for name, value in required.items() if not value]

    @property
    def is_production(self) -> bool:
        return self.environment == "production"
