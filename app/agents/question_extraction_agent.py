"""Question Extraction Agent - identifies and isolates questions."""

import logging
from typing import Dict, Any
from app.services.extraction_orchestrator import AgentState

logger = logging.getLogger(__name__)


class QuestionExtractionAgent:
    """Agent responsible for extracting questions from parsed content."""
    
    def process(self, state: AgentState) -> AgentState:
        """
        Process question extraction.
        
        Args:
            state: Current agent state with parsed_markdown
            
        Returns:
            Updated agent state with extracted_questions
        """
        logger.info(f"Processing question extraction for job {state['job_id']}")
        # TODO: Implement question extraction logic with LLM
        return state

