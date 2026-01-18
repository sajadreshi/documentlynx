"""Database models."""

from sqlalchemy import Column, String, Boolean, DateTime, Integer, Text, Float
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from app.database import Base


class ClientCredential(Base):
    """Model for client credentials."""

    __tablename__ = "client_credentials"

    client_id = Column(String(255), primary_key=True, index=True)
    client_secret = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def __repr__(self):
        return f"<ClientCredential(client_id='{self.client_id}', is_active={self.is_active})>"


class PromptTemplate(Base):
    """Model for prompt templates with flexible JSONB configuration."""

    __tablename__ = "prompt_templates"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, index=True)
    version = Column(String(50), default="v1", index=True)
    description = Column(Text)
    
    # Full prompt configuration stored as JSONB
    # Structure: {
    #   "instruction": "...",
    #   "output_constraints": ["...", "..."],
    #   "role": "...",
    #   "style_or_tone": ["...", "..."],
    #   "goal": "..."
    # }
    config = Column(JSONB, nullable=False)
    
    # A/B Testing configuration
    experiment_group = Column(String(50), index=True)  # "A", "B", "control"
    traffic_percentage = Column(Float, default=1.0)  # 0.0 to 1.0
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    created_by = Column(String(255))
    extra_metadata = Column(JSONB)  # Additional flexible data (renamed from metadata to avoid SQLAlchemy conflict)

    def __repr__(self):
        return f"<PromptTemplate(name='{self.name}', version='{self.version}', group='{self.experiment_group}')>"
    
    def get_full_prompt(self, **variables) -> str:
        """
        Render the full prompt from config sections using template builder.
        
        Args:
            **variables: Variables to format into the prompt template
            
        Returns:
            str: Fully rendered prompt
        """
        from app.services.prompt_template_builder import PromptTemplateBuilder
        
        # Use template builder for dynamic construction
        builder = PromptTemplateBuilder(self.config, variables)
        
        # Validate variables if schema exists
        schema = builder.get_variable_schema()
        if schema:
            is_valid, missing = builder.validate_variables(variables)
            if not is_valid:
                raise ValueError(
                    f"Missing required variables: {', '.join(missing)}. "
                    f"Required variables: {', '.join(schema.keys())}"
                )
        
        # Build and return the prompt
        return builder.build()
    
    def get_required_variables(self) -> list[str]:
        """
        Extract required variable names from the prompt template.
        
        Returns:
            list[str]: List of variable names found in the template
        """
        from app.services.prompt_template_builder import PromptTemplateBuilder
        builder = PromptTemplateBuilder(self.config)
        return builder.get_required_variables()
    
    def get_variable_schema(self) -> dict:
        """
        Get variable schema from config if defined, otherwise extract from template.
        
        Returns:
            dict: Variable schema with descriptions, types, defaults, etc.
        """
        from app.services.prompt_template_builder import PromptTemplateBuilder
        builder = PromptTemplateBuilder(self.config)
        return builder.get_variable_schema()
    
    def validate_variables(self, variables: dict) -> tuple[bool, list[str]]:
        """
        Validate that all required variables are provided.
        
        Args:
            variables: Dictionary of variables to validate
            
        Returns:
            tuple: (is_valid, list_of_missing_variables)
        """
        from app.services.prompt_template_builder import PromptTemplateBuilder
        builder = PromptTemplateBuilder(self.config, variables)
        return builder.validate_variables(variables)

