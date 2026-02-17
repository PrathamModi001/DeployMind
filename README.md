# DeployMind

AI-Powered Autonomous Deployment Platform

This monorepo contains two main components:

## Projects

### 1. [DeployMind Core](./deploymind-core/)
Main Python application with Clean Architecture, multi-agent AI system, and CLI.

**Features:**
- Multi-agent AI deployment system (Groq LLM)
- Security scanning with Trivy
- AWS EC2 deployment with rollback
- Clean Architecture (Hexagonal)

**Quick Start:**
```bash
cd deploymind-core
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
pip install -e .
deploymind --help
```

See [deploymind-core/README.md](./deploymind-core/README.md) for full documentation.

### 2. [DeployMind Web](./deploymind-web/)
Full-stack web application with FastAPI backend and Next.js frontend.

**Features:**
- GitHub OAuth authentication
- Real-time deployment monitoring
- Analytics dashboard
- Modern responsive UI

**Quick Start:**
```bash
# Terminal 1: Backend
cd deploymind-web/backend
pip install -r requirements.txt
uvicorn api.main:app --reload

# Terminal 2: Frontend
cd deploymind-web/frontend
npm install
npm run dev
```

See [deploymind-web/README.md](./deploymind-web/README.md) for full documentation.

## Architecture

- **Core App**: Clean Architecture with AI agents, AWS deployment, security scanning
- **Web App**: FastAPI + Next.js with GitHub OAuth, JWT auth, PostgreSQL

```
deploymind/
├── deploymind-core/      # Python core application
│   ├── deploymind/       # Main package
│   ├── tests/            # Core tests
│   └── docs/             # Documentation
│
└── deploymind-web/       # Web application
    ├── backend/          # FastAPI backend
    └── frontend/         # Next.js frontend
```

## Documentation

- [QUICKSTART.md](./QUICKSTART.md) - Quick start guide
- [CLAUDE.md](./CLAUDE.md) - Claude Code guidance
- [deploymind-core/docs/](./deploymind-core/docs/) - Architecture docs

## License

See [LICENSE](./LICENSE) for details.
