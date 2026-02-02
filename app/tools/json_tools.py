"""JSON parsing tools for LLM response processing.

These tools help extract and parse JSON from LLM responses, handling
common formatting issues like markdown code blocks.
"""

import json
import logging
from typing import Any

from langchain_core.tools import tool

logger = logging.getLogger(__name__)


@tool
def parse_json_array(response_text: str) -> list[dict[str, Any]]:
    """Parse a JSON array from LLM response text.
    
    Handles common formatting issues from LLM outputs:
    - Removes ```json or ``` markdown code block wrappers
    - Finds and extracts the JSON array portion from surrounding text
    - Returns empty list on parse failure (does not raise exceptions)
    
    Args:
        response_text: Raw text from LLM response that may contain a JSON array
        
    Returns:
        Parsed list of dictionaries, or empty list if parsing fails
        
    Example:
        >>> result = parse_json_array.invoke('```json\\n[{"id": 1}]\\n```')
        >>> print(result)
        [{"id": 1}]
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
        
        # Find JSON array boundaries
        start = text.find('[')
        end = text.rfind(']') + 1
        
        if start >= 0 and end > start:
            json_str = text[start:end]
            parsed = json.loads(json_str)
            
            if isinstance(parsed, list):
                return parsed
            else:
                logger.warning(f"Parsed JSON is not an array: {type(parsed)}")
                return []
        
        logger.warning(f"Could not find JSON array in text: {text[:200]}...")
        return []
        
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error: {str(e)}")
        return []
    except Exception as e:
        logger.error(f"Error parsing JSON array: {str(e)}")
        return []


@tool
def parse_json_object(response_text: str) -> dict[str, Any]:
    """Parse a JSON object from LLM response text.
    
    Handles common formatting issues from LLM outputs:
    - Removes ```json or ``` markdown code block wrappers
    - Finds and extracts the JSON object portion from surrounding text
    - Returns empty dict on parse failure (does not raise exceptions)
    
    Args:
        response_text: Raw text from LLM response that may contain a JSON object
        
    Returns:
        Parsed dictionary, or empty dict if parsing fails
        
    Example:
        >>> result = parse_json_object.invoke('```json\\n{"name": "test"}\\n```')
        >>> print(result)
        {"name": "test"}
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
        
        # Find JSON object boundaries
        start = text.find('{')
        end = text.rfind('}') + 1
        
        if start >= 0 and end > start:
            json_str = text[start:end]
            parsed = json.loads(json_str)
            
            if isinstance(parsed, dict):
                return parsed
            else:
                logger.warning(f"Parsed JSON is not an object: {type(parsed)}")
                return {}
        
        logger.warning(f"Could not find JSON object in text: {text[:200]}...")
        return {}
        
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error: {str(e)}")
        return {}
    except Exception as e:
        logger.error(f"Error parsing JSON object: {str(e)}")
        return {}
