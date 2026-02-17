# Tools Directory

This directory contains external tools used by DeployMind.

## Trivy Scanner

DeployMind uses Docker-based Trivy for vulnerability scanning. No manual binary download required.

### Setup

Ensure Docker is installed and running:

```bash
# Verify Docker installation
docker --version

# Test Trivy (pulls image automatically on first use)
docker run --rm aquasec/trivy --version
```

**First run**: Docker will pull the `aquasec/trivy:latest` image (~200MB, one-time only)

### Usage

```python
from infrastructure.security.trivy_scanner import TrivyScanner

# Initialize scanner (Docker-based)
scanner = TrivyScanner()

# Scan Docker image
result = scanner.scan_image("python:3.11-slim")
print(result.severity_summary)

# Scan filesystem
result = scanner.scan_filesystem("./my-app")
if not result.passed:
    print(f"Found {result.critical_count} CRITICAL vulnerabilities")
```

### Requirements

- Docker installed and running
- Internet connection (for first-time image pull)
