"""DeployMind Backend API - Main Application."""
import logging
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import time

from .config import settings
from .routes import auth, deployments, analytics, websocket, ai, environment, monitoring, webhooks, security, github, uploads, instances, ai_advanced

# Set up logger
logger = logging.getLogger("uvicorn.error")

# Create FastAPI app
app = FastAPI(
    title=settings.api_title,
    version=settings.api_version,
    description=settings.api_description,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

# Configure CORS - Allow all localhost ports for development
allowed_origins = [
    "http://localhost:3000",
    "http://localhost:3001",
    "http://localhost:3002",
    "http://localhost:5000",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:3001",
    "http://127.0.0.1:3002",
    "http://127.0.0.1:5000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

print("CORS: Allowing localhost ports: 3000, 3001, 3002, 5000")


# Add request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all incoming requests."""
    start_time = time.time()

    # Log incoming request
    logger.info("=" * 80)
    logger.info(f"[REQUEST] {request.method} {request.url.path}")
    logger.info(f"[REQUEST] Full URL: {request.url}")
    logger.info(f"[REQUEST] Client: {request.client.host if request.client else 'unknown'}")

    # Process request
    try:
        response = await call_next(request)
        process_time = time.time() - start_time
        logger.info(f"[RESPONSE] Status: {response.status_code}")
        logger.info(f"[RESPONSE] Time: {process_time:.3f}s")
        logger.info("=" * 80)
        return response
    except Exception as e:
        logger.error(f"[ERROR] Request failed: {str(e)}")
        logger.error(f"[ERROR] Exception type: {type(e).__name__}")
        import traceback
        logger.error(f"[ERROR] Traceback:\n{traceback.format_exc()}")
        logger.info("=" * 80)
        raise

# Include routers
app.include_router(auth.router)
app.include_router(deployments.router)
app.include_router(analytics.router)
app.include_router(websocket.router)
app.include_router(ai.router)
app.include_router(environment.router)
app.include_router(monitoring.router)
app.include_router(webhooks.router)
app.include_router(security.router)
app.include_router(github.router)
app.include_router(uploads.router)
app.include_router(instances.router)
app.include_router(ai_advanced.router)


@app.get("/")
async def root():
    """Root endpoint - API information."""
    return {
        "name": settings.api_title,
        "version": settings.api_version,
        "description": settings.api_description,
        "docs": "/api/docs",
        "health": "/health",
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "deploymind-api",
        "version": settings.api_version,
    }


@app.get("/api/health")
async def api_health():
    """API health check endpoint."""
    return await health_check()


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Handle all uncaught exceptions."""
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error",
            "message": str(exc) if settings.api_version.startswith("dev") else "An error occurred"
        }
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,  # Enable auto-reload for development
    )
