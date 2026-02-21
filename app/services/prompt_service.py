"""Service for managing prompt templates with A/B testing support."""

import hashlib
import logging
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from app.models import PromptTemplate

logger = logging.getLogger(__name__)


class PromptService:
    """Service for prompt template management and A/B testing."""

    def __init__(self, db: Session):
        """Initialize prompt service with database session."""
        self.db = db

    def get_prompt(
        self,
        name: str,
        user_id: Optional[str] = None,
        version: Optional[str] = None,
        **variables
    ) -> str:
        """
        Get and render a prompt template with A/B testing support.

        Args:
            name: Name of the prompt template
            user_id: Optional user ID for consistent A/B testing assignment
            version: Optional specific version to use (defaults to active version)
            **variables: Variables to format into the prompt template

        Returns:
            str: Fully rendered prompt

        Raises:
            ValueError: If prompt not found or rendering fails
        """
        # Determine experiment group if user_id provided
        experiment_group = None
        if user_id:
            experiment_group = self._assign_experiment_group(name, user_id)

        # Build query
        query = self.db.query(PromptTemplate).filter(
            PromptTemplate.name == name,
            PromptTemplate.is_active == True
        )

        if version:
            query = query.filter(PromptTemplate.version == version)

        if experiment_group:
            query = query.filter(PromptTemplate.experiment_group == experiment_group)

        # Get template
        template = query.first()

        if not template:
            # Fallback: try without experiment group filter
            template = self.db.query(PromptTemplate).filter(
                PromptTemplate.name == name,
                PromptTemplate.is_active == True,
                PromptTemplate.experiment_group == "control"
            ).first()

        if not template:
            raise ValueError(f"Prompt template '{name}' not found or not active")

        # Render prompt
        try:
            return template.get_full_prompt(**variables)
        except Exception as e:
            logger.error(f"Error rendering prompt {name}: {str(e)}")
            raise ValueError(f"Failed to render prompt: {str(e)}")

    def _assign_experiment_group(self, name: str, user_id: str) -> str:
        """
        Assign user to experiment group using consistent hashing.

        Args:
            name: Prompt template name
            user_id: User identifier

        Returns:
            str: Experiment group ("A" or "B")
        """
        # Consistent hashing for stable assignment
        hash_input = f"{name}:{user_id}"
        hash_value = int(hashlib.md5(hash_input.encode()).hexdigest(), 16)
        return "A" if hash_value % 2 == 0 else "B"

    def create_template(
        self,
        name: str,
        config: Dict[str, Any],
        version: str = "v1",
        description: Optional[str] = None,
        experiment_group: str = "control",
        traffic_percentage: float = 1.0,
        created_by: Optional[str] = None,
        extra_metadata: Optional[Dict[str, Any]] = None
    ) -> PromptTemplate:
        """
        Create a new prompt template.

        Args:
            name: Template name
            config: Prompt configuration dict (instruction, role, etc.)
            version: Version string
            description: Optional description
            experiment_group: Experiment group ("A", "B", or "control")
            traffic_percentage: Traffic percentage (0.0 to 1.0)
            created_by: Creator identifier
            extra_metadata: Optional metadata dict

        Returns:
            PromptTemplate: Created template
        """
        template = PromptTemplate(
            name=name,
            version=version,
            description=description,
            config=config,
            experiment_group=experiment_group,
            traffic_percentage=traffic_percentage,
            created_by=created_by,
            extra_metadata=extra_metadata or {}
        )

        self.db.add(template)
        self.db.commit()
        self.db.refresh(template)

        logger.info(f"Created prompt template: {name} v{version} (group: {experiment_group})")
        return template

    def update_template(
        self,
        template_id: int,
        config: Optional[Dict[str, Any]] = None,
        description: Optional[str] = None,
        is_active: Optional[bool] = None,
        traffic_percentage: Optional[float] = None,
        extra_metadata: Optional[Dict[str, Any]] = None
    ) -> PromptTemplate:
        """
        Update an existing prompt template.

        Args:
            template_id: Template ID
            config: Updated config dict
            description: Updated description
            is_active: Updated active status
            traffic_percentage: Updated traffic percentage
            extra_metadata: Updated metadata

        Returns:
            PromptTemplate: Updated template

        Raises:
            ValueError: If template not found
        """
        template = self.db.query(PromptTemplate).filter(
            PromptTemplate.id == template_id
        ).first()

        if not template:
            raise ValueError(f"Prompt template with ID {template_id} not found")

        if config is not None:
            template.config = config
        if description is not None:
            template.description = description
        if is_active is not None:
            template.is_active = is_active
        if traffic_percentage is not None:
            template.traffic_percentage = traffic_percentage
        if extra_metadata is not None:
            template.extra_metadata = extra_metadata

        self.db.commit()
        self.db.refresh(template)

        logger.info(f"Updated prompt template: {template.name} (ID: {template_id})")
        return template

    def list_templates(
        self,
        name: Optional[str] = None,
        version: Optional[str] = None,
        experiment_group: Optional[str] = None,
        is_active: Optional[bool] = None
    ) -> list[PromptTemplate]:
        """
        List prompt templates with optional filters.

        Args:
            name: Filter by name
            version: Filter by version
            experiment_group: Filter by experiment group
            is_active: Filter by active status

        Returns:
            list[PromptTemplate]: List of templates
        """
        query = self.db.query(PromptTemplate)

        if name:
            query = query.filter(PromptTemplate.name == name)
        if version:
            query = query.filter(PromptTemplate.version == version)
        if experiment_group:
            query = query.filter(PromptTemplate.experiment_group == experiment_group)
        if is_active is not None:
            query = query.filter(PromptTemplate.is_active == is_active)

        return query.order_by(PromptTemplate.name, PromptTemplate.version).all()

    def get_template(self, template_id: int) -> Optional[PromptTemplate]:
        """
        Get a prompt template by ID.

        Args:
            template_id: Template ID

        Returns:
            PromptTemplate or None if not found
        """
        return self.db.query(PromptTemplate).filter(
            PromptTemplate.id == template_id
        ).first()

    def deactivate_template(self, template_id: int) -> PromptTemplate:
        """
        Deactivate a prompt template.

        Args:
            template_id: Template ID

        Returns:
            PromptTemplate: Deactivated template

        Raises:
            ValueError: If template not found
        """
        return self.update_template(template_id, is_active=False)

    def activate_template(self, template_id: int) -> PromptTemplate:
        """
        Activate a prompt template.

        Args:
            template_id: Template ID

        Returns:
            PromptTemplate: Activated template

        Raises:
            ValueError: If template not found
        """
        return self.update_template(template_id, is_active=True)

    def delete_template(self, template_id: int) -> bool:
        """
        Delete a prompt template.

        Args:
            template_id: Template ID

        Returns:
            bool: True if deleted, False if not found
        """
        template = self.get_template(template_id)
        if not template:
            return False

        self.db.delete(template)
        self.db.commit()
        logger.info(f"Deleted prompt template: {template.name} (ID: {template_id})")
        return True

