# DeployMind Architecture

**Pattern**: Clean Architecture (Hexagonal Architecture)
**Language**: Python 3.11+
**Frameworks**: CrewAI, FastAPI, SQLAlchemy

---

## 🏛️ Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     Presentation Layer                       │
│                  (CLI, REST API, WebUI)                      │
└────────────────────────┬────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────┐
│                    Application Layer                         │
│              (Use Cases, DTOs, Orchestration)                │
└────────────────────────┬────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────┐
│                      Domain Layer                            │
│         (Business Logic, Entities, Interfaces)               │
└────────────────────────┬────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────┐
│                   Infrastructure Layer                       │
│        (Database, Cloud APIs, External Services)             │
└─────────────────────────────────────────────────────────────┘
```

---

## 📁 Directory Structure

```
deploymind/
├── domain/                      # 🎯 CORE BUSINESS LOGIC (No external dependencies)
│   ├── __init__.py
│   ├── entities/                # Domain entities (core business objects)
│   │   ├── __init__.py
│   │   ├── deployment.py        # Deployment entity
│   │   ├── security_scan.py     # Security scan result entity
│   │   ├── build_result.py      # Build result entity
│   │   └── health_check.py      # Health check entity
│   ├── value_objects/           # Immutable value objects
│   │   ├── __init__.py
│   │   ├── deployment_status.py # Enum: pending, in_progress, success, failed
│   │   ├── deployment_strategy.py # Enum: rolling, canary, blue_green
│   │   └── security_severity.py # Enum: critical, high, medium, low
│   ├── repositories/            # Repository interfaces (ports)
│   │   ├── __init__.py
│   │   ├── deployment_repository.py
│   │   ├── security_scan_repository.py
│   │   └── build_repository.py
│   └── services/                # Domain services (business rules)
│       ├── __init__.py
│       ├── deployment_validator.py
│       └── rollback_strategy.py
│
├── application/                 # 📋 USE CASES & APPLICATION LOGIC
│   ├── __init__.py
│   ├── use_cases/               # Application use cases
│   │   ├── __init__.py
│   │   ├── deploy_application.py      # Main deployment use case
│   │   ├── scan_security.py           # Security scanning use case
│   │   ├── build_docker_image.py      # Build use case
│   │   ├── rollback_deployment.py     # Rollback use case
│   │   └── check_deployment_status.py # Status check use case
│   ├── dto/                     # Data Transfer Objects
│   │   ├── __init__.py
│   │   ├── deployment_request.py
│   │   ├── deployment_response.py
│   │   ├── security_scan_result.py
│   │   └── build_result.py
│   └── interfaces/              # Application service interfaces
│       ├── __init__.py
│       ├── llm_service.py       # LLM provider interface
│       ├── cloud_service.py     # Cloud provider interface
│       └── vcs_service.py       # Version control interface
│
├── infrastructure/              # 🔌 EXTERNAL DEPENDENCIES & ADAPTERS
│   ├── __init__.py
│   ├── database/                # Database implementations
│   │   ├── __init__.py
│   │   ├── models.py            # SQLAlchemy models
│   │   ├── connection.py        # Database connection
│   │   └── repositories/        # Repository implementations
│   │       ├── __init__.py
│   │       ├── deployment_repo_impl.py
│   │       ├── security_scan_repo_impl.py
│   │       └── build_repo_impl.py
│   ├── cloud/                   # Cloud provider clients
│   │   ├── __init__.py
│   │   ├── aws/
│   │   │   ├── __init__.py
│   │   │   ├── ec2_client.py    # AWS EC2 operations
│   │   │   ├── ecr_client.py    # AWS ECR (Docker registry)
│   │   │   └── ssm_client.py    # AWS SSM (commands)
│   │   └── adapters/
│   │       ├── __init__.py
│   │       └── cloud_service_adapter.py
│   ├── vcs/                     # Version Control Systems
│   │   ├── __init__.py
│   │   ├── github/
│   │   │   ├── __init__.py
│   │   │   └── github_client.py
│   │   └── adapters/
│   │       ├── __init__.py
│   │       └── vcs_service_adapter.py
│   ├── cache/                   # Caching layer
│   │   ├── __init__.py
│   │   └── redis_client.py
│   ├── llm/                     # LLM providers
│   │   ├── __init__.py
│   │   ├── groq/
│   │   │   ├── __init__.py
│   │   │   └── groq_client.py
│   │   └── adapters/
│   │       ├── __init__.py
│   │       └── llm_service_adapter.py
│   ├── security/                # Security tools
│   │   ├── __init__.py
│   │   └── trivy_scanner.py
│   └── containers/              # Container tools
│       ├── __init__.py
│       └── docker_client.py
│
├── agents/                      # 🤖 AI AGENTS (Orchestration Layer)
│   ├── __init__.py
│   ├── base/                    # Base agent classes
│   │   ├── __init__.py
│   │   └── base_agent.py
│   ├── security/                # Security agent
│   │   ├── __init__.py
│   │   ├── agent.py
│   │   └── tools.py
│   ├── build/                   # Build agent
│   │   ├── __init__.py
│   │   ├── agent.py
│   │   └── tools.py
│   ├── deploy/                  # Deploy agent
│   │   ├── __init__.py
│   │   ├── agent.py
│   │   └── tools.py
│   └── orchestrator/            # Orchestrator agent
│       ├── __init__.py
│       ├── agent.py
│       └── crew.py
│
├── presentation/                # 🖥️ USER INTERFACES
│   ├── __init__.py
│   ├── cli/                     # Command-line interface
│   │   ├── __init__.py
│   │   ├── main.py
│   │   ├── commands/
│   │   │   ├── __init__.py
│   │   │   ├── deploy.py
│   │   │   ├── status.py
│   │   │   └── rollback.py
│   │   └── formatters/
│   │       ├── __init__.py
│   │       └── output.py
│   └── api/                     # REST API (FastAPI)
│       ├── __init__.py
│       ├── main.py
│       ├── routes/
│       │   ├── __init__.py
│       │   ├── deployments.py
│       │   ├── health.py
│       │   └── status.py
│       └── middleware/
│           ├── __init__.py
│           └── error_handler.py
│
├── config/                      # ⚙️ CONFIGURATION
│   ├── __init__.py
│   ├── settings.py              # Environment configuration
│   ├── logging.py               # Logging configuration
│   └── dependencies.py          # Dependency injection
│
├── shared/                      # 🔄 SHARED UTILITIES
│   ├── __init__.py
│   ├── exceptions.py            # Custom exceptions
│   ├── constants.py             # Application constants
│   └── utils.py                 # Utility functions
│
├── tests/                       # 🧪 TESTS (mirrors structure)
│   ├── unit/
│   │   ├── domain/
│   │   ├── application/
│   │   └── infrastructure/
│   ├── integration/
│   │   ├── test_deployment_flow.py
│   │   └── test_agent_coordination.py
│   └── e2e/
│       └── test_full_deployment.py
│
├── scripts/                     # 📜 UTILITY SCRIPTS
│   ├── verify_credentials.py
│   ├── setup_database.py
│   └── seed_data.py
│
├── docker-compose.yml
├── requirements.txt
├── .env.example
├── .env
└── README.md
```

---

## 🔄 Dependency Flow (Clean Architecture Rule)

**Rule**: Dependencies point INWARD only.

```
Presentation → Application → Domain ← Infrastructure
                                ↑
                              Agents
```

- ✅ **Presentation** can depend on **Application** and **Domain**
- ✅ **Application** can depend on **Domain** only
- ✅ **Domain** depends on NOTHING (pure business logic)
- ✅ **Infrastructure** implements **Domain** interfaces
- ✅ **Agents** use **Application** use cases

- ❌ **Domain** NEVER depends on **Infrastructure**
- ❌ **Application** NEVER depends on **Infrastructure** directly
- ❌ **Domain** NEVER depends on **Agents**

---

## 📦 Layer Responsibilities

### 1. Domain Layer (Core Business Logic)

**What it contains**:
- Entities: `Deployment`, `SecurityScan`, `BuildResult`
- Value Objects: `DeploymentStatus`, `SecuritySeverity`
- Repository Interfaces: Define how to persist entities
- Domain Services: Complex business rules

**Rules**:
- ❌ NO framework dependencies (no SQLAlchemy, no FastAPI)
- ❌ NO infrastructure code (no boto3, no requests)
- ✅ Pure Python dataclasses/Pydantic models
- ✅ Business rules only

**Example**:
```python
# domain/entities/deployment.py
from dataclasses import dataclass
from datetime import datetime
from domain.value_objects.deployment_status import DeploymentStatus

@dataclass
class Deployment:
    id: str
    repository: str
    instance_id: str
    status: DeploymentStatus
    created_at: datetime

    def can_rollback(self) -> bool:
        """Business rule: Can only rollback deployed/failed deployments"""
        return self.status in [DeploymentStatus.DEPLOYED, DeploymentStatus.FAILED]
```

---

### 2. Application Layer (Use Cases)

**What it contains**:
- Use Cases: `DeployApplication`, `ScanSecurity`, `RollbackDeployment`
- DTOs: Input/output data structures
- Interfaces: Abstract contracts for external services

**Rules**:
- ✅ Orchestrates domain objects
- ✅ Calls domain services
- ✅ Depends on domain interfaces only
- ❌ NO direct infrastructure calls

**Example**:
```python
# application/use_cases/deploy_application.py
from domain.repositories.deployment_repository import DeploymentRepository
from application.dto.deployment_request import DeploymentRequest
from application.interfaces.cloud_service import CloudService

class DeployApplication:
    def __init__(
        self,
        deployment_repo: DeploymentRepository,
        cloud_service: CloudService
    ):
        self.deployment_repo = deployment_repo
        self.cloud_service = cloud_service

    def execute(self, request: DeploymentRequest):
        # Use case logic here
        deployment = self.deployment_repo.create(request)
        self.cloud_service.deploy(deployment)
        return deployment
```

---

### 3. Infrastructure Layer (External Services)

**What it contains**:
- Database implementations (SQLAlchemy)
- Cloud clients (boto3 for AWS)
- VCS clients (PyGithub)
- LLM clients (Groq)
- Cache (Redis)

**Rules**:
- ✅ Implements domain interfaces
- ✅ All external dependencies here
- ✅ Adapters pattern

**Example**:
```python
# infrastructure/cloud/aws/ec2_client.py
from application.interfaces.cloud_service import CloudService
import boto3

class EC2CloudService(CloudService):
    def __init__(self, access_key: str, secret_key: str):
        self.ec2 = boto3.client('ec2', ...)

    def deploy(self, deployment):
        # AWS-specific implementation
        self.ec2.run_instances(...)
```

---

### 4. Agents Layer (AI Orchestration)

**What it contains**:
- CrewAI agents
- Agent tools
- Crew coordination

**Rules**:
- ✅ Uses application use cases
- ✅ Orchestrates workflows
- ❌ NO direct infrastructure calls

**Example**:
```python
# agents/security/agent.py
from crewai import Agent
from application.use_cases.scan_security import ScanSecurity

class SecurityAgent:
    def __init__(self, scan_security_use_case: ScanSecurity):
        self.scan_security = scan_security_use_case

    def create_agent(self):
        return Agent(
            role="Security Specialist",
            tools=[self.scan_dockerfile, self.scan_dependencies]
        )
```

---

### 5. Presentation Layer (User Interfaces)

**What it contains**:
- CLI (Click)
- REST API (FastAPI)
- Web UI (future)

**Rules**:
- ✅ Calls application use cases
- ✅ Formats output for users
- ❌ NO business logic

**Example**:
```python
# presentation/cli/commands/deploy.py
import click
from application.use_cases.deploy_application import DeployApplication

@click.command()
@click.option('--repo', required=True)
def deploy(repo: str):
    use_case = DeployApplication(...)  # Injected via DI
    result = use_case.execute(repo)
    click.echo(f"Deployed: {result.id}")
```

---

## 🎯 Benefits of This Architecture

### 1. **Testability**
- Test domain logic without databases
- Mock external services easily
- Fast unit tests

### 2. **Flexibility**
- Swap AWS for GCP without touching domain
- Switch from Groq to Claude without changing use cases
- Add new interfaces (web UI) without changing core

### 3. **Maintainability**
- Clear separation of concerns
- Easy to find code
- Onboard new developers faster

### 4. **Scalability**
- Add features without breaking existing code
- Horizontal scaling (each layer can scale independently)

---

## 🔧 Dependency Injection

Use **dependency injection** to wire layers together:

```python
# config/dependencies.py
from infrastructure.database.repositories.deployment_repo_impl import DeploymentRepoImpl
from application.use_cases.deploy_application import DeployApplication
from infrastructure.cloud.aws.ec2_client import EC2CloudService

class DependencyContainer:
    def __init__(self):
        # Infrastructure
        self.deployment_repo = DeploymentRepoImpl()
        self.cloud_service = EC2CloudService()

        # Application
        self.deploy_use_case = DeployApplication(
            deployment_repo=self.deployment_repo,
            cloud_service=self.cloud_service
        )

# Singleton instance
container = DependencyContainer()
```

---

## 📝 File Naming Conventions

- **Entities**: `deployment.py`, `security_scan.py`
- **Use Cases**: `deploy_application.py`, `scan_security.py`
- **Repositories**: `deployment_repository.py` (interface), `deployment_repo_impl.py` (implementation)
- **Clients**: `ec2_client.py`, `github_client.py`
- **Tests**: `test_deployment.py`, `test_deploy_application.py`

---

## 🧪 Testing Strategy

```
tests/
├── unit/                        # Fast, isolated tests
│   ├── domain/                  # Test business logic
│   │   └── test_deployment.py
│   ├── application/             # Test use cases (mocked repos)
│   │   └── test_deploy_application.py
│   └── infrastructure/          # Test adapters
│       └── test_ec2_client.py
├── integration/                 # Test layer integration
│   └── test_deployment_flow.py
└── e2e/                         # Full system tests
    └── test_full_deployment.py
```

---

## 📚 References

- [Clean Architecture - Robert C. Martin](https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture.html)
- [Hexagonal Architecture](https://alistair.cockburn.us/hexagonal-architecture/)
- [Domain-Driven Design](https://martinfowler.com/bliki/DomainDrivenDesign.html)

---

**This architecture ensures DeployMind is maintainable, testable, and scalable.**
