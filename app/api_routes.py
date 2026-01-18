"""API routes for document upload endpoints."""

import logging
import uuid
from fastapi import APIRouter, UploadFile, File, HTTPException, Form, Depends, BackgroundTasks
from pydantic import BaseModel, Field
from typing import Optional
from app.services.storage_service import StorageService
from app.auth import authenticate_client
from app.models import ClientCredential
from app.services.extraction_orchestrator import create_extraction_graph, AgentState
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
    success: bool = Field(..., description="Whether the processing was queued")
    message: str = Field(..., description="Response message")
    job_id: str = Field(..., description="Job ID for tracking (if needed)")


async def process_document_background(document_url: str, user_id: str, job_id: str):
    """
    Background task to process document through LangGraph pipeline.
    
    Args:
        document_url: URL of the document in GCS
        user_id: User ID
        job_id: Unique job identifier
    """
    logger.info(f"Starting background processing for job {job_id}, document: {document_url}")
    
    try:
        # Extract filename from URL
        from pathlib import Path
        document_filename = Path(document_url).name
        
        # Create initial agent state with minimal required fields
        initial_state: AgentState = {
            "job_id": job_id,
            "user_id": user_id,
            "document_url": document_url,
            "document_filename": document_filename,
            "file_type": "",  # Will be set by ingestion agent
            "raw_content": None,
            "parsed_markdown": None,
            "extracted_questions": None,
            "validated_markdown": None,
            "vector_ids": None,
            "status": "pending",
            "error_message": None,
            "metadata": {},
            "validation_attempts": 0,
            "validation_passed": False,
        }
        
        # Create and run the extraction graph
        graph = create_extraction_graph()
        
        # Run the graph (will process through all nodes, but only ingestion does real work)
        final_state = graph.invoke(initial_state)
        
        logger.info(f"Background processing completed for job {job_id}, final status: {final_state.get('status')}")
        
    except Exception as e:
        logger.error(f"Error in background processing for job {job_id}: {str(e)}", exc_info=True)


@router.post("/process-doc", response_model=ProcessDocResponse)
async def process_document(
    request: ProcessDocRequest,
    background_tasks: BackgroundTasks,
    client: ClientCredential = Depends(authenticate_client)
):
    """
    Process a document through the extraction pipeline.
    
    Accepts a document URL (from /upload endpoint) and triggers the LangGraph pipeline.
    Processing happens asynchronously in the background.
    
    Requires authentication via X-Client-Id and X-Client-Secret headers.
    """
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
        
        # Generate a simple job ID
        job_id = str(uuid.uuid4())
        
        logger.info(f"Queuing document processing: job_id={job_id}, url={request.document_url}, user_id={request.user_id}")
        
        # Add background task
        background_tasks.add_task(
            process_document_background,
            document_url=request.document_url.strip(),
            user_id=request.user_id.strip(),
            job_id=job_id
        )
        
        return ProcessDocResponse(
            success=True,
            message="Document processing queued successfully",
            job_id=job_id
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error queuing document processing: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to queue document processing: {str(e)}"
        )

