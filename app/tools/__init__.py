"""LangChain tools for document processing agents.

This module provides reusable tools decorated with @tool from langchain_core.tools.
Tools are self-documenting and can be used across different agents.

Example usage:
    from app.tools import parse_json_array, classify_question
    
    # Tools have metadata
    print(parse_json_array.name)        # "parse_json_array"
    print(parse_json_array.description) # From docstring
    
    # Direct invocation
    result = parse_json_array.invoke('```json\\n[{"id": 1}]\\n```')
"""

from app.tools.json_tools import parse_json_array, parse_json_object
from app.tools.classification_tools import classify_question, classify_questions_batch

__all__ = [
    "parse_json_array",
    "parse_json_object",
    "classify_question",
    "classify_questions_batch",
]
