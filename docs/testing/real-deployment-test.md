# Real Deployment Testing Guide

This guide explains how to perform a real end-to-end deployment test with actual AWS infrastructure.

## Prerequisites

### 1. AWS Setup
```bash
# EC2 Instance Requirements
- Ubuntu 22.04 LTS or Amazon Linux 2
- Docker installed and running
- Security group allowing inbound traffic on your app port (e.g., 8080)
- SSH key pair configured
- IAM role with necessary permissions (optional)

# Note your instance ID
INSTANCE_ID="i-0123456789abcdef0"
```

### 2. Environment Variables
```bash
# Required in .env
GROQ_API_KEY=gsk_your_real_groq_key
AWS_ACCESS_KEY_ID=AKIA...
AWS_SECRET_ACCESS_KEY=...
AWS_REGION=us-east-1
GITHUB_TOKEN=ghp_...
```

### 3. Local Services Running
```bash
# Start PostgreSQL and Redis
docker-compose up -d postgres redis

# Verify services
docker-compose ps
```

## Test Scenarios

### Scenario 1: Simple Python Flask App

**Step 1: Create Test Repository**
```bash
# Create a simple Flask app in GitHub
mkdir test-flask-app && cd test-flask-app
git init

# Create app.py
cat > app.py <<EOF
from flask import Flask
app = Flask(__name__)

@app.route('/health')
def health():
    return {'status': 'healthy'}, 200

@app.route('/')
def hello():
    return 'Hello from DeployMind!'

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
EOF

# Create requirements.txt
cat > requirements.txt <<EOF
flask==3.0.0
EOF

# Create Dockerfile
cat > Dockerfile <<EOF
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py .
EXPOSE 8080
CMD ["python", "app.py"]
EOF

# Push to GitHub
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/YOUR_USERNAME/test-flask-app.git
git push -u origin main
```

**Step 2: Run Real Deployment**
```python
from config.settings import Settings
from agents.enhanced_orchestrator import create_orchestrator

# Load settings (reads from .env)
settings = Settings.load()

# Verify credentials
missing = settings.validate()
if missing:
    print(f"Missing credentials: {missing}")
    exit(1)

# Create orchestrator
orchestrator = create_orchestrator(settings)

# Deploy to real EC2 instance
print("Starting real deployment...")
response = orchestrator.deploy_application(
    repository="YOUR_USERNAME/test-flask-app",
    instance_id="i-0123456789abcdef0",  # Your real EC2 instance
    port=8080,
    strategy="rolling",
    health_check_path="/health",
    environment="production"
)

# Check results
if response.success:
    print(f"✅ DEPLOYMENT SUCCESSFUL!")
    print(f"   Application URL: {response.application_url}")
    print(f"   Image Tag: {response.image_tag}")
    print(f"   Duration: {response.duration_seconds}s")
    print(f"\nTest the deployment:")
    print(f"   curl {response.application_url}/health")
    print(f"   curl {response.application_url}/")
else:
    print(f"❌ DEPLOYMENT FAILED")
    print(f"   Phase: {response.error_phase}")
    print(f"   Error: {response.error_message}")
    if response.rollback_performed:
        print(f"   ⚠️  Rolled back to previous version")

orchestrator.close()
```

**Step 3: Verify Deployment**
```bash
# Get EC2 instance public IP
aws ec2 describe-instances \
  --instance-ids i-0123456789abcdef0 \
  --query 'Reservations[0].Instances[0].PublicIpAddress' \
  --output text

# Test health endpoint
curl http://<EC2_PUBLIC_IP>:8080/health
# Expected: {"status":"healthy"}

# Test main endpoint
curl http://<EC2_PUBLIC_IP>:8080/
# Expected: Hello from DeployMind!

# SSH to EC2 and check Docker
ssh -i your-key.pem ubuntu@<EC2_PUBLIC_IP>
docker ps
docker logs <container_id>
```

### Scenario 2: Test Security Rejection

**Create Vulnerable App**
```dockerfile
# Intentionally vulnerable Dockerfile
FROM node:14.0.0  # Old, vulnerable version
WORKDIR /app
COPY package.json .
RUN npm install
COPY . .
EXPOSE 3000
CMD ["node", "app.js"]
```

**Expected Result:**
- Security scan should find CRITICAL vulnerabilities
- AI agent should analyze and **REJECT** deployment
- Pipeline should stop at security phase
- No build or deployment should occur

### Scenario 3: Test Rollback on Health Check Failure

**Create App with Broken Health Check**
```python
# app.py - health check always fails
from flask import Flask
app = Flask(__name__)

@app.route('/health')
def health():
    return {'status': 'unhealthy'}, 500  # Always fails

@app.route('/')
def hello():
    return 'App is running but unhealthy'

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
```

**Expected Result:**
- Build succeeds
- Deployment starts
- Health checks fail (2-minute timeout)
- Automatic rollback to previous container
- Response: `rollback_performed=True`

## Monitoring Real Deployment

### Real-Time Progress
```python
def on_deployment_event(event):
    """Monitor real-time deployment events."""
    print(f"📡 {event['event_type']}: {event.get('message', '')}")

    if event['event_type'] == 'security_scan_completed':
        print(f"   Vulnerabilities: {event.get('vulnerabilities', 0)}")
        print(f"   Passed: {event.get('passed')}")

    elif event['event_type'] == 'build_completed':
        print(f"   Image: {event.get('image_tag')}")
        print(f"   Size: {event.get('image_size_mb')} MB")

    elif event['event_type'] == 'deployment_completed':
        print(f"   Container: {event.get('container_id')}")
        print(f"   URL: {event.get('application_url')}")

# Subscribe to events
orchestrator.subscribe_to_events(on_deployment_event)

# Deploy (events stream in real-time)
response = orchestrator.deploy_application(...)
```

### Check Database Records
```python
from infrastructure.database.connection import get_session
from infrastructure.database.models import Deployment, SecurityScan, BuildResult, HealthCheck

with get_session() as session:
    # Get latest deployment
    deployment = session.query(Deployment).order_by(Deployment.created_at.desc()).first()
    print(f"Deployment ID: {deployment.id}")
    print(f"Status: {deployment.status}")
    print(f"Image: {deployment.image_tag}")

    # Get security scan
    scan = deployment.security_scan
    print(f"Scan passed: {scan.passed}")
    print(f"Critical: {scan.critical_count}")

    # Get build result
    build = deployment.build_result
    print(f"Image size: {build.image_size_mb} MB")

    # Get health checks
    for check in deployment.health_checks:
        print(f"Health check: {check.healthy} ({check.response_time_ms}ms)")
```

## Common Issues

### Issue 1: EC2 Instance Not Accessible
```bash
# Check security group allows SSH (port 22)
aws ec2 describe-security-groups \
  --group-ids sg-xxxx \
  --query 'SecurityGroups[0].IpPermissions'

# Add SSH rule if needed
aws ec2 authorize-security-group-ingress \
  --group-id sg-xxxx \
  --protocol tcp \
  --port 22 \
  --cidr 0.0.0.0/0
```

### Issue 2: Docker Not Installed on EC2
```bash
# SSH to instance
ssh -i your-key.pem ubuntu@<EC2_IP>

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker ubuntu

# Start Docker
sudo systemctl start docker
sudo systemctl enable docker
```

### Issue 3: Health Check Timeout
```bash
# Check if app is actually listening
netstat -tulpn | grep 8080

# Check app logs
docker logs <container_id>

# Test health endpoint locally on EC2
curl http://localhost:8080/health
```

### Issue 4: Groq API Rate Limit
```bash
# Groq free tier limits:
# - 30 requests/minute
# - 14,400 requests/day

# If exceeded, wait or upgrade to paid tier
# Check usage at: https://console.groq.com/usage
```

## Success Criteria

A successful real deployment test should:

✅ **Security Phase**
- Clone GitHub repository
- Run Trivy scan via Docker
- AI analyzes results and approves/rejects
- Database records security scan

✅ **Build Phase**
- Generate or detect Dockerfile
- Build Docker image locally
- Tag image with commit SHA
- Database records build result

✅ **Deploy Phase**
- Connect to EC2 via SSH (or SSM)
- Pull/run Docker container
- Perform health checks (HTTP/TCP)
- Database records health checks
- Return application URL

✅ **Verification**
- Can access application URL from browser
- Health endpoint returns 200 OK
- Container is running on EC2
- All database records created
- Redis events published

## Performance Benchmarks

Expected timings for real deployment:
- Repository clone: 5-30s (depends on size)
- Security scan: 30-120s (depends on project)
- Docker build: 60-300s (depends on complexity)
- EC2 deployment: 120-180s (includes 2min health checks)

**Total: 4-8 minutes** for complete deployment

## Cleanup

```bash
# Stop container on EC2
ssh ubuntu@<EC2_IP> 'docker stop $(docker ps -q)'

# Remove all containers
ssh ubuntu@<EC2_IP> 'docker system prune -af'

# Terminate EC2 instance (if test instance)
aws ec2 terminate-instances --instance-ids i-xxxx
```

## Next Steps

After successful real deployment testing:
1. Set up CI/CD pipeline (GitHub Actions)
2. Configure production monitoring (CloudWatch, DataDog)
3. Set up alerting (PagerDuty, Slack)
4. Document deployment runbooks
5. Create disaster recovery procedures
