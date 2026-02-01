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
    cleaned_markdown: str | None  # Cleaned/formatted markdown for UI display
    extracted_questions: list[dict] | None
    validated_markdown: str | None
    vector_ids: list[str] | None
    
    # Status and metadata
    status: Literal["pending", "ingesting", "parsing", "extracting", "validating", "persisting", "classifying", "vectorizing", "completed", "failed"]
    error_message: str | None
    metadata: dict
    
    # Validation loop control
    validation_attempts: int
    validation_passed: bool
    
    # Docling options (agents can modify these to customize conversion)
    docling_options: dict | None
    
    # File-based conversion settings
    use_file_conversion: bool  # If True, use file-based conversion with ZIP output
    output_zip_path: str | None  # Path to output ZIP for next agent
    
    # Validation-specific fields
    source_file_path: str | None  # Path to downloaded source file (kept for validation)
    validation_feedback: str | None  # LLM feedback on quality issues
    
    # Persistence-specific fields
    document_id: str | None  # Database document UUID
    question_ids: list[str] | None  # List of persisted question UUIDs
    public_markdown: str | None  # Markdown with public GCS image URLs


def create_extraction_graph() -> StateGraph:
    """
    Create the LangGraph state graph for document question extraction.
    
    Returns:
        StateGraph: Configured graph with all agent nodes and edges
    """
    # Initialize the graph
    workflow = StateGraph(AgentState)
    
    # Add nodes for each agent
    workflow.add_node("ingestion", ingestion_node)
    workflow.add_node("parsing", parsing_node)
    workflow.add_node("question_extraction", question_extraction_node)
    workflow.add_node("markdown_validation", markdown_validation_node)
    workflow.add_node("persistence", persistence_node)
    workflow.add_node("classification", classification_node)
    workflow.add_node("vectorization", vectorization_node)
    
    # Define the workflow edges
    # Start with ingestion
    workflow.set_entry_point("ingestion")
    
    # Ingestion -> Parsing
    workflow.add_edge("ingestion", "parsing")
    
    # Parsing -> Question Extraction
    workflow.add_edge("parsing", "question_extraction")
    
    # Question Extraction -> Markdown Validation
    workflow.add_edge("question_extraction", "markdown_validation")
    
    # Markdown Validation -> either back to Ingestion (if validation fails) or to Persistence
    # Note: Loops back to ingestion (not parsing) because Docling options need to be modified
    workflow.add_conditional_edges(
        "markdown_validation",
        should_retry_ingestion,
        {
            "retry": "ingestion",
            "continue": "persistence"
        }
    )
    
    # Persistence -> Classification (persistence creates questions, then we classify them)
    workflow.add_edge("persistence", "classification")
    
    # Classification -> Vectorization (classification adds metadata, then we embed with that context)
    workflow.add_edge("classification", "vectorization")
    
    # Vectorization -> END
    workflow.add_edge("vectorization", END)
    
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
    """Parsing Agent node - cleans up markdown using LLM for better UI display."""
    from app.agents.parsing_agent import ParsingAgent
    
    logger.info(f"Parsing agent processing job {state['job_id']}")
    
    # Use ParsingAgent to process
    agent = ParsingAgent()
    updated_state = agent.process(state)
    
    return updated_state


def question_extraction_node(state: AgentState) -> AgentState:
    """Question Extraction Agent node - identifies and isolates questions."""
    logger.info(f"Question extraction agent processing job {state['job_id']}")
    # TODO: Implement question extraction logic
    state["status"] = "extracting"
    return state


def markdown_validation_node(state: AgentState) -> AgentState:
    """Markdown Validation Agent node - validates markdown quality using LLM."""
    from app.agents.markdown_validation_agent import MarkdownValidationAgent
    
    logger.info(f"Markdown validation agent processing job {state['job_id']}")
    
    # Use MarkdownValidationAgent to process
    agent = MarkdownValidationAgent()
    updated_state = agent.process(state)
    
    return updated_state


def classification_node(state: AgentState) -> AgentState:
    """Classification Agent node - classifies questions by subject, difficulty, and other metadata."""
    from app.agents.classification_agent import ClassificationAgent
    
    logger.info(f"Classification agent processing job {state['job_id']}")
    
    # Use ClassificationAgent to process
    agent = ClassificationAgent()
    updated_state = agent.process(state)
    
    return updated_state


def vectorization_node(state: AgentState) -> AgentState:
    """Vectorization Agent node - generates embeddings for questions using pgvector."""
    from app.agents.vectorization_agent import VectorizationAgent
    
    logger.info(f"Vectorization agent processing job {state['job_id']}")
    
    # Use VectorizationAgent to process
    agent = VectorizationAgent()
    updated_state = agent.process(state)
    
    return updated_state


def persistence_node(state: AgentState) -> AgentState:
    """Persistence Agent node - uploads images, extracts questions, persists to database."""
    from app.agents.persistence_agent import PersistenceAgent
    
    logger.info(f"Persistence agent processing job {state['job_id']}")
    
    # Use PersistenceAgent to process
    agent = PersistenceAgent()
    updated_state = agent.process(state)
    
    return updated_state


def should_retry_ingestion(state: AgentState) -> Literal["retry", "continue"]:
    """
    Determine if ingestion should be retried based on validation results.
    
    When validation fails, we loop back to ingestion (not parsing) because
    the validation agent modifies Docling options to try different conversion
    parameters (PDF backend, OCR engine, etc.).
    
    Args:
        state: Current agent state
        
    Returns:
        "retry" if validation failed and attempts < max, "continue" otherwise
    """
    validation_passed = state.get("validation_passed", False)
    validation_attempts = state.get("validation_attempts", 0)
    max_attempts = 3
    
    if not validation_passed and validation_attempts < max_attempts:
        logger.warning(f"Validation failed, retrying ingestion with new Docling options (attempt {validation_attempts + 1}/{max_attempts})")
        return "retry"
    
    if not validation_passed:
        logger.error(f"Validation failed after {max_attempts} attempts, continuing anyway")
    
    return "continue"

