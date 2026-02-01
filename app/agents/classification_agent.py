"""Classification Agent - classifies questions by subject, difficulty, and other metadata."""

import json
import logging
import uuid
from typing import Optional

from app.services.extraction_orchestrator import AgentState
from app.database import SessionLocal
from app.models import Question
from llms import get_llm

logger = logging.getLogger(__name__)

# Prompt template for LLM-based classification
CLASSIFICATION_PROMPT = """You are an expert educational content classifier. Your task is to analyze questions and classify them with appropriate metadata.

## Questions to Classify
{questions_json}

## Instructions
For each question, provide classification in the following categories:

1. **topic** (required): The primary subject area. Choose ONE from:
   - math, physics, chemistry, biology, psychology, history, geography, 
   - english, literature, economics, computer_science, art, music, 
   - philosophy, sociology, political_science, environmental_science, other

2. **subtopic** (required): A more specific area within the subject. Examples:
   - Math: algebra, geometry, calculus, statistics, trigonometry, number_theory
   - Physics: mechanics, thermodynamics, electromagnetism, optics, quantum
   - Chemistry: organic, inorganic, physical, biochemistry, analytical
   - Biology: genetics, ecology, anatomy, microbiology, evolution

3. **difficulty** (required): The difficulty level. Choose ONE from:
   - easy: Basic recall, simple concepts
   - medium: Application of concepts, moderate complexity
   - hard: Analysis, synthesis, complex problem-solving

4. **grade_level** (required): The appropriate educational level. Examples:
   - "elementary" (grades 1-5)
   - "middle_school" (grades 6-8)
   - "high_school" (grades 9-12)
   - "undergraduate"
   - "graduate"
   - Or specific grade like "8" for 8th grade

5. **cognitive_level** (required): Based on Bloom's Taxonomy. Choose ONE from:
   - knowledge: Recall facts and basic concepts
   - comprehension: Understand and explain ideas
   - application: Use information in new situations
   - analysis: Draw connections, compare, contrast
   - synthesis: Create new ideas, design solutions
   - evaluation: Justify decisions, critique

6. **tags** (required): Array of 3-5 relevant keywords for search. Be specific.

## Output Format
Return a JSON array with classification for each question. Match by question_id.

```json
[
  {{
    "question_id": "uuid-string",
    "topic": "math",
    "subtopic": "geometry",
    "difficulty": "medium",
    "grade_level": "8",
    "cognitive_level": "application",
    "tags": ["area", "triangles", "2D shapes", "measurement"]
  }}
]
```

Output ONLY the JSON array, no additional text."""


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
        
        Args:
            questions_data: List of question dictionaries
            
        Returns:
            List of classification dictionaries
        """
        try:
            # Get LLM instance
            llm = get_llm(self.llm_model)
            
            # Build JSON for prompt
            questions_json = json.dumps(questions_data, indent=2)
            
            # Escape curly braces for format string
            escaped_json = questions_json.replace("{", "{{").replace("}", "}}")
            
            # Build prompt
            prompt = CLASSIFICATION_PROMPT.format(questions_json=escaped_json)
            
            # Call LLM
            response = llm.invoke(prompt)
            response_text = response.content if hasattr(response, 'content') else str(response)
            
            # Parse JSON response
            classifications = self._parse_classification_json(response_text)
            
            return classifications
            
        except Exception as e:
            logger.error(f"LLM classification error: {str(e)}", exc_info=True)
            return []
    
    def _parse_classification_json(self, response_text: str) -> list[dict]:
        """
        Parse JSON array of classifications from LLM response.
        
        Args:
            response_text: Raw LLM response
            
        Returns:
            List of classification dictionaries
        """
        try:
            # Clean up response
            text = response_text.strip()
            
            # Remove markdown code block wrappers
            if text.startswith("```json"):
                text = text[7:]
            elif text.startswith("```"):
                text = text[3:]
            
            if text.endswith("```"):
                text = text[:-3]
            
            text = text.strip()
            
            # Find JSON array
            start = text.find('[')
            end = text.rfind(']') + 1
            
            if start >= 0 and end > start:
                json_str = text[start:end]
                classifications = json.loads(json_str)
                
                if isinstance(classifications, list):
                    return classifications
            
            logger.warning(f"Could not parse classification JSON: {text[:200]}...")
            return []
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {str(e)}")
            return []
        except Exception as e:
            logger.error(f"Error parsing classifications: {str(e)}")
            return []
    
    def classify_single_question(self, question_id: str) -> bool:
        """
        Classify a single question (utility method).
        
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
            
            # Prepare question data
            questions_data = [{
                "question_id": str(question.id),
                "question_text": question.question_text[:1000] if question.question_text else "",
                "question_type": question.question_type,
                "options": question.options
            }]
            
            # Classify
            classifications = self._classify_with_llm(questions_data)
            
            if classifications and len(classifications) > 0:
                classification = classifications[0]
                
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
