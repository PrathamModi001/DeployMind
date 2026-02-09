"""
Temporary FastAPI application for DeployMind health checks.

This is a minimal web API that allows DeployMind to be deployed as a containerized
service with health check endpoints. This is TEMPORARY and only for testing the
deployment pipeline.

DO NOT use this in production. DeployMind is designed as a CLI/library tool.
"""
from fastapi import FastAPI
from datetime import datetime
import os

app = FastAPI(
    title="DeployMind Health API",
    description="Temporary API for testing DeployMind deployment",
    version="0.1.0"
)


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "DeployMind",
        "status": "running",
        "message": "Temporary API for deployment testing",
        "timestamp": datetime.utcnow().isoformat()
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "deploymind-api",
        "timestamp": datetime.utcnow().isoformat(),
        "environment": os.getenv("ENVIRONMENT", "unknown"),
        "version": "0.1.0"
    }


@app.get("/status")
async def status():
    """Detailed status endpoint."""
    return {
        "status": "operational",
        "service": "deploymind-api",
        "uptime": "available",
        "checks": {
            "api": "healthy",
            "container": "running"
        },
        "metadata": {
            "environment": os.getenv("ENVIRONMENT", "development"),
            "aws_region": os.getenv("AWS_REGION", "unknown"),
            "timestamp": datetime.utcnow().isoformat()
        }
    }


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
