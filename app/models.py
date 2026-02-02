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


class Job(Base):
    """Model for tracking document processing jobs."""
    
    __tablename__ = "jobs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(String(255), nullable=False, index=True)
    document_url = Column(Text, nullable=False)
    
    # Status tracking
    # Values: queued, ingesting, parsing, validating, persisting, classifying, vectorizing, completed, failed
    status = Column(String(50), default="queued", nullable=False, index=True)
    error_message = Column(Text)
    
    # Results (populated on completion)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="SET NULL"))
    question_count = Column(Integer, default=0)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    
    # Relationship to document
    document = relationship("Document", foreign_keys=[document_id])
    
    def __repr__(self):
        return f"<Job(id='{self.id}', status='{self.status}', user_id='{self.user_id}')>"
    
    def to_dict(self) -> dict:
        """Convert job to dictionary for API responses."""
        return {
            "job_id": str(self.id),
            "user_id": self.user_id,
            "document_url": self.document_url,
            "status": self.status,
            "error_message": self.error_message,
            "document_id": str(self.document_id) if self.document_id else None,
            "question_count": self.question_count,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


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

