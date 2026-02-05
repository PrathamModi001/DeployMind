"""SQLAlchemy database models for DeployMind.

These models represent the data persistence layer and map
domain entities to database tables.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Column, String, Integer, DateTime, ForeignKey, Text,
    Boolean, JSON, Enum as SQLEnum, Float
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
import enum

Base = declarative_base()


# Enums
class DeploymentStatusEnum(str, enum.Enum):
    """Deployment status values."""
    PENDING = "pending"
    SECURITY_SCANNING = "security_scanning"
    SECURITY_FAILED = "security_failed"
    BUILDING = "building"
    BUILD_FAILED = "build_failed"
    DEPLOYING = "deploying"
    DEPLOYED = "deployed"
    FAILED = "failed"
    ROLLING_BACK = "rolling_back"
    ROLLED_BACK = "rolled_back"


class DeploymentStrategyEnum(str, enum.Enum):
    """Deployment strategy types."""
    ROLLING = "rolling"
    CANARY = "canary"
    BLUE_GREEN = "blue_green"


class SecuritySeverityEnum(str, enum.Enum):
    """Security vulnerability severity levels."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


# Models
class Deployment(Base):
    """Main deployment tracking table.

    Stores information about each deployment attempt, including
    repository, target instance, status, and timestamps.
    """
    __tablename__ = "deployments"

    # Primary Key
    id = Column(String(50), primary_key=True)  # e.g., "deploy-20260204-abc123"

    # Repository Information
    repository = Column(String(255), nullable=False)  # e.g., "owner/repo"
    commit_sha = Column(String(40), nullable=True)  # Git commit SHA
    branch = Column(String(100), default="main")

    # Target Infrastructure
    instance_id = Column(String(50), nullable=False)  # AWS EC2 instance ID
    region = Column(String(20), default="us-east-1")

    # Deployment Configuration
    strategy = Column(SQLEnum(DeploymentStrategyEnum), default=DeploymentStrategyEnum.ROLLING)
    status = Column(SQLEnum(DeploymentStatusEnum), default=DeploymentStatusEnum.PENDING)

    # Docker Image
    image_tag = Column(String(255), nullable=True)  # e.g., "repo:commit-sha"
    image_size_mb = Column(Float, nullable=True)  # Image size in MB

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    # Deployment Duration
    duration_seconds = Column(Integer, nullable=True)

    # User/Trigger Information
    triggered_by = Column(String(100), nullable=True)  # User or system
    trigger_type = Column(String(50), default="manual")  # manual, webhook, scheduled

    # Rollback Information
    previous_deployment_id = Column(String(50), ForeignKey("deployments.id"), nullable=True)
    rollback_reason = Column(Text, nullable=True)

    # Additional metadata
    extra_data = Column(JSON, nullable=True)  # Additional deployment info

    # Relationships
    security_scans = relationship("SecurityScan", back_populates="deployment", cascade="all, delete-orphan")
    build_results = relationship("BuildResult", back_populates="deployment", cascade="all, delete-orphan")
    health_checks = relationship("HealthCheck", back_populates="deployment", cascade="all, delete-orphan")
    logs = relationship("DeploymentLog", back_populates="deployment", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Deployment(id={self.id}, repo={self.repository}, status={self.status})>"


class SecurityScan(Base):
    """Security scan results table.

    Stores results from Trivy security scans including vulnerabilities,
    severity levels, and recommendations.
    """
    __tablename__ = "security_scans"

    # Primary Key
    id = Column(Integer, primary_key=True, autoincrement=True)

    # Foreign Key
    deployment_id = Column(String(50), ForeignKey("deployments.id"), nullable=False)

    # Scan Information
    scan_type = Column(String(50), nullable=False)  # dockerfile, dependencies, secrets
    scanner = Column(String(50), default="trivy")
    scan_started_at = Column(DateTime, default=datetime.utcnow)
    scan_completed_at = Column(DateTime, nullable=True)
    scan_duration_seconds = Column(Integer, nullable=True)

    # Results
    passed = Column(Boolean, default=False)
    total_vulnerabilities = Column(Integer, default=0)
    critical_count = Column(Integer, default=0)
    high_count = Column(Integer, default=0)
    medium_count = Column(Integer, default=0)
    low_count = Column(Integer, default=0)

    # Detailed Results (JSON)
    vulnerabilities = Column(JSON, nullable=True)  # List of vulnerability objects
    recommendations = Column(JSON, nullable=True)  # AI-generated fix suggestions

    # Agent Decision
    agent_decision = Column(String(20), nullable=True)  # approve, reject, warn
    agent_reasoning = Column(Text, nullable=True)  # AI reasoning for decision

    # Metadata
    trivy_version = Column(String(20), nullable=True)
    scan_output = Column(Text, nullable=True)  # Raw scan output

    # Relationship
    deployment = relationship("Deployment", back_populates="security_scans")

    def __repr__(self):
        return f"<SecurityScan(id={self.id}, deployment={self.deployment_id}, passed={self.passed})>"


class BuildResult(Base):
    """Docker build results table.

    Stores information about Docker image builds including build logs,
    optimization suggestions, and build metrics.
    """
    __tablename__ = "build_results"

    # Primary Key
    id = Column(Integer, primary_key=True, autoincrement=True)

    # Foreign Key
    deployment_id = Column(String(50), ForeignKey("deployments.id"), nullable=False)

    # Build Information
    build_started_at = Column(DateTime, default=datetime.utcnow)
    build_completed_at = Column(DateTime, nullable=True)
    build_duration_seconds = Column(Integer, nullable=True)

    # Build Status
    success = Column(Boolean, default=False)
    exit_code = Column(Integer, nullable=True)

    # Dockerfile Information
    dockerfile_path = Column(String(255), default="Dockerfile")
    dockerfile_generated = Column(Boolean, default=False)  # Was Dockerfile auto-generated?
    detected_language = Column(String(50), nullable=True)  # nodejs, python, go
    detected_framework = Column(String(50), nullable=True)  # express, fastapi, gin

    # Image Information
    image_id = Column(String(255), nullable=True)  # Docker image ID
    image_tag = Column(String(255), nullable=True)  # Full image tag
    image_size_bytes = Column(Integer, nullable=True)
    layer_count = Column(Integer, nullable=True)

    # Optimization
    optimizations_applied = Column(JSON, nullable=True)  # List of optimizations
    original_size_bytes = Column(Integer, nullable=True)
    optimized_size_bytes = Column(Integer, nullable=True)
    size_reduction_percent = Column(Float, nullable=True)

    # Build Logs
    build_log = Column(Text, nullable=True)  # Full build output
    error_message = Column(Text, nullable=True)  # Error if build failed

    # Agent Suggestions
    agent_suggestions = Column(JSON, nullable=True)  # AI suggestions for improvement

    # Relationship
    deployment = relationship("Deployment", back_populates="build_results")

    def __repr__(self):
        return f"<BuildResult(id={self.id}, deployment={self.deployment_id}, success={self.success})>"


class HealthCheck(Base):
    """Health check results table.

    Stores results of health checks performed during and after deployment
    to ensure application is running correctly.
    """
    __tablename__ = "health_checks"

    # Primary Key
    id = Column(Integer, primary_key=True, autoincrement=True)

    # Foreign Key
    deployment_id = Column(String(50), ForeignKey("deployments.id"), nullable=False)

    # Check Information
    check_time = Column(DateTime, default=datetime.utcnow)
    check_type = Column(String(50), default="http")  # http, tcp, command
    check_url = Column(String(500), nullable=True)  # Health check endpoint

    # Results
    healthy = Column(Boolean, default=False)
    status_code = Column(Integer, nullable=True)  # HTTP status code
    response_time_ms = Column(Integer, nullable=True)
    response_body = Column(Text, nullable=True)

    # Instance Status
    instance_state = Column(String(20), nullable=True)  # running, stopped, etc.
    instance_status = Column(String(20), nullable=True)  # ok, impaired, etc.

    # Error Information
    error_message = Column(Text, nullable=True)

    # Retry Information
    attempt_number = Column(Integer, default=1)
    max_attempts = Column(Integer, default=5)

    # Relationship
    deployment = relationship("Deployment", back_populates="health_checks")

    def __repr__(self):
        return f"<HealthCheck(id={self.id}, deployment={self.deployment_id}, healthy={self.healthy})>"


class DeploymentLog(Base):
    """Deployment logs table.

    Stores chronological logs of deployment events for debugging
    and audit purposes.
    """
    __tablename__ = "deployment_logs"

    # Primary Key
    id = Column(Integer, primary_key=True, autoincrement=True)

    # Foreign Key
    deployment_id = Column(String(50), ForeignKey("deployments.id"), nullable=False)

    # Log Information
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    level = Column(String(10), default="INFO")  # DEBUG, INFO, WARNING, ERROR, CRITICAL
    agent = Column(String(50), nullable=True)  # security, build, deploy, orchestrator
    message = Column(Text, nullable=False)

    # Structured Data
    event_type = Column(String(50), nullable=True)  # scan_started, build_completed, etc.
    event_data = Column(JSON, nullable=True)  # Additional event data

    # Relationship
    deployment = relationship("Deployment", back_populates="logs")

    def __repr__(self):
        return f"<DeploymentLog(id={self.id}, level={self.level}, message={self.message[:50]}...)>"


class AgentExecution(Base):
    """Agent execution tracking table.

    Tracks individual agent executions within a deployment for
    performance monitoring and debugging.
    """
    __tablename__ = "agent_executions"

    # Primary Key
    id = Column(Integer, primary_key=True, autoincrement=True)

    # Foreign Key
    deployment_id = Column(String(50), ForeignKey("deployments.id"), nullable=False)

    # Agent Information
    agent_name = Column(String(50), nullable=False)  # security, build, deploy
    agent_version = Column(String(20), nullable=True)

    # Execution
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    duration_seconds = Column(Integer, nullable=True)
    success = Column(Boolean, default=False)

    # LLM Usage
    llm_model = Column(String(50), nullable=True)  # llama-3.1-70b-versatile
    llm_tokens_input = Column(Integer, nullable=True)
    llm_tokens_output = Column(Integer, nullable=True)
    llm_cost_usd = Column(Float, nullable=True)

    # Results
    output = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)

    def __repr__(self):
        return f"<AgentExecution(id={self.id}, agent={self.agent_name}, success={self.success})>"
