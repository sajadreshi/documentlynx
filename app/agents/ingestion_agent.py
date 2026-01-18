"""Ingestion Agent - handles file upload and format detection."""

import logging
from app.services.extraction_orchestrator import AgentState

logger = logging.getLogger(__name__)


class IngestionAgent:
    """Agent responsible for document ingestion and format detection."""
    
    def process(self, state: AgentState) -> AgentState:
        """
        Process document ingestion.
        
        Receives the document URL, logs it, and updates the state.
        This is a minimal implementation - just making URL available.
        
        Args:
            state: Current agent state with document_url
            
        Returns:
            Updated agent state
        """
        job_id = state.get("job_id", "unknown")
        document_url = state.get("document_url", "")
        user_id = state.get("user_id", "")
        document_filename = state.get("document_filename", "")
        
        logger.info(f"Ingestion agent processing job {job_id}")
        logger.info(f"  - Document URL: {document_url}")
        logger.info(f"  - User ID: {user_id}")
        logger.info(f"  - Filename: {document_filename}")
        
        # Update state to indicate ingestion is complete
        state["status"] = "ingesting"
        
        # Add metadata about ingestion
        if "metadata" not in state:
            state["metadata"] = {}
        state["metadata"]["ingestion_completed"] = True
        state["metadata"]["ingestion_logged"] = True
        
        logger.info(f"Ingestion agent completed for job {job_id} - URL is now available in state")
        
        return state

