"""Markdown Validation Agent - validates markdown quality against source document using LLM."""

import json
import logging
import os
import re
import zipfile
from pathlib import Path
from typing import Optional

from app.services.extraction_orchestrator import AgentState
from app.services.docling_service import docling_service
from app.services.prompt_template_builder import PromptTemplateBuilder
from llms import get_llm

logger = logging.getLogger(__name__)


def repair_json(json_str: str) -> str:
    """
    Attempt to repair common JSON formatting issues from LLM responses.
    
    Args:
        json_str: Potentially malformed JSON string
        
    Returns:
        Repaired JSON string
    """
    # Remove any markdown code block markers
    json_str = re.sub(r'^```json?\s*', '', json_str, flags=re.MULTILINE)
    json_str = re.sub(r'```\s*$', '', json_str, flags=re.MULTILINE)
    
    # Remove trailing commas before closing brackets/braces
    json_str = re.sub(r',\s*([}\]])', r'\1', json_str)
    
    # Fix unescaped quotes inside strings (common LLM error)
    # This is tricky - we try to fix obvious cases
    # Pattern: look for strings with unescaped quotes that break JSON
    
    # Fix single quotes used instead of double quotes for keys/values
    # Only do this if it looks like the string uses single quotes consistently
    if "'" in json_str and '"' not in json_str.replace('\\"', ''):
        json_str = json_str.replace("'", '"')
    
    # Fix boolean values (True/False -> true/false)
    json_str = re.sub(r'\bTrue\b', 'true', json_str)
    json_str = re.sub(r'\bFalse\b', 'false', json_str)
    json_str = re.sub(r'\bNone\b', 'null', json_str)
    
    # Remove any control characters that might break parsing
    json_str = re.sub(r'[\x00-\x1f\x7f-\x9f]', ' ', json_str)
    
    # Fix missing commas between array elements (heuristic)
    # Pattern: "value" "key": -> "value", "key":
    json_str = re.sub(r'"\s+(?="[^"]+":)', '", ', json_str)
    
    return json_str.strip()


def parse_json_safely(response_text: str) -> Optional[dict]:
    """
    Safely parse JSON from LLM response with multiple fallback strategies.
    
    Args:
        response_text: Raw response text from LLM
        
    Returns:
        Parsed dictionary or None if all parsing attempts fail
    """
    # Strategy 1: Try to extract JSON block from the response
    json_start = response_text.find('{')
    json_end = response_text.rfind('}') + 1
    
    if json_start < 0 or json_end <= json_start:
        logger.warning("No JSON object found in response")
        return None
    
    json_str = response_text[json_start:json_end]
    
    # Strategy 2: Try direct parsing
    try:
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        logger.debug(f"Direct JSON parse failed: {e}")
    
    # Strategy 3: Try with repairs
    try:
        repaired = repair_json(json_str)
        return json.loads(repaired)
    except json.JSONDecodeError as e:
        logger.debug(f"Repaired JSON parse failed: {e}")
    
    # Strategy 4: Try to extract just the core fields we need
    try:
        result = {}
        
        # Extract score
        score_match = re.search(r'"score"\s*:\s*(\d+)', json_str)
        if score_match:
            result["score"] = int(score_match.group(1))
        
        # Extract passed
        passed_match = re.search(r'"passed"\s*:\s*(true|false)', json_str, re.IGNORECASE)
        if passed_match:
            result["passed"] = passed_match.group(1).lower() == "true"
        elif "score" in result:
            result["passed"] = result["score"] >= 70
        
        # Extract issues array (simplified)
        issues_match = re.search(r'"issues"\s*:\s*\[(.*?)\]', json_str, re.DOTALL)
        if issues_match:
            issues_content = issues_match.group(1)
            # Extract strings from the array
            issues = re.findall(r'"([^"]+)"', issues_content)
            result["issues"] = issues
        else:
            result["issues"] = []
        
        # Extract recommendation
        rec_match = re.search(r'"recommendation"\s*:\s*"([^"]*(?:\\.[^"]*)*)"', json_str)
        if rec_match:
            result["recommendation"] = rec_match.group(1).replace('\\"', '"')
        else:
            result["recommendation"] = ""
        
        if result.get("score") is not None or result.get("passed") is not None:
            logger.info("Extracted validation result using regex fallback")
            return result
            
    except Exception as e:
        logger.debug(f"Regex extraction failed: {e}")
    
    logger.warning(f"All JSON parsing strategies failed for: {json_str[:200]}...")
    return None

# Default retry configurations with different Docling parameters
DOCLING_RETRY_CONFIGS = [
    # Attempt 2: Force OCR with tesseract
    {
        "pdf_backend": "dlparse_v4",
        "force_ocr": True,
        "ocr_engine": "tesseract",
    },
    # Attempt 3: Different PDF backend + EasyOCR (more robust for complex docs)
    {
        "pdf_backend": "dlparse_v2",
        "force_ocr": True,
        "ocr_engine": "easyocr",
        "do_formula_enrichment": True,
    },
]

class MarkdownValidationAgent:
    """Agent responsible for validating markdown quality against source document using LLM."""
    
    def __init__(self, llm_model: Optional[str] = None, max_attempts: Optional[int] = None):
        """
        Initialize the validation agent.
        
        Args:
            llm_model: Name of the LLM model to use for validation (defaults to settings)
            max_attempts: Maximum number of conversion attempts before giving up (defaults to settings)
        """
        from app.config import settings
        
        self.llm_model = llm_model or settings.validation_llm_model
        self.max_attempts = max_attempts or settings.max_validation_attempts
        self.passing_score = 70
    
    def process(self, state: AgentState) -> AgentState:
        """
        Process markdown validation by comparing generated markdown against source document.
        
        Workflow:
        1. Load markdown content from ZIP
        2. Load source file information
        3. Call LLM to assess quality
        4. If failed and attempts < max, prepare next Docling config for retry
        5. Update state with validation results
        
        Args:
            state: Current agent state with output_zip_path and source_file_path
            
        Returns:
            Updated agent state with validation_passed, validation_feedback, etc.
        """
        job_id = state.get("job_id", "unknown")
        validation_attempts = state.get("validation_attempts", 0) + 1
        
        logger.info(f"Markdown validation agent processing job {job_id} (attempt {validation_attempts}/{self.max_attempts})")
        
        # Update state
        state["status"] = "validating"
        state["validation_attempts"] = validation_attempts
        
        # Initialize metadata if not present
        if "metadata" not in state:
            state["metadata"] = {}
        
        try:
            # Step 1: Load markdown content from ZIP
            output_zip_path = state.get("output_zip_path")
            if not output_zip_path or not Path(output_zip_path).exists():
                error_msg = f"Output ZIP not found: {output_zip_path}"
                logger.error(error_msg)
                state["validation_passed"] = False
                state["validation_feedback"] = error_msg
                return state
            
            markdown_content, image_files = self._extract_markdown_from_zip(output_zip_path)
            
            if not markdown_content:
                error_msg = "No markdown content found in ZIP"
                logger.error(error_msg)
                state["validation_passed"] = False
                state["validation_feedback"] = error_msg
                return state
            
            logger.info(f"  - Loaded markdown: {len(markdown_content)} chars, {len(image_files)} images")
            
            # Step 2: Get source file information
            source_file_path = state.get("source_file_path")
            source_info = self._get_source_info(source_file_path)
            
            logger.info(f"  - Source file: {source_info.get('filename', 'unknown')}")
            
            # Step 3: Call LLM to validate quality
            logger.info(f"  - Calling LLM for quality assessment...")
            validation_result = self._validate_with_llm(
                markdown_content=markdown_content,
                image_files=image_files,
                source_info=source_info,
                file_type=state.get("file_type", "unknown")
            )
            
            # Step 4: Process validation result
            if validation_result:
                passed = validation_result.get("passed", False)
                score = validation_result.get("score", 0)
                issues = validation_result.get("issues", [])
                recommendation = validation_result.get("recommendation", "")
                
                state["validation_passed"] = passed
                state["validation_feedback"] = json.dumps(validation_result)
                state["metadata"]["validation_score"] = score
                state["metadata"]["validation_issues"] = issues
                
                logger.info(f"  - Validation result: {'PASSED' if passed else 'FAILED'} (score: {score}/100)")
                
                if not passed:
                    logger.warning(f"  - Issues found: {issues}")
                    logger.warning(f"  - Recommendation: {recommendation}")
                    
                    # Step 5: If failed and more attempts available, prepare retry config
                    if validation_attempts < self.max_attempts:
                        next_config = self._get_next_docling_config(validation_attempts, state)
                        if next_config:
                            state["docling_options"] = next_config
                            state["metadata"]["retry_config"] = next_config
                            logger.info(f"  - Preparing retry with config: {next_config}")
            else:
                # LLM call failed - don't block the pipeline
                logger.warning("LLM validation failed, passing by default")
                state["validation_passed"] = True
                state["validation_feedback"] = "LLM validation unavailable, passed by default"
            
            # Step 6: Handle cleanup if validation passed or max attempts reached
            if state.get("validation_passed", False) or validation_attempts >= self.max_attempts:
                self._cleanup_source_file(state)
                
                if not state.get("validation_passed", False):
                    logger.warning(f"Max validation attempts ({self.max_attempts}) reached, proceeding anyway")
                    state["validation_passed"] = True  # Allow pipeline to continue
                    state["metadata"]["max_attempts_reached"] = True
            
        except Exception as e:
            error_msg = f"Error during validation: {str(e)}"
            logger.error(error_msg, exc_info=True)
            state["validation_passed"] = True  # Don't block pipeline on validation errors
            state["validation_feedback"] = error_msg
            self._cleanup_source_file(state)
        
        logger.info(f"Markdown validation agent completed for job {job_id}")
        return state
    
    def _extract_markdown_from_zip(self, zip_path: str) -> tuple[str, list[str]]:
        """
        Extract markdown content and list of image files from ZIP.
        
        Args:
            zip_path: Path to the ZIP file
            
        Returns:
            Tuple of (markdown_content, list_of_image_files)
        """
        markdown_content = ""
        image_files = []
        
        try:
            with zipfile.ZipFile(zip_path, 'r') as zf:
                for name in zf.namelist():
                    if name.endswith('.md'):
                        markdown_content = zf.read(name).decode('utf-8')
                    elif name.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg')):
                        image_files.append(name)
        except Exception as e:
            logger.error(f"Error extracting from ZIP: {str(e)}")
        
        return markdown_content, image_files
    
    def _get_source_info(self, source_file_path: Optional[str]) -> dict:
        """
        Get information about the source file.
        
        Args:
            source_file_path: Path to the source file
            
        Returns:
            Dictionary with source file information
        """
        if not source_file_path or not Path(source_file_path).exists():
            return {
                "filename": "unknown",
                "file_size": 0,
                "exists": False
            }
        
        path = Path(source_file_path)
        return {
            "filename": path.name,
            "file_size": path.stat().st_size,
            "exists": True
        }
    
    def _validate_with_llm(
        self,
        markdown_content: str,
        image_files: list[str],
        source_info: dict,
        file_type: str
    ) -> Optional[dict]:
        """
        Call LLM to validate markdown quality.
        
        Uses PromptTemplateBuilder to construct the prompt from YAML file.
        
        Args:
            markdown_content: The generated markdown content
            image_files: List of image files in the ZIP
            source_info: Information about the source file
            file_type: Detected file type
            
        Returns:
            Validation result dictionary or None if LLM call fails
        """
        try:
            # Get LLM instance
            llm = get_llm(self.llm_model)
            
            # Truncate markdown if too long (keep first 15000 chars for context)
            truncated_markdown = markdown_content[:15000]
            if len(markdown_content) > 15000:
                truncated_markdown += f"\n\n... [truncated, total {len(markdown_content)} characters]"
            
            # Format image list
            image_list = "\n".join([f"- {img}" for img in image_files]) if image_files else "No images found"
            
            # Prepare variables for prompt
            # Note: No need to escape curly braces - PromptTemplateBuilder uses
            # explicit variable replacement, not Python's .format()
            variables = {
                "source_filename": source_info.get("filename", "unknown"),
                "file_type": file_type,
                "file_size": str(source_info.get("file_size", 0)),
                "markdown_content": truncated_markdown,
                "image_list": image_list
            }
            
            # Build prompt using PromptTemplateBuilder
            prompt = self._build_validation_prompt(variables)
            
            # Call LLM
            response = llm.invoke(prompt)
            response_text = response.content if hasattr(response, 'content') else str(response)
            
            # Parse JSON response using robust parser
            result = parse_json_safely(response_text)
            
            if result:
                # Ensure passed field is based on score if not explicitly set
                if "score" in result and "passed" not in result:
                    result["passed"] = result["score"] >= self.passing_score
                
                return result
            else:
                logger.warning(f"Could not parse validation result from LLM response: {response_text[:500]}")
                return None
                
        except Exception as e:
            logger.error(f"LLM validation error: {str(e)}", exc_info=True)
            return None
    
    def _build_validation_prompt(self, variables: dict) -> str:
        """
        Build the validation prompt using PromptTemplateBuilder.
        
        Loads prompt from YAML file.
        
        Args:
            variables: Variables to substitute in the prompt
            
        Returns:
            Built prompt string
        """
        try:
            # Load prompt from file
            return PromptTemplateBuilder.build_from_file(
                name="markdown_validation",
                variables=variables
            )
            
        except Exception as e:
            logger.error(f"Error building validation prompt: {e}")
            # Ultimate fallback - simple formatted string
            source_filename = variables.get('source_filename', 'unknown')
            file_type = variables.get('file_type', 'unknown')
            markdown_content = variables.get('markdown_content', '')[:5000]
            image_list = variables.get('image_list', 'None')
            
            return f"""You are a document quality validator. Evaluate this markdown conversion:

Source: {source_filename} ({file_type})

Markdown:
{markdown_content}

Images found: {image_list}

Respond with JSON only. Example format:
{{"passed": true, "score": 85, "issues": ["issue 1", "issue 2"], "recommendation": "your recommendation"}}

Score 70+ means passing quality.
"""
    
    def _get_next_docling_config(self, current_attempt: int, state: AgentState) -> Optional[dict]:
        """
        Get the next Docling configuration to try based on current attempt.
        
        Args:
            current_attempt: Current validation attempt number
            state: Current agent state
            
        Returns:
            Dictionary of Docling options or None if no more configs
        """
        # Use the predefined retry configurations
        # Note: Custom configs can be passed via docling_options if needed
        retry_configs = DOCLING_RETRY_CONFIGS
        
        # Attempt 1 uses default config, so retry_configs[0] is for attempt 2
        config_index = current_attempt - 1
        
        if config_index < len(retry_configs):
            return retry_configs[config_index]
        
        return None
    
    def _cleanup_source_file(self, state: AgentState) -> None:
        """
        Clean up the source file after validation is complete.
        
        Args:
            state: Current agent state
        """
        source_file_path = state.get("source_file_path")
        
        if source_file_path:
            try:
                docling_service.cleanup_temp_file(source_file_path)
                logger.info(f"Cleaned up source file: {source_file_path}")
                state["source_file_path"] = None  # Clear the path
            except Exception as e:
                logger.warning(f"Failed to cleanup source file: {str(e)}")
