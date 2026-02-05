# DeployMind

Multi-agent autonomous deployment system powered by AI.

**100% FREE** - Uses Groq's free tier (1000 requests/day) or local Ollama.

---

## 🚀 Quick Start

```bash
# 1. Create virtual environment
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment
cp .env.example .env
# Get free Groq API key: https://console.groq.com/keys
# Edit .env with your API keys

# 4. Start local services
docker-compose up -d

# 5. Initialize database
python -c "from infrastructure.database.connection import init_db; init_db()"

# 6. Verify setup
python scripts/verify_architecture.py
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

**Phase 1: Setup** ✅ **COMPLETE**
- ✅ Clean Architecture implemented
- ✅ Database models created
- ✅ Infrastructure clients ready (AWS, GitHub, Groq, Redis)
- ✅ Dependency injection configured
- ✅ Security framework (60+ tests passing)

**Phase 2: Implementation** ⏳ **IN PROGRESS**
- ✅ Day 2: Security Agent (32/32 tests passing)
- Next: Day 3 - Build Agent

**See**: [docs/project/next-steps.md](docs/project/next-steps.md)

---

## 🔧 Development Commands

```bash
# Verify all credentials
python scripts/verify_all_credentials.py

# Verify architecture
python scripts/verify_architecture.py

# Initialize database
python -c "from infrastructure.database.connection import init_db; init_db()"

# Start services
docker-compose up -d

# Stop services
docker-compose down
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
