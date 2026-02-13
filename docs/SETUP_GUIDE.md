# DeployMind Setup Guide

Complete step-by-step guide to set up DeployMind from scratch.

## Prerequisites

### System Requirements

- **Operating System**: Windows 10+, macOS 10.14+, or Linux
- **Python**: 3.11 or higher
- **Docker**: 20.10+ (for local services and Trivy scanning)
- **Git**: 2.30+
- **Memory**: 4GB RAM minimum (8GB recommended)
- **Disk**: 10GB free space

### Required Accounts (All FREE)

1. **Groq API** - For LLM-powered agents
   - Sign up: https://console.groq.com
   - Get free API key (1000 requests/day)
   - No credit card required

2. **GitHub** - For repository access
   - Create personal access token: https://github.com/settings/tokens
   - Required scopes: `repo`, `read:packages`

3. **AWS** - For EC2 deployments
   - AWS Free Tier: https://aws.amazon.com/free
   - 750 hours/month of t2.micro instances free for 12 months

---

## Step 1: Clone Repository

```bash
git clone <repository-url>
cd deploymind
```

---

## Step 2: Create Virtual Environment

### Windows

```cmd
# Create virtual environment
python -m venv venv

# Activate
venv\Scripts\activate

# Verify Python version
python --version  # Should be 3.11+
```

### Linux/Mac

```bash
# Create virtual environment
python3 -m venv venv

# Activate
source venv/bin/activate

# Verify Python version
python --version  # Should be 3.11+
```

**Note**: Keep this environment activated for all subsequent commands.

---

## Step 3: Install Dependencies

```bash
# Upgrade pip
python -m pip install --upgrade pip

# Install all dependencies
pip install -r requirements.txt

# Verify installation
pip list | grep -E "(crewai|groq|boto3|psycopg2)"
```

**Expected output:**
```
boto3                     1.34.47
crewai                    0.28.8
groq                      1.0.0
psycopg2-binary          2.9.9
```

---

## Step 4: Get API Keys

### 4.1 Groq API Key (FREE)

1. Go to https://console.groq.com/keys
2. Sign up with Google/GitHub (no credit card needed)
3. Click "Create API Key"
4. Copy the key (starts with `gsk_...`)

### 4.2 GitHub Personal Access Token

1. Go to https://github.com/settings/tokens
2. Click "Generate new token (classic)"
3. Select scopes:
   - ✅ `repo` (Full control of private repositories)
   - ✅ `read:packages` (Download packages from GitHub Package Registry)
4. Click "Generate token"
5. Copy the token (starts with `ghp_...`)

**Note**: Save this token securely - GitHub won't show it again!

### 4.3 AWS Credentials

**Option A: AWS CLI (Recommended)**

```bash
# Install AWS CLI
# Windows: Download from https://aws.amazon.com/cli/
# Mac: brew install awscli
# Linux: sudo apt install awscli

# Configure
aws configure

# Enter:
# - AWS Access Key ID
# - AWS Secret Access Key
# - Default region (e.g., us-east-1)
# - Default output format (json)
```

**Option B: Manual Setup**

1. Log in to AWS Console: https://console.aws.amazon.com
2. Go to IAM → Users → Your User → Security Credentials
3. Create access key
4. Save:
   - Access Key ID
   - Secret Access Key

---

## Step 5: Configure Environment

```bash
# Copy example environment file
cp .env.example .env

# Edit .env with your editor
nano .env  # or vim, code, notepad, etc.
```

**Required `.env` configuration:**

```bash
# Groq LLM API
GROQ_API_KEY=gsk_your_groq_api_key_here

# GitHub
GITHUB_TOKEN=ghp_your_github_token_here

# AWS Credentials
AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE
AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
AWS_REGION=us-east-1

# Database (PostgreSQL - defaults work for local Docker)
DATABASE_URL=postgresql://admin:password@localhost:5432/deploymind

# Redis (defaults work for local Docker)
REDIS_URL=redis://localhost:6379

# Optional: Logging
LOG_LEVEL=INFO
```

**Verify no syntax errors:**
```bash
python -c "from config.settings import Settings; s = Settings.load(); print('Config loaded:', s.groq_api_key[:10] + '...')"
```

---

## Step 6: Start Local Services

DeployMind requires PostgreSQL (database) and Redis (caching).

### Using Docker Compose (Recommended)

```bash
# Start services in background
docker-compose up -d

# Verify services are running
docker-compose ps

# Expected output:
# NAME                  STATUS       PORTS
# deploymind-postgres   Up          0.0.0.0:5432->5432/tcp
# deploymind-redis      Up          0.0.0.0:6379->6379/tcp

# Check logs if needed
docker-compose logs postgres
docker-compose logs redis
```

### Alternative: Manual Installation

**PostgreSQL:**
```bash
# Ubuntu/Debian
sudo apt install postgresql postgresql-contrib
sudo systemctl start postgresql

# macOS
brew install postgresql
brew services start postgresql

# Create database
psql -U postgres -c "CREATE DATABASE deploymind;"
psql -U postgres -c "CREATE USER admin WITH PASSWORD 'password';"
psql -U postgres -c "GRANT ALL PRIVILEGES ON DATABASE deploymind TO admin;"
```

**Redis:**
```bash
# Ubuntu/Debian
sudo apt install redis-server
sudo systemctl start redis

# macOS
brew install redis
brew services start redis
```

---

## Step 7: Initialize Database

Create database tables and schema:

```bash
# Initialize database
python -c "from infrastructure.database.connection import init_db; init_db()"

# Expected output:
# Creating all tables...
# Database initialized successfully!
```

**Verify tables created:**
```bash
# Connect to database
psql -U admin -d deploymind -h localhost

# List tables
\dt

# Expected tables:
# deployments
# security_scans
# build_results
# health_checks
# deployment_logs
# agent_executions

# Exit
\q
```

---

## Step 8: Verify Setup

### 8.1 Verify Credentials

```bash
python scripts/verify_all_credentials.py
```

**Expected output:**
```
Verifying All Credentials
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✓ Groq API Key: Valid (gsk_...)
✓ GitHub Token: Valid (authenticated as: your-username)
✓ AWS Access Key: Valid (region: us-east-1)
✓ Database: Connected (6 tables)
✓ Redis: Connected (version: 7.0.11)

All credentials valid! ✓
```

### 8.2 Verify Architecture

```bash
python scripts/verify_architecture.py
```

**Expected output:**
```
Verifying Clean Architecture Compliance
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✓ Domain layer has no external dependencies
✓ Application layer depends only on domain
✓ Infrastructure implements domain interfaces
✓ No circular dependencies detected

Architecture verified! ✓
```

### 8.3 Run Tests

```bash
# Run core unit tests (should all pass)
pytest tests/unit/ tests/security/ -v

# Expected: 196 tests passing
```

---

## Step 9: AWS EC2 Setup

### 9.1 Create EC2 Instance

1. **Launch Instance:**
   - Go to AWS Console → EC2 → Launch Instance
   - **Name**: DeployMind-Test-Instance
   - **AMI**: Ubuntu Server 22.04 LTS
   - **Instance Type**: t2.micro (free tier eligible)
   - **Key Pair**: Create new or use existing
   - **Network**: Allow SSH (22) and HTTP (80, 8000)

2. **Configure Security Group:**
   ```
   Inbound Rules:
   - SSH (22): Your IP
   - HTTP (80): 0.0.0.0/0
   - Custom TCP (8000): 0.0.0.0/0  # Application port
   ```

3. **Launch and Note:**
   - Instance ID (e.g., `i-1234567890abcdef0`)
   - Public IP address

### 9.2 Install Docker on EC2

```bash
# SSH into instance
ssh -i your-key.pem ubuntu@<public-ip>

# Update packages
sudo apt update

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Add user to docker group
sudo usermod -aG docker ubuntu

# Start Docker
sudo systemctl enable docker
sudo systemctl start docker

# Verify
docker --version
docker run hello-world

# Exit SSH
exit
```

---

## Step 10: First Deployment Test

### 10.1 Test with Dry-Run

```bash
python presentation/cli/main.py deploy \
  --repo octocat/Hello-World \
  --instance-id i-your-instance-id \
  --dry-run
```

**Expected:** Validation passes, no actual deployment.

### 10.2 Real Deployment

```bash
python presentation/cli/main.py deploy \
  --repo octocat/Hello-World \
  --instance-id i-your-instance-id \
  --commit master
```

**Watch the agents work:**
1. **Security Agent**: Scans repository with Trivy
2. **Build Agent**: Generates Dockerfile, builds image
3. **Deploy Agent**: Deploys to EC2, runs health checks
4. **Orchestrator**: Coordinates everything

### 10.3 Check Deployment Status

```bash
# Get deployment ID from previous output
python presentation/cli/main.py status <deployment-id>
```

---

## Troubleshooting

### Issue: "No module named 'groq'"

```bash
# Reinstall dependencies
pip install -r requirements.txt --force-reinstall
```

### Issue: "Connection refused" (PostgreSQL)

```bash
# Check Docker is running
docker-compose ps

# Restart services
docker-compose down
docker-compose up -d
```

### Issue: "AWS credentials not found"

```bash
# Verify .env file
cat .env | grep AWS

# Or use AWS CLI config
aws configure list
```

### Issue: "GitHub token invalid"

```bash
# Test token
curl -H "Authorization: token YOUR_TOKEN" https://api.github.com/user
```

### Issue: Trivy scanner not working

```bash
# Pull Trivy image
docker pull aquasec/trivy:latest

# Test Trivy
docker run aquasec/trivy:latest --version
```

---

## Optional: Create CLI Alias

### Linux/Mac

```bash
# Add to ~/.bashrc or ~/.zshrc
echo 'alias deploymind="python /path/to/deploymind/presentation/cli/main.py"' >> ~/.bashrc
source ~/.bashrc

# Now use
deploymind deploy --help
```

### Windows (PowerShell)

```powershell
# Add to profile
notepad $PROFILE

# Add line:
function deploymind { python C:\path\to\deploymind\presentation\cli\main.py $args }

# Reload
. $PROFILE

# Now use
deploymind deploy --help
```

---

## Next Steps

1. **Read the CLI Reference**: [docs/CLI_REFERENCE.md](CLI_REFERENCE.md)
2. **Deploy your own application**: Follow patterns in the guide
3. **Set up CI/CD**: Integrate with GitHub Actions
4. **Monitor deployments**: Use analytics dashboard
5. **Manage costs**: Use AWS pause/resume scripts

---

## Cost Management

### Pause AWS Resources (Save Money!)

When not using DeployMind:

```bash
# Pause all EC2 instances
python scripts/pause_aws_resources.py

# Resume when needed
python scripts/resume_aws_resources.py
```

**Savings**: Stopped instances don't incur compute charges!

---

## Getting Help

- **Documentation**: [docs/](../docs/)
- **CLI Reference**: [docs/CLI_REFERENCE.md](CLI_REFERENCE.md)
- **Architecture**: [docs/architecture/clean-architecture.md](architecture/clean-architecture.md)
- **Issues**: Check logs with `deploymind logs <deployment-id>`

**Support**: Open an issue on GitHub with:
- DeployMind version
- Python version
- Error message
- Steps to reproduce
