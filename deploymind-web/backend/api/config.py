"""API Configuration using Pydantic Settings."""
from pydantic_settings import BaseSettings
from typing import List
from pydantic import field_validator, Field


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Database
    database_url: str = "postgresql://admin:password@localhost:5432/deploymind"

    # Redis
    redis_url: str = "redis://localhost:6379"

    # JWT
    jwt_secret: str = "your-secret-key-change-this"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    # CORS - use str type to avoid Pydantic auto-parsing, then validate to list
    cors_origins_str: str = Field(default="http://localhost:5000", alias="CORS_ORIGINS")

    @property
    def cors_origins(self) -> List[str]:
        """Get CORS origins as a list."""
        v = self.cors_origins_str
        if isinstance(v, str):
            # If it's a single string, convert to list
            if v.startswith('['):
                # Try to parse as JSON
                import json
                try:
                    return json.loads(v)
                except:
                    pass
            # Split by comma for multiple origins, or return as single item list
            if ',' in v:
                return [origin.strip() for origin in v.split(',')]
            return [v.strip()]
        return [v]

    # API
    api_title: str = "DeployMind API"
    api_version: str = "1.0.0"
    api_description: str = "AI-Powered Deployment Platform API"

    # GitHub OAuth
    github_client_id: str
    github_client_secret: str
    github_redirect_uri: str = "http://localhost:5000/auth/callback"

    # GitHub Webhooks
    github_webhook_secret: str = ""
    api_base_url: str = "http://localhost:8000"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
