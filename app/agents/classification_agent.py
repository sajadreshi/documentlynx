"""Classification Agent - classifies questions by subject, difficulty, and other metadata.

This agent uses LangChain tools for reusable operations:
- parse_json_array: Parse JSON arrays from LLM responses
- classify_question: Classify a single question
- classify_questions_batch: Classify multiple questions efficiently
"""

import json
import logging
import uuid
from typing import Optional

from app.services.extraction_orchestrator import AgentState
from app.services.prompt_template_builder import PromptTemplateBuilder
from app.database import SessionLocal
from app.models import Question
from app.tools import parse_json_array, classify_question, classify_questions_batch
from app.observability import traceable
from llms import get_llm

logger = logging.getLogger(__name__)


class ClassificationAgent:
    """Agent responsible for classifying questions with subject and difficulty metadata."""
    
    def __init__(self, llm_model: Optional[str] = None):
        """
        Initialize the classification agent.
        
        Args:
            llm_model: Name of the LLM model to use (defaults to settings)
        """
        from app.config import settings
        
        self.llm_model = llm_model or settings.validation_llm_model
    
    @traceable(name="ClassificationAgent.process", tags=["agent", "classification"])
    def process(self, state: AgentState) -> AgentState:
        """
        Classify questions created by PersistenceAgent.
        
        Workflow:
        1. Get question_ids from state
        2. Load questions from database
        3. Use LLM to classify each question
        4. Update questions with classification metadata
        
        Args:
            state: Current agent state with question_ids
            
        Returns:
            Updated agent state
        """
        job_id = state.get("job_id", "unknown")
        
        logger.info(f"Classification agent processing job {job_id}")
        
        # Update state
        state["status"] = "classifying"
        
        # Initialize metadata if not present
        if "metadata" not in state:
            state["metadata"] = {}
        
        # Get question IDs from state
        question_ids = state.get("question_ids", [])
        
        if not question_ids:
            logger.warning(f"No question_ids in state for job {job_id}, skipping classification")
            state["metadata"]["classified_count"] = 0
            return state
        
        logger.info(f"  - Classifying {len(question_ids)} questions")
        
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
                state["metadata"]["classified_count"] = 0
                return state
            
            logger.info(f"  - Loaded {len(questions)} questions from database")
            
            # Step 2: Prepare questions for LLM
            questions_data = []
            for q in questions:
                q_data = {
                    "question_id": str(q.id),
                    "question_text": q.question_text[:1000] if q.question_text else "",  # Truncate long questions
                    "question_type": q.question_type,
                    "options": q.options
                }
                questions_data.append(q_data)
            
            # Step 3: Call LLM for classification
            logger.info(f"  - Calling LLM for classification...")
            classifications = self._classify_with_llm(questions_data)
            
            if not classifications:
                logger.warning("LLM classification returned no results")
                state["metadata"]["classified_count"] = 0
                return state
            
            logger.info(f"  - Received {len(classifications)} classifications")
            
            # Step 4: Update questions with classifications
            classification_map = {c["question_id"]: c for c in classifications if "question_id" in c}
            
            classified_count = 0
            for question in questions:
                q_id = str(question.id)
                if q_id in classification_map:
                    classification = classification_map[q_id]
                    
                    question.topic = classification.get("topic")
                    question.subtopic = classification.get("subtopic")
                    question.difficulty = classification.get("difficulty")
                    question.grade_level = classification.get("grade_level")
                    question.cognitive_level = classification.get("cognitive_level")
                    question.tags = classification.get("tags", [])
                    question.is_classified = True
                    
                    classified_count += 1
            
            # Commit changes
            db.commit()
            
            state["metadata"]["classified_count"] = classified_count
            
            logger.info(f"  - Successfully classified {classified_count} questions")
            logger.info(f"Classification agent completed for job {job_id}")
            
        except Exception as e:
            if db:
                db.rollback()
            error_msg = f"Error during classification: {str(e)}"
            logger.error(error_msg, exc_info=True)
            state["metadata"]["classification_error"] = error_msg
            # Don't fail the pipeline - continue without classification
            state["metadata"]["classified_count"] = 0
            
        finally:
            if db:
                db.close()
        
        return state
    
    def _classify_with_llm(self, questions_data: list[dict]) -> list[dict]:
        """
        Use LLM to classify questions.
        
        Uses the classify_questions_batch tool for efficient batch classification.
        
        Args:
            questions_data: List of question dictionaries
            
        Returns:
            List of classification dictionaries
        """
        try:
            # Use the classify_questions_batch tool for batch processing
            # This tool handles LLM invocation and JSON parsing internally
            logger.info(f"  - Using classify_questions_batch tool (LangChain @tool)")
            classifications = classify_questions_batch.invoke({
                "questions": questions_data,
                "llm_model": self.llm_model
            })
            
            return classifications
            
        except Exception as e:
            logger.error(f"LLM classification error: {str(e)}", exc_info=True)
            return []
    
    def _parse_classification_json(self, response_text: str) -> list[dict]:
        """
        Parse JSON array of classifications from LLM response.
        
        Uses the parse_json_array tool (LangChain @tool) for consistent parsing.
        
        Args:
            response_text: Raw LLM response
            
        Returns:
            List of classification dictionaries
        """
        # Delegate to the parse_json_array tool
        return parse_json_array.invoke(response_text)
    
    def classify_single_question(self, question_id: str) -> bool:
        """
        Classify a single question (utility method).
        
        Uses the classify_question tool (LangChain @tool) for single question classification.
        Useful for classifying individual questions after updates.
        
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
            
            # Use the classify_question tool (LangChain @tool)
            logger.info(f"  - Using classify_question tool (LangChain @tool)")
            classification = classify_question.invoke({
                "question_text": question.question_text[:1000] if question.question_text else "",
                "question_type": question.question_type or "open_ended",
                "options": question.options,
                "question_id": str(question.id),
                "llm_model": self.llm_model
            })
            
            if classification and "error" not in classification:
                question.topic = classification.get("topic")
                question.subtopic = classification.get("subtopic")
                question.difficulty = classification.get("difficulty")
                question.grade_level = classification.get("grade_level")
                question.cognitive_level = classification.get("cognitive_level")
                question.tags = classification.get("tags", [])
                question.is_classified = True
                
                db.commit()
                
                logger.info(f"Successfully classified question: {question_id}")
                return True
            
            return False
            
        except Exception as e:
            if db:
                db.rollback()
            logger.error(f"Error classifying question {question_id}: {e}")
            return False
            
        finally:
            if db:
                db.close()
    
    def classify_unclassified_questions(self, user_id: Optional[str] = None, limit: int = 50) -> int:
        """
        Batch classify questions that haven't been classified yet.
        
        Useful for backfilling classifications or re-classifying after prompt changes.
        
        Args:
            user_id: Optional filter by user
            limit: Maximum number of questions to process
            
        Returns:
            Number of questions classified
        """
        db = None
        try:
            db = SessionLocal()
            
            # Query unclassified questions
            query = db.query(Question).filter(Question.is_classified == False)
            
            if user_id:
                query = query.filter(Question.user_id == user_id)
            
            questions = query.limit(limit).all()
            
            if not questions:
                logger.info("No unclassified questions found")
                return 0
            
            logger.info(f"Classifying {len(questions)} questions...")
            
            # Prepare questions data
            questions_data = []
            for q in questions:
                q_data = {
                    "question_id": str(q.id),
                    "question_text": q.question_text[:1000] if q.question_text else "",
                    "question_type": q.question_type,
                    "options": q.options
                }
                questions_data.append(q_data)
            
            # Classify
            classifications = self._classify_with_llm(questions_data)
            
            if not classifications:
                return 0
            
            # Build map
            classification_map = {c["question_id"]: c for c in classifications if "question_id" in c}
            
            # Update questions
            classified_count = 0
            for question in questions:
                q_id = str(question.id)
                if q_id in classification_map:
                    classification = classification_map[q_id]
                    
                    question.topic = classification.get("topic")
                    question.subtopic = classification.get("subtopic")
                    question.difficulty = classification.get("difficulty")
                    question.grade_level = classification.get("grade_level")
                    question.cognitive_level = classification.get("cognitive_level")
                    question.tags = classification.get("tags", [])
                    question.is_classified = True
                    
                    classified_count += 1
            
            db.commit()
            
            logger.info(f"Successfully classified {classified_count} questions")
            return classified_count
            
        except Exception as e:
            if db:
                db.rollback()
            logger.error(f"Error in batch classification: {e}")
            return 0
            
        finally:
            if db:
                db.close()
