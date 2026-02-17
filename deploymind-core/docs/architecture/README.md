# Architecture Documentation

Documentation for DeployMind's Clean Architecture implementation.

---

## 📁 Files

### **[Clean Architecture](clean-architecture.md)** (Required Reading)
**What**: Complete system architecture guide
**Topics**:
- Layer structure (Domain, Application, Infrastructure, Agents, Presentation)
- Dependency flow rules
- Layer responsibilities
- Design patterns used
- Benefits of Clean Architecture

**Read this if**: You want to understand how the system is organized

---

### **[Database Models](database-models.md)** (Essential)
**What**: Complete database schema documentation
**Topics**:
- 6 database tables explained
- Data relationships
- Example queries
- Storage estimates
- What data is tracked

**Read this if**: You need to work with the database or understand what data is stored

---

### **[Migration Guide](migration-guide.md)** (Reference)
**What**: How we migrated from flat structure to Clean Architecture
**Topics**:
- Before/after comparison
- Migration steps
- File movements
- Breaking changes
- Migration checklist

**Read this if**: You want to understand the migration process

---

### **[Migration Complete](migration-complete.md)** (Reference)
**What**: Verification that migration was successful
**Topics**:
- What was migrated
- Verification results
- New file locations
- Next steps after migration

**Read this if**: You want to verify the migration completed successfully

---

### **[Security Design](security-design.md)** (Critical)
**What**: Comprehensive security architecture and best practices
**Topics**:
- 10 security layers (authentication, validation, secrets, container security, etc.)
- Input validation and sanitization
- Secret management and redaction
- Container security best practices
- Network security and AWS security groups
- Database security (SQL injection prevention)
- Deployment safety (rollback mechanisms)
- Monitoring and incident response
- Security roadmap (MVP to production)
- Known risks and mitigations

**Read this if**: You want to understand how security is implemented throughout the system

---

## 🎯 Quick Reference

### **System Layers**
```
Presentation  →  Application  →  Domain  ←  Infrastructure
                                   ↑
                                Agents
```

### **Key Principle**
**Dependencies point INWARD only**
- Domain has NO dependencies
- Infrastructure implements domain interfaces
- Application uses domain entities
- Presentation uses application use cases

### **Database Tables**
1. `deployments` - Main tracking
2. `security_scans` - Trivy results
3. `build_results` - Docker builds
4. `health_checks` - Monitoring
5. `deployment_logs` - Audit trail
6. `agent_executions` - Performance

---

**Last Updated**: 2026-02-05
