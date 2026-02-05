# Database Models Summary
**DeployMind Data Architecture**

---

## 📊 Overview

DeployMind stores **6 types of data** across **7 database tables** to track deployments, security scans, builds, health checks, logs, and agent executions.

**Database**: PostgreSQL (local Docker or cloud)
**ORM**: SQLAlchemy
**Location**: `infrastructure/database/models.py`

---

## 🗄️ Database Tables

### **1. Deployments** (Main Table)
**Purpose**: Track each deployment from start to finish

**What's Stored**:
```
Primary Data:
- Deployment ID (unique identifier like "deploy-20260204-abc123")
- Repository info (owner/repo, commit SHA, branch)
- Target infrastructure (EC2 instance ID, region)
- Deployment status (pending → deploying → deployed/failed)
- Strategy (rolling, canary, blue-green)

Docker Image:
- Image tag (e.g., "myapp:commit-abc123")
- Image size in MB

Timestamps:
- Created at (when deployment started)
- Started at (when actual deployment began)
- Completed at (when deployment finished)
- Duration in seconds

Metadata:
- Who/what triggered deployment (user, webhook, scheduled)
- Previous deployment ID (for rollbacks)
- Rollback reason
- Additional JSON metadata
```

**Example Row**:
```json
{
  "id": "deploy-20260204-abc123",
  "repository": "PrathamModi001/my-app",
  "commit_sha": "a1b2c3d4",
  "instance_id": "i-0123456789",
  "region": "ap-south-1",
  "strategy": "rolling",
  "status": "deployed",
  "image_tag": "my-app:a1b2c3d4",
  "image_size_mb": 156.3,
  "created_at": "2026-02-04 10:00:00",
  "completed_at": "2026-02-04 10:05:30",
  "duration_seconds": 330,
  "triggered_by": "PrathamModi001",
  "trigger_type": "manual"
}
```

---

### **2. Security Scans**
**Purpose**: Store Trivy security scan results

**What's Stored**:
```
Scan Info:
- Scan type (dockerfile, dependencies, secrets)
- Scanner name (trivy)
- Scan duration

Results:
- Pass/fail status
- Total vulnerabilities found
- Count by severity (critical, high, medium, low)
- Detailed vulnerability list (JSON)

AI Analysis:
- Agent decision (approve, reject, warn)
- Agent reasoning (why approved/rejected)
- Recommendations for fixes

Raw Data:
- Trivy version used
- Complete scan output
```

**Example Row**:
```json
{
  "deployment_id": "deploy-20260204-abc123",
  "scan_type": "dockerfile",
  "passed": true,
  "total_vulnerabilities": 3,
  "critical_count": 0,
  "high_count": 0,
  "medium_count": 2,
  "low_count": 1,
  "vulnerabilities": [
    {
      "package": "nginx",
      "version": "1.21.0",
      "severity": "MEDIUM",
      "cve": "CVE-2023-12345"
    }
  ],
  "agent_decision": "approve",
  "agent_reasoning": "Only medium and low severity issues found. No critical vulnerabilities. Safe to deploy."
}
```

---

### **3. Build Results**
**Purpose**: Track Docker image builds

**What's Stored**:
```
Build Info:
- Build duration
- Success/failure status
- Exit code

Dockerfile:
- Path to Dockerfile
- Was it auto-generated? (yes/no)
- Detected language (nodejs, python, go)
- Detected framework (express, fastapi, gin)

Image Info:
- Docker image ID
- Image tag
- Size in bytes
- Number of layers

Optimization:
- Which optimizations were applied
- Original vs optimized size
- Size reduction percentage

Logs:
- Full build output
- Error messages (if failed)
- AI suggestions for improvement
```

**Example Row**:
```json
{
  "deployment_id": "deploy-20260204-abc123",
  "success": true,
  "build_duration_seconds": 120,
  "dockerfile_generated": false,
  "detected_language": "nodejs",
  "detected_framework": "express",
  "image_tag": "my-app:a1b2c3d4",
  "image_size_bytes": 163840000,
  "layer_count": 8,
  "optimizations_applied": ["multi-stage build", "alpine base"],
  "original_size_bytes": 245760000,
  "size_reduction_percent": 33.3
}
```

---

### **4. Health Checks**
**Purpose**: Monitor application health after deployment

**What's Stored**:
```
Check Info:
- Check time
- Check type (HTTP, TCP, command)
- Check URL (e.g., http://instance-ip:8080/health)

Results:
- Healthy? (yes/no)
- HTTP status code
- Response time in milliseconds
- Response body

Instance Status:
- Instance state (running, stopped)
- Instance health (ok, impaired)

Retry Info:
- Current attempt number
- Maximum attempts allowed
- Error message (if failed)
```

**Example Row**:
```json
{
  "deployment_id": "deploy-20260204-abc123",
  "check_time": "2026-02-04 10:05:00",
  "check_type": "http",
  "check_url": "http://13.127.45.123:8080/health",
  "healthy": true,
  "status_code": 200,
  "response_time_ms": 45,
  "response_body": "{\"status\": \"ok\"}",
  "instance_state": "running",
  "instance_status": "ok",
  "attempt_number": 1
}
```

---

### **5. Deployment Logs**
**Purpose**: Chronological log of all deployment events

**What's Stored**:
```
Log Entry:
- Timestamp
- Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- Which agent generated it (security, build, deploy, orchestrator)
- Message text

Structured Data:
- Event type (scan_started, build_completed, deploy_failed)
- Additional event data (JSON)
```

**Example Rows**:
```json
[
  {
    "deployment_id": "deploy-20260204-abc123",
    "timestamp": "2026-02-04 10:00:00",
    "level": "INFO",
    "agent": "orchestrator",
    "message": "Deployment started for PrathamModi001/my-app"
  },
  {
    "timestamp": "2026-02-04 10:00:30",
    "level": "INFO",
    "agent": "security",
    "message": "Security scan passed: 0 critical vulnerabilities"
  },
  {
    "timestamp": "2026-02-04 10:02:00",
    "level": "INFO",
    "agent": "build",
    "message": "Docker image built successfully: my-app:a1b2c3d4"
  },
  {
    "timestamp": "2026-02-04 10:05:30",
    "level": "INFO",
    "agent": "deploy",
    "message": "Deployment completed successfully"
  }
]
```

---

### **6. Agent Executions**
**Purpose**: Track AI agent performance and costs

**What's Stored**:
```
Agent Info:
- Agent name (security, build, deploy)
- Agent version

Execution:
- Start/end timestamps
- Duration
- Success/failure

LLM Usage:
- Which model was used (llama-3.1-70b-versatile)
- Tokens consumed (input + output)
- Cost in USD (always $0 with Groq!)

Results:
- Agent output (JSON)
- Error messages
```

**Example Row**:
```json
{
  "deployment_id": "deploy-20260204-abc123",
  "agent_name": "security",
  "started_at": "2026-02-04 10:00:15",
  "completed_at": "2026-02-04 10:00:45",
  "duration_seconds": 30,
  "success": true,
  "llm_model": "llama-3.1-70b-versatile",
  "llm_tokens_input": 450,
  "llm_tokens_output": 120,
  "llm_cost_usd": 0.00,
  "output": {
    "decision": "approve",
    "vulnerabilities_found": 3,
    "recommendation": "safe to deploy"
  }
}
```

---

## 🔗 Table Relationships

```
Deployments (1) ──→ (many) Security Scans
            (1) ──→ (many) Build Results
            (1) ──→ (many) Health Checks
            (1) ──→ (many) Deployment Logs
            (1) ──→ (many) Agent Executions
            (1) ──→ (1) Previous Deployment (for rollback)
```

**Example**: One deployment has:
- 1-3 security scans (dockerfile, dependencies, secrets)
- 1 build result
- 5-10 health checks (monitored over time)
- 20-50 log entries
- 3-4 agent executions (security, build, deploy, orchestrator)

---

## 📈 Data Volume Estimates

**For 100 deployments**:
```
Deployments:        100 rows
Security Scans:     300 rows (3 scans per deployment)
Build Results:      100 rows (1 per deployment)
Health Checks:      500 rows (5 checks per deployment)
Deployment Logs:  3,000 rows (30 logs per deployment)
Agent Executions:   400 rows (4 agents per deployment)

TOTAL:           ~4,400 rows
Storage:         ~50-100 MB (with JSON data)
```

---

## 🎯 What Can You Query?

### **Deployment Analytics**
```sql
-- Average deployment time
SELECT AVG(duration_seconds) FROM deployments WHERE status = 'deployed';

-- Success rate
SELECT
  COUNT(*) FILTER (WHERE status = 'deployed') * 100.0 / COUNT(*) as success_rate
FROM deployments;

-- Deployments per day
SELECT DATE(created_at), COUNT(*) FROM deployments GROUP BY DATE(created_at);
```

### **Security Insights**
```sql
-- Most vulnerable repositories
SELECT repository, SUM(critical_count + high_count) as critical_vulns
FROM deployments d
JOIN security_scans s ON d.id = s.deployment_id
GROUP BY repository
ORDER BY critical_vulns DESC;

-- Security scan pass rate
SELECT
  COUNT(*) FILTER (WHERE passed = true) * 100.0 / COUNT(*) as pass_rate
FROM security_scans;
```

### **Build Performance**
```sql
-- Average build time by language
SELECT detected_language, AVG(build_duration_seconds)
FROM build_results
WHERE success = true
GROUP BY detected_language;

-- Image size optimization
SELECT AVG(size_reduction_percent)
FROM build_results
WHERE optimized_size_bytes IS NOT NULL;
```

### **Health Monitoring**
```sql
-- Failed health checks
SELECT deployment_id, check_time, error_message
FROM health_checks
WHERE healthy = false
ORDER BY check_time DESC;

-- Average response time
SELECT AVG(response_time_ms) FROM health_checks WHERE healthy = true;
```

### **Cost Tracking** (LLM Usage)
```sql
-- Total LLM cost (always $0 with Groq!)
SELECT SUM(llm_cost_usd) FROM agent_executions;

-- Tokens used per agent
SELECT agent_name, SUM(llm_tokens_input + llm_tokens_output) as total_tokens
FROM agent_executions
GROUP BY agent_name;
```

---

## 🔐 Data Retention

**Recommended retention policies**:
- **Deployments**: Keep forever (audit trail)
- **Security Scans**: Keep 90 days
- **Build Results**: Keep 30 days
- **Health Checks**: Keep 7 days
- **Deployment Logs**: Keep 30 days
- **Agent Executions**: Keep 30 days

---

## 💾 Database Schema Diagram

```
┌─────────────────┐
│  Deployments    │ (Main table)
├─────────────────┤
│ id (PK)         │
│ repository      │
│ instance_id     │
│ status          │
│ image_tag       │
│ created_at      │
│ completed_at    │
│ ...             │
└────────┬────────┘
         │
         ├──→ ┌──────────────────┐
         │    │ Security Scans   │
         │    ├──────────────────┤
         │    │ id (PK)          │
         │    │ deployment_id(FK)│
         │    │ scan_type        │
         │    │ passed           │
         │    │ vulnerabilities  │
         │    └──────────────────┘
         │
         ├──→ ┌──────────────────┐
         │    │ Build Results    │
         │    ├──────────────────┤
         │    │ id (PK)          │
         │    │ deployment_id(FK)│
         │    │ image_tag        │
         │    │ success          │
         │    └──────────────────┘
         │
         ├──→ ┌──────────────────┐
         │    │ Health Checks    │
         │    ├──────────────────┤
         │    │ id (PK)          │
         │    │ deployment_id(FK)│
         │    │ healthy          │
         │    │ response_time_ms │
         │    └──────────────────┘
         │
         ├──→ ┌──────────────────┐
         │    │ Deployment Logs  │
         │    ├──────────────────┤
         │    │ id (PK)          │
         │    │ deployment_id(FK)│
         │    │ level            │
         │    │ message          │
         │    └──────────────────┘
         │
         └──→ ┌──────────────────┐
              │ Agent Executions │
              ├──────────────────┤
              │ id (PK)          │
              │ deployment_id(FK)│
              │ agent_name       │
              │ llm_tokens       │
              └──────────────────┘
```

---

## 🧪 Testing the Database

```bash
# Initialize database
cd deploymind
python -c "from infrastructure.database.connection import init_db; init_db()"

# Expected output:
# INFO: Initializing database...
# INFO: Database initialized successfully
```

---

## ✅ Summary

**What's Being Stored**:
1. ✅ **Deployments** - Every deployment attempt with full tracking
2. ✅ **Security Scans** - Trivy results + AI analysis
3. ✅ **Build Results** - Docker builds with optimization data
4. ✅ **Health Checks** - Application monitoring after deployment
5. ✅ **Deployment Logs** - Chronological event trail
6. ✅ **Agent Executions** - AI agent performance tracking

**Benefits**:
- Complete audit trail of all deployments
- Security compliance tracking
- Performance analytics
- Cost monitoring (LLM usage)
- Debugging failed deployments
- Historical data for ML/predictions

---

**Database models are ready to use!** 🚀
