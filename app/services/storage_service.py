"""Google Cloud Storage service for document uploads."""

import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional
from google.cloud import storage
from google.cloud.exceptions import GoogleCloudError
from app.config import settings

logger = logging.getLogger(__name__)


class StorageService:
    """Service for handling Google Cloud Storage operations."""

    def __init__(self):
        """Initialize the storage client."""
        # Set the credentials path for Google Cloud
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = settings.google_application_credentials
        
        self.client = storage.Client(project=settings.google_cloud_project_id)
        self.bucket_name = settings.google_cloud_storage_bucket
        self.bucket = self.client.bucket(self.bucket_name)

    def upload_document(
        self, file_content: bytes, filename: str, user_id: str
    ) -> str:
        """
        Upload a document to Google Cloud Storage.

        Args:
            file_content: The file content as bytes
            filename: The original filename
            user_id: The user ID to organize documents

        Returns:
            str: Public URL of the uploaded document

        Raises:
            GoogleCloudError: If upload fails
            ValueError: If user_id or filename is invalid
        """
        if not user_id or not user_id.strip():
            raise ValueError("user_id cannot be empty")
        
        if not filename or not filename.strip():
            raise ValueError("filename cannot be empty")

        # Construct the blob path: documents.in/{user_id}/{filename}
        blob_path = f"documents.in/{user_id.strip()}/{filename.strip()}"
        
        # Create blob and upload
        blob = self.bucket.blob(blob_path)
        
        # Upload file content
        blob.upload_from_string(file_content, content_type=self._get_content_type(filename))
        
        # Generate a signed URL for public access
        # For uniform bucket-level access, we use signed URLs instead of ACLs
        # Expiration time is configurable via SIGNED_URL_EXPIRATION_SECONDS in .env
        # Maximum allowed by Google Cloud Storage is 7 days (604800 seconds)
        expiration = datetime.now(timezone.utc) + timedelta(seconds=settings.signed_url_expiration_seconds)
        
        try:
            # Generate signed URL using the blob's method
            # The blob is already associated with the bucket and client that has credentials
            url = blob.generate_signed_url(
                expiration=expiration,
                method='GET',
                version='v4'
            )
            
            # Verify it's actually a signed URL (contains signature parameters)
            if '?' not in url:
                raise ValueError("Generated URL does not contain query parameters (not a signed URL)")
            
            # Check for signed URL indicators
            has_signature = any(param in url for param in ['X-Goog-Algorithm', 'X-Goog-Signature', 'Signature'])
            if not has_signature:
                raise ValueError("Generated URL does not appear to be a signed URL")
            
            logger.info(f"Generated signed URL successfully for {blob_path}")
                
        except Exception as e:
            # Log the full error for debugging
            logger.error(f"Failed to generate signed URL: {str(e)}", exc_info=True)
            # Re-raise the exception so we can see what's wrong
            # For now, fallback to standard URL but log the error
            logger.warning("Using standard URL format as fallback - signed URL generation failed")
            url = f"https://storage.googleapis.com/{self.bucket_name}/{blob_path}"
        
        return url

    def _get_content_type(self, filename: str) -> str:
        """
        Determine content type based on file extension.

        Args:
            filename: The filename

        Returns:
            str: Content type
        """
        extension = Path(filename).suffix.lower()
        content_types = {
            ".pdf": "application/pdf",
            ".doc": "application/msword",
            ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ".txt": "text/plain",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".gif": "image/gif",
            ".xls": "application/vnd.ms-excel",
            ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        }
        return content_types.get(extension, "application/octet-stream")

    def document_exists(self, filename: str, user_id: str) -> bool:
        """
        Check if a document already exists.

        Args:
            filename: The filename
            user_id: The user ID

        Returns:
            bool: True if document exists, False otherwise
        """
        blob_path = f"documents.in/{user_id.strip()}/{filename.strip()}"
        blob = self.bucket.blob(blob_path)
        return blob.exists()

