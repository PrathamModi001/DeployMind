# DeployMind

Multi-agent autonomous deployment system powered by AI.

## Quick Start

```bash
# 1. Create virtual environment
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment
cp .env.example .env
# Edit .env with your API keys

# 4. Start local services
docker-compose up -d

# 5. Run CLI
python -m cli.main --help
```

## Architecture

```
Orchestrator Agent (Coordinator)
    +-- Security Agent  (Trivy scanning, CVE checks)
    +-- Build Agent     (Dockerfile generation, Docker builds)
    +-- Deploy Agent    (Rolling deployment, health checks, rollback)
```

## Testing

```bash
pytest tests/ -v              # All tests
pytest -m unit                # Unit tests only
pytest -m "aws or github"    # Integration tests only
```
