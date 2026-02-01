"""Database models."""

import uuid
from sqlalchemy import Column, String, Boolean, DateTime, Integer, Text, Float, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from pgvector.sqlalchemy import Vector
from app.database import Base
from app.config import settings


class ClientCredential(Base):
    """Model for client credentials."""

    __tablename__ = "client_credentials"

    client_id = Column(String(255), primary_key=True, index=True)
    client_secret = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def __repr__(self):
        return f"<ClientCredential(client_id='{self.client_id}', is_active={self.is_active})>"


class PromptTemplate(Base):
    """Model for prompt templates with flexible JSONB configuration."""

    __tablename__ = "prompt_templates"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, index=True)
    version = Column(String(50), default="v1", index=True)
    description = Column(Text)
    
    # Full prompt configuration stored as JSONB
    # Structure: {
    #   "instruction": "...",
    #   "output_constraints": ["...", "..."],
    #   "role": "...",
    #   "style_or_tone": ["...", "..."],
    #   "goal": "..."
    # }
    config = Column(JSONB, nullable=False)
    
    # A/B Testing configuration
    experiment_group = Column(String(50), index=True)  # "A", "B", "control"
    traffic_percentage = Column(Float, default=1.0)  # 0.0 to 1.0
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    created_by = Column(String(255))
    extra_metadata = Column(JSONB)  # Additional flexible data (renamed from metadata to avoid SQLAlchemy conflict)

    def __repr__(self):
        return f"<PromptTemplate(name='{self.name}', version='{self.version}', group='{self.experiment_group}')>"
    
    def get_full_prompt(self, **variables) -> str:
        """
        Render the full prompt from config sections using template builder.
        
        Args:
            **variables: Variables to format into the prompt template
            
        Returns:
            str: Fully rendered prompt
        """
        from app.services.prompt_template_builder import PromptTemplateBuilder
        
        # Use template builder for dynamic construction
        builder = PromptTemplateBuilder(self.config, variables)
        
        # Validate variables if schema exists
        schema = builder.get_variable_schema()
        if schema:
            is_valid, missing = builder.validate_variables(variables)
            if not is_valid:
                raise ValueError(
                    f"Missing required variables: {', '.join(missing)}. "
                    f"Required variables: {', '.join(schema.keys())}"
                )
        
        # Build and return the prompt
        return builder.build()
    
    def get_required_variables(self) -> list[str]:
        """
        Extract required variable names from the prompt template.
        
        Returns:
            list[str]: List of variable names found in the template
        """
        from app.services.prompt_template_builder import PromptTemplateBuilder
        builder = PromptTemplateBuilder(self.config)
        return builder.get_required_variables()
    
    def get_variable_schema(self) -> dict:
        """
        Get variable schema from config if defined, otherwise extract from template.
        
        Returns:
            dict: Variable schema with descriptions, types, defaults, etc.
        """
        from app.services.prompt_template_builder import PromptTemplateBuilder
        builder = PromptTemplateBuilder(self.config)
        return builder.get_variable_schema()
    
    def validate_variables(self, variables: dict) -> tuple[bool, list[str]]:
        """
        Validate that all required variables are provided.
        
        Args:
            variables: Dictionary of variables to validate
            
        Returns:
            tuple: (is_valid, list_of_missing_variables)
        """
        from app.services.prompt_template_builder import PromptTemplateBuilder
        builder = PromptTemplateBuilder(self.config, variables)
        return builder.validate_variables(variables)


class Document(Base):
    """Model for processed documents."""
    
    __tablename__ = "documents"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(String(255), nullable=False, index=True)
    filename = Column(String(500), nullable=False)
    source_url = Column(Text)  # Original GCS URL of the uploaded document
    job_id = Column(String(100), index=True)  # Processing job ID
    
    # Content
    original_markdown = Column(Text)  # Raw markdown from Docling
    cleaned_markdown = Column(Text)  # Cleaned markdown after parsing agent
    public_markdown = Column(Text)  # Markdown with public image URLs
    
    # Status
    status = Column(String(50), default="processed", index=True)
    question_count = Column(Integer, default=0)
    
    # Metadata
    file_type = Column(String(50))  # pdf, docx, etc.
    file_size = Column(Integer)  # Size in bytes
    extra_metadata = Column(JSONB)  # Additional flexible data
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationship to questions
    questions = relationship("Question", back_populates="document", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Document(id='{self.id}', filename='{self.filename}', user_id='{self.user_id}')>"


class Question(Base):
    """Model for extracted questions with LLM answer support."""
    
    __tablename__ = "questions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(String(255), nullable=False, index=True)
    
    # Question content
    question_number = Column(Integer)  # Order in document (1-based)
    question_text = Column(Text, nullable=False)  # Full question markdown with images
    question_type = Column(String(50), default="multiple_choice")  # "multiple_choice", "open_ended", "true_false", etc.
    options = Column(JSONB)  # For MCQ: {"A": "option text", "B": "option text", ...}
    
    # Answer fields (for future LLM solving)
    correct_answer = Column(String(500))  # Expected correct answer (e.g., "A" or full text)
    llm_answer = Column(String(500))  # LLM's generated answer
    llm_explanation = Column(Text)  # LLM's reasoning/explanation
    llm_confidence = Column(Float)  # Confidence score 0.0 to 1.0
    llm_model = Column(String(100))  # Model used for answering
    
    # Answer status
    is_answered = Column(Boolean, default=False, index=True)
    is_correct = Column(Boolean)  # Whether LLM answer matches correct answer
    answered_at = Column(DateTime(timezone=True))
    
    # Classification metadata (populated by ClassificationAgent)
    difficulty = Column(String(50))  # "easy", "medium", "hard"
    topic = Column(String(255), index=True)  # Primary subject: "math", "physics", "chemistry", etc.
    subtopic = Column(String(255))  # More specific area: "algebra", "geometry", "mechanics", etc.
    grade_level = Column(String(50))  # Educational level: "8", "high school", "college", etc.
    cognitive_level = Column(String(50))  # Bloom's taxonomy: "knowledge", "comprehension", "application", etc.
    tags = Column(JSONB)  # Flexible tags array for searchable keywords
    is_classified = Column(Boolean, default=False, index=True)  # Whether classification has been done
    
    # Other metadata
    image_urls = Column(JSONB)  # List of image URLs in this question
    extra_metadata = Column(JSONB)  # Additional flexible data
    
    # Embedding fields for vector search
    embedding = Column(Vector(settings.embedding_dimensions))  # Vector embedding for similarity search
    is_embedded = Column(Boolean, default=False, index=True)  # Whether embedding has been generated
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationship to document
    document = relationship("Document", back_populates="questions")
    
    def __repr__(self):
        return f"<Question(id='{self.id}', number={self.question_number}, type='{self.question_type}')>"
    
    def to_dict(self) -> dict:
        """Convert question to dictionary for API responses."""
        return {
            "id": str(self.id),
            "document_id": str(self.document_id),
            "user_id": self.user_id,
            "question_number": self.question_number,
            "question_text": self.question_text,
            "question_type": self.question_type,
            "options": self.options,
            "correct_answer": self.correct_answer,
            "llm_answer": self.llm_answer,
            "llm_explanation": self.llm_explanation,
            "llm_confidence": self.llm_confidence,
            "is_answered": self.is_answered,
            "is_correct": self.is_correct,
            "difficulty": self.difficulty,
            "topic": self.topic,
            "subtopic": self.subtopic,
            "grade_level": self.grade_level,
            "cognitive_level": self.cognitive_level,
            "tags": self.tags,
            "is_classified": self.is_classified,
            "image_urls": self.image_urls,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

