"""Docling API service for document conversion and processing."""

import json
import logging
import os
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional
import httpx
from app.config import settings

logger = logging.getLogger(__name__)


@dataclass
class DoclingOptions:
    """Configurable options for Docling API calls.
    
    Agents can modify these options via AgentState to customize
    document conversion behavior.
    """
    
    # Output settings
    target_type: str = "inbody"  # "inbody" or "zip"
    to_formats: list[str] = field(default_factory=lambda: ["md"])
    
    # OCR settings
    do_ocr: bool = True
    force_ocr: bool = False
    ocr_engine: str = "easyocr"
    ocr_lang: list[str] = field(default_factory=lambda: ["fr", "de", "es", "en"])
    
    # Table settings
    table_mode: str = "accurate"
    do_table_structure: bool = True
    table_cell_matching: bool = True
    
    # Image settings
    include_images: bool = True
    images_scale: int = 2
    image_export_mode: str = "referenced"
    
    # PDF settings
    pdf_backend: str = "dlparse_v2"
    
    # Pipeline settings
    pipeline: str = "standard"  # "legacy", "standard", "vlm", "asr"
    page_range: list[int] = field(default_factory=lambda: [1, 9223372036854776000])
    document_timeout: int = 604800
    
    # Markdown settings
    md_page_break_placeholder: str = ""
    
    # Error handling
    abort_on_error: bool = False
    
    # Enrichment options
    do_code_enrichment: bool = False
    do_formula_enrichment: bool = True  # Enable formula OCR to convert math to LaTeX
    do_picture_classification: bool = False
    do_picture_description: bool = False
    picture_description_area_threshold: float = 0.05
    
    def to_dict(self) -> dict:
        """Convert options to dictionary for API payload."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> "DoclingOptions":
        """Create DoclingOptions from dictionary (e.g., from AgentState)."""
        if data is None:
            return cls()
        # Filter to only valid fields
        valid_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered_data = {k: v for k, v in data.items() if k in valid_fields}
        return cls(**filtered_data)


@dataclass
class DoclingResponse:
    """Response model for Docling API calls."""
    
    success: bool
    markdown: Optional[str] = None
    filename: Optional[str] = None
    processing_time: float = 0.0
    error: Optional[str] = None


@dataclass
class DoclingZipResponse:
    """Response model for Docling ZIP output."""
    
    success: bool
    zip_path: Optional[str] = None
    processing_time: float = 0.0
    error: Optional[str] = None


class DoclingService:
    """
    Service for interacting with Docling API.
    
    Provides methods for document conversion and processing,
    with centralized configuration and error handling.
    """
    
    def __init__(self):
        """Initialize the Docling service with configuration from settings."""
        self.url_endpoint = settings.docling_api_url
        self.file_endpoint = settings.docling_file_api_url
        self.timeout = settings.docling_timeout_seconds
        self.temp_dir = settings.docling_temp_dir
    
    def _build_options_payload(self, file_type: str, options: Optional[DoclingOptions] = None) -> dict:
        """
        Build the options portion of the API payload.
        
        Args:
            file_type: The detected file type
            options: Optional DoclingOptions to customize conversion
            
        Returns:
            Dictionary of options for the API payload
        """
        opts = options or DoclingOptions()
        
        return {
            "from_formats": [file_type],
            "to_formats": opts.to_formats,
            "image_export_mode": opts.image_export_mode,
            "do_ocr": opts.do_ocr,
            "force_ocr": opts.force_ocr,
            "ocr_engine": opts.ocr_engine,
            "ocr_lang": opts.ocr_lang,
            "pdf_backend": opts.pdf_backend,
            "table_mode": opts.table_mode,
            "table_cell_matching": opts.table_cell_matching,
            "pipeline": opts.pipeline,
            "page_range": opts.page_range,
            "document_timeout": opts.document_timeout,
            "abort_on_error": opts.abort_on_error,
            "do_table_structure": opts.do_table_structure,
            "include_images": opts.include_images,
            "images_scale": opts.images_scale,
            "md_page_break_placeholder": opts.md_page_break_placeholder,
            "do_code_enrichment": opts.do_code_enrichment,
            "do_formula_enrichment": opts.do_formula_enrichment,
            "do_picture_classification": opts.do_picture_classification,
            "do_picture_description": opts.do_picture_description,
            "picture_description_area_threshold": opts.picture_description_area_threshold,
        }
    
    def _parse_response(self, result: dict) -> DoclingResponse:
        """
        Parse Docling API response into DoclingResponse.
        
        Args:
            result: JSON response from Docling API
            
        Returns:
            DoclingResponse with parsed content
        """
        # Check API response status
        if result.get("status") != "success":
            errors = result.get("errors", [])
            error_msg = f"Docling API returned status '{result.get('status')}': {errors}"
            logger.error(error_msg)
            return DoclingResponse(success=False, error=error_msg)
        
        # Extract content from response
        document = result.get("document", {})
        markdown_content = document.get("md_content")
        filename = document.get("filename")
        processing_time = result.get("processing_time", 0.0)
        
        if markdown_content:
            logger.info(f"Successfully converted document to markdown ({len(markdown_content)} chars, {processing_time:.2f}s)")
            return DoclingResponse(
                success=True,
                markdown=markdown_content,
                filename=filename,
                processing_time=processing_time
            )
        else:
            error_msg = "Docling API response missing md_content field"
            logger.error(error_msg)
            return DoclingResponse(success=False, error=error_msg)
    
    def convert_to_markdown(
        self, 
        document_url: str, 
        file_type: str,
        options: Optional[DoclingOptions] = None
    ) -> DoclingResponse:
        """
        Convert a document to markdown format using the Docling URL API.
        
        Args:
            document_url: The URL of the document to convert (e.g., GCS signed URL)
            file_type: The detected file type (e.g., "pdf", "docx", "image")
            options: Optional DoclingOptions to customize conversion
            
        Returns:
            DoclingResponse with success status, markdown content, and metadata
        """
        logger.info(f"Converting document to markdown (URL): {document_url[:100]}...")
        logger.info(f"  - File type: {file_type}")
        
        # Build the API payload
        payload = {
            "options": self._build_options_payload(file_type, options),
            "sources": [{
                "kind": "http",
                "url": document_url,
            }],
        }
        
        try:
            # Make the API request with timeout
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(
                    self.url_endpoint,
                    json=payload,
                    headers={"Content-Type": "application/json"}
                )
                
                # Check for HTTP errors
                response.raise_for_status()
                
                # Parse and return response
                return self._parse_response(response.json())
                    
        except httpx.TimeoutException:
            error_msg = f"Timeout while converting document (exceeded {self.timeout}s)"
            logger.error(error_msg)
            return DoclingResponse(success=False, error=error_msg)
            
        except httpx.HTTPStatusError as e:
            error_msg = f"HTTP error from Docling API: {e.response.status_code} - {e.response.text[:500]}"
            logger.error(error_msg)
            return DoclingResponse(success=False, error=error_msg)
            
        except httpx.RequestError as e:
            error_msg = f"Failed to connect to Docling API at {self.url_endpoint}: {str(e)}"
            logger.error(error_msg)
            return DoclingResponse(success=False, error=error_msg)
            
        except Exception as e:
            error_msg = f"Unexpected error during document conversion: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return DoclingResponse(success=False, error=error_msg)
    
    def convert_file_to_markdown(
        self,
        file_path: str,
        file_type: str,
        options: Optional[DoclingOptions] = None
    ) -> DoclingResponse:
        """
        Convert a local file to markdown format using multipart/form-data.
        
        Args:
            file_path: Path to the local file to convert
            file_type: The detected file type (e.g., "pdf", "docx", "image")
            options: Optional DoclingOptions to customize conversion
            
        Returns:
            DoclingResponse with success status, markdown content, and metadata
        """
        logger.info(f"Converting file to markdown: {file_path}")
        logger.info(f"  - File type: {file_type}")
        
        # Verify file exists
        if not os.path.exists(file_path):
            error_msg = f"File not found: {file_path}"
            logger.error(error_msg)
            return DoclingResponse(success=False, error=error_msg)
        
        # Build options payload
        options_payload = self._build_options_payload(file_type, options)
        
        try:
            # Open file and send as multipart/form-data
            with open(file_path, "rb") as f:
                files = {
                    "files": (os.path.basename(file_path), f, "application/octet-stream")
                }
                data = {
                    "options": json.dumps(options_payload)
                }
                
                with httpx.Client(timeout=self.timeout) as client:
                    response = client.post(
                        self.file_endpoint,
                        files=files,
                        data=data
                    )
                    
                    # Check for HTTP errors
                    response.raise_for_status()
                    
                    # Parse and return response
                    return self._parse_response(response.json())
                    
        except httpx.TimeoutException:
            error_msg = f"Timeout while converting file (exceeded {self.timeout}s)"
            logger.error(error_msg)
            return DoclingResponse(success=False, error=error_msg)
            
        except httpx.HTTPStatusError as e:
            error_msg = f"HTTP error from Docling API: {e.response.status_code} - {e.response.text[:500]}"
            logger.error(error_msg)
            return DoclingResponse(success=False, error=error_msg)
            
        except httpx.RequestError as e:
            error_msg = f"Failed to connect to Docling API at {self.file_endpoint}: {str(e)}"
            logger.error(error_msg)
            return DoclingResponse(success=False, error=error_msg)
            
        except Exception as e:
            error_msg = f"Unexpected error during file conversion: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return DoclingResponse(success=False, error=error_msg)
    
    def convert_file_to_zip(
        self,
        file_path: str,
        file_type: str,
        job_id: str,
        options: Optional[DoclingOptions] = None
    ) -> DoclingZipResponse:
        """
        Convert a local file and return ZIP output.
        
        Downloads the document, converts it via Docling file API with target_type="zip",
        and saves the ZIP to a job-specific directory.
        
        Args:
            file_path: Path to the local file to convert
            file_type: The detected file type (e.g., "pdf", "docx", "image")
            job_id: Job ID for organizing output directory
            options: Optional DoclingOptions to customize conversion
            
        Returns:
            DoclingZipResponse with path to output ZIP file
        """
        logger.info(f"Converting file to ZIP: {file_path}")
        logger.info(f"  - File type: {file_type}")
        logger.info(f"  - Job ID: {job_id}")
        
        # Verify file exists
        if not os.path.exists(file_path):
            error_msg = f"File not found: {file_path}"
            logger.error(error_msg)
            return DoclingZipResponse(success=False, error=error_msg)
        
        # Create job output directory
        job_output_dir = Path(self.temp_dir) / job_id
        job_output_dir.mkdir(parents=True, exist_ok=True)
        output_zip_path = job_output_dir / "output.zip"
        
        # Build options payload with target_type forced to "zip"
        opts = options or DoclingOptions()
        opts.target_type = "zip"  # Force ZIP output
        options_payload = self._build_options_payload(file_type, opts)
        options_payload["target_type"] = "zip"  # Ensure it's in the payload
        
        # Log the key options being used
        logger.debug(f"Docling API options: image_export_mode={opts.image_export_mode}, include_images={opts.include_images}")
        
        # Build form data with options as individual fields
        # Some APIs expect options as separate form fields rather than a JSON blob
        form_data = {
            "target_type": "zip",
            "image_export_mode": opts.image_export_mode,
            "include_images": str(opts.include_images).lower(),
            "images_scale": str(opts.images_scale),
            "do_ocr": str(opts.do_ocr).lower(),
            "force_ocr": str(opts.force_ocr).lower(),
            "ocr_engine": opts.ocr_engine,
            "pdf_backend": opts.pdf_backend,
            "table_mode": opts.table_mode,
            "table_cell_matching": str(opts.table_cell_matching).lower(),
            "do_table_structure": str(opts.do_table_structure).lower(),
            "abort_on_error": str(opts.abort_on_error).lower(),
            "pipeline": opts.pipeline,
            "document_timeout": str(opts.document_timeout),
            # Enrichment options
            "do_formula_enrichment": str(opts.do_formula_enrichment).lower(),
            "do_code_enrichment": str(opts.do_code_enrichment).lower(),
            "do_picture_classification": str(opts.do_picture_classification).lower(),
            "do_picture_description": str(opts.do_picture_description).lower(),
            # Also include the full options JSON as fallback
            "options": json.dumps(options_payload),
        }
        
        logger.debug(f"Form data: target_type={form_data['target_type']}, image_export_mode={form_data['image_export_mode']}")
        
        try:
            # Open file and send as multipart/form-data
            with open(file_path, "rb") as f:
                files = {
                    "files": (os.path.basename(file_path), f, "application/octet-stream")
                }
                
                with httpx.Client(timeout=self.timeout) as client:
                    response = client.post(
                        self.file_endpoint,
                        files=files,
                        data=form_data
                    )
                    
                    # Check for HTTP errors
                    response.raise_for_status()
                    
                    # Check if response is ZIP (binary) or JSON (error)
                    content_type = response.headers.get("content-type", "")
                    
                    if "application/zip" in content_type or "application/octet-stream" in content_type:
                        # Save ZIP file
                        with open(output_zip_path, "wb") as zip_file:
                            zip_file.write(response.content)
                        
                        logger.info(f"Successfully saved ZIP to: {output_zip_path} ({len(response.content)} bytes)")
                        return DoclingZipResponse(
                            success=True,
                            zip_path=str(output_zip_path),
                            processing_time=0.0  # Not available in ZIP response
                        )
                    elif "application/json" in content_type:
                        # JSON response - could be error or success with metadata
                        result = response.json()
                        if result.get("status") == "success":
                            # Some implementations return JSON with ZIP URL or content
                            logger.warning("Received JSON response instead of ZIP binary")
                            return DoclingZipResponse(
                                success=False,
                                error="Expected ZIP binary but received JSON response"
                            )
                        else:
                            errors = result.get("errors", [])
                            error_msg = f"Docling API returned status '{result.get('status')}': {errors}"
                            logger.error(error_msg)
                            return DoclingZipResponse(success=False, error=error_msg)
                    else:
                        # Assume it's binary ZIP data
                        with open(output_zip_path, "wb") as zip_file:
                            zip_file.write(response.content)
                        
                        logger.info(f"Saved response as ZIP to: {output_zip_path} ({len(response.content)} bytes)")
                        return DoclingZipResponse(
                            success=True,
                            zip_path=str(output_zip_path)
                        )
                    
        except httpx.TimeoutException:
            error_msg = f"Timeout while converting file to ZIP (exceeded {self.timeout}s)"
            logger.error(error_msg)
            return DoclingZipResponse(success=False, error=error_msg)
            
        except httpx.HTTPStatusError as e:
            error_msg = f"HTTP error from Docling API: {e.response.status_code} - {e.response.text[:500]}"
            logger.error(error_msg)
            return DoclingZipResponse(success=False, error=error_msg)
            
        except httpx.RequestError as e:
            error_msg = f"Failed to connect to Docling API at {self.file_endpoint}: {str(e)}"
            logger.error(error_msg)
            return DoclingZipResponse(success=False, error=error_msg)
            
        except Exception as e:
            error_msg = f"Unexpected error during file to ZIP conversion: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return DoclingZipResponse(success=False, error=error_msg)
    
    def download_to_temp(self, url: str, filename: str) -> str:
        """
        Download a file from URL to the temp directory.
        
        Args:
            url: URL to download from (e.g., GCS signed URL)
            filename: Name to save the file as
            
        Returns:
            Full path to the downloaded file
            
        Raises:
            Exception: If download fails
        """
        logger.info(f"Downloading file to temp: {filename}")
        
        # Ensure temp directory exists
        temp_path = Path(self.temp_dir)
        temp_path.mkdir(parents=True, exist_ok=True)
        
        # Generate full file path
        file_path = temp_path / filename
        
        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.get(url)
                response.raise_for_status()
                
                # Write content to file
                with open(file_path, "wb") as f:
                    f.write(response.content)
                
                logger.info(f"Downloaded file to: {file_path} ({len(response.content)} bytes)")
                return str(file_path)
                
        except httpx.TimeoutException:
            error_msg = f"Timeout while downloading file (exceeded {self.timeout}s)"
            logger.error(error_msg)
            raise Exception(error_msg)
            
        except httpx.HTTPStatusError as e:
            error_msg = f"HTTP error while downloading: {e.response.status_code}"
            logger.error(error_msg)
            raise Exception(error_msg)
            
        except Exception as e:
            error_msg = f"Failed to download file: {str(e)}"
            logger.error(error_msg)
            raise
    
    def cleanup_temp_file(self, file_path: str) -> None:
        """
        Remove a temp file after processing.
        
        Args:
            file_path: Path to the file to remove
        """
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.info(f"Cleaned up temp file: {file_path}")
        except Exception as e:
            logger.warning(f"Failed to clean up temp file {file_path}: {str(e)}")


# Global service instance
docling_service = DoclingService()
