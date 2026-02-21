"""Ingestion Agent - handles file upload and format detection."""

import logging
from urllib.parse import urlparse
from pathlib import Path
from app.services.extraction_orchestrator import AgentState
from app.services.docling_service import docling_service, DoclingOptions
from app.observability import traceable

logger = logging.getLogger(__name__)


def determine_document_type(url: str, filename: str = "") -> str:
    """
    Determine document type from URL or filename.
    
    Handles URLs with query parameters by extracting the filename from the path component.
    Example: https://storage.googleapis.com/.../file.pdf?X-Goog-Algorithm=... 
    will correctly identify "pdf" from the path before the query parameters.
    
    Args:
        url: Document URL (may include query parameters)
        filename: Optional filename (may be more reliable than URL)
        
    Returns:
        Document type string: "docx", "pptx", "html", "image", "pdf", etc.
    """
    # Try to get extension from filename first, then from URL
    if filename:
        # Use filename directly if provided
        source_path = filename
    elif url:
        # Parse URL to get path component (removes query params and fragments)
        parsed_url = urlparse(url)
        path = parsed_url.path
        # Extract just the filename (last component of path)
        source_path = Path(path).name if path else ""
    else:
        return "unknown"
    
    if not source_path:
        return "unknown"
    
    # Get file extension from the filename
    extension = Path(source_path).suffix.lower()
    
    # Remove the dot from extension
    ext = extension.lstrip('.') if extension else ""
    
    # Mapping of extensions to document types
    extension_map = {
        # Office documents
        "docx": "docx",
        "doc": "docx",  # Treat .doc as docx for compatibility
        "pptx": "pptx",
        "ppt": "pptx",  # Treat .ppt as pptx for compatibility
        "xlsx": "xlsx",
        "xls": "xlsx",  # Treat .xls as xlsx for compatibility
        
        # Web formats
        "html": "html",
        "htm": "html",
        
        # Document formats
        "pdf": "pdf",
        "md": "md",
        "markdown": "md",
        "asciidoc": "asciidoc",
        "adoc": "asciidoc",
        
        # Data formats
        "csv": "csv",
        "xml": "xml_uspto",  # Default XML type, can be refined later
        
        # Image formats
        "jpg": "image",
        "jpeg": "image",
        "png": "image",
        "gif": "image",
        "bmp": "image",
        "webp": "image",
        "svg": "image",
        "tiff": "image",
        "tif": "image",
        "ico": "image",
        
        # Audio formats
        "mp3": "audio",
        "wav": "audio",
        "ogg": "audio",
        "flac": "audio",
        "aac": "audio",
        "m4a": "audio",
        "wma": "audio",
        
        # Video/Subtitle formats
        "vtt": "vtt",
        
        # Special formats
        "json": "json_docling",
    }
    
    # Check for special XML types based on URL patterns or content hints
    if ext == "xml":
        # Check URL path for hints about XML type (use full path from URL if available)
        if url:
            parsed_url = urlparse(url)
            path_to_check = parsed_url.path.lower()
        else:
            path_to_check = source_path.lower()
        
        if "uspto" in path_to_check or "patent" in path_to_check:
            return "xml_uspto"
        elif "jats" in path_to_check:
            return "xml_jats"
        elif "mets" in path_to_check or "gbs" in path_to_check:
            return "mets_gbs"
        else:
            return "xml_uspto"  # Default
    
    # Return mapped type or "unknown"
    return extension_map.get(ext, "unknown")


class IngestionAgent:
    """Agent responsible for document ingestion and format detection."""
    
    @traceable(name="IngestionAgent.process", tags=["agent", "ingestion"])
    def process(self, state: AgentState) -> AgentState:
        """
        Process document ingestion.

        Receives the document URL, determines document type, converts to markdown,
        and updates the state. Supports two conversion methods:
        - URL-based (default): Sends URL to Docling API, returns markdown in-body
        - File-based (when use_file_conversion=True): Downloads file, converts with ZIP output

        Args:
            state: Current agent state with document_url

        Returns:
            Updated agent state with file_type and raw_content (or output_zip_path) set
        """
        # Check if file-based conversion is requested
        if state.get("use_file_conversion", False):
            return self.process_by_file(state)
        
        job_id = state.get("job_id", "unknown")
        document_url = state.get("document_url", "")
        user_id = state.get("user_id", "")
        document_filename = state.get("document_filename", "")
        
        logger.info(f"Ingestion agent processing job {job_id}")
        logger.info(f"  - Document URL: {document_url}")
        logger.info(f"  - User ID: {user_id}")
        logger.info(f"  - Filename: {document_filename}")
        
        # Determine document type from URL/filename
        file_type = determine_document_type(document_url, document_filename)
        state["file_type"] = file_type
        
        logger.info(f"  - Detected document type: {file_type}")
        
        # Update state to indicate ingestion is in progress
        state["status"] = "ingesting"
        
        # Initialize metadata if not present
        if "metadata" not in state:
            state["metadata"] = {}
        state["metadata"]["detected_file_type"] = file_type
        
        # Convert document to markdown using Docling service
        if file_type != "unknown":
            logger.info(f"Converting document to markdown for job {job_id}...")
            
            # Get docling options from state if present, otherwise use defaults
            docling_options_dict = state.get("docling_options")
            options = DoclingOptions.from_dict(docling_options_dict) if docling_options_dict else None
            
            if options:
                logger.info(f"  - Using custom Docling options from state")
            
            # Use the Docling service for conversion
            result = docling_service.convert_to_markdown(
                document_url=document_url,
                file_type=file_type,
                options=options
            )
            
            if result.success:
                state["raw_content"] = result.markdown
                state["metadata"]["conversion_completed"] = True
                state["metadata"]["markdown_length"] = len(result.markdown) if result.markdown else 0
                state["metadata"]["processing_time"] = result.processing_time
                if result.filename:
                    state["metadata"]["source_filename"] = result.filename
                logger.info(f"Document conversion successful for job {job_id}")
            else:
                state["error_message"] = result.error
                state["metadata"]["conversion_completed"] = False
                state["metadata"]["conversion_error"] = result.error
                logger.error(f"Document conversion failed for job {job_id}: {result.error}")
        else:
            logger.warning(f"Unknown file type for job {job_id}, skipping conversion")
            state["metadata"]["conversion_completed"] = False
            state["metadata"]["conversion_error"] = "Unknown file type"
        
        state["metadata"]["ingestion_completed"] = True
        logger.info(f"Ingestion agent completed for job {job_id}")
        
        return state
    
    def process_by_file(self, state: AgentState) -> AgentState:
        """
        Process document using file-based conversion with ZIP output.
        
        1. Download file from GCS to temp directory (or reuse if retry)
        2. Convert via Docling file API with target_type="zip"
        3. Save ZIP to job directory
        4. Store paths in state for validation and next agent
        
        Note: Source file is kept for validation comparison and only cleaned up
        after validation passes or max attempts are reached.
        
        Args:
            state: Current agent state with document_url
            
        Returns:
            Updated agent state with output_zip_path and source_file_path set
        """
        job_id = state.get("job_id", "unknown")
        document_url = state.get("document_url", "")
        user_id = state.get("user_id", "")
        document_filename = state.get("document_filename", "")
        validation_attempts = state.get("validation_attempts", 0)
        existing_source_path = state.get("source_file_path")
        
        # Check if this is a retry (validation loop)
        is_retry = validation_attempts > 0 and existing_source_path is not None
        
        if is_retry:
            logger.info(f"Ingestion agent RE-PROCESSING job {job_id} (attempt {validation_attempts + 1})")
            logger.info(f"  - Using existing source file: {existing_source_path}")
        else:
            logger.info(f"Ingestion agent processing job {job_id} (file-based with ZIP output)")
            logger.info(f"  - Document URL: {document_url}")
        
        logger.info(f"  - User ID: {user_id}")
        logger.info(f"  - Filename: {document_filename}")
        
        # Determine document type from URL/filename
        file_type = determine_document_type(document_url, document_filename)
        state["file_type"] = file_type
        
        logger.info(f"  - Detected document type: {file_type}")
        
        # Update state to indicate ingestion is in progress
        state["status"] = "ingesting"
        
        # Initialize metadata if not present
        if "metadata" not in state:
            state["metadata"] = {}
        state["metadata"]["detected_file_type"] = file_type
        state["metadata"]["conversion_method"] = "file_based_zip"
        state["metadata"]["is_retry"] = is_retry
        state["metadata"]["attempt_number"] = validation_attempts + 1
        
        if file_type == "unknown":
            logger.warning(f"Unknown file type for job {job_id}, skipping conversion")
            state["metadata"]["conversion_completed"] = False
            state["metadata"]["conversion_error"] = "Unknown file type"
            state["metadata"]["ingestion_completed"] = True
            return state
        
        # Get docling options from state if present, otherwise use defaults
        docling_options_dict = state.get("docling_options")
        options = DoclingOptions.from_dict(docling_options_dict) if docling_options_dict else None
        
        if options:
            logger.info(f"  - Using custom Docling options from state")
            if is_retry:
                logger.info(f"  - Retry with modified options: pdf_backend={options.pdf_backend}, ocr_engine={options.ocr_engine}")
        
        source_file_path = existing_source_path
        
        try:
            # Step 1: Download file from GCS (skip if retry and source exists)
            if is_retry and existing_source_path and Path(existing_source_path).exists():
                logger.info(f"Skipping download, using existing source file for job {job_id}")
                source_file_path = existing_source_path
            else:
                logger.info(f"Downloading file from GCS for job {job_id}...")
                source_file_path = docling_service.download_to_temp(
                    url=document_url,
                    filename=document_filename
                )
                # Store source file path for validation comparison (NOT deleted after conversion)
                state["source_file_path"] = source_file_path
                logger.info(f"  - Downloaded to: {source_file_path}")
            
            state["metadata"]["source_file_path"] = source_file_path
            
            # Step 2: Convert file to ZIP using Docling service
            logger.info(f"Converting file to ZIP for job {job_id}...")
            result = docling_service.convert_file_to_zip(
                file_path=source_file_path,
                file_type=file_type,
                job_id=job_id,
                options=options
            )
            
            if result.success:
                state["output_zip_path"] = result.zip_path
                state["metadata"]["conversion_completed"] = True
                state["metadata"]["output_zip_path"] = result.zip_path
                state["metadata"]["processing_time"] = result.processing_time
                logger.info(f"File conversion to ZIP successful for job {job_id}")
                logger.info(f"  - ZIP output: {result.zip_path}")
            else:
                state["error_message"] = result.error
                state["metadata"]["conversion_completed"] = False
                state["metadata"]["conversion_error"] = result.error
                logger.error(f"File conversion to ZIP failed for job {job_id}: {result.error}")
                
        except Exception as e:
            error_msg = f"Error during file-based conversion: {str(e)}"
            logger.error(error_msg, exc_info=True)
            state["error_message"] = error_msg
            state["metadata"]["conversion_completed"] = False
            state["metadata"]["conversion_error"] = error_msg
        
        # NOTE: Source file is NOT cleaned up here - kept for validation comparison
        # Cleanup happens in validation agent after validation passes or max attempts
        
        state["metadata"]["ingestion_completed"] = True
        logger.info(f"Ingestion agent (file-based) completed for job {job_id}")
        
        return state
