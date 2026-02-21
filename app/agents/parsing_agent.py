"""Parsing Agent - cleans up markdown using LLM for better UI display."""

import json
import logging
import os
import re
import zipfile
from pathlib import Path
from typing import Optional

from app.services.extraction_orchestrator import AgentState
from app.services.prompt_template_builder import PromptTemplateBuilder
from app.observability import traceable
from app.retry import retry_with_backoff
from llms import get_llm

logger = logging.getLogger(__name__)


class ParsingAgent:
    """Agent responsible for cleaning up markdown using LLM for better UI display."""
    
    def __init__(self, llm_model: Optional[str] = None):
        """
        Initialize the parsing agent.
        
        Args:
            llm_model: Name of the LLM model to use (defaults to settings)
        """
        from app.config import settings
        
        self.llm_model = llm_model or settings.validation_llm_model  # Reuse validation model setting
    
    @traceable(name="ParsingAgent.process", tags=["agent", "parsing"])
    def process(self, state: AgentState) -> AgentState:
        """
        Process markdown cleanup using LLM.

        Workflow:
        1. Load markdown content from ZIP
        2. Send to LLM for cleanup
        3. Save cleaned markdown back to ZIP or state
        4. Update state with cleaned content

        Args:
            state: Current agent state with output_zip_path

        Returns:
            Updated agent state with cleaned_markdown
        """
        job_id = state.get("job_id", "unknown")
        
        logger.info(f"Parsing agent processing job {job_id}")
        
        # Update state
        state["status"] = "parsing"
        
        # Initialize metadata if not present
        if "metadata" not in state:
            state["metadata"] = {}
        
        try:
            # Step 1: Load markdown content from ZIP
            output_zip_path = state.get("output_zip_path")
            if not output_zip_path or not Path(output_zip_path).exists():
                error_msg = f"Output ZIP not found: {output_zip_path}"
                logger.error(error_msg)
                state["metadata"]["parsing_error"] = error_msg
                return state
            
            markdown_content, image_files = self._extract_markdown_from_zip(output_zip_path)
            
            if not markdown_content:
                error_msg = "No markdown content found in ZIP"
                logger.error(error_msg)
                state["metadata"]["parsing_error"] = error_msg
                return state
            
            logger.info(f"  - Loaded markdown: {len(markdown_content)} chars, {len(image_files)} images")
            
            # Step 2: Clean up markdown using LLM
            logger.info(f"  - Calling LLM for markdown cleanup...")
            cleaned_markdown = self._cleanup_with_llm(
                markdown_content=markdown_content,
                image_files=image_files
            )
            
            if cleaned_markdown:
                # Step 3: Save cleaned markdown
                state["cleaned_markdown"] = cleaned_markdown
                state["metadata"]["original_markdown_length"] = len(markdown_content)
                state["metadata"]["cleaned_markdown_length"] = len(cleaned_markdown)
                
                # Also save to ZIP directory
                self._save_cleaned_markdown(output_zip_path, cleaned_markdown)
                
                logger.info(f"  - Cleanup complete: {len(markdown_content)} -> {len(cleaned_markdown)} chars")
            else:
                # LLM cleanup failed - use original markdown
                logger.warning("LLM cleanup failed, using original markdown")
                state["cleaned_markdown"] = markdown_content
                state["metadata"]["parsing_fallback"] = True
                
        except Exception as e:
            error_msg = f"Error during parsing: {str(e)}"
            logger.error(error_msg, exc_info=True)
            state["metadata"]["parsing_error"] = error_msg
            # Don't fail - just continue with original content
        
        logger.info(f"Parsing agent completed for job {job_id}")
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
    
    def _cleanup_with_llm(
        self,
        markdown_content: str,
        image_files: list[str]
    ) -> Optional[str]:
        """
        Call LLM to clean up markdown content.
        
        Args:
            markdown_content: The original markdown content
            image_files: List of image files in the ZIP
            
        Returns:
            Cleaned markdown content or None if LLM call fails
        """
        try:
            # Get LLM instance
            llm = get_llm(self.llm_model)
            
            # Truncate markdown if too long (keep first 30000 chars for context)
            # Parsing needs more context than validation
            max_chars = 30000
            truncated_markdown = markdown_content[:max_chars]
            if len(markdown_content) > max_chars:
                truncated_markdown += f"\n\n... [truncated, total {len(markdown_content)} characters]"
            
            # Format image list
            image_list = "\n".join([f"- {img}" for img in image_files]) if image_files else "No images found"
            
            # Prepare variables for prompt
            # Note: No need to escape curly braces - PromptTemplateBuilder uses
            # explicit variable replacement, not Python's .format()
            variables = {
                "markdown_content": truncated_markdown,
                "image_list": image_list
            }
            
            # Build prompt using PromptTemplateBuilder
            prompt = self._build_parsing_prompt(variables)

            # Call LLM with retry
            @retry_with_backoff(max_retries=2, base_delay=2.0)
            def _invoke_llm():
                return llm.invoke(prompt)

            response = _invoke_llm()
            response_text = response.content if hasattr(response, 'content') else str(response)
            
            # Clean up the response - remove any markdown code block wrappers
            cleaned = self._extract_markdown_from_response(response_text)
            
            return cleaned if cleaned else None
                
        except Exception as e:
            logger.error(f"LLM parsing error: {str(e)}", exc_info=True)
            return None
    
    def _build_parsing_prompt(self, variables: dict) -> str:
        """
        Build the parsing prompt using PromptTemplateBuilder.
        
        Loads prompt from YAML file.
        
        Args:
            variables: Variables to substitute in the prompt
            
        Returns:
            Built prompt string
        """
        try:
            # Load prompt from file
            return PromptTemplateBuilder.build_from_file(
                name="parsing",
                variables=variables
            )
            
        except Exception as e:
            logger.error(f"Error building parsing prompt: {e}")
            # Ultimate fallback - simple formatted string
            markdown_content = variables.get('markdown_content', '')[:10000]
            image_list = variables.get('image_list', 'None')
            
            return f"""You are a document processing agent. Clean up this markdown content for display:

{markdown_content}

Images: {image_list}

Instructions:
- Remove page numbers, headers, footers
- Format multiple choice questions clearly
- Preserve mathematical notation
- Keep image references
- Output ONLY the cleaned markdown, no explanations
"""
    
    def _extract_markdown_from_response(self, response_text: str) -> str:
        """
        Extract clean markdown from LLM response.
        
        Handles cases where LLM wraps output in code blocks.
        
        Args:
            response_text: Raw response from LLM
            
        Returns:
            Cleaned markdown content
        """
        # Remove markdown code block wrappers if present
        text = response_text.strip()
        
        # Check for ```markdown or ``` wrapper
        if text.startswith("```markdown"):
            text = text[len("```markdown"):].strip()
        elif text.startswith("```md"):
            text = text[len("```md"):].strip()
        elif text.startswith("```"):
            text = text[3:].strip()
        
        # Remove trailing ``` if present
        if text.endswith("```"):
            text = text[:-3].strip()
        
        return text
    
    def _save_cleaned_markdown(self, zip_path: str, cleaned_markdown: str) -> None:
        """
        Save cleaned markdown to the same directory as the ZIP.
        
        Args:
            zip_path: Path to the original ZIP file
            cleaned_markdown: Cleaned markdown content
        """
        try:
            output_dir = Path(zip_path).parent
            cleaned_path = output_dir / "cleaned.md"
            
            with open(cleaned_path, "w", encoding="utf-8") as f:
                f.write(cleaned_markdown)
            
            logger.info(f"  - Saved cleaned markdown to: {cleaned_path}")
        except Exception as e:
            logger.warning(f"Failed to save cleaned markdown: {str(e)}")
