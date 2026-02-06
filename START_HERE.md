# START HERE - DeployMind Quick Context

**For New Claude Code Sessions: Read this file first for instant project context**

---

## Project Overview

**DeployMind** - Multi-agent autonomous deployment system powered by AI

**Status:** Day 1 Complete ✅ - Foundation set up, credentials verified, ready for Day 2 (Security Agent implementation)

**Tech Stack (All FREE):**
- AI Framework: CrewAI 1.9.3 (MIT license, 100% free)
- LLM: Groq API (FREE - 1000 requests/day)
- Cloud: AWS Free Tier (t2.micro, 12 months free)
- Database: PostgreSQL (Docker local)
- Cache: Redis (Docker local)
- Language: Python 3.13

**Total Cost:** $0 (using Groq free tier instead of Claude API)

---

## Current Project Status

### ✅ Completed

**Day 1 Tasks (Foundation):**
- [x] Project structure initialized (Clean Architecture)
- [x] Virtual environment set up with all dependencies
- [x] docker-compose.yml created (PostgreSQL + Redis)
- [x] PostgreSQL running and healthy
- [x] Redis running (lms-redis container on port 6379)
- [x] Environment variables configured (.env file)
- [x] All credentials verified (Groq, GitHub, AWS)
- [x] CrewAI license verified (MIT - free)
- [x] Basic agent files created (security_agent.py, build_agent.py, deploy_agent.py, orchestrator.py)
- [x] Testing infrastructure set up (pytest with markers)
- [x] Security validation framework implemented

**Credentials Status:**
- ✅ Groq API: Working (free tier)
- ✅ GitHub API: Working (PrathamModi001, 4999/5000 requests)
- ✅ AWS: Working (ap-south-1 region, 0 instances running)

### 🚧 Next Steps

**Day 2 Tasks (Security Agent):**
- [ ] Design Security Agent tools (scan_dockerfile, scan_dependencies, check_secrets, suggest_fix)
- [ ] Implement Trivy integration for security scanning
- [ ] Implement Security Agent with CrewAI
- [ ] Create decision logic (approve/reject/suggest fixes)
- [ ] Test with real repositories
- [ ] Write unit tests for Security Agent

---

## Quick Start Commands

### Development Environment

```bash
# Activate virtual environment
cd E:\devops\deploymind
.\venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac

# Check services status
docker-compose ps
docker exec lms-redis redis-cli ping  # Should return PONG

# Verify credentials (if needed)
PYTHONIOENCODING=utf-8 python verify_all_credentials.py
```

### Testing

```bash
# Run all tests
pytest tests/ -v

# Run specific test categories
pytest -m unit           # Unit tests only
pytest -m integration    # Integration tests
pytest -m aws            # AWS tests
pytest -m github         # GitHub tests

# Run with coverage
pytest --cov=agents --cov=core --cov-report=html
```

### Docker Services

```bash
# Start all services
docker-compose up -d

# Check service health
docker-compose ps

# View logs
docker-compose logs postgres
docker-compose logs redis  # Note: Using lms-redis instead

# Stop services
docker-compose down

# Redis commands (using existing container)
docker exec lms-redis redis-cli ping
docker exec lms-redis redis-cli INFO
```

### Database

```bash
# Initialize database
python -c "from infrastructure.database.connection import init_db; init_db()"

# Connect to PostgreSQL
docker exec -it deploymind-postgres psql -U admin -d deploymind

# Database URL
# postgresql://admin:password@localhost:5432/deploymind
```

---

## Project Structure

```
deploymind/
├── agents/                  # AI agents (Security, Build, Deploy, Orchestrator)
│   ├── security/            # Security agent implementation
│   ├── build/               # Build agent implementation
│   ├── deploy/              # Deploy agent implementation
│   └── orchestrator/        # Orchestrator agent
├── application/             # Use cases & workflows
├── infrastructure/          # External services (AWS, GitHub, Groq, Redis, Database)
├── domain/                  # Business logic (pure Python, no dependencies)
├── core/                    # Shared utilities (config, AWS client, GitHub client)
├── cli/                     # CLI interface (Click + Rich)
├── tests/                   # Test suite (pytest)
│   ├── unit/                # Unit tests
│   ├── integration/         # Integration tests
│   ├── e2e/                 # End-to-end tests
│   └── manual/              # Manual testing scripts
├── scripts/                 # Utility scripts
├── docs/                    # Documentation
├── .env                     # Environment variables (NEVER commit!)
├── docker-compose.yml       # Local development services
├── requirements.txt         # Python dependencies
└── pytest.ini               # Test configuration
```

**Architecture Pattern:** Clean Architecture (Hexagonal)
- Dependencies point inward only
- Domain layer has no external dependencies
- Infrastructure implements domain interfaces

---

## Environment Variables

**Location:** `E:\devops\deploymind\.env`

**Required Variables:**
```bash
# Groq API (FREE - 1000 requests/day)
GROQ_API_KEY=gsk_***

# AWS Free Tier
AWS_ACCESS_KEY_ID=AKIA***
AWS_SECRET_ACCESS_KEY=***
AWS_REGION=ap-south-1

# GitHub API (FREE - 5000 requests/hour)
GITHUB_TOKEN=ghp_***

# Database (local Docker)
DATABASE_URL=postgresql://admin:password@localhost:5432/deploymind

# Redis (local Docker)
REDIS_URL=redis://localhost:6379

# Application
ENVIRONMENT=development
LOG_LEVEL=INFO
```

---

## Common Issues & Solutions

### Issue: Docker container port conflicts

**Problem:** `Bind for 0.0.0.0:6379 failed: port is already allocated`

**Solution:** Another Redis container (lms-redis) is already using port 6379. This is fine - DeployMind can use the existing Redis instance.

```bash
# Verify Redis is accessible
docker exec lms-redis redis-cli ping  # Should return PONG
```

### Issue: Unicode encoding errors on Windows

**Problem:** `UnicodeEncodeError: 'charmap' codec can't encode character`

**Solution:** Set UTF-8 encoding before running Python scripts:
```bash
PYTHONIOENCODING=utf-8 python script.py
```

### Issue: AWS Free Tier usage

**Current Status:** 0 instances running in ap-south-1 region

**Important:**
- Only t2.micro is free tier eligible (750 hrs/month for 12 months)
- Stop instances when not testing to avoid charges
- Monitor billing at: https://console.aws.amazon.com/billing/

### Issue: Groq API rate limits

**Free Tier Limits:**
- 1000 requests/day
- 6000 tokens/minute

**Strategy:**
- Use llama-3.1-8b-instant for simple tasks (faster, cheaper)
- Use llama-3.1-70b-versatile for complex reasoning
- Cache prompts to reduce redundant requests

---

## Testing Strategy

**Coverage Target:** 80%+ for agents and core modules

**Test Categories (pytest markers):**
- `@pytest.mark.unit` - Unit tests (no external dependencies)
- `@pytest.mark.integration` - Integration tests
- `@pytest.mark.aws` - AWS integration tests (requires credentials)
- `@pytest.mark.github` - GitHub integration tests (requires token)

**Run specific tests:**
```bash
pytest -m unit                     # Fast unit tests
pytest -m "aws or github"          # Integration tests
pytest tests/test_security_agent.py -v  # Specific file
```

---

## Agent Architecture

```
Orchestrator Agent (Coordinator)
    ├── Security Agent (Trivy scanning, CVE analysis, auto-fix suggestions)
    ├── Build Agent (Dockerfile generation, Docker image optimization)
    └── Deploy Agent (Rolling deployment, health checks, automatic rollback)
            ↓
    Redis Pub/Sub (Inter-agent communication)
```

**Deployment Flow:**
```
GitHub Repository → Security Scan → Build Docker Image → Deploy to AWS EC2 → Health Checks → (Rollback if needed)
```

---

## Key Documentation

**Essential Files:**
- `docs/project/2-week-plan.md` - Complete 2-week implementation plan
- `ARCHITECTURE.md` - System architecture overview
- `docs/architecture/clean-architecture.md` - Architecture patterns
- `docs/architecture/security-design.md` - Security implementation
- `CLAUDE.md` - Project instructions for Claude Code (in parent directory)

**Development:**
- `pytest.ini` - Test configuration
- `.env.example` - Environment variable template
- `requirements.txt` - Python dependencies

---

## Monitoring & Cost Tracking

### Groq API Usage
- Dashboard: https://console.groq.com/usage
- Free tier: 1000 requests/day
- Current usage: Check daily to stay within limits

### GitHub API Rate Limit
```bash
curl -H "Authorization: token $GITHUB_TOKEN" https://api.github.com/rate_limit
```
- Free tier: 5000 requests/hour
- Current: 4999/5000 remaining

### AWS Costs
- Billing Dashboard: https://console.aws.amazon.com/billing/
- Free tier: t2.micro (750 hrs/month)
- Current: 0 instances running

**Budget:** Aim for $0/month (100% free tier)

---

## Next Session Template

**Starting a new Claude Code session? Provide this context:**

```
I'm working on DeployMind - a multi-agent autonomous deployment system.

**Read for context:**
1. deploymind/START_HERE.md - Project status and quick commands (THIS FILE)
2. deploymind/docs/project/2-week-plan.md - Full implementation plan

**Current Status:**
Day 1 complete ✅ - Foundation set up, credentials verified

**Working on:**
Day 2 - Security Agent implementation

**Help me with:** [your specific task]
```

---

## Git Repository

**Location:** Local git repository at `E:\devops\deploymind\.git`

**Current Branch:** Check with `git branch`

**Important:**
- .env file is gitignored (contains secrets)
- Commit messages should be descriptive
- Test before committing

---

## Support & Resources

**CrewAI Documentation:**
- Official docs: https://docs.crewai.com/
- GitHub: https://github.com/crewAIInc/crewAI
- License: MIT (100% free)

**Groq API:**
- Console: https://console.groq.com/
- Docs: https://console.groq.com/docs
- Free tier: 1000 requests/day

**AWS Free Tier:**
- Guide: https://aws.amazon.com/free/
- Eligibility: 12 months from account creation
- Monitoring: https://console.aws.amazon.com/billing/

**GitHub API:**
- Docs: https://docs.github.com/en/rest
- Rate limits: https://docs.github.com/en/rest/rate-limit
- Token management: https://github.com/settings/tokens

---

## Quick Health Check

Run this to verify everything is working:

```bash
cd E:\devops\deploymind

# 1. Check services
docker-compose ps
docker exec lms-redis redis-cli ping

# 2. Check environment
python -c "from dotenv import load_dotenv; load_dotenv(); import os; print('Groq API:', '✅' if os.getenv('GROQ_API_KEY') else '❌'); print('GitHub:', '✅' if os.getenv('GITHUB_TOKEN') else '❌'); print('AWS:', '✅' if os.getenv('AWS_ACCESS_KEY_ID') else '❌')"

# 3. Run credential verification
PYTHONIOENCODING=utf-8 python verify_all_credentials.py

# 4. Run quick tests
pytest tests/test_config.py -v
```

---

**Last Updated:** 2026-02-05
**Project Status:** Day 1 Complete - Ready for Day 2 (Security Agent)
**Next Task:** Implement Trivy integration for Security Agent
