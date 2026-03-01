"""Application settings and configuration.

Migrated from core/config.py to follow Clean Architecture.
"""

import os
from dataclasses import dataclass
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)


@dataclass
class Settings:
    """Application settings loaded from environment variables.

    This is a singleton configuration object that loads all
    environment variables at application startup.
    """

    # Groq API (free tier: 1000 req/day)
    groq_api_key: str = ""
    default_llm: str = "llama-3.1-70b-versatile"  # Complex reasoning
    cost_saving_llm: str = "llama-3.1-8b-instant"  # Simple tasks

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
    max_deployment_time_seconds: int = 300
    health_check_interval_seconds: int = 10

    # Kubernetes
    kubeconfig_path: str = ""
    kubernetes_namespace: str = "default"
    kubernetes_cluster_name: str = ""

    @classmethod
    def load(cls, env_file: str | None = None) -> "Settings":
        """Load configuration from environment variables and optional .env file.

        Args:
            env_file: Optional path to .env file. If None, uses default location.

        Returns:
            Configured Settings instance.
        """
        if env_file:
            load_dotenv(env_file)
        else:
            load_dotenv(env_path)

        return cls(
            groq_api_key=os.getenv("GROQ_API_KEY", ""),
            default_llm=os.getenv("DEFAULT_LLM", "llama-3.1-70b-versatile"),
            cost_saving_llm=os.getenv("COST_SAVING_LLM", "llama-3.1-8b-instant"),
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
            max_deployment_time_seconds=int(
                os.getenv("MAX_DEPLOYMENT_TIME_SECONDS", "300")
            ),
            health_check_interval_seconds=int(
                os.getenv("HEALTH_CHECK_INTERVAL_SECONDS", "10")
            ),
            kubeconfig_path=os.getenv("KUBECONFIG_PATH", ""),
            kubernetes_namespace=os.getenv("KUBERNETES_NAMESPACE", "default"),
            kubernetes_cluster_name=os.getenv("KUBERNETES_CLUSTER_NAME", ""),
        )

    def validate(self) -> list[str]:
        """Validate configuration, returning a list of missing required variables.

        Returns:
            List of missing environment variable names.
        """
        required = {
            "GROQ_API_KEY": self.groq_api_key,
            "AWS_ACCESS_KEY_ID": self.aws_access_key_id,
            "AWS_SECRET_ACCESS_KEY": self.aws_secret_access_key,
            "GITHUB_TOKEN": self.github_token,
        }
        return [name for name, value in required.items() if not value]

    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.environment == "production"

    @property
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.environment == "development"


# Global settings instance (auto-loaded)
settings = Settings.load()
