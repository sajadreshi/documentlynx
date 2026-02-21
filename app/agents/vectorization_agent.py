"""Vectorization Agent - generates embeddings for questions and stores in pgvector."""

import logging
import uuid
from typing import Optional

from app.services.extraction_orchestrator import AgentState
from app.services.embedding_service import EmbeddingService
from app.database import SessionLocal
from app.models import Question
from app.observability import traceable

logger = logging.getLogger(__name__)


class VectorizationAgent:
    """Agent responsible for generating embeddings and storing in PostgreSQL with pgvector.
    
    This agent:
    1. Loads questions from database using question_ids from state
    2. Builds text representations for each question
    3. Generates embeddings in batch using configured provider
    4. Updates questions with embeddings in database
    """
    
    def __init__(self, embedding_service: Optional[EmbeddingService] = None):
        """
        Initialize the vectorization agent.
        
        Args:
            embedding_service: Optional pre-configured embedding service
        """
        self.embedding_service = embedding_service or EmbeddingService()
    
    @traceable(name="VectorizationAgent.process", tags=["agent", "vectorization"])
    def process(self, state: AgentState) -> AgentState:
        """
        Generate embeddings for questions created by PersistenceAgent.
        
        Workflow:
        1. Get question_ids from state
        2. Load questions from database
        3. Build text representations
        4. Generate embeddings in batch
        5. Update questions with embeddings
        
        Args:
            state: Current agent state with question_ids
            
        Returns:
            Updated agent state with vector_ids
        """
        job_id = state.get("job_id", "unknown")
        
        logger.info(f"Vectorization agent processing job {job_id}")
        
        # Update state
        state["status"] = "vectorizing"
        
        # Initialize metadata if not present
        if "metadata" not in state:
            state["metadata"] = {}
        
        # Get question IDs from state
        question_ids = state.get("question_ids", [])
        
        if not question_ids:
            logger.warning(f"No question_ids in state for job {job_id}, skipping vectorization")
            state["vector_ids"] = []
            state["metadata"]["embedded_count"] = 0
            return state
        
        logger.info(f"  - Processing {len(question_ids)} questions for embedding")
        
        db = None
        try:
            # Get database session
            db = SessionLocal()
            
            # Step 1: Load questions from database
            questions = db.query(Question).filter(
                Question.id.in_([uuid.UUID(qid) for qid in question_ids])
            ).all()
            
            if not questions:
                logger.warning(f"No questions found in database for job {job_id}")
                state["vector_ids"] = []
                state["metadata"]["embedded_count"] = 0
                return state
            
            logger.info(f"  - Loaded {len(questions)} questions from database")
            
            # Step 2: Build text representations
            texts = self.embedding_service.build_question_texts(questions)
            
            # Log sample text for debugging
            if texts:
                sample_text = texts[0][:200] + "..." if len(texts[0]) > 200 else texts[0]
                logger.debug(f"  - Sample text for embedding: {sample_text}")
            
            # Step 3: Generate embeddings in batch
            logger.info(f"  - Generating embeddings using {self.embedding_service.provider}/{self.embedding_service.model}...")
            embeddings = self.embedding_service.embed_texts(texts)
            
            logger.info(f"  - Generated {len(embeddings)} embeddings")
            
            # Step 4: Update questions with embeddings
            embedded_count = 0
            for question, embedding in zip(questions, embeddings):
                question.embedding = embedding
                question.is_embedded = True
                embedded_count += 1
            
            # Commit changes
            db.commit()
            
            # Update state
            state["vector_ids"] = question_ids  # Same as question_ids since we embed each question
            state["metadata"]["embedded_count"] = embedded_count
            state["metadata"]["embedding_provider"] = self.embedding_service.provider
            state["metadata"]["embedding_model"] = self.embedding_service.model
            state["metadata"]["embedding_dimensions"] = self.embedding_service.dimensions
            
            logger.info(f"  - Successfully embedded {embedded_count} questions")
            logger.info(f"Vectorization agent completed for job {job_id}")
            
        except Exception as e:
            if db:
                db.rollback()
            error_msg = f"Error during vectorization: {str(e)}"
            logger.error(error_msg, exc_info=True)
            state["metadata"]["vectorization_error"] = error_msg
            # Don't fail the entire pipeline - continue without embeddings
            state["vector_ids"] = []
            state["metadata"]["embedded_count"] = 0
            
        finally:
            if db:
                db.close()
        
        return state
    
    def embed_single_question(self, question_id: str) -> bool:
        """
        Generate embedding for a single question (utility method).
        
        Useful for re-embedding individual questions after updates.
        
        Args:
            question_id: UUID string of the question
            
        Returns:
            True if successful, False otherwise
        """
        db = None
        try:
            db = SessionLocal()
            
            question = db.query(Question).filter(
                Question.id == uuid.UUID(question_id)
            ).first()
            
            if not question:
                logger.warning(f"Question not found: {question_id}")
                return False
            
            # Build text and generate embedding
            text = self.embedding_service.build_question_text(question)
            embedding = self.embedding_service.embed_text(text)
            
            # Update question
            question.embedding = embedding
            question.is_embedded = True
            
            db.commit()
            
            logger.info(f"Successfully embedded question: {question_id}")
            return True
            
        except Exception as e:
            if db:
                db.rollback()
            logger.error(f"Error embedding question {question_id}: {e}")
            return False
            
        finally:
            if db:
                db.close()
    
    def embed_unembed_questions(self, user_id: Optional[str] = None, limit: int = 100) -> int:
        """
        Batch embed questions that don't have embeddings yet.
        
        Useful for backfilling embeddings or re-embedding after model changes.
        
        Args:
            user_id: Optional filter by user
            limit: Maximum number of questions to process
            
        Returns:
            Number of questions embedded
        """
        db = None
        try:
            db = SessionLocal()
            
            # Query questions without embeddings
            query = db.query(Question).filter(Question.is_embedded == False)
            
            if user_id:
                query = query.filter(Question.user_id == user_id)
            
            questions = query.limit(limit).all()
            
            if not questions:
                logger.info("No unembedded questions found")
                return 0
            
            logger.info(f"Embedding {len(questions)} questions...")
            
            # Build texts and generate embeddings
            texts = self.embedding_service.build_question_texts(questions)
            embeddings = self.embedding_service.embed_texts(texts)
            
            # Update questions
            for question, embedding in zip(questions, embeddings):
                question.embedding = embedding
                question.is_embedded = True
            
            db.commit()
            
            logger.info(f"Successfully embedded {len(questions)} questions")
            return len(questions)
            
        except Exception as e:
            if db:
                db.rollback()
            logger.error(f"Error in batch embedding: {e}")
            return 0
            
        finally:
            if db:
                db.close()
