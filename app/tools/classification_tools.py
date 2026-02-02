"""Classification tools for educational content.

These tools help classify educational questions by subject, difficulty,
and other metadata using LLM-based analysis.
"""

import json
import logging
from typing import Any, Optional

from langchain_core.tools import tool

from app.services.prompt_template_builder import PromptTemplateBuilder
from app.tools.json_tools import parse_json_array
from llms import get_llm

logger = logging.getLogger(__name__)


@tool
def classify_question(
    question_text: str,
    question_type: str = "open_ended",
    options: Optional[dict[str, str]] = None,
    question_id: Optional[str] = None,
    llm_model: Optional[str] = None
) -> dict[str, Any]:
    """Classify a question by subject, difficulty, and educational metadata.
    
    Uses an LLM to analyze the question content and determine appropriate
    classification metadata for educational purposes.
    
    Args:
        question_text: The full text of the question to classify
        question_type: Type of question (multiple_choice, open_ended, true_false, fill_in_blank)
        options: For multiple choice questions, dict of option labels to text (e.g., {"A": "Option A text"})
        question_id: Optional ID to include in the response for tracking
        llm_model: Optional LLM model name to use (defaults to config setting)
        
    Returns:
        Classification dictionary with:
        - question_id: The provided ID or "single_question"
        - topic: Primary subject area (math, physics, chemistry, etc.)
        - subtopic: More specific area within the subject
        - difficulty: easy, medium, or hard
        - grade_level: Educational level (elementary, middle_school, high_school, undergraduate, graduate)
        - cognitive_level: Bloom's taxonomy level (knowledge, comprehension, application, analysis, synthesis, evaluation)
        - tags: List of 3-5 relevant keywords
        
    Example:
        >>> result = classify_question.invoke({
        ...     "question_text": "What is the area of a triangle with base 4 and height 3?",
        ...     "question_type": "multiple_choice",
        ...     "options": {"A": "6", "B": "7", "C": "12", "D": "14"}
        ... })
        >>> print(result["topic"])
        "math"
        >>> print(result["subtopic"])
        "geometry"
    """
    try:
        # Get LLM instance
        if llm_model:
            llm = get_llm(llm_model)
        else:
            from app.config import settings
            llm = get_llm(settings.validation_llm_model)
        
        # Prepare question data for the prompt
        q_id = question_id or "single_question"
        question_data = [{
            "question_id": q_id,
            "question_text": question_text[:1000] if question_text else "",  # Truncate long questions
            "question_type": question_type,
            "options": options
        }]
        
        # Build JSON for prompt
        questions_json = json.dumps(question_data, indent=2)
        
        # Build prompt from file
        prompt = PromptTemplateBuilder.build_from_file(
            name="classification",
            variables={"questions_json": questions_json}
        )
        
        # Call LLM
        response = llm.invoke(prompt)
        response_text = response.content if hasattr(response, 'content') else str(response)
        
        # Parse JSON response using our json tool
        classifications = parse_json_array.invoke(response_text)
        
        if classifications and len(classifications) > 0:
            classification = classifications[0]
            # Ensure question_id is set
            if "question_id" not in classification:
                classification["question_id"] = q_id
            return classification
        
        # Return default classification if parsing failed
        logger.warning("Classification returned no results, using defaults")
        return {
            "question_id": q_id,
            "topic": "other",
            "subtopic": "general",
            "difficulty": "medium",
            "grade_level": "high_school",
            "cognitive_level": "comprehension",
            "tags": []
        }
        
    except Exception as e:
        logger.error(f"Error classifying question: {str(e)}", exc_info=True)
        return {
            "question_id": question_id or "single_question",
            "topic": "other",
            "subtopic": "general",
            "difficulty": "medium",
            "grade_level": "high_school",
            "cognitive_level": "comprehension",
            "tags": [],
            "error": str(e)
        }


@tool
def classify_questions_batch(
    questions: list[dict[str, Any]],
    llm_model: Optional[str] = None
) -> list[dict[str, Any]]:
    """Classify multiple questions in a single LLM call for efficiency.
    
    More efficient than calling classify_question multiple times when
    classifying many questions at once.
    
    Args:
        questions: List of question dictionaries, each containing:
            - question_id: Unique identifier
            - question_text: The question text
            - question_type: Type of question
            - options: Optional dict of answer options
        llm_model: Optional LLM model name to use
        
    Returns:
        List of classification dictionaries, each containing:
        - question_id: Matching the input question
        - topic, subtopic, difficulty, grade_level, cognitive_level, tags
        
    Example:
        >>> questions = [
        ...     {"question_id": "q1", "question_text": "What is 2+2?", "question_type": "open_ended"},
        ...     {"question_id": "q2", "question_text": "Name the capital of France", "question_type": "open_ended"}
        ... ]
        >>> results = classify_questions_batch.invoke({"questions": questions})
        >>> print(len(results))
        2
    """
    try:
        # Get LLM instance
        if llm_model:
            llm = get_llm(llm_model)
        else:
            from app.config import settings
            llm = get_llm(settings.validation_llm_model)
        
        if not questions:
            return []
        
        # Prepare questions data (truncate long text)
        questions_data = []
        for q in questions:
            q_data = {
                "question_id": q.get("question_id", "unknown"),
                "question_text": (q.get("question_text") or "")[:1000],
                "question_type": q.get("question_type", "open_ended"),
                "options": q.get("options")
            }
            questions_data.append(q_data)
        
        # Build JSON for prompt
        questions_json = json.dumps(questions_data, indent=2)
        
        # Build prompt from file
        prompt = PromptTemplateBuilder.build_from_file(
            name="classification",
            variables={"questions_json": questions_json}
        )
        
        # Call LLM
        response = llm.invoke(prompt)
        response_text = response.content if hasattr(response, 'content') else str(response)
        
        # Parse JSON response
        classifications = parse_json_array.invoke(response_text)
        
        return classifications if classifications else []
        
    except Exception as e:
        logger.error(f"Error in batch classification: {str(e)}", exc_info=True)
        return []
