"""Persistence Agent - manages image upload, question extraction, and database storage."""

import json
import logging
import os
import re
import zipfile
from pathlib import Path
from typing import Optional
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.services.extraction_orchestrator import AgentState
from app.services.storage_service import StorageService
from app.services.prompt_template_builder import PromptTemplateBuilder
from app.database import SessionLocal
from app.models import Document, Question
from app.observability import traceable
from app.retry import retry_with_backoff
from llms import get_llm

logger = logging.getLogger(__name__)


class PersistenceAgent:
    """Agent responsible for image upload, question extraction, and database persistence."""
    
    def __init__(self, llm_model: Optional[str] = None):
        """
        Initialize the persistence agent.
        
        Args:
            llm_model: Name of the LLM model to use (defaults to settings)
        """
        from app.config import settings
        
        self.llm_model = llm_model or settings.validation_llm_model
        self.storage_service = StorageService()
    
    @traceable(name="PersistenceAgent.process", tags=["agent", "persistence"])
    def process(self, state: AgentState) -> AgentState:
        """
        Process persistence: upload images, extract questions, save to database.

        Workflow:
        1. Extract images from ZIP and upload to GCS
        2. Replace image paths in markdown with public URLs
        3. Use LLM to parse questions from markdown
        4. Create Document and Question records in database

        Args:
            state: Current agent state with cleaned_markdown and output_zip_path

        Returns:
            Updated agent state with document_id and question_ids
        """
        job_id = state.get("job_id", "unknown")
        user_id = state.get("user_id", "unknown")
        
        logger.info(f"Persistence agent processing job {job_id}")
        
        # Update state
        state["status"] = "persisting"
        
        # Initialize metadata if not present
        if "metadata" not in state:
            state["metadata"] = {}
        
        db = None
        try:
            # Get database session
            db = SessionLocal()
            
            # Step 1: Upload images and get URL mapping
            output_zip_path = state.get("output_zip_path")
            url_mapping = {}
            
            if output_zip_path and Path(output_zip_path).exists():
                logger.info(f"  - Uploading images from ZIP...")
                url_mapping = self.storage_service.upload_images_from_zip(
                    output_zip_path, user_id, job_id
                )
                logger.info(f"  - Uploaded {len(url_mapping) // 2} images")
            
            # Step 2: Get markdown and replace image paths
            markdown_content = state.get("cleaned_markdown") or self._extract_markdown_from_zip(output_zip_path)
            
            if not markdown_content:
                logger.warning("No markdown content available for persistence")
                state["status"] = "completed"
                return state
            
            # Replace image paths with public URLs
            public_markdown = self._replace_image_paths(markdown_content, url_mapping)
            state["public_markdown"] = public_markdown
            
            logger.info(f"  - Replaced {len(url_mapping) // 2} image references with public URLs")
            
            # Step 3: Extract questions using LLM
            logger.info(f"  - Extracting questions using LLM...")
            questions_data = self._extract_questions_with_llm(public_markdown)
            
            if not questions_data:
                logger.warning("No questions extracted from document")
                questions_data = []
            
            logger.info(f"  - Extracted {len(questions_data)} questions")
            
            # Step 4: Create Document record
            document = Document(
                user_id=user_id,
                filename=state.get("document_filename", "unknown"),
                source_url=state.get("document_url"),
                job_id=job_id,
                original_markdown=self._extract_markdown_from_zip(output_zip_path) if output_zip_path else None,
                cleaned_markdown=state.get("cleaned_markdown"),
                public_markdown=public_markdown,
                status="processed",
                question_count=len(questions_data),
                file_type=state.get("file_type"),
                extra_metadata={
                    "validation_score": state.get("metadata", {}).get("validation_score"),
                    "image_count": len(url_mapping) // 2 if url_mapping else 0,
                }
            )
            
            db.add(document)
            db.flush()  # Get the document ID
            
            state["document_id"] = str(document.id)
            logger.info(f"  - Created document record: {document.id}")
            
            # Step 5: Create Question records
            question_ids = []
            
            for q_data in questions_data:
                question = Question(
                    document_id=document.id,
                    user_id=user_id,
                    question_number=q_data.get("question_number"),
                    question_text=q_data.get("question_text", ""),
                    question_type=q_data.get("question_type", "multiple_choice"),
                    options=q_data.get("options"),
                    image_urls=q_data.get("image_urls", []),
                    extra_metadata=q_data.get("metadata"),
                )
                
                db.add(question)
                db.flush()
                question_ids.append(str(question.id))
            
            # Commit all changes
            db.commit()
            
            state["question_ids"] = question_ids
            state["metadata"]["question_count"] = len(question_ids)
            state["status"] = "completed"
            
            logger.info(f"  - Created {len(question_ids)} question records")
            logger.info(f"Persistence agent completed for job {job_id}")
            
        except Exception as e:
            if db:
                db.rollback()
            error_msg = f"Error during persistence: {str(e)}"
            logger.error(error_msg, exc_info=True)
            state["error_message"] = error_msg
            state["status"] = "failed"
            
        finally:
            if db:
                db.close()
        
        return state
    
    def _extract_markdown_from_zip(self, zip_path: str) -> Optional[str]:
        """
        Extract markdown content from ZIP file.
        
        Args:
            zip_path: Path to the ZIP file
            
        Returns:
            Markdown content or None
        """
        if not zip_path or not Path(zip_path).exists():
            return None
        
        try:
            with zipfile.ZipFile(zip_path, 'r') as zf:
                for name in zf.namelist():
                    if name.endswith('.md'):
                        return zf.read(name).decode('utf-8')
        except Exception as e:
            logger.error(f"Error extracting markdown from ZIP: {str(e)}")
        
        return None
    
    def _replace_image_paths(self, markdown: str, url_mapping: dict) -> str:
        """
        Replace local image paths with public GCS URLs.
        
        Args:
            markdown: Original markdown content
            url_mapping: Mapping of local paths to public URLs
            
        Returns:
            Markdown with public image URLs
        """
        if not url_mapping:
            return markdown
        
        result = markdown
        
        # Sort by longest path first to avoid partial replacements
        sorted_mappings = sorted(url_mapping.items(), key=lambda x: -len(x[0]))
        
        for local_path, public_url in sorted_mappings:
            # Replace in markdown image syntax: ![alt](path)
            result = result.replace(f"]({local_path})", f"]({public_url})")
            
            # Also replace in HTML img tags if present
            result = result.replace(f'src="{local_path}"', f'src="{public_url}"')
            result = result.replace(f"src='{local_path}'", f"src='{public_url}'")
        
        return result
    
    def _extract_questions_with_llm(self, markdown: str) -> list[dict]:
        """
        Use LLM to extract questions from markdown.
        
        Args:
            markdown: Markdown content with public image URLs
            
        Returns:
            List of question dictionaries
        """
        try:
            # Get LLM instance
            llm = get_llm(self.llm_model)
            
            # Truncate if too long
            max_chars = 25000
            truncated_markdown = markdown[:max_chars]
            if len(markdown) > max_chars:
                truncated_markdown += f"\n\n... [truncated, {len(markdown)} total characters]"
            
            # Build prompt from file
            # Note: No need to escape curly braces - PromptTemplateBuilder uses
            # explicit variable replacement, not Python's .format()
            prompt = PromptTemplateBuilder.build_from_file(
                name="question_extraction",
                variables={"markdown_content": truncated_markdown}
            )
            
            # Call LLM with retry
            @retry_with_backoff(max_retries=2, base_delay=2.0)
            def _invoke_llm():
                return llm.invoke(prompt)

            response = _invoke_llm()
            response_text = response.content if hasattr(response, 'content') else str(response)

            # Parse JSON response
            questions = self._parse_questions_json(response_text)

            return questions

        except Exception as e:
            logger.error(f"LLM question extraction error: {str(e)}", exc_info=True)
            return []
    
    def _fix_json_escapes(self, raw: str) -> str:
        """
        Fix invalid JSON escape sequences in LLM output.
        JSON only allows \\, \", \\/, \\b, \\f, \\n, \\r, \\t, \\uXXXX.
        Other backslashes (e.g. \\N, \\frac, \\ in paths) cause JSONDecodeError.
        """
        result = []
        i = 0
        while i < len(raw):
            if raw[i] != "\\":
                result.append(raw[i])
                i += 1
                continue
            if i + 1 >= len(raw):
                result.append("\\")
                i += 1
                continue
            next_c = raw[i + 1]
            if next_c in '"\\/bfnrt':
                result.append(raw[i])
                result.append(next_c)
                i += 2
                continue
            if next_c == "u" and i + 5 < len(raw):
                hex_part = raw[i + 2 : i + 6]
                if all(c in "0123456789abcdefABCDEF" for c in hex_part):
                    result.append(raw[i : i + 6])
                    i += 6
                    continue
            # Invalid escape: escape the backslash so next char is literal
            result.append("\\\\")
            i += 1
        return "".join(result)

    def _parse_questions_json(self, response_text: str) -> list[dict]:
        """
        Parse JSON array of questions from LLM response.
        
        Args:
            response_text: Raw LLM response
            
        Returns:
            List of question dictionaries
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
                json_str = self._fix_json_escapes(json_str)
                questions = json.loads(json_str)
                
                if isinstance(questions, list):
                    return questions
            
            logger.warning(f"Could not parse questions JSON: {text[:200]}...")
            return []
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error parsing questions: {str(e)}", exc_info=True)
            return []
        except Exception as e:
            logger.error(f"Error parsing questions: {str(e)}", exc_info=True)
            return []
