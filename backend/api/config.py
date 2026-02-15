"""API Configuration using Pydantic Settings."""
from pydantic_settings import BaseSettings
from typing import List


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

    # CORS
    cors_origins: List[str] = ["http://localhost:3000", "http://localhost:3001"]

    # API
    api_title: str = "DeployMind API"
    api_version: str = "1.0.0"
    api_description: str = "AI-Powered Deployment Platform API"

    # GitHub OAuth (optional - for production)
    github_client_id: str = "mock_client_id"
    github_client_secret: str = "mock_client_secret"
    github_redirect_uri: str = "http://localhost:3000/auth/callback"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
