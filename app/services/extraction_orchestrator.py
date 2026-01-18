"""LangGraph orchestration for multi-agent document question extraction."""

import logging
from typing import TypedDict, Literal
from langgraph.graph import StateGraph, END

logger = logging.getLogger(__name__)


# Define the agent state schema
class AgentState(TypedDict):
    """State shared between agents in the extraction workflow."""
    
    # Job information
    job_id: str
    user_id: str
    
    # Document information
    document_url: str
    document_filename: str
    file_type: str
    
    # Processing stages
    raw_content: str | None
    parsed_markdown: str | None
    extracted_questions: list[dict] | None
    validated_markdown: str | None
    vector_ids: list[str] | None
    
    # Status and metadata
    status: Literal["pending", "ingesting", "parsing", "extracting", "validating", "vectorizing", "persisting", "completed", "failed"]
    error_message: str | None
    metadata: dict
    
    # Validation loop control
    validation_attempts: int
    validation_passed: bool


def create_extraction_graph() -> StateGraph:
    """
    Create the LangGraph state graph for document question extraction.
    
    Returns:
        StateGraph: Configured graph with all agent nodes and edges
    """
    # Initialize the graph
    workflow = StateGraph(AgentState)
    
    # Add nodes for each agent
    # TODO: Implement actual agent logic in separate files
    workflow.add_node("ingestion", ingestion_node)
    workflow.add_node("parsing", parsing_node)
    workflow.add_node("question_extraction", question_extraction_node)
    workflow.add_node("markdown_validation", markdown_validation_node)
    workflow.add_node("vectorization", vectorization_node)
    workflow.add_node("persistence", persistence_node)
    
    # Define the workflow edges
    # Start with ingestion
    workflow.set_entry_point("ingestion")
    
    # Ingestion -> Parsing
    workflow.add_edge("ingestion", "parsing")
    
    # Parsing -> Question Extraction
    workflow.add_edge("parsing", "question_extraction")
    
    # Question Extraction -> Markdown Validation
    workflow.add_edge("question_extraction", "markdown_validation")
    
    # Markdown Validation -> either back to Parsing (if validation fails) or to Vectorization
    workflow.add_conditional_edges(
        "markdown_validation",
        should_retry_parsing,
        {
            "retry": "parsing",
            "continue": "vectorization"
        }
    )
    
    # Vectorization -> Persistence
    workflow.add_edge("vectorization", "persistence")
    
    # Persistence -> END
    workflow.add_edge("persistence", END)
    
    return workflow.compile()


# Placeholder node functions (to be implemented in separate agent files)
def ingestion_node(state: AgentState) -> AgentState:
    """Ingestion Agent node - handles file upload and format detection."""
    from app.agents.ingestion_agent import IngestionAgent
    
    logger.info(f"Ingestion agent processing job {state['job_id']}")
    
    # Use IngestionAgent to process
    agent = IngestionAgent()
    updated_state = agent.process(state)
    
    return updated_state


def parsing_node(state: AgentState) -> AgentState:
    """Parsing Agent node - uses Docling and format-specific tools to generate Markdown."""
    logger.info(f"Parsing agent processing job {state['job_id']}")
    # TODO: Implement parsing logic
    state["status"] = "parsing"
    return state


def question_extraction_node(state: AgentState) -> AgentState:
    """Question Extraction Agent node - identifies and isolates questions."""
    logger.info(f"Question extraction agent processing job {state['job_id']}")
    # TODO: Implement question extraction logic
    state["status"] = "extracting"
    return state


def markdown_validation_node(state: AgentState) -> AgentState:
    """Markdown Validation Agent node - validates and refines Markdown output."""
    logger.info(f"Markdown validation agent processing job {state['job_id']}")
    # TODO: Implement validation logic
    state["status"] = "validating"
    state["validation_attempts"] = state.get("validation_attempts", 0) + 1
    # For now, always pass validation (will be implemented later)
    state["validation_passed"] = True
    return state


def vectorization_node(state: AgentState) -> AgentState:
    """Vectorization Agent node - embeds and stores questions with deduplication."""
    logger.info(f"Vectorization agent processing job {state['job_id']}")
    # TODO: Implement vectorization logic
    state["status"] = "vectorizing"
    return state


def persistence_node(state: AgentState) -> AgentState:
    """Persistence Agent node - manages database storage and user scoping."""
    logger.info(f"Persistence agent processing job {state['job_id']}")
    # TODO: Implement persistence logic
    state["status"] = "persisting"
    state["status"] = "completed"
    return state


def should_retry_parsing(state: AgentState) -> Literal["retry", "continue"]:
    """
    Determine if parsing should be retried based on validation results.
    
    Args:
        state: Current agent state
        
    Returns:
        "retry" if validation failed and attempts < 3, "continue" otherwise
    """
    validation_passed = state.get("validation_passed", False)
    validation_attempts = state.get("validation_attempts", 0)
    max_attempts = 3
    
    if not validation_passed and validation_attempts < max_attempts:
        logger.warning(f"Validation failed, retrying parsing (attempt {validation_attempts + 1}/{max_attempts})")
        return "retry"
    
    if not validation_passed:
        logger.error(f"Validation failed after {max_attempts} attempts, continuing anyway")
    
    return "continue"

