# DeployMind CLI Reference

Complete command-line interface documentation for DeployMind.

## Installation

```bash
# Install DeployMind
pip install -r requirements.txt

# Verify installation
python presentation/cli/main.py --version
```

## Global Options

Available for all commands:

```bash
--verbose, -v          Enable verbose output
--quiet, -q            Suppress non-error output
--json                 Output in JSON format
--config FILE          Use custom config file (default: .deploymind.yml)
--profile NAME         Use configuration profile
```

## Commands

### `deploy` - Deploy Application

Deploy a GitHub repository to an AWS EC2 instance.

```bash
deploymind deploy [OPTIONS]
```

**Required Options:**
- `--repo TEXT` - GitHub repository (format: owner/repo)
- `--instance-id TEXT` - AWS EC2 instance ID (format: i-[a-f0-9]{8,17})

**Optional:**
- `--commit TEXT` - Git commit SHA (default: latest)
- `--branch TEXT` - Git branch (default: main)
- `--strategy TEXT` - Deployment strategy: rolling|blue-green|canary (default: rolling)
- `--environment TEXT` - Environment name: development|staging|production
- `--health-check-path TEXT` - Health check endpoint (default: /health)
- `--health-check-timeout INT` - Health check timeout in seconds (default: 120)
- `--port INT` - Application port (default: 8000)
- `--dry-run` - Validate without executing deployment

**Examples:**

```bash
# Basic deployment
deploymind deploy \
  --repo myorg/myapp \
  --instance-id i-1234567890abcdef

# Deploy specific commit with custom health check
deploymind deploy \
  --repo myorg/myapp \
  --instance-id i-1234567890abcdef \
  --commit abc123def456 \
  --health-check-path /api/health \
  --health-check-timeout 180

# Production deployment with blue-green strategy
deploymind deploy \
  --repo myorg/myapp \
  --instance-id i-1234567890abcdef \
  --strategy blue-green \
  --environment production

# Dry-run to validate configuration
deploymind deploy \
  --repo myorg/myapp \
  --instance-id i-1234567890abcdef \
  --dry-run
```

**Exit Codes:**
- `0` - Deployment successful
- `1` - Validation error
- `2` - Security scan failed
- `3` - Build failed
- `4` - Deployment failed
- `5` - Health check failed (rollback performed)

---

### `status` - Get Deployment Status

View detailed status of a deployment.

```bash
deploymind status DEPLOYMENT_ID [OPTIONS]
```

**Arguments:**
- `DEPLOYMENT_ID` - Deployment identifier

**Options:**
- `--json` - Output in JSON format
- `--watch` - Watch status in real-time (updates every 5s)

**Examples:**

```bash
# View deployment status
deploymind status 70a59bdb

# Watch deployment progress
deploymind status 70a59bdb --watch

# JSON output for scripting
deploymind status 70a59bdb --json
```

**Output:**
```
Deployment Status
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Deployment ID:  70a59bdb
Repository:     myorg/myapp
Commit SHA:     abc123def456
Status:         completed
Strategy:       rolling
Environment:    production
Started:        2026-02-13 10:30:00
Duration:       3m 42s

Security Scan
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✓ Passed
  Critical: 0  High: 2  Medium: 5  Low: 12
  AI Decision: APPROVED
  Reasoning: No critical vulnerabilities found

Build
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✓ Successful
  Image: myorg/myapp:abc123def456
  Size: 245.3 MB
  Optimizations: multi-stage build, alpine base

Deployment
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✓ Successful
  Instance: i-1234567890abcdef
  Container: 8f9a2b1c3d4e
  URL: http://54.123.45.67:8000

Health Check
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✓ Passed
  Status: 200 OK
  Response Time: 45ms
  Checks: 12/12 successful
```

---

### `list` - List Deployments

List all deployments with optional filtering.

```bash
deploymind list [OPTIONS]
```

**Options:**
- `--repository TEXT` - Filter by repository (format: owner/repo)
- `--status TEXT` - Filter by status: pending|in_progress|completed|failed|rolled_back
- `--environment TEXT` - Filter by environment
- `--limit INT` - Maximum results (default: 50)
- `--offset INT` - Skip first N results (default: 0)
- `--sort TEXT` - Sort by: created_at|updated_at|status (default: created_at)
- `--order TEXT` - Sort order: asc|desc (default: desc)

**Examples:**

```bash
# List all deployments
deploymind list

# List deployments for specific repository
deploymind list --repository myorg/myapp

# List failed deployments
deploymind list --status failed

# Production deployments only
deploymind list --environment production

# Last 10 deployments
deploymind list --limit 10

# Paginated results
deploymind list --limit 25 --offset 25
```

---

### `logs` - View Deployment Logs

View logs for a specific deployment.

```bash
deploymind logs DEPLOYMENT_ID [OPTIONS]
```

**Arguments:**
- `DEPLOYMENT_ID` - Deployment identifier

**Options:**
- `--level TEXT` - Filter by log level: DEBUG|INFO|WARNING|ERROR|CRITICAL
- `--agent TEXT` - Filter by agent: security|build|deploy|orchestrator
- `--limit INT` - Maximum log entries (default: 100)
- `--follow, -f` - Follow log output in real-time
- `--since TEXT` - Show logs since timestamp (ISO 8601 or relative like "1h", "30m")

**Examples:**

```bash
# View last 100 logs
deploymind logs 70a59bdb

# View errors only
deploymind logs 70a59bdb --level ERROR

# View build agent logs
deploymind logs 70a59bdb --agent build

# Last 500 logs
deploymind logs 70a59bdb --limit 500

# Follow logs in real-time
deploymind logs 70a59bdb --follow

# Logs from last hour
deploymind logs 70a59bdb --since 1h
```

---

### `rollback` - Rollback Deployment

Manually rollback a deployment to previous version.

```bash
deploymind rollback DEPLOYMENT_ID [OPTIONS]
```

**Arguments:**
- `DEPLOYMENT_ID` - Deployment identifier to rollback

**Options:**
- `--force` - Skip confirmation prompt
- `--reason TEXT` - Rollback reason for audit trail

**Examples:**

```bash
# Rollback with confirmation
deploymind rollback 70a59bdb

# Force rollback with reason
deploymind rollback 70a59bdb \
  --force \
  --reason "Critical bug found in production"
```

**Note:** Automatic rollback occurs when health checks fail. Manual rollback is for cases where issues are detected after deployment completes.

---

### `analytics` - Deployment Analytics

View deployment metrics and analytics.

```bash
deploymind analytics [OPTIONS]
```

**Options:**
- `--repository TEXT` - Filter by repository
- `--days INT` - Number of days to analyze (default: 7)
- `--environment TEXT` - Filter by environment
- `--format TEXT` - Output format: table|json|chart (default: table)

**Examples:**

```bash
# Last 7 days analytics
deploymind analytics

# Last 30 days for specific repository
deploymind analytics --repository myorg/myapp --days 30

# Production analytics
deploymind analytics --environment production --days 14

# JSON output for custom processing
deploymind analytics --days 30 --format json
```

**Metrics Shown:**
- Total deployments
- Success rate
- Average deployment time
- Rollback rate
- Security scan statistics
- Build performance
- Most common failure reasons

---

## Configuration File

Create `.deploymind.yml` in your project root:

```yaml
# Default settings for all deployments
defaults:
  strategy: rolling
  health_check_path: /health
  health_check_timeout: 120
  port: 8000

# Named profiles for different environments
profiles:
  production:
    repository: myorg/myapp
    instance_id: i-prod1234567890abc
    environment: production
    strategy: blue-green
    health_check_timeout: 180

  staging:
    repository: myorg/myapp
    instance_id: i-stage1234567890abc
    environment: staging
    strategy: rolling

  development:
    repository: myorg/myapp
    instance_id: i-dev1234567890abc
    environment: development
    health_check_timeout: 60
```

**Using Profiles:**

```bash
# Deploy to production using profile
deploymind deploy --profile production --commit abc123

# Override profile settings
deploymind deploy --profile production --port 9000
```

---

## Environment Variables

DeployMind reads configuration from environment variables:

**Required:**
- `GROQ_API_KEY` - Groq API key (get free at https://console.groq.com/keys)
- `GITHUB_TOKEN` - GitHub personal access token
- `AWS_ACCESS_KEY_ID` - AWS access key
- `AWS_SECRET_ACCESS_KEY` - AWS secret key
- `AWS_REGION` - AWS region (e.g., us-east-1)

**Optional:**
- `DATABASE_URL` - PostgreSQL connection string (default: local)
- `REDIS_URL` - Redis connection string (default: local)
- `LOG_LEVEL` - Logging level: DEBUG|INFO|WARNING|ERROR (default: INFO)
- `DEPLOYMENT_TIMEOUT` - Global deployment timeout in seconds (default: 3600)

**Setting Environment Variables:**

```bash
# Linux/Mac
export GROQ_API_KEY="your_key_here"
export GITHUB_TOKEN="your_token_here"

# Windows CMD
set GROQ_API_KEY=your_key_here

# Windows PowerShell
$env:GROQ_API_KEY="your_key_here"

# Or use .env file
cp .env.example .env
# Edit .env with your values
```

---

## Exit Codes

All commands return standard exit codes:

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Validation error or invalid arguments |
| 2 | Security scan failed (deployment blocked) |
| 3 | Build failed |
| 4 | Deployment failed |
| 5 | Health check failed (rollback performed) |
| 10 | Configuration error |
| 11 | Authentication error (AWS/GitHub/Groq) |
| 12 | Network error |
| 99 | Unexpected internal error |

**Use in Scripts:**

```bash
#!/bin/bash
deploymind deploy --repo myorg/myapp --instance-id i-xxx

if [ $? -eq 0 ]; then
  echo "Deployment successful"
else
  echo "Deployment failed with code $?"
  exit 1
fi
```

---

## JSON Output

Use `--json` flag for machine-readable output:

```bash
deploymind status 70a59bdb --json
```

```json
{
  "deployment_id": "70a59bdb",
  "repository": "myorg/myapp",
  "commit_sha": "abc123def456",
  "status": "completed",
  "strategy": "rolling",
  "environment": "production",
  "created_at": "2026-02-13T10:30:00Z",
  "completed_at": "2026-02-13T10:33:42Z",
  "duration_seconds": 222,
  "security_scan": {
    "passed": true,
    "critical": 0,
    "high": 2,
    "medium": 5,
    "low": 12
  },
  "build": {
    "successful": true,
    "image_tag": "myorg/myapp:abc123def456",
    "image_size_mb": 245.3
  },
  "deployment": {
    "successful": true,
    "instance_id": "i-1234567890abcdef",
    "container_id": "8f9a2b1c3d4e",
    "url": "http://54.123.45.67:8000"
  },
  "health_check": {
    "passed": true,
    "status_code": 200,
    "response_time_ms": 45,
    "checks_passed": 12,
    "checks_total": 12
  }
}
```

---

## Troubleshooting

**Command not found:**
```bash
# Use full path
python presentation/cli/main.py deploy --help

# Or create alias
alias deploymind="python /path/to/deploymind/presentation/cli/main.py"
```

**Authentication errors:**
```bash
# Verify credentials
python scripts/verify_all_credentials.py

# Check environment variables
echo $GROQ_API_KEY
echo $GITHUB_TOKEN
echo $AWS_ACCESS_KEY_ID
```

**Deployment hangs:**
- Check health check path is correct
- Verify instance security groups allow traffic
- Check application logs on EC2 instance
- Increase health check timeout: `--health-check-timeout 300`

**For more help:**
```bash
deploymind --help
deploymind deploy --help
```
