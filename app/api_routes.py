"""API routes for document upload endpoints."""

import asyncio
import logging
from datetime import datetime
from urllib.parse import urlparse
from pathlib import Path
from uuid import UUID
from fastapi import APIRouter, UploadFile, File, HTTPException, Form, Depends
from fastapi.responses import Response
from pydantic import BaseModel, Field
from typing import Optional
from app.services.storage_service import StorageService
from app.auth import authenticate_client
from app.models import ClientCredential
from app.database import SessionLocal
from app.services.extraction_orchestrator import create_extraction_graph, AgentState
from app.services.job_service import JobService
from google.cloud.exceptions import GoogleCloudError

# Configure logging
logger = logging.getLogger(__name__)

# Initialize API router with prefix
router = APIRouter(prefix="/documently/api/v1", tags=["Document Upload API"])

# Initialize storage service
storage_service = StorageService()


class UploadResponse(BaseModel):
    """Response model for document upload."""
    success: bool = Field(..., description="Whether the upload was successful")
    message: str = Field(..., description="Response message")
    url: Optional[str] = Field(None, description="Public URL of the uploaded document")
    user_id: Optional[str] = Field(None, description="User ID")
    filename: Optional[str] = Field(None, description="Uploaded filename")


@router.post("/upload", response_model=UploadResponse)
async def upload_document(
    file: UploadFile = File(..., description="The document file to upload"),
    user_id: str = Form(..., description="User ID to organize documents"),
    client: ClientCredential = Depends(authenticate_client)
):
    """
    Upload a document to Google Cloud Storage.

    The document will be stored at: documents.in/{user_id}/{filename}
    The returned URL will have public access rights.

    Args:
        file: The file to upload
        user_id: User ID for organizing documents

    Returns:
        UploadResponse: Response containing the public URL of the uploaded document

    Raises:
        HTTPException: If upload fails or validation fails
    """
    try:
        # Validate user_id
        if not user_id or not user_id.strip():
            raise HTTPException(
                status_code=400,
                detail="user_id is required and cannot be empty"
            )

        # Validate file
        if not file.filename:
            raise HTTPException(
                status_code=400,
                detail="Filename is required"
            )

        # Read file content
        file_content = await file.read()
        
        if not file_content:
            raise HTTPException(
                status_code=400,
                detail="File content is empty"
            )

        logger.info(f"Uploading document: {file.filename} for user: {user_id}")

        # Upload to Google Cloud Storage
        public_url = storage_service.upload_document(
            file_content=file_content,
            filename=file.filename,
            user_id=user_id.strip()
        )

        logger.info(f"Document uploaded successfully. URL: {public_url}")

        return UploadResponse(
            success=True,
            message="Document uploaded successfully",
            url=public_url,
            user_id=user_id.strip(),
            filename=file.filename
        )

    except ValueError as e:
        logger.error(f"Validation error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    
    except GoogleCloudError as e:
        logger.error(f"Google Cloud Storage error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to upload document to cloud storage: {str(e)}"
        )
    
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"An unexpected error occurred: {str(e)}"
        )


class ProcessDocRequest(BaseModel):
    """Request model for processing a document."""
    document_url: str = Field(..., description="Public URL of the document from /upload endpoint")
    user_id: str = Field(..., description="User ID for scoping the processing")


class ProcessDocResponse(BaseModel):
    """Response model for document processing request."""
    job_id: str = Field(..., description="Job ID for tracking status")
    status: str = Field(..., description="Current job status")
    message: str = Field(..., description="Response message")


def _run_extraction_pipeline(initial_state: AgentState) -> dict:
    """
    Run the extraction pipeline synchronously.
    
    This function is designed to be run in a thread pool to avoid blocking
    the async event loop.
    
    Args:
        initial_state: Initial agent state
        
    Returns:
        Final state dictionary from the pipeline
    """
    graph = create_extraction_graph()
    return graph.invoke(initial_state)


async def process_document_background(document_url: str, user_id: str, job_id: str):
    """
    Background task to process document through LangGraph pipeline.
    
    Runs the blocking pipeline in a thread pool to avoid blocking the event loop.
    
    Args:
        document_url: URL of the document in GCS
        user_id: User ID
        job_id: Unique job identifier (UUID string)
    """
    logger.info(f"Starting background processing for job {job_id}, document: {document_url}")
    
    db = None
    try:
        # Extract filename from URL (parse URL to remove query parameters)
        parsed_url = urlparse(document_url)
        document_filename = Path(parsed_url.path).name
        
        # Create initial agent state with minimal required fields
        initial_state: AgentState = {
            "job_id": job_id,
            "user_id": user_id,
            "document_url": document_url,
            "document_filename": document_filename,
            "file_type": "",  # Will be set by ingestion agent
            "raw_content": None,
            "parsed_markdown": None,
            "cleaned_markdown": None,  # Cleaned/formatted markdown for UI display
            "extracted_questions": None,
            "validated_markdown": None,
            "vector_ids": None,
            "status": "pending",
            "error_message": None,
            "metadata": {},
            "validation_attempts": 0,
            "validation_passed": False,
            "docling_options": None,  # Agents can modify to customize Docling conversion
            "use_file_conversion": True,  # Uses file-based conversion with ZIP output by default
            "output_zip_path": None,  # Path to output ZIP (set by ingestion agent when use_file_conversion=True)
            "source_file_path": None,  # Path to source file (kept for validation comparison)
            "validation_feedback": None,  # LLM feedback on quality issues
            "document_id": None,  # Database document UUID (set by persistence agent)
            "question_ids": None,  # List of persisted question UUIDs (set by persistence agent)
            "public_markdown": None,  # Markdown with public GCS image URLs
        }
        
        # Run the blocking pipeline in a thread pool to avoid blocking the event loop
        final_state = await asyncio.to_thread(_run_extraction_pipeline, initial_state)
        
        # Check for soft failures (pipeline completed but no output)
        db = SessionLocal()
        document_id = final_state.get("document_id")
        question_ids = final_state.get("question_ids") or []
        error_message = final_state.get("error_message")
        
        # Determine if the job actually succeeded
        # A job is considered failed if:
        # 1. There's an explicit error_message in state
        # 2. No document was created (document_id is None)
        # 3. No markdown content was produced
        has_content = (
            final_state.get("cleaned_markdown") or 
            final_state.get("parsed_markdown") or 
            final_state.get("raw_content")
        )
        
        if error_message:
            # Explicit error from an agent
            JobService.fail_job(db, job_id, error_message)
            logger.error(f"Job {job_id} failed with error: {error_message}")
        elif not document_id and not has_content:
            # No document created and no content - something went wrong
            failure_reason = "Processing failed: No content extracted from document. The source URL may be invalid or expired."
            JobService.fail_job(db, job_id, failure_reason)
            logger.error(f"Job {job_id} failed: {failure_reason}")
        else:
            # Success
            JobService.complete_job(
                db=db,
                job_id=job_id,
                document_id=UUID(document_id) if document_id else None,
                question_count=len(question_ids)
            )
            logger.info(f"Background processing completed for job {job_id}, document_id={document_id}, questions={len(question_ids)}")
        
    except Exception as e:
        logger.error(f"Error in background processing for job {job_id}: {str(e)}", exc_info=True)
        
        # Mark job as failed
        try:
            if db is None:
                db = SessionLocal()
            JobService.fail_job(db, job_id, str(e))
        except Exception as fail_error:
            logger.error(f"Failed to mark job {job_id} as failed: {fail_error}")
    finally:
        if db:
            db.close()


@router.post("/process-doc", response_model=ProcessDocResponse)
async def process_document(
    request: ProcessDocRequest,
    client: ClientCredential = Depends(authenticate_client)
):
    """
    Process a document through the extraction pipeline.
    
    Accepts a document URL (from /upload endpoint) and triggers the LangGraph pipeline.
    Processing happens asynchronously in the background - this endpoint returns immediately.
    
    Use GET /jobs/{job_id} to check processing status.
    
    Requires authentication via X-Client-Id and X-Client-Secret headers.
    """
    db = None
    try:
        # Validate inputs
        if not request.document_url or not request.document_url.strip():
            raise HTTPException(
                status_code=400,
                detail="document_url is required and cannot be empty"
            )
        
        if not request.user_id or not request.user_id.strip():
            raise HTTPException(
                status_code=400,
                detail="user_id is required and cannot be empty"
            )
        
        # Create job record in database
        db = SessionLocal()
        job = JobService.create_job(
            db=db,
            user_id=request.user_id.strip(),
            document_url=request.document_url.strip()
        )
        job_id = str(job.id)
        
        logger.info(f"Queuing document processing: job_id={job_id}, url={request.document_url}, user_id={request.user_id}")
        
        # Fire-and-forget: Create an async task that runs independently
        # This returns immediately without waiting for the pipeline to complete
        asyncio.create_task(
            process_document_background(
                document_url=request.document_url.strip(),
                user_id=request.user_id.strip(),
                job_id=job_id
            )
        )
        
        return ProcessDocResponse(
            job_id=job_id,
            status="queued",
            message="Document processing queued. Use GET /jobs/{job_id} to check status."
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error queuing document processing: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to queue document processing: {str(e)}"
        )
    finally:
        if db:
            db.close()


@router.get("/images/{user_id}/{job_id}/{filename}")
async def serve_image(
    user_id: str,
    job_id: str,
    filename: str
):
    """
    Serve an image from Google Cloud Storage.
    
    This endpoint acts as a proxy for GCS images, handling authentication
    internally. Images are cached by browsers via Cache-Control headers.
    
    This is a public endpoint - no authentication required for viewing images.
    
    Args:
        user_id: The user ID who owns the image
        job_id: The processing job ID
        filename: The image filename
        
    Returns:
        The image content with appropriate content-type headers
        
    Raises:
        HTTPException 404: If image not found
        HTTPException 500: If error retrieving image
    """
    try:
        # Validate path parameters
        if not user_id or not job_id or not filename:
            raise HTTPException(
                status_code=400,
                detail="user_id, job_id, and filename are required"
            )
        
        # Retrieve image from GCS
        content, content_type = storage_service.get_image(user_id, job_id, filename)
        
        if content is None:
            raise HTTPException(
                status_code=404,
                detail=f"Image not found: {filename}"
            )
        
        # Return image with caching headers
        return Response(
            content=content,
            media_type=content_type,
            headers={
                "Cache-Control": "public, max-age=31536000",  # Cache for 1 year
                "Content-Disposition": f"inline; filename=\"{filename}\""
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error serving image: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve image: {str(e)}"
        )


class JobStatusResponse(BaseModel):
    """Response model for job status query."""
    job_id: str = Field(..., description="Job UUID")
    user_id: str = Field(..., description="User ID")
    status: str = Field(..., description="Current job status: queued, ingesting, parsing, validating, persisting, classifying, vectorizing, completed, failed")
    error_message: Optional[str] = Field(None, description="Error message if job failed")
    document_id: Optional[str] = Field(None, description="Document UUID (available when completed)")
    question_count: int = Field(0, description="Number of questions extracted")
    created_at: Optional[datetime] = Field(None, description="When the job was created")
    started_at: Optional[datetime] = Field(None, description="When processing started")
    completed_at: Optional[datetime] = Field(None, description="When processing completed")


@router.get("/jobs/{job_id}", response_model=JobStatusResponse)
async def get_job_status(
    job_id: str,
    client: ClientCredential = Depends(authenticate_client)
):
    """
    Get the current status of a processing job.
    
    Use this endpoint to poll for job completion after calling POST /process-doc.
    
    Requires authentication via X-Client-Id and X-Client-Secret headers.
    
    Args:
        job_id: The job UUID returned from /process-doc
        
    Returns:
        JobStatusResponse: Current job status and details
        
    Raises:
        HTTPException 404: If job not found
    """
    db = None
    try:
        db = SessionLocal()
        job = JobService.get_job(db, job_id)
        
        if not job:
            raise HTTPException(
                status_code=404,
                detail=f"Job not found: {job_id}"
            )
        
        return JobStatusResponse(
            job_id=str(job.id),
            user_id=job.user_id,
            status=job.status,
            error_message=job.error_message,
            document_id=str(job.document_id) if job.document_id else None,
            question_count=job.question_count or 0,
            created_at=job.created_at,
            started_at=job.started_at,
            completed_at=job.completed_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting job status: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get job status: {str(e)}"
        )
    finally:
        if db:
            db.close()


# =============================================================================
# Search Endpoints
# =============================================================================

class SearchResult(BaseModel):
    """A single search result."""
    question: dict = Field(..., description="Question data")
    similarity: float = Field(..., description="Similarity score (0-1)")


class SearchResponse(BaseModel):
    """Response model for question search."""
    query: str = Field(..., description="The search query")
    results: list[SearchResult] = Field(..., description="List of matching questions")
    count: int = Field(..., description="Number of results returned")


class SearchStatsResponse(BaseModel):
    """Response model for search statistics."""
    user_id: str = Field(..., description="User ID")
    total_questions: int = Field(..., description="Total questions for user")
    embedded_questions: int = Field(..., description="Questions with embeddings")
    searchable_percentage: float = Field(..., description="Percentage of searchable questions")


@router.get("/questions/search", response_model=SearchResponse)
async def search_questions(
    q: str,
    limit: int = 10,
    min_similarity: float = 0.3,
    user_id: str = None,
    client: ClientCredential = Depends(authenticate_client)
):
    """
    Semantic search for questions.
    
    Finds questions semantically similar to the search query using vector embeddings.
    Results are scoped to the authenticated user's questions only.
    
    Requires authentication via X-Client-Id and X-Client-Secret headers.
    
    Args:
        q: Search query (natural language)
        limit: Maximum results to return (default: 10, max: 50)
        min_similarity: Minimum similarity threshold 0-1 (default: 0.3)
        user_id: Optional user ID filter (defaults to all users for this client)
        
    Returns:
        SearchResponse: List of matching questions with similarity scores
        
    Example:
        GET /questions/search?q=area%20of%20triangle&limit=5
    """
    from app.services.search_service import SearchService
    
    if not q or not q.strip():
        raise HTTPException(
            status_code=400,
            detail="Search query 'q' is required"
        )
    
    # Use provided user_id or require one
    search_user_id = user_id
    if not search_user_id:
        raise HTTPException(
            status_code=400,
            detail="user_id is required for search"
        )
    
    try:
        search_service = SearchService()
        results = search_service.search_questions(
            query=q.strip(),
            user_id=search_user_id,
            limit=min(limit, 50),
            min_similarity=min_similarity
        )
        
        return SearchResponse(
            query=q.strip(),
            results=[
                SearchResult(
                    question=r["question"],
                    similarity=r["similarity"]
                )
                for r in results
            ],
            count=len(results)
        )
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error during search: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Search failed: {str(e)}"
        )


@router.get("/questions/{question_id}/similar", response_model=SearchResponse)
async def find_similar_questions(
    question_id: str,
    limit: int = 5,
    user_id: str = None,
    client: ClientCredential = Depends(authenticate_client)
):
    """
    Find questions similar to an existing question.
    
    Useful for "related questions" or "you might also like" features.
    
    Requires authentication via X-Client-Id and X-Client-Secret headers.
    
    Args:
        question_id: UUID of the source question
        limit: Maximum results to return (default: 5)
        user_id: User ID who owns the question
        
    Returns:
        SearchResponse: List of similar questions with similarity scores
    """
    from app.services.search_service import SearchService
    
    if not user_id:
        raise HTTPException(
            status_code=400,
            detail="user_id is required"
        )
    
    try:
        search_service = SearchService()
        results = search_service.find_similar_to_question(
            question_id=question_id,
            user_id=user_id,
            limit=min(limit, 20)
        )
        
        return SearchResponse(
            query=f"similar to {question_id}",
            results=[
                SearchResult(
                    question=r["question"],
                    similarity=r["similarity"]
                )
                for r in results
            ],
            count=len(results)
        )
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error finding similar questions: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to find similar questions: {str(e)}"
        )


@router.get("/questions/search/stats", response_model=SearchStatsResponse)
async def get_search_stats(
    user_id: str,
    client: ClientCredential = Depends(authenticate_client)
):
    """
    Get statistics about searchable questions for a user.
    
    Returns counts of total and embedded questions.
    
    Requires authentication via X-Client-Id and X-Client-Secret headers.
    
    Args:
        user_id: User ID to get stats for
        
    Returns:
        SearchStatsResponse: Question counts and search coverage
    """
    from app.services.search_service import SearchService
    
    if not user_id:
        raise HTTPException(
            status_code=400,
            detail="user_id is required"
        )
    
    try:
        search_service = SearchService()
        stats = search_service.get_search_stats(user_id=user_id)
        
        return SearchStatsResponse(**stats)
        
    except Exception as e:
        logger.error(f"Error getting search stats: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get search stats: {str(e)}"
        )

