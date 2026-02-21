"""FastAPI application for document upload API."""

import sys
from pathlib import Path

# Add project root to Python path to avoid conflicts with site-packages app.py
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import logging
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.config import settings
from app.api_routes import router
from app.question_routes import router as question_router
from app.database import Base, engine, SessionLocal

# Configure logging
# Set to DEBUG for development, INFO for production
log_level = logging.DEBUG if os.getenv("DEBUG", "false").lower() == "true" else logging.INFO
logging.basicConfig(
    level=log_level,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Document Upload API",
    description="API for uploading documents to Google Cloud Storage",
    version="1.0.0"
)

# CORS middleware — allow Vite dev server and configurable origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize database tables on startup and configure LangSmith
@app.on_event("startup")
async def startup_event():
    """Initialize database tables and optional LangSmith tracing on startup."""
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database tables: {str(e)}")

    # Configure LangSmith tracing if API key is provided
    if settings.langsmith_api_key:
        os.environ["LANGSMITH_API_KEY"] = settings.langsmith_api_key
        os.environ["LANGSMITH_PROJECT"] = settings.langsmith_project
        os.environ["LANGSMITH_TRACING_V2"] = str(settings.langsmith_tracing_v2).lower()
        logger.info(
            "LangSmith tracing configured (project=%s, v2=%s)",
            settings.langsmith_project,
            settings.langsmith_tracing_v2,
        )
    else:
        os.environ.pop("LANGSMITH_TRACING_V2", None)
        os.environ.pop("LANGSMITH_API_KEY", None)
        logger.debug("LangSmith tracing disabled (no API key)")

# Include API routes
app.include_router(router)
app.include_router(question_router)


@app.get("/")
async def root():
    """Root endpoint - basic health check."""
    return {"status": "healthy", "service": "Document Upload API"}


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "Document Upload API"}


@app.get("/health/detailed")
async def health_check_detailed():
    """Detailed health check with dependency status."""
    checks: dict = {}
    overall = "healthy"

    # Check database connectivity
    try:
        db = SessionLocal()
        db.execute("SELECT 1")
        db.close()
        checks["database"] = {"status": "ok"}
    except Exception as e:
        checks["database"] = {"status": "error", "detail": str(e)}
        overall = "degraded"

    # Check GCS bucket access (optional)
    try:
        from app.services.storage_service import StorageService
        svc = StorageService()
        svc.bucket.exists()
        checks["gcs"] = {"status": "ok"}
    except Exception as e:
        checks["gcs"] = {"status": "error", "detail": str(e)}
        overall = "degraded"

    # Check Docling API reachability (optional)
    try:
        import httpx
        resp = httpx.get(
            settings.docling_api_url.replace("/v1/convert/source", "/health"),
            timeout=5,
        )
        checks["docling"] = {"status": "ok" if resp.status_code < 500 else "error"}
    except Exception:
        checks["docling"] = {"status": "unreachable"}
        overall = "degraded"

    return {"status": overall, "checks": checks}


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler."""
    logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "An internal server error occurred"}
    )


if __name__ == "__main__":
    import uvicorn
    # Enable debug mode if DEBUG env var is set
    debug_mode = os.getenv("DEBUG", "false").lower() == "true"
    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True,
        log_level="debug" if debug_mode else "info"
    )
