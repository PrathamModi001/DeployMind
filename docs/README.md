# DeployMind Documentation

Complete documentation for the DeployMind autonomous deployment system.

---

## 📚 Quick Navigation

### **Start Here**
- **[Getting Started](../README.md)** - Quick start guide
- **[Next Steps](project/next-steps.md)** - Implementation roadmap

### **Architecture**
- **[Clean Architecture Overview](architecture/clean-architecture.md)** - System architecture
- **[Database Models](architecture/database-models.md)** - Data persistence layer
- **[Migration Guide](architecture/migration-guide.md)** - Architecture migration details

### **Project**
- **[2-Week Plan](project/2-week-plan.md)** - Complete MVP implementation plan
- **[Free Tier Setup](project/free-tier-setup.md)** - Zero-cost infrastructure setup

---

## 📖 Documentation Structure

```
docs/
├── README.md                    # This file
├── architecture/                # Architecture documentation
│   ├── clean-architecture.md   # System design & patterns
│   ├── database-models.md      # Database schema & models
│   ├── migration-guide.md      # How we migrated to Clean Architecture
│   └── migration-complete.md   # Migration completion summary
│
├── project/                     # Project management
│   ├── 2-week-plan.md          # Complete implementation timeline
│   ├── free-tier-setup.md      # Free tier infrastructure setup
│   └── next-steps.md           # Current implementation roadmap
│
└── guides/                      # How-to guides (future)
    └── (to be added)
```

---

## 🎯 Documentation by Role

### **For Developers**
1. [Clean Architecture](architecture/clean-architecture.md) - Understand the system structure
2. [Database Models](architecture/database-models.md) - Understand data persistence
3. [Next Steps](project/next-steps.md) - Know what to implement next

### **For DevOps**
1. [Free Tier Setup](project/free-tier-setup.md) - Infrastructure setup
2. [2-Week Plan](project/2-week-plan.md) - Deployment timeline

### **For Project Managers**
1. [2-Week Plan](project/2-week-plan.md) - Complete timeline
2. [Next Steps](project/next-steps.md) - Current progress

---

## 📝 Key Concepts

### **Clean Architecture**
DeployMind follows Clean Architecture (Hexagonal Architecture) with these layers:
- **Domain**: Business logic (no dependencies)
- **Application**: Use cases & workflows
- **Infrastructure**: External services (AWS, GitHub, Groq, Redis)
- **Agents**: AI orchestration layer
- **Presentation**: User interfaces (CLI, API)

**Read**: [architecture/clean-architecture.md](architecture/clean-architecture.md)

### **Multi-Agent System**
Four specialized AI agents powered by Groq:
- **Security Agent**: Trivy scanning + AI analysis
- **Build Agent**: Docker image building + optimization
- **Deploy Agent**: Rolling deployments + health checks
- **Orchestrator**: Coordinates all agents

**Read**: [project/2-week-plan.md](project/2-week-plan.md)

### **Free Tier Stack**
Everything runs on free tier ($0 total cost):
- **LLM**: Groq (1000 req/day, FREE)
- **Cloud**: AWS Free Tier (t2.micro, 12 months)
- **Database**: PostgreSQL (local Docker)
- **Cache**: Redis (local Docker)
- **VCS**: GitHub API (5000 req/hr)

**Read**: [project/free-tier-setup.md](project/free-tier-setup.md)

---

## 🔍 Finding Documentation

### **I want to understand...**
- **How the system is architected** → [Clean Architecture](architecture/clean-architecture.md)
- **What data is stored** → [Database Models](architecture/database-models.md)
- **How to set up infrastructure** → [Free Tier Setup](project/free-tier-setup.md)
- **What to implement next** → [Next Steps](project/next-steps.md)
- **The complete plan** → [2-Week Plan](project/2-week-plan.md)

---

## 📊 Documentation Status

| Document | Status | Last Updated |
|----------|--------|--------------|
| Clean Architecture | ✅ Complete | 2026-02-04 |
| Database Models | ✅ Complete | 2026-02-05 |
| Migration Guide | ✅ Complete | 2026-02-04 |
| 2-Week Plan | ✅ Complete | 2026-02-03 |
| Free Tier Setup | ✅ Complete | 2026-02-04 |
| Next Steps | ✅ Complete | 2026-02-04 |

---

## 🤝 Contributing to Documentation

When adding new documentation:
1. Place architecture docs in `architecture/`
2. Place project docs in `project/`
3. Place how-to guides in `guides/`
4. Update this README
5. Keep docs concise and focused

---

**Last Updated**: 2026-02-05
