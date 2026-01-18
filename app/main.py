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
from fastapi.responses import JSONResponse
from app.config import settings
from app.api_routes import router
from app.prompt_routes import router as prompt_router
from app.database import Base, engine

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

# Initialize database tables on startup
@app.on_event("startup")
async def startup_event():
    """Initialize database tables on application startup."""
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database tables: {str(e)}")

# Include API routes with prefix
app.include_router(router)
app.include_router(prompt_router)


@app.get("/")
async def root():
    """Root endpoint - basic health check."""
    return {"status": "healthy", "service": "Document Upload API"}


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "Document Upload API"}


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

