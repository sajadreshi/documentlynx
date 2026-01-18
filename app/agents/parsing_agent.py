"""Parsing Agent - uses Docling and format-specific tools to generate Markdown."""

import logging
from typing import Dict, Any
from app.services.extraction_orchestrator import AgentState

logger = logging.getLogger(__name__)


class ParsingAgent:
    """Agent responsible for document parsing and Markdown generation."""
    
    def process(self, state: AgentState) -> AgentState:
        """
        Process document parsing.
        
        Args:
            state: Current agent state
            
        Returns:
            Updated agent state with parsed_markdown
        """
        logger.info(f"Processing parsing for job {state['job_id']}")
        # TODO: Implement parsing logic with Docling
        return state

