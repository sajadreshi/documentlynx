"""Google Cloud Storage service for document uploads."""

import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional, Tuple
from google.cloud import storage
from google.cloud.exceptions import GoogleCloudError, NotFound
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
    
    def upload_image_public(
        self, file_content: bytes, filename: str, user_id: str, job_id: str
    ) -> str:
        """
        Upload an image to Google Cloud Storage and return an application-served URL.
        
        Images are stored in the processed/{user_id}/{job_id}/images/ directory.
        Instead of direct GCS URLs (which require auth), returns an application
        endpoint URL that serves the image through the API.

        Args:
            file_content: The image content as bytes
            filename: The image filename
            user_id: The user ID to organize images
            job_id: The job ID for grouping related images

        Returns:
            str: Full application URL for serving the image (includes host from settings)

        Raises:
            GoogleCloudError: If upload fails
            ValueError: If parameters are invalid
        """
        if not user_id or not user_id.strip():
            raise ValueError("user_id cannot be empty")
        
        if not filename or not filename.strip():
            raise ValueError("filename cannot be empty")
        
        if not job_id or not job_id.strip():
            raise ValueError("job_id cannot be empty")

        # Construct the blob path: processed/{user_id}/{job_id}/images/{filename}
        blob_path = f"processed/{user_id.strip()}/{job_id.strip()}/images/{filename.strip()}"
        
        # Create blob and upload
        blob = self.bucket.blob(blob_path)
        
        # Upload file content
        blob.upload_from_string(file_content, content_type=self._get_content_type(filename))
        
        logger.info(f"Uploaded image to GCS: {blob_path}")
        
        # Return full application URL that serves images through our API
        # Base URL is configurable via API_BASE_URL in .env
        base_url = settings.api_base_url.rstrip('/')
        app_url = f"{base_url}/documently/api/v1/images/{user_id.strip()}/{job_id.strip()}/{filename.strip()}"
        
        return app_url
    
    def upload_images_from_zip(
        self, zip_path: str, user_id: str, job_id: str
    ) -> dict[str, str]:
        """
        Extract and upload all images from a ZIP file.
        
        Args:
            zip_path: Path to the ZIP file
            user_id: The user ID
            job_id: The job ID
            
        Returns:
            dict: Mapping of local paths to public URLs
        """
        import zipfile
        import os
        
        url_mapping = {}
        
        failed_images = []
        try:
            with zipfile.ZipFile(zip_path, 'r') as zf:
                for name in zf.namelist():
                    # Check if it's an image file
                    if name.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg')):
                        # Read image content
                        image_content = zf.read(name)

                        # Get just the filename
                        filename = os.path.basename(name)

                        # Upload to GCS with per-image retry
                        uploaded = False
                        for attempt in range(3):
                            try:
                                public_url = self.upload_image_public(
                                    image_content, filename, user_id, job_id
                                )
                                # Map both full path and filename to URL
                                url_mapping[name] = public_url
                                url_mapping[filename] = public_url
                                logger.debug(f"Uploaded image: {name} -> {public_url}")
                                uploaded = True
                                break
                            except Exception as img_err:
                                logger.warning(
                                    "Image upload attempt %d/3 failed for %s: %s",
                                    attempt + 1, name, img_err,
                                )
                        if not uploaded:
                            failed_images.append(name)

            total = len(url_mapping) // 2
            logger.info(f"Uploaded {total} images from ZIP for job {job_id}")
            if failed_images:
                logger.error(f"Failed to upload {len(failed_images)} images: {failed_images}")

        except Exception as e:
            logger.error(f"Error uploading images from ZIP: {str(e)}", exc_info=True)

        return url_mapping
    
    def get_image(
        self, user_id: str, job_id: str, filename: str
    ) -> Tuple[Optional[bytes], Optional[str]]:
        """
        Retrieve an image from Google Cloud Storage.
        
        Args:
            user_id: The user ID
            job_id: The job ID
            filename: The image filename
            
        Returns:
            Tuple of (image_content, content_type) or (None, None) if not found
        """
        if not user_id or not job_id or not filename:
            return None, None
        
        # Construct the blob path
        blob_path = f"processed/{user_id.strip()}/{job_id.strip()}/images/{filename.strip()}"
        
        try:
            blob = self.bucket.blob(blob_path)
            
            if not blob.exists():
                logger.warning(f"Image not found in GCS: {blob_path}")
                return None, None
            
            # Download the image content
            content = blob.download_as_bytes()
            content_type = self._get_content_type(filename)
            
            logger.debug(f"Retrieved image from GCS: {blob_path}")
            return content, content_type
            
        except NotFound:
            logger.warning(f"Image not found: {blob_path}")
            return None, None
        except Exception as e:
            logger.error(f"Error retrieving image from GCS: {str(e)}", exc_info=True)
            return None, None

