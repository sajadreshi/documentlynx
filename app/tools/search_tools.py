"""Search tools for semantic similarity search over questions.

These tools provide LangChain-compatible interfaces for searching
questions using pgvector embeddings.
"""

import logging
from typing import Any, Optional

from langchain_core.tools import tool

from app.services.search_service import SearchService

logger = logging.getLogger(__name__)

# Singleton service instance for reuse
_search_service: Optional[SearchService] = None


def _get_search_service() -> SearchService:
    """Get or create the search service singleton."""
    global _search_service
    if _search_service is None:
        _search_service = SearchService()
    return _search_service


@tool
def search_similar_questions(
    query: str,
    user_id: str,
    limit: int = 10,
    min_similarity: float = 0.3
) -> list[dict[str, Any]]:
    """Search for questions semantically similar to the query.
    
    Uses vector embeddings and cosine similarity to find questions
    that are semantically related to the search query. Results are
    automatically scoped to the specified user's questions only.
    
    Args:
        query: Natural language search query (e.g., "area of a triangle")
        user_id: User ID to scope the search (required for data isolation)
        limit: Maximum number of results to return (default: 10, max: 50)
        min_similarity: Minimum similarity threshold 0-1 (default: 0.3)
        
    Returns:
        List of dictionaries, each containing:
        - question: Question data with id, text, type, topic, difficulty, etc.
        - similarity: Float score from 0-1 (higher = more similar)
        
    Example:
        >>> results = search_similar_questions.invoke({
        ...     "query": "What is the area of a triangle?",
        ...     "user_id": "user123",
        ...     "limit": 5
        ... })
        >>> print(results[0]["similarity"])
        0.89
        >>> print(results[0]["question"]["topic"])
        "math"
    """
    try:
        service = _get_search_service()
        return service.search_questions(
            query=query,
            user_id=user_id,
            limit=limit,
            min_similarity=min_similarity
        )
    except Exception as e:
        logger.error(f"Error in search_similar_questions tool: {str(e)}", exc_info=True)
        return []


@tool
def find_related_questions(
    question_id: str,
    user_id: str,
    limit: int = 5
) -> list[dict[str, Any]]:
    """Find questions similar to an existing question.
    
    Useful for "related questions" or "you might also like" features.
    Uses the embedding of the source question to find similar ones.
    
    Args:
        question_id: UUID of the source question to find similar ones for
        user_id: User ID to scope the search (required for data isolation)
        limit: Maximum number of similar questions to return (default: 5)
        
    Returns:
        List of similar questions with similarity scores
        
    Example:
        >>> related = find_related_questions.invoke({
        ...     "question_id": "550e8400-e29b-41d4-a716-446655440000",
        ...     "user_id": "user123",
        ...     "limit": 3
        ... })
        >>> print(len(related))
        3
    """
    try:
        service = _get_search_service()
        return service.find_similar_to_question(
            question_id=question_id,
            user_id=user_id,
            limit=limit,
            exclude_self=True
        )
    except Exception as e:
        logger.error(f"Error in find_related_questions tool: {str(e)}", exc_info=True)
        return []


@tool
def get_search_statistics(user_id: str) -> dict[str, Any]:
    """Get statistics about searchable questions for a user.
    
    Returns counts of total and embedded questions, useful for
    understanding search coverage.
    
    Args:
        user_id: User ID to get stats for
        
    Returns:
        Dictionary with:
        - total_questions: Total question count
        - embedded_questions: Questions with embeddings
        - searchable_percentage: Percentage that can be searched
        
    Example:
        >>> stats = get_search_statistics.invoke({"user_id": "user123"})
        >>> print(stats["searchable_percentage"])
        95.5
    """
    try:
        service = _get_search_service()
        return service.get_search_stats(user_id=user_id)
    except Exception as e:
        logger.error(f"Error in get_search_statistics tool: {str(e)}", exc_info=True)
        return {
            "user_id": user_id,
            "total_questions": 0,
            "embedded_questions": 0,
            "searchable_percentage": 0,
            "error": str(e)
        }
