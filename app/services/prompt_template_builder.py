"""Template builder for dynamically constructing prompts from config."""

import logging
from typing import Dict, Any, Optional, List
import re
from sqlalchemy.orm import Session
from app.models import PromptTemplate

logger = logging.getLogger(__name__)


class PromptTemplateBuilder:
    """Dynamically builds prompts from config structure with variable substitution."""
    
    # Default section formatters - maps config keys to formatting functions
    DEFAULT_FORMATTERS = {
        "role": lambda value, **kwargs: f"Role: {value}",
        "instruction": lambda value, **kwargs: f"Instruction: {value}",
        "goal": lambda value, **kwargs: f"Goal: {value}",
        "context": lambda value, **kwargs: f"Context: {value}",
        "background": lambda value, **kwargs: f"Background: {value}",
    }
    
    # List sections that should be formatted as bullet points
    LIST_SECTIONS = {
        "output_constraints",
        "style_or_tone",
        "constraints",
        "requirements",
        "guidelines",
        "examples",
        "key_points",
    }
    
    # Sections to exclude from prompt building
    EXCLUDED_SECTIONS = {
        "variable_schema",
        "metadata",
        "template_config",
    }
    
    def __init__(self, config: Dict[str, Any], variables: Optional[Dict[str, Any]] = None):
        """
        Initialize template builder.
        
        Args:
            config: Prompt configuration dictionary
            variables: Optional variables for substitution
        """
        self.config = config
        self.variables = variables or {}
        self.parts: List[str] = []
    
    @classmethod
    def from_database(
        cls,
        db: Session,
        name: str,
        variables: Optional[Dict[str, Any]] = None,
        version: Optional[str] = None
    ) -> 'PromptTemplateBuilder':
        """
        Create a builder by reading prompt template from database by name and version.
        
        Args:
            db: Database session
            name: Template name to look up
            variables: Variables for substitution
            version: Optional specific version (defaults to active version if not specified)
            
        Returns:
            PromptTemplateBuilder: Initialized builder with config from database
            
        Raises:
            ValueError: If template not found or not active
        """
        # Build query
        query = db.query(PromptTemplate).filter(
            PromptTemplate.name == name,
            PromptTemplate.is_active == True
        )
        
        if version:
            query = query.filter(PromptTemplate.version == version)
        
        # Get template
        template = query.first()
        
        if not template:
            raise ValueError(
                f"Prompt template '{name}'" + 
                (f" version '{version}'" if version else "") + 
                " not found or not active"
            )
        
        # Create builder with template config
        return cls(template.config, variables or {})
    
    @classmethod
    def build_from_database(
        cls,
        db: Session,
        name: str,
        variables: Optional[Dict[str, Any]] = None,
        version: Optional[str] = None
    ) -> str:
        """
        Read prompt from database by name and version, replace dynamic values, and return complete prompt.
        
        This is a convenience method that combines reading from database and building.
        
        Args:
            db: Database session
            name: Template name to look up
            variables: Dictionary of variables to replace {variable} placeholders
            version: Optional specific version (defaults to active version if not specified)
            
        Returns:
            str: Fully built prompt with all dynamic values replaced
            
        Raises:
            ValueError: If template not found, not active, or variables are missing
            
        Example:
            ```python
            from app.database import get_db
            
            db = next(get_db())
            prompt = PromptTemplateBuilder.build_from_database(
                db=db,
                name="summarization_prompt_cfg5",
                version="v1",
                variables={
                    "document": "Article content...",
                    "word_count": "100"
                }
            )
            # Returns complete prompt with all variables replaced
            ```
        """
        # Read from database and create builder
        builder = cls.from_database(
            db=db,
            name=name,
            variables=variables,
            version=version
        )
        
        # Validate variables if schema exists
        schema = builder.get_variable_schema()
        if schema:
            is_valid, missing = builder.validate_variables(variables or {})
            if not is_valid:
                raise ValueError(
                    f"Missing required variables: {', '.join(missing)}. "
                    f"Required variables: {', '.join(schema.keys())}"
                )
        
        # Build and return the complete prompt
        return builder.build()
    
    def build(self) -> str:
        """
        Build the complete prompt from config.
        
        Returns:
            str: Complete formatted prompt
        """
        self.parts = []
        
        # Process each section in config
        for key, value in self.config.items():
            if key in self.EXCLUDED_SECTIONS:
                continue
            
            if value is None:
                continue
            
            # Handle list sections
            if key in self.LIST_SECTIONS:
                self._add_list_section(key, value)
            # Handle string sections
            elif isinstance(value, str):
                self._add_string_section(key, value)
            # Handle dict sections (nested config)
            elif isinstance(value, dict):
                self._add_dict_section(key, value)
            # Handle other types (convert to string)
            else:
                self._add_generic_section(key, value)
        
        # Join all parts
        prompt = "\n\n".join(self.parts)
        
        # Apply variable substitution
        prompt = self._substitute_variables(prompt)
        
        return prompt
    
    def _add_string_section(self, key: str, value: str) -> None:
        """Add a string section to the prompt."""
        # Use custom formatter if available
        if key in self.DEFAULT_FORMATTERS:
            formatted = self.DEFAULT_FORMATTERS[key](value, **self.variables)
        else:
            # Default: use key as label
            formatted = f"{key.replace('_', ' ').title()}: {value}"
        
        # Apply variable substitution to the value before adding
        try:
            formatted = formatted.format(**self.variables)
        except KeyError:
            # If variable not found, keep original (will be handled in final substitution)
            pass
        
        self.parts.append(formatted)
    
    def _add_list_section(self, key: str, value: List[str]) -> None:
        """Add a list section to the prompt (formatted as bullets)."""
        if not value:
            return
        
        # Format section header
        header = key.replace('_', ' ').title()
        self.parts.append(f"{header}:")
        
        # Add each item as a bullet point
        for item in value:
            # Apply variable substitution to each item
            try:
                item = item.format(**self.variables)
            except KeyError:
                pass
            self.parts.append(f"  - {item}")
    
    def _add_dict_section(self, key: str, value: Dict[str, Any]) -> None:
        """Add a nested dictionary section."""
        header = key.replace('_', ' ').title()
        self.parts.append(f"{header}:")
        
        for sub_key, sub_value in value.items():
            if isinstance(sub_value, list):
                self.parts.append(f"  {sub_key.replace('_', ' ').title()}:")
                for item in sub_value:
                    try:
                        item = item.format(**self.variables)
                    except KeyError:
                        pass
                    self.parts.append(f"    - {item}")
            elif isinstance(sub_value, str):
                try:
                    sub_value = sub_value.format(**self.variables)
                except KeyError:
                    pass
                self.parts.append(f"  {sub_key.replace('_', ' ').title()}: {sub_value}")
            else:
                self.parts.append(f"  {sub_key.replace('_', ' ').title()}: {sub_value}")
    
    def _add_generic_section(self, key: str, value: Any) -> None:
        """Add a generic section (non-string, non-list, non-dict)."""
        header = key.replace('_', ' ').title()
        self.parts.append(f"{header}: {value}")
    
    def _substitute_variables(self, text: str) -> str:
        """
        Substitute variables in the text using Python string formatting.
        
        Args:
            text: Text with {variable} placeholders
            
        Returns:
            str: Text with variables substituted
            
        Raises:
            ValueError: If required variables are missing
        """
        if not self.variables:
            # Check if there are any variables in the text
            if re.search(r'\{(\w+)\}', text):
                # Extract missing variables
                missing = set(re.findall(r'\{(\w+)\}', text))
                raise ValueError(
                    f"Missing required variables: {', '.join(sorted(missing))}. "
                    f"Required variables: {', '.join(sorted(missing))}"
                )
            return text
        
        try:
            return text.format(**self.variables)
        except KeyError as e:
            # Find all variables in the text
            all_vars = set(re.findall(r'\{(\w+)\}', text))
            provided = set(self.variables.keys())
            missing = all_vars - provided
            
            if missing:
                raise ValueError(
                    f"Missing required variables: {', '.join(sorted(missing))}. "
                    f"Required: {', '.join(sorted(all_vars))}, "
                    f"Provided: {', '.join(sorted(provided))}"
                )
            raise ValueError(f"Error formatting variables: {e}")
    
    def get_required_variables(self) -> List[str]:
        """
        Extract all required variables from the config.
        
        Returns:
            List[str]: Sorted list of variable names
        """
        variables = set()
        config_text = str(self.config)
        
        # Find all {variable} patterns
        pattern = r'\{(\w+)\}'
        matches = re.findall(pattern, config_text)
        variables.update(matches)
        
        return sorted(list(variables))
    
    def get_variable_schema(self) -> Dict[str, Dict[str, Any]]:
        """
        Get variable schema from config if defined, otherwise auto-generate.
        
        Returns:
            Dict: Variable schema with metadata
        """
        if "variable_schema" in self.config:
            return self.config["variable_schema"]
        
        # Auto-generate schema from detected variables
        variables = self.get_required_variables()
        return {
            var: {
                "required": True,
                "description": f"Variable {var}",
                "type": "string"
            }
            for var in variables
        }
    
    def validate_variables(self, variables: Optional[Dict[str, Any]] = None) -> tuple[bool, List[str]]:
        """
        Validate that all required variables are provided.
        
        Args:
            variables: Variables to validate (uses self.variables if None)
            
        Returns:
            tuple: (is_valid, list_of_missing_variables)
        """
        vars_to_check = variables if variables is not None else self.variables
        schema = self.get_variable_schema()
        missing = []
        
        for var_name, var_config in schema.items():
            if var_config.get("required", True):
                if var_name not in vars_to_check or vars_to_check[var_name] is None:
                    missing.append(var_name)
        
        return len(missing) == 0, missing

