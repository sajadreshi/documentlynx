"""Embedding service for generating vector embeddings with configurable providers."""

import logging
from typing import Optional

from app.config import settings
from app.models import Question
from app.retry import retry_with_backoff

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Service for generating embeddings with configurable providers.
    
    Supports:
    - HuggingFace (local) models via sentence-transformers
    - OpenAI embeddings via langchain-openai
    
    The provider and model are configured via environment variables:
    - EMBEDDING_PROVIDER: "huggingface" or "openai"
    - EMBEDDING_MODEL: Model name (e.g., "all-MiniLM-L6-v2" or "text-embedding-3-small")
    """
    
    def __init__(self, provider: Optional[str] = None, model: Optional[str] = None):
        """
        Initialize the embedding service.
        
        Args:
            provider: Override the configured provider ("huggingface" or "openai")
            model: Override the configured model name
        """
        self.provider = provider or settings.embedding_provider
        self.model = model or settings.embedding_model
        self.dimensions = settings.embedding_dimensions
        self._embeddings = None
        
        logger.info(f"Initializing EmbeddingService with provider={self.provider}, model={self.model}")
    
    @property
    def embeddings(self):
        """Lazy-load the embeddings model."""
        if self._embeddings is None:
            self._embeddings = self._create_embeddings()
        return self._embeddings
    
    def _create_embeddings(self):
        """Create the appropriate embeddings instance based on provider."""
        if self.provider == "openai":
            try:
                from langchain_openai import OpenAIEmbeddings  # type: ignore[import-untyped]
                
                logger.info(f"Creating OpenAI embeddings with model: {self.model}")
                return OpenAIEmbeddings(
                    model=self.model,
                    openai_api_key=settings.openai_api_key
                )
            except ImportError:
                logger.error("langchain-openai not installed. Run: pip install langchain-openai")
                raise
            except Exception as e:
                logger.error(f"Failed to create OpenAI embeddings: {e}")
                raise
        else:
            # Default to HuggingFace
            try:
                from langchain_community.embeddings import HuggingFaceEmbeddings  # type: ignore[import-not-found]
                
                logger.info(f"Creating HuggingFace embeddings with model: {self.model}")
                return HuggingFaceEmbeddings(
                    model_name=self.model,
                    model_kwargs={'device': 'cpu'},  # Use CPU for compatibility
                    encode_kwargs={'normalize_embeddings': True}
                )
            except ImportError:
                logger.error("langchain-community or sentence-transformers not installed.")
                logger.error("Run: pip install langchain-community sentence-transformers")
                raise
            except Exception as e:
                logger.error(f"Failed to create HuggingFace embeddings: {e}")
                raise
    
    @retry_with_backoff(max_retries=2, base_delay=1.0)
    def embed_text(self, text: str) -> list[float]:
        """
        Generate embedding for a single text.

        Args:
            text: Text to embed

        Returns:
            List of floats representing the embedding vector
        """
        try:
            return self.embeddings.embed_query(text)
        except Exception as e:
            logger.error(f"Error embedding text: {e}")
            raise

    @retry_with_backoff(max_retries=2, base_delay=1.0)
    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """
        Generate embeddings for multiple texts (batch processing).

        Args:
            texts: List of texts to embed

        Returns:
            List of embedding vectors
        """
        if not texts:
            return []

        try:
            return self.embeddings.embed_documents(texts)
        except Exception as e:
            logger.error(f"Error embedding texts batch: {e}")
            raise
    
    @staticmethod
    def build_question_text(question: Question) -> str:
        """
        Build text representation of a question for embedding.
        
        Combines classification metadata with question text and options
        to create a rich text representation for semantic search.
        
        The classification context (topic, subtopic, difficulty, etc.) is
        prepended to help the embedding model understand the domain and
        improve similarity matching for subject-specific queries.
        
        Args:
            question: Question model instance
            
        Returns:
            Combined text suitable for embedding
        """
        text_parts = []
        context_parts = []
        
        # Build classification context prefix
        if question.topic:
            context_parts.append(question.topic)
        if question.subtopic:
            context_parts.append(question.subtopic)
        if question.difficulty:
            context_parts.append(f"{question.difficulty} difficulty")
        if question.grade_level:
            context_parts.append(f"grade {question.grade_level}")
        
        # Add context as a bracketed prefix
        if context_parts:
            text_parts.append(f"[{' | '.join(context_parts)}]")
        
        # Add tags as keywords
        if question.tags and isinstance(question.tags, list):
            tags_str = ", ".join(question.tags[:5])  # Limit to 5 tags
            text_parts.append(f"Keywords: {tags_str}")
        
        # Add question text
        if question.question_text:
            text_parts.append(question.question_text.strip())
        
        # Add options for MCQ
        if question.options and isinstance(question.options, dict):
            for letter, option_text in sorted(question.options.items()):
                text_parts.append(f"{letter}) {option_text}")
        
        return "\n".join(text_parts)
    
    @staticmethod
    def build_question_texts(questions: list[Question]) -> list[str]:
        """
        Build text representations for multiple questions.
        
        Args:
            questions: List of Question model instances
            
        Returns:
            List of text representations
        """
        return [EmbeddingService.build_question_text(q) for q in questions]
