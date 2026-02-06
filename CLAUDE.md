# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

### Environment Setup
```bash
# Create and activate virtual environment
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with API keys: GROQ_API_KEY, GITHUB_TOKEN, AWS credentials

# Start local services (PostgreSQL, Redis)
docker-compose up -d

# Initialize database
python -c "from infrastructure.database.connection import init_db; init_db()"
```

### Testing
```bash
# Run all tests
pytest tests/ -v

# Run specific test categories
pytest -m unit           # Unit tests only
pytest -m integration    # Integration tests
pytest -m trivy          # Tests requiring Trivy scanner
pytest -m "not aws"      # Exclude AWS integration tests

# Run with coverage
pytest tests/ --cov=deploymind --cov-report=html

# Run single test file
pytest tests/unit/domain/test_deployment.py -v

# Run specific test function
pytest tests/unit/infrastructure/test_trivy_scanner.py::TestTrivyScanner::test_scan_image_success -v
```

### Development
```bash
# Verify all credentials (AWS, GitHub, Groq)
python scripts/verify_all_credentials.py

# Verify architecture compliance
python scripts/verify_architecture.py

# Stop services
docker-compose down
```

## Architecture

DeployMind follows **Clean Architecture** (Hexagonal Architecture) with strict dependency rules.

### Dependency Flow
**Rule**: Dependencies point INWARD only.
```
Presentation → Application → Domain ← Infrastructure
                                ↑
                              Agents
```

**Key Principles**:
- Domain layer has ZERO external dependencies (pure Python)
- Application layer depends ONLY on domain interfaces, never infrastructure
- Infrastructure implements domain interfaces (adapter pattern)
- All external services isolated in infrastructure layer

### Layer Structure
```
deploymind/
├── domain/              # Pure business logic (no framework dependencies)
│   ├── entities/        # Deployment, SecurityScan, BuildResult, HealthCheck
│   ├── value_objects/   # DeploymentStatus, DeploymentStrategy, SecuritySeverity
│   ├── repositories/    # ABC interfaces defining persistence contracts
│   └── services/        # Business rules (deployment validation, rollback logic)
│
├── application/         # Use cases & workflows
│   ├── use_cases/       # DeployApplication, ScanSecurity, RollbackDeployment
│   ├── dto/             # Data transfer objects for input/output
│   └── interfaces/      # Abstract service interfaces (CloudService, VCSService)
│
├── infrastructure/      # External service adapters
│   ├── cloud/aws/       # EC2Client (boto3)
│   ├── vcs/github/      # GitHubClient (PyGithub)
│   ├── llm/groq/        # GroqClient (Groq SDK)
│   ├── cache/           # RedisClient
│   ├── database/        # SQLAlchemy ORM (6 tables), repository implementations
│   └── security/        # TrivyScanner (Docker-based)
│
├── agents/              # AI agent orchestration (CrewAI)
│   ├── orchestrator.py  # Crew coordinator with sequential workflow
│   ├── security_agent.py
│   ├── build_agent.py
│   └── deploy_agent.py
│
├── presentation/        # User interfaces
│   └── cli/             # Click-based CLI
│
├── config/              # Settings & dependency injection
│   ├── settings.py      # Settings dataclass with .env loading
│   └── dependencies.py  # DependencyContainer for DI
│
└── shared/              # Cross-cutting utilities
    ├── validators.py    # 15+ security validators
    ├── secure_logging.py # Logger with secret redaction
    └── exceptions.py    # Custom exception hierarchy
```

### Multi-Agent System
Four AI agents powered by Groq LLM in sequential workflow:
```
Orchestrator Agent (Coordinator)
    ↓
Security Agent → Trivy scanning, CVE analysis, approve/reject decision
    ↓ (only if passed)
Build Agent → Dockerfile detection/generation, Docker build, optimization
    ↓ (only if successful)
Deploy Agent → Rolling deployment to EC2, health checks (2min), rollback if failed
```

**Implementation Pattern**:
- Each agent: `agents/{agent}_agent.py` with `create_{agent}_agent()` factory
- Agent properties: role, goal, backstory, tools (CrewAI decorators)
- Crew in `agents/orchestrator.py`: `create_deployment_crew()` with sequential tasks
- Agents use tool decorators (`@tool`) that wrap application use cases
- LLM: Groq API with `llama-3.1-70b-versatile` (complex) or `llama-3.1-8b-instant` (simple)

### Database Schema
6 PostgreSQL tables (SQLAlchemy ORM):
1. **deployments** - Main tracking (id, repository, commit_sha, instance_id, status, strategy, image_tag, timestamps, rollback info)
2. **security_scans** - Trivy results (scan_type, vulnerabilities JSON, severity counts, agent_decision, agent_reasoning)
3. **build_results** - Docker builds (dockerfile_path, detected_language, image_size, optimizations_applied, build_log)
4. **health_checks** - Application monitoring (check_type, healthy, status_code, response_time_ms, attempt_number)
5. **deployment_logs** - Audit trail (timestamp, level, agent, message, event_type, event_data JSON)
6. **agent_executions** - LLM tracking (agent_name, llm_model, tokens, cost_usd, duration_seconds)

**Repository Pattern**:
- Domain interface: `domain/repositories/{entity}_repository.py` (ABC)
- Implementation: `infrastructure/database/repositories/{entity}_repo_impl.py` (SQLAlchemy)
- Converts between database models and domain entities via `_to_domain()` method

### Dependency Injection
**DependencyContainer** (`config/dependencies.py`):
- Singleton instance: `container = DependencyContainer()`
- Wires infrastructure implementations to application use cases
- Validates all services on startup: `container.validate_all()`
- Usage: `from config.dependencies import container`

**Settings** (`config/settings.py`):
- Dataclass with environment variable loading via `python-dotenv`
- `Settings.load()` - Loads from `.env` file
- `settings.validate()` - Returns missing required variables
- Global instance: `settings = Settings.load()` (auto-loaded on import)

**Required Environment Variables**:
- `GROQ_API_KEY` - Groq LLM API key (free tier: https://console.groq.com/keys)
- `GITHUB_TOKEN` - GitHub personal access token
- `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION`
- `DATABASE_URL` - PostgreSQL connection (default: postgresql://admin:password@localhost:5432/deploymind)
- `REDIS_URL` - Redis connection (default: redis://localhost:6379)

### Security & Validation
**Input Validation** (`shared/validators.py`):
- `SecurityValidator` class with 15+ validators
- Key methods:
  - `validate_repository(repo)` - Owner/repo format, prevents path traversal
  - `validate_instance_id(instance_id)` - AWS EC2 ID format (i-[a-f0-9]{8,17})
  - `sanitize_docker_tag(tag)` - Removes injection characters
  - `validate_file_path(path)` - Prevents path traversal attacks
  - `validate_url(url)` - URL format and scheme validation
- Always validate user inputs before use

**Secret Redaction** (`shared/secure_logging.py`):
- All logs automatically redact 9 secret patterns: API keys, passwords, tokens, AWS keys
- `StructuredLogger` with `SecureFormatter` for JSON structured logs
- `AuditLogger` for security event tracking
- Never log raw user input - always sanitize first

**Trivy Scanner** (`infrastructure/security/trivy_scanner.py`):
- Docker-based (no binary download needed)
- `TrivyScanner.scan_image(image_name, severity)` - Scan Docker images
- `TrivyScanner.scan_filesystem(path, severity)` - Scan repository code
- Returns `TrivyScanResult` with severity counts and vulnerabilities list
- Pass/fail based on CRITICAL vulnerability count

## Development Patterns

### Adding New Features

**Add new cloud provider (e.g., GCP)**:
1. Create `infrastructure/cloud/gcp/gcp_client.py`
2. Implement `application/interfaces/cloud_service.py` interface
3. Update `config/dependencies.py` to inject GCP client
4. Application layer needs NO changes (dependency inversion)

**Add new AI agent**:
1. Create `agents/{agent}_agent.py` with `create_{agent}_agent()` factory
2. Define: role, goal, backstory, tools (CrewAI decorators)
3. Add task to `agents/orchestrator.py` crew with description and expected_output
4. Tools should wrap application use cases, not call infrastructure directly

**Add new database table**:
1. Create SQLAlchemy model in `infrastructure/database/models.py`
2. Add relationship to `Deployment` model if tracking per-deployment
3. Create repository interface in `domain/repositories/`
4. Implement in `infrastructure/database/repositories/`
5. Run `init_db()` to create tables

**Add security validator**:
1. Add method to `SecurityValidator` class in `shared/validators.py`
2. Use regex patterns or string checks
3. Raise `ValidationError` on invalid input
4. Add test in `tests/unit/test_validators.py`

### Testing Patterns

**Test Structure** (mirrors source):
```
tests/
├── unit/           # Fast, isolated (mocked dependencies)
├── integration/    # Layer integration (real services)
└── e2e/            # Full system tests
```

**Fixtures** (`tests/conftest.py`):
- `mock_api_keys` - Auto-mocks API keys for all tests
- `config` - Test configuration with dummy values
- `env_vars` - Manages test environment variables with cleanup

**Mocking Pattern**:
```python
@patch('subprocess.run')  # Mock system calls
def test_trivy_scan(mock_run):
    mock_run.return_value = Mock(returncode=0, stdout='{"Results": []}')
    result = scanner.scan_image("test:latest")
    assert result.passed
```

**Test Markers**:
- `@pytest.mark.unit` - Unit tests (no external dependencies)
- `@pytest.mark.integration` - Integration tests (requires services)
- `@pytest.mark.trivy` - Requires Trivy installed
- `@pytest.mark.aws` - Requires AWS credentials
- Run selective tests: `pytest -m "not aws"`

### Code Conventions

**Architecture Rules**:
- NEVER import infrastructure in domain layer
- NEVER import infrastructure in application layer (use interfaces only)
- Always inject dependencies via constructor (don't instantiate in classes)
- Use lazy initialization pattern for expensive clients (EC2, GitHub)

**File Organization**:
- Entities: `deployment.py` (domain/entities/)
- Use cases: `deploy_application.py` (application/use_cases/)
- Repository interface: `deployment_repository.py` (domain/repositories/)
- Repository implementation: `deployment_repo_impl.py` (infrastructure/database/repositories/)
- Tests: `test_deployment.py` (tests/unit/domain/)

**Naming**:
- Classes: PascalCase (`DeploymentRepository`)
- Functions/methods: snake_case (`validate_repository()`)
- Constants: UPPER_SNAKE_CASE (`REPO_PATTERN`)
- Private methods: `_to_domain()` (prefix with underscore)

**Error Handling**:
- Use custom exceptions from `shared/exceptions.py`
- Validate inputs at boundaries (CLI, API)
- Never expose internal errors to users
- Log exceptions with `logger.exception()` for stack traces

## Current Status

**Phase 1: Setup** - COMPLETE
- Clean Architecture implemented
- Database models created (6 tables)
- Infrastructure clients ready (AWS, GitHub, Groq, Redis)
- Dependency injection configured
- Security framework (60+ tests passing)

**Phase 2: Implementation** - IN PROGRESS
- Day 2: Security Agent (32/32 tests passing)
- Next: Build Agent with Dockerfile generation

See `docs/project/next-steps.md` for implementation roadmap.

## Key Files Reference

**Configuration**:
- `config/settings.py` - Environment configuration
- `config/dependencies.py` - Dependency injection container
- `.env.example` - Required environment variables template

**Architecture Docs**:
- `docs/architecture/clean-architecture.md` - Visual architecture guide
- `docs/architecture/database-models.md` - Database schema
- `docs/architecture/security-design.md` - Security framework

**Core Infrastructure**:
- `infrastructure/cloud/aws/ec2_client.py` - AWS EC2 operations
- `infrastructure/vcs/github/github_client.py` - GitHub API
- `infrastructure/llm/groq/groq_client.py` - Groq LLM
- `infrastructure/security/trivy_scanner.py` - Security scanning
- `infrastructure/database/models.py` - SQLAlchemy ORM

**Agents**:
- `agents/orchestrator.py` - Crew creation and task coordination
- `agents/security_agent.py` - Security scanning agent
- `agents/build_agent.py` - Docker build agent
- `agents/deploy_agent.py` - Deployment agent

**Shared**:
- `shared/validators.py` - Input validation and sanitization
- `shared/secure_logging.py` - Secure logging with secret redaction
- `shared/exceptions.py` - Custom exception hierarchy
