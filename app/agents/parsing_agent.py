"""Parsing Agent - cleans up markdown using LLM for better UI display."""

import json
import logging
import os
import re
import zipfile
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from app.services.extraction_orchestrator import AgentState
from app.services.prompt_template_builder import PromptTemplateBuilder
from llms import get_llm

logger = logging.getLogger(__name__)

# Prompt template name for database lookup
PARSING_PROMPT_NAME = "document_parsing"

# Default parsing prompt config (used when not found in database)
DEFAULT_PARSING_PROMPT_CONFIG = {
    "role": """You are a highly intelligent document processing agent specializing in educational materials. Your task is to analyze the provided markdown content and convert it into clean, well-structured Markdown. The document may contain multiple-choice questions and other complex material.""",
    
    "instruction": """Strictly adhere to the following instructions:

1. **Extract Core Content:** Accurately transcribe the main educational content. Focus on questions, options, paragraphs, and explanations.

2. **Ignore Extraneous Noise:** You MUST OMIT any extraneous elements that are not part of the core content. This includes, but is not limited to: page numbers, headers (e.g., "Chapter 5 Review", "Section 2.1"), footers, timestamps, and marginalia. The final output should be a clean representation of the educational material itself.

3. **Structure and Formatting:** Preserve the original document's structure using Markdown elements like headings (#, ##), lists, bold (**text**), italics (*text*), and blockquotes (>).

4. **CRITICAL - Image Formatting:** Images MUST be properly spaced:
   - ALWAYS put a blank line BEFORE each image
   - ALWAYS put a blank line AFTER each image
   - Images should NEVER be inline with text
   - Format: `![Image](image_path)`
   - Example of CORRECT formatting:
     ```
     The diagram below shows a person flying a kite.
     
     ![Image](artifacts/image_001.png)
     
     Which equation can be used to determine the value of x?
     ```
   - Example of WRONG formatting (DO NOT do this):
     ```
     The diagram below shows a person flying a kite. ![Image](artifacts/image_001.png) Which equation...
     ```

5. **CRITICAL - Multiple Choice Questions:** Each question MUST be properly formatted:
   - Put the question text on its own line(s)
   - Put a blank line between the question and the options
   - Put EACH option on its OWN LINE (A, B, C, D must be separate lines)
   - Use inline math ($...$) for equations in options, NOT block math ($$...$$)
   - Put a blank line between questions
   - Example of CORRECT formatting:
     ```
     ## Question 5
     
     What is the equation of the line?
     
     A) $y = -2x + 6$
     B) $y = -\\frac{1}{2}x + 3$
     C) $y = -\\frac{1}{2}x + 6$
     D) $y = 2x + 3$
     
     ## Question 6
     ```
   - Example of WRONG formatting (DO NOT do this):
     ```
     What is the equation? A) $y = -2x + 6$ B) $y = -\\frac{1}{2}x + 3$ C) ...
     ```

6. **Mathematical & Scientific Notation:** 
   - Use inline math ($...$) for equations within text or answer options
   - Use block math ($$...$$) ONLY for standalone equations that need their own line
   - Remove excessive spacing in LaTeX (e.g., $y = -\\frac{1}{2}x$ not $y = - \\frac { 1 } { 2 } x$)

7. **Chemical Equations:** Transcribe chemical equations accurately using subscripts/superscripts (e.g., H₂O).

8. **Tables:** Recreate any tables using Markdown table syntax.

9. **Cleanliness:** Do not include any conversational text, apologies, or explanations. Output ONLY the cleaned markdown content.""",
    
    "context": """## Original Markdown Content
```markdown
{markdown_content}
```

## Images Referenced
{image_list}""",
    
    "output_constraints": [
        "Output ONLY the cleaned markdown content",
        "EVERY image must have a blank line before AND after it",
        "EVERY MCQ option (A, B, C, D) must be on its own separate line",
        "Preserve all image references exactly as provided",
        "Use proper line breaks between questions",
    ],
    
    "variable_schema": {
        "markdown_content": {"required": True, "description": "Original markdown content to clean", "type": "string"},
        "image_list": {"required": True, "description": "List of images referenced in the document", "type": "string"},
    }
}


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
        image_files: list[str],
        db: Optional[Session] = None
    ) -> Optional[str]:
        """
        Call LLM to clean up markdown content.
        
        Args:
            markdown_content: The original markdown content
            image_files: List of image files in the ZIP
            db: Optional database session for loading prompt from database
            
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
            
            # Escape curly braces in markdown content to prevent format string errors
            # LaTeX formulas like {matrix} would otherwise be interpreted as variables
            escaped_markdown = truncated_markdown.replace("{", "{{").replace("}", "}}")
            
            # Format image list
            image_list = "\n".join([f"- {img}" for img in image_files]) if image_files else "No images found"
            
            # Prepare variables for prompt
            variables = {
                "markdown_content": escaped_markdown,
                "image_list": image_list
            }
            
            # Build prompt using PromptTemplateBuilder
            prompt = self._build_parsing_prompt(variables, db)
            
            # Call LLM
            response = llm.invoke(prompt)
            response_text = response.content if hasattr(response, 'content') else str(response)
            
            # Clean up the response - remove any markdown code block wrappers
            cleaned = self._extract_markdown_from_response(response_text)
            
            return cleaned if cleaned else None
                
        except Exception as e:
            logger.error(f"LLM parsing error: {str(e)}", exc_info=True)
            return None
    
    def _build_parsing_prompt(
        self,
        variables: dict,
        db: Optional[Session] = None
    ) -> str:
        """
        Build the parsing prompt using PromptTemplateBuilder.
        
        Tries to load from database first, falls back to default config.
        
        Args:
            variables: Variables to substitute in the prompt
            db: Optional database session
            
        Returns:
            Built prompt string
        """
        try:
            # Try to load from database if session provided
            if db:
                try:
                    prompt = PromptTemplateBuilder.build_from_database(
                        db=db,
                        name=PARSING_PROMPT_NAME,
                        variables=variables
                    )
                    logger.debug(f"Loaded parsing prompt from database: {PARSING_PROMPT_NAME}")
                    return prompt
                except ValueError as e:
                    logger.debug(f"Prompt not found in database, using default: {e}")
            
            # Fall back to default config
            builder = PromptTemplateBuilder(
                config=DEFAULT_PARSING_PROMPT_CONFIG,
                variables=variables
            )
            return builder.build()
            
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
