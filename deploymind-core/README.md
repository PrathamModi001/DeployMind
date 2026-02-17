# DeployMind Core

Main Python application with Clean Architecture, multi-agent AI system, and CLI.

## Features

- **Clean Architecture**: Hexagonal architecture with clear separation of concerns
- **Multi-Agent System**: AI-powered deployment agents using Groq LLM
- **Security Scanning**: Trivy integration for vulnerability detection
- **AWS Deployment**: EC2 deployment with health checks and rollback
- **GitHub Integration**: Repository management and OAuth

## Quick Start

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
pip install -e .

# Configure environment
cp .env.example .env
# Edit .env with your API keys

# Start local services (PostgreSQL, Redis)
docker-compose up -d

# Initialize database
python -c "from deploymind.infrastructure.database.connection import init_db; init_db()"

# Run CLI
deploymind --help
```

## Project Structure

```
deploymind/
├── deploymind/              # Main package
│   ├── agents/              # AI agents (security, build, deploy)
│   ├── application/         # Use cases & workflows
│   ├── domain/              # Business entities & rules
│   ├── infrastructure/      # External service adapters
│   ├── config/              # Settings & dependency injection
│   ├── shared/              # Cross-cutting utilities
│   └── presentation/        # CLI interface
├── tests/                   # All tests
├── scripts/                 # Utility scripts
├── docs/                    # Documentation
└── docker-compose.yml       # Local services
```

## Testing

```bash
# Run all tests
pytest tests/ -v

# Run specific categories
pytest -m unit           # Unit tests only
pytest -m integration    # Integration tests

# Run with coverage
pytest tests/ --cov=deploymind --cov-report=html
```

## Development

```bash
# Verify credentials
python scripts/verify_all_credentials.py

# Verify architecture compliance
python scripts/verify_architecture.py

# Stop services
docker-compose down
```

## Documentation

- [Architecture Guide](docs/architecture/clean-architecture.md)
- [Database Schema](docs/architecture/database-models.md)
- [Security Design](docs/architecture/security-design.md)

## Environment Variables

See `.env.example` for required configuration:
- `GROQ_API_KEY` - Groq LLM API key
- `GITHUB_TOKEN` - GitHub personal access token
- `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION`
- `DATABASE_URL` - PostgreSQL connection string
- `REDIS_URL` - Redis connection string
