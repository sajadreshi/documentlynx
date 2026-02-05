"""Search service for semantic similarity search over questions using pgvector."""

import logging
from typing import Optional

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import Question
from app.services.embedding_service import EmbeddingService

logger = logging.getLogger(__name__)


class SearchService:
    """Service for semantic search over questions using pgvector.
    
    Provides user-scoped similarity search using cosine distance
    on question embeddings stored in PostgreSQL with pgvector.
    
    All searches are filtered by user_id to ensure data isolation.
    """
    
    def __init__(self, embedding_service: Optional[EmbeddingService] = None):
        """
        Initialize the search service.
        
        Args:
            embedding_service: Optional pre-configured embedding service
        """
        self.embedding_service = embedding_service or EmbeddingService()
    
    def search_questions(
        self,
        query: str,
        user_id: str,
        limit: int = 10,
        min_similarity: float = 0.3,
        db: Optional[Session] = None
    ) -> list[dict]:
        """
        Search for questions semantically similar to the query.
        
        Uses pgvector's cosine distance operator to find similar questions.
        Results are automatically filtered to the specified user_id.
        
        Args:
            query: Natural language search query
            user_id: User ID to scope the search (required for data isolation)
            limit: Maximum number of results to return (default: 10, max: 50)
            min_similarity: Minimum similarity threshold 0-1 (default: 0.3)
            db: Optional database session (will create one if not provided)
            
        Returns:
            List of dictionaries containing:
            - question: Question data (from to_dict())
            - similarity: Float similarity score (0-1, higher is more similar)
            
        Example:
            >>> service = SearchService()
            >>> results = service.search_questions(
            ...     query="area of a triangle",
            ...     user_id="user123",
            ...     limit=5
            ... )
            >>> print(results[0]["similarity"])
            0.89
        """
        if not query or not query.strip():
            logger.warning("Empty search query provided")
            return []
        
        if not user_id:
            logger.error("user_id is required for search")
            raise ValueError("user_id is required for search")
        
        # Clamp limit
        limit = min(max(1, limit), 50)
        
        # Clamp similarity threshold
        min_similarity = max(0.0, min(1.0, min_similarity))
        
        should_close_db = db is None
        if db is None:
            db = SessionLocal()
        
        try:
            # Step 1: Generate embedding for search query
            logger.info(f"Generating embedding for query: '{query[:50]}...'")
            query_embedding = self.embedding_service.embed_text(query.strip())
            
            # Step 2: Query with cosine distance
            # pgvector's <=> operator returns cosine distance (0 = identical, 2 = opposite)
            # We convert to similarity: 1 - distance (for normalized vectors, distance is 0-1)
            distance = Question.embedding.cosine_distance(query_embedding)
            similarity = (1 - distance).label('similarity')
            
            # Step 3: Build and execute query with user filter
            results = db.query(Question, similarity).filter(
                Question.user_id == user_id,
                Question.is_embedded == True,
                Question.embedding.isnot(None)
            ).order_by(
                distance  # Ascending - closest (most similar) first
            ).limit(limit).all()
            
            logger.info(f"Found {len(results)} results for user {user_id}")
            
            # Step 4: Format results and filter by similarity threshold
            formatted_results = []
            for question, sim_score in results:
                # Convert similarity score to float
                sim_float = float(sim_score) if sim_score is not None else 0.0
                
                # Skip results below threshold
                if sim_float < min_similarity:
                    continue
                
                formatted_results.append({
                    "question": question.to_dict(),
                    "similarity": round(sim_float, 4)
                })
            
            logger.info(f"Returning {len(formatted_results)} results above similarity threshold {min_similarity}")
            return formatted_results
            
        except Exception as e:
            logger.error(f"Error during search: {str(e)}", exc_info=True)
            raise
            
        finally:
            if should_close_db:
                db.close()
    
    def find_similar_to_question(
        self,
        question_id: str,
        user_id: str,
        limit: int = 5,
        exclude_self: bool = True,
        db: Optional[Session] = None
    ) -> list[dict]:
        """
        Find questions similar to an existing question.
        
        Useful for "related questions" or "you might also like" features.
        
        Args:
            question_id: UUID of the source question
            user_id: User ID to scope the search
            limit: Maximum number of results
            exclude_self: Whether to exclude the source question from results
            db: Optional database session
            
        Returns:
            List of similar questions with similarity scores
        """
        import uuid
        
        should_close_db = db is None
        if db is None:
            db = SessionLocal()
        
        try:
            # Get the source question
            source_question = db.query(Question).filter(
                Question.id == uuid.UUID(question_id),
                Question.user_id == user_id
            ).first()
            
            if not source_question:
                logger.warning(f"Question not found: {question_id}")
                return []
            
            if not source_question.embedding:
                logger.warning(f"Question has no embedding: {question_id}")
                return []
            
            # Use the question's embedding for search
            source_embedding = source_question.embedding
            distance = Question.embedding.cosine_distance(source_embedding)
            similarity = (1 - distance).label('similarity')
            
            # Build query
            query_builder = db.query(Question, similarity).filter(
                Question.user_id == user_id,
                Question.is_embedded == True,
                Question.embedding.isnot(None)
            )
            
            # Optionally exclude the source question
            if exclude_self:
                query_builder = query_builder.filter(Question.id != source_question.id)
            
            results = query_builder.order_by(distance).limit(limit).all()
            
            # Format results
            return [
                {
                    "question": q.to_dict(),
                    "similarity": round(float(sim), 4)
                }
                for q, sim in results
            ]
            
        except Exception as e:
            logger.error(f"Error finding similar questions: {str(e)}", exc_info=True)
            raise
            
        finally:
            if should_close_db:
                db.close()
    
    def get_search_stats(self, user_id: str, db: Optional[Session] = None) -> dict:
        """
        Get statistics about searchable questions for a user.
        
        Args:
            user_id: User ID
            db: Optional database session
            
        Returns:
            Dictionary with counts and stats
        """
        should_close_db = db is None
        if db is None:
            db = SessionLocal()
        
        try:
            total_questions = db.query(Question).filter(
                Question.user_id == user_id
            ).count()
            
            embedded_questions = db.query(Question).filter(
                Question.user_id == user_id,
                Question.is_embedded == True
            ).count()
            
            return {
                "user_id": user_id,
                "total_questions": total_questions,
                "embedded_questions": embedded_questions,
                "searchable_percentage": round(
                    (embedded_questions / total_questions * 100) if total_questions > 0 else 0, 
                    1
                )
            }
            
        finally:
            if should_close_db:
                db.close()
