# Tools Directory

This directory contains external tools used by DeployMind.

## Trivy Scanner

**Why not included**: Trivy executable is 200+ MB and exceeds GitHub's file size limit.

### How to Setup Trivy

**Option 1: Automatic Download (Recommended)**
```bash
# From project root
python scripts/setup_trivy.py
```

**Option 2: Manual Download**
1. Visit: https://github.com/aquasecurity/trivy/releases
2. Download the latest release for your platform
3. Extract to this directory (tools/)
4. Rename to trivy.exe (Windows) or trivy (Linux/macOS)

**Option 3: Use Docker (No Download Needed)**
```bash
# Trivy runs in Docker container
# No manual setup required
```

### Verify Installation

```bash
# Windows PowerShell
.\tools\trivy.exe --version

# Docker
docker run aquasec/trivy --version
```

Expected output: `Version: 0.48.3` (or higher)
