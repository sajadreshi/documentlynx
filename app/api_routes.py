"""API routes for document upload endpoints."""

import logging
from fastapi import APIRouter, UploadFile, File, HTTPException, Form, Depends
from pydantic import BaseModel, Field
from typing import Optional
from app.services.storage_service import StorageService
from app.auth import authenticate_client
from app.models import ClientCredential
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

