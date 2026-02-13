# DeployMind 🚀

**AI-Powered Autonomous Deployment Platform**

Deploy applications to AWS with zero manual intervention using intelligent multi-agent orchestration.

**100% FREE** - Uses Groq's free tier (1000 requests/day) | **Production Ready** | **Security First**

## ✨ Features

- 🤖 **Multi-Agent AI System** - 4 specialized agents (Orchestrator, Security, Build, Deploy)
- 🔒 **Security First** - Trivy scanning, OWASP Top 10 compliance, CVE analysis
- 🐳 **Smart Docker Builds** - AI-generated Dockerfiles with multi-stage optimization
- ☁️ **AWS Deployment** - Rolling deployment to EC2 with automated health checks
- 🔄 **Auto Rollback** - Instant rollback on health check failures
- 📊 **Analytics & Monitoring** - Real-time deployment metrics and performance tracking
- 💾 **Complete Audit Trail** - Every action logged with security event tracking
- 🧪 **Comprehensive Testing** - 250+ tests with 196 core tests passing

---

## 🚀 Quick Start (5 minutes)

```bash
# 1. Clone and setup environment
git clone <repository-url>
cd deploymind
python -m venv venv

# Windows
venv\Scripts\activate
# Linux/Mac
source venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment
cp .env.example .env
# Edit .env with your API keys:
# - GROQ_API_KEY (get free at https://console.groq.com/keys)
# - GITHUB_TOKEN (GitHub personal access token)
# - AWS credentials (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION)

# 4. Start local services (PostgreSQL, Redis)
docker-compose up -d

# 5. Initialize database
python -c "from infrastructure.database.connection import init_db; init_db()"

# 6. Verify setup
python scripts/verify_all_credentials.py
python scripts/verify_architecture.py

# 7. Deploy your first application!
python presentation/cli/main.py deploy \
  --repo owner/repository \
  --instance-id i-1234567890abcdef \
  --commit abc123
```

---

## 📖 CLI Usage

```bash
# Deploy application
deploymind deploy --repo user/app --instance-id i-xxx --commit sha

# Get deployment status
deploymind status <deployment-id>

# List all deployments
deploymind list [--repository user/app] [--status pending]

# View deployment logs
deploymind logs <deployment-id> [--level ERROR] [--limit 100]

# Manual rollback
deploymind rollback <deployment-id>

# View analytics
deploymind analytics [--days 7] [--repository user/app]

# Dry-run deployment (validate without executing)
deploymind deploy --repo user/app --instance-id i-xxx --dry-run
```

**Configuration File Support** (`.deploymind.yml`):
```yaml
defaults:
  strategy: rolling
  health_check_path: /health
  health_check_timeout: 120

profiles:
  production:
    repository: myorg/myapp
    instance_id: i-prod123456
    environment: production

  staging:
    repository: myorg/myapp
    instance_id: i-stage123456
    environment: staging
```

```bash
# Use profile
deploymind deploy --profile production --commit abc123
```

---

## 🏗️ Architecture

DeployMind follows **Clean Architecture** (layered pattern):

```
deploymind/
├── domain/              # Business logic (pure Python)
├── application/         # Use cases & workflows
├── infrastructure/      # AWS, GitHub, Groq, Redis, Database
├── agents/              # AI agents (Security, Build, Deploy)
├── presentation/        # CLI & API interfaces
├── config/              # Configuration & DI
└── shared/              # Utilities
```

**Key Principles**:
- Dependencies point inward only
- Domain has no external dependencies
- Infrastructure implements domain interfaces

**Read more**: [docs/architecture/clean-architecture.md](docs/architecture/clean-architecture.md)

---

## 🤖 Multi-Agent System

Four specialized AI agents powered by Groq LLM:

```
Orchestrator Agent (Coordinator)
    ├── Security Agent  (Trivy scanning, CVE analysis)
    ├── Build Agent     (Dockerfile generation, optimization)
    └── Deploy Agent    (Rolling deployment, health checks, rollback)
```

**Workflow**: GitHub Repository → Security Scan → Build Docker Image → Deploy to AWS EC2 → Health Checks → (Rollback if needed)

---

## 🔒 Security

**Security-first approach** with comprehensive protection:

**Input Validation**:
- 15+ validators prevent SQL injection, command injection, path traversal, XSS
- All user inputs validated before use
- Docker tags sanitized to prevent image poisoning

**Secret Management**:
- Automatic secret redaction in all logs (API keys, passwords, tokens)
- No secrets in code (environment variables only)
- Secure logging framework prevents credential leakage

**Audit & Compliance**:
- Complete audit trail for all operations
- Security event logging with severity levels
- OWASP Top 10 compliance (5/10 complete, 5/10 in progress)

**Testing**:
- 45 security tests (100% passing)
- Attack prevention verified (injection, traversal, XSS)
- Comprehensive test coverage

**Read more**: [docs/architecture/security-design.md](docs/architecture/security-design.md)

---

## 💾 Database

**6 PostgreSQL tables** track deployments:

| Table | Purpose |
|-------|---------|
| `deployments` | Main deployment tracking |
| `security_scans` | Trivy results + AI analysis |
| `build_results` | Docker build information |
| `health_checks` | Application monitoring |
| `deployment_logs` | Chronological audit trail |
| `agent_executions` | AI agent performance |

**Read more**: [docs/architecture/database-models.md](docs/architecture/database-models.md)

---

## 🧪 Testing

```bash
# Run all tests
pytest tests/ -v

# Run unit tests only
pytest tests/unit/ -v

# Run with coverage
pytest tests/ --cov=deploymind --cov-report=html

# Integration tests
pytest -m "aws or github"
```

---

## 📚 Documentation

**Essential Reading**:
- **[Getting Started](docs/project/next-steps.md)** - What to implement next
- **[Architecture Guide](docs/architecture/clean-architecture.md)** - System design
- **[Database Models](docs/architecture/database-models.md)** - Data schema
- **[2-Week Plan](docs/project/2-week-plan.md)** - Complete MVP timeline

**All Documentation**: [docs/README.md](docs/README.md)

---

## 💰 Cost

**Total Cost: $0** (Everything is FREE)

| Component | Tool | Cost |
|-----------|------|------|
| **LLM** | Groq | $0 (1000 req/day) |
| **Cloud** | AWS Free Tier | $0 (12 months) |
| **Database** | PostgreSQL (Docker) | $0 |
| **Cache** | Redis (Docker) | $0 |
| **VCS** | GitHub API | $0 |

---

## 🎯 Current Status

✅ **PRODUCTION READY** - All core features implemented and tested

**Completed** (Days 1-9):
- ✅ Clean Architecture with dependency injection
- ✅ Security Agent with Trivy integration (26 OWASP tests passing)
- ✅ Build Agent with AI Dockerfile generation
- ✅ Deploy Agent with rolling deployment & auto-rollback
- ✅ Full deployment workflow with health checks
- ✅ Analytics & monitoring dashboard
- ✅ CLI with comprehensive commands
- ✅ 196 core tests passing (255 total tests)
- ✅ AWS resource management (pause/resume scripts)

**Day 10: Documentation & Finalization** ⏳ **IN PROGRESS**
- ⏳ Comprehensive README (this file)
- ⏳ API/CLI documentation
- ⏳ Deployment guides
- ⏳ Final E2E validation

**Test Coverage**:
- **196/196** core unit tests ✅
- **26/26** security tests (OWASP compliance) ✅
- **15** integration tests (require database)
- **15** E2E tests (require full stack)

**See**: [docs/project/2-week-schedule.md](docs/project/2-week-schedule.md)

---

## 🔧 Development Commands

```bash
# Verify all credentials
python scripts/verify_all_credentials.py

# Verify architecture compliance
python scripts/verify_architecture.py

# Database management
python -c "from infrastructure.database.connection import init_db; init_db()"

# Start local services (PostgreSQL, Redis)
docker-compose up -d

# Stop services
docker-compose down

# Run tests
pytest tests/ -v                    # All tests
pytest tests/unit/ -v               # Unit tests only
pytest tests/security/ -v           # Security tests
pytest -m "not aws" -v              # Exclude AWS tests
pytest --cov=deploymind            # With coverage

# AWS resource management
python scripts/pause_aws_resources.py --dry-run    # Preview pause
python scripts/pause_aws_resources.py              # Pause EC2 instances
python scripts/resume_aws_resources.py             # Resume instances
```

---

## 📖 Project Structure

```
deploymind/
├── agents/                 # AI agents (CrewAI)
├── application/            # Use cases & interfaces
├── config/                 # Settings & dependency injection
├── domain/                 # Business entities & rules
├── infrastructure/         # External services
│   ├── cloud/aws/         # AWS EC2 client
│   ├── vcs/github/        # GitHub client
│   ├── cache/             # Redis client
│   ├── llm/groq/          # Groq LLM client
│   └── database/          # PostgreSQL models
├── presentation/           # CLI & API
├── shared/                 # Utilities & exceptions
├── tests/                  # Organized tests
├── scripts/                # Utility scripts
└── docs/                   # Documentation
```

---

## 🤝 Contributing

See [docs/project/2-week-plan.md](docs/project/2-week-plan.md) for the implementation roadmap.

---

## 📄 License

MIT License - See LICENSE file

---

**Built with**: Python 3.11+ • CrewAI • Groq • AWS • PostgreSQL • Redis
