"""Template builder for dynamically constructing prompts from YAML config files."""

import logging
import os
from pathlib import Path
from typing import Dict, Any, Optional, List
import re
import yaml

logger = logging.getLogger(__name__)

# Default prompts directory (relative to project root)
PROMPTS_DIR = Path(__file__).parent.parent.parent / "prompts"


class PromptTemplateBuilder:
    """Dynamically builds prompts from config structure with variable substitution."""
    
    # Default section formatters - maps config keys to formatting functions
    DEFAULT_FORMATTERS = {
        "role": lambda value: f"Role: {value}",
        "instruction": lambda value: f"Instruction: {value}",
        "goal": lambda value: f"Goal: {value}",
        "context": lambda value: f"Context: {value}",
        "background": lambda value: f"Background: {value}",
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
    def from_file(
        cls,
        name: str,
        variables: Optional[Dict[str, Any]] = None,
        prompts_dir: Optional[Path] = None
    ) -> 'PromptTemplateBuilder':
        """
        Create a builder by loading prompt config from a YAML file.
        
        Args:
            name: Prompt name (filename without .yaml extension)
            variables: Variables for substitution
            prompts_dir: Optional custom prompts directory
            
        Returns:
            PromptTemplateBuilder: Initialized builder with config from file
            
        Raises:
            FileNotFoundError: If prompt file not found
            yaml.YAMLError: If YAML parsing fails
        """
        dir_path = prompts_dir or PROMPTS_DIR
        file_path = dir_path / f"{name}.yaml"
        
        if not file_path.exists():
            raise FileNotFoundError(f"Prompt file not found: {file_path}")
        
        with open(file_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        if not config:
            raise ValueError(f"Empty or invalid YAML config in: {file_path}")
        
        logger.debug(f"Loaded prompt config from: {file_path}")
        return cls(config, variables or {})
    
    @classmethod
    def build_from_file(
        cls,
        name: str,
        variables: Optional[Dict[str, Any]] = None,
        prompts_dir: Optional[Path] = None
    ) -> str:
        """
        Load prompt from YAML file, replace dynamic values, and return complete prompt.
        
        This is a convenience method that combines loading from file and building.
        
        Args:
            name: Prompt name (filename without .yaml extension)
            variables: Dictionary of variables to replace {variable} placeholders
            prompts_dir: Optional custom prompts directory
            
        Returns:
            str: Fully built prompt with all dynamic values replaced
            
        Raises:
            FileNotFoundError: If prompt file not found
            ValueError: If variables are missing
            
        Example:
            ```python
            prompt = PromptTemplateBuilder.build_from_file(
                name="classification",
                variables={
                    "questions_json": "[{...}]"
                }
            )
            # Returns complete prompt with all variables replaced
            ```
        """
        # Load from file and create builder
        builder = cls.from_file(
            name=name,
            variables=variables,
            prompts_dir=prompts_dir
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
            formatted = self.DEFAULT_FORMATTERS[key](value)
        else:
            # Default: use key as label
            formatted = f"{key.replace('_', ' ').title()}: {value}"
        
        # Variable substitution is handled in the final _substitute_variables call
        self.parts.append(formatted)
    
    def _add_list_section(self, key: str, value: List[str]) -> None:
        """Add a list section to the prompt (formatted as bullets)."""
        if not value:
            return
        
        # Format section header
        header = key.replace('_', ' ').title()
        self.parts.append(f"{header}:")
        
        # Add each item as a bullet point
        # Variable substitution is handled in the final _substitute_variables call
        for item in value:
            self.parts.append(f"  - {item}")
    
    def _add_dict_section(self, key: str, value: Dict[str, Any]) -> None:
        """Add a nested dictionary section."""
        header = key.replace('_', ' ').title()
        self.parts.append(f"{header}:")
        
        # Variable substitution is handled in the final _substitute_variables call
        for sub_key, sub_value in value.items():
            if isinstance(sub_value, list):
                self.parts.append(f"  {sub_key.replace('_', ' ').title()}:")
                for item in sub_value:
                    self.parts.append(f"    - {item}")
            elif isinstance(sub_value, str):
                self.parts.append(f"  {sub_key.replace('_', ' ').title()}: {sub_value}")
            else:
                self.parts.append(f"  {sub_key.replace('_', ' ').title()}: {sub_value}")
    
    def _add_generic_section(self, key: str, value: Any) -> None:
        """Add a generic section (non-string, non-list, non-dict)."""
        header = key.replace('_', ' ').title()
        self.parts.append(f"{header}: {value}")
    
    def _substitute_variables(self, text: str) -> str:
        """
        Substitute variables in the text using explicit replacement.
        
        Only replaces known variable placeholders like {variable_name}, leaving
        all other curly braces (like JSON, LaTeX, etc.) untouched.
        
        Args:
            text: Text with {variable} placeholders
            
        Returns:
            str: Text with variables substituted
            
        Raises:
            ValueError: If required variables are missing
        """
        # Get the expected variables from the schema
        schema = self.get_variable_schema()
        expected_vars = set(schema.keys())
        
        if not self.variables:
            if expected_vars:
                raise ValueError(
                    f"Missing required variables: {', '.join(sorted(expected_vars))}. "
                    f"Required variables: {', '.join(sorted(expected_vars))}"
                )
            return text
        
        # Check for missing required variables
        provided = set(self.variables.keys())
        missing = expected_vars - provided
        
        if missing:
            # Only raise if required variables are missing
            required_missing = [
                var for var in missing 
                if schema.get(var, {}).get("required", True)
            ]
            if required_missing:
                raise ValueError(
                    f"Missing required variables: {', '.join(sorted(required_missing))}. "
                    f"Required: {', '.join(sorted(expected_vars))}, "
                    f"Provided: {', '.join(sorted(provided))}"
                )
        
        # Replace only the known variables using explicit string replacement
        # This avoids issues with curly braces in content (JSON, LaTeX, etc.)
        result = text
        for var_name, var_value in self.variables.items():
            placeholder = "{" + var_name + "}"
            result = result.replace(placeholder, str(var_value))
        
        return result
    
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
