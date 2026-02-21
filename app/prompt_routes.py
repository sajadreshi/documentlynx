"""API routes for prompt template management."""

import logging
from typing import Optional, Dict, Any, List
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, Body
from pydantic import BaseModel, Field, field_serializer
from sqlalchemy.orm import Session
from app.database import get_db
from app.auth import authenticate_client
from app.models import ClientCredential, PromptTemplate
from app.services.prompt_service import PromptService

logger = logging.getLogger(__name__)

# Initialize API router
router = APIRouter(prefix="/documently/api/v1/prompts", tags=["Prompt Templates"])


# Request/Response Models
class PromptConfig(BaseModel):
    """Prompt configuration structure."""
    instruction: Optional[str] = Field(None, description="Main instruction for the prompt")
    output_constraints: Optional[List[str]] = Field(None, description="List of output constraints")
    role: Optional[str] = Field(None, description="Role description")
    style_or_tone: Optional[List[str]] = Field(None, description="List of style/tone guidelines")
    goal: Optional[str] = Field(None, description="Goal of the prompt")
    
    class Config:
        extra = "allow"  # Allow additional fields in config


class PromptTemplateCreate(BaseModel):
    """Request model for creating a prompt template."""
    name: str = Field(..., description="Template name")
    config: PromptConfig = Field(..., description="Prompt configuration")
    version: str = Field(default="v1", description="Version string")
    description: Optional[str] = Field(None, description="Template description")
    experiment_group: str = Field(default="control", description="Experiment group (A, B, or control)")
    traffic_percentage: float = Field(default=1.0, ge=0.0, le=1.0, description="Traffic percentage")
    created_by: Optional[str] = Field(None, description="Creator identifier")
    extra_metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")


class PromptTemplateUpdate(BaseModel):
    """Request model for updating a prompt template."""
    config: Optional[PromptConfig] = Field(None, description="Updated prompt configuration")
    description: Optional[str] = Field(None, description="Updated description")
    is_active: Optional[bool] = Field(None, description="Active status")
    traffic_percentage: Optional[float] = Field(None, ge=0.0, le=1.0, description="Traffic percentage")
    extra_metadata: Optional[Dict[str, Any]] = Field(None, description="Updated metadata")


class PromptTemplateResponse(BaseModel):
    """Response model for prompt template."""
    id: int
    name: str
    version: str
    description: Optional[str]
    config: Dict[str, Any]
    experiment_group: str
    traffic_percentage: float
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime]
    created_by: Optional[str]
    extra_metadata: Optional[Dict[str, Any]]

    @field_serializer('created_at', 'updated_at')
    def serialize_datetime(self, value: Optional[datetime], _info) -> Optional[str]:
        """Serialize datetime to ISO format string."""
        if value is None:
            return None
        return value.isoformat()

    class Config:
        from_attributes = True


class PromptRenderRequest(BaseModel):
    """Request model for rendering a prompt."""
    name: str = Field(..., description="Template name")
    user_id: Optional[str] = Field(None, description="User ID for A/B testing")
    version: Optional[str] = Field(None, description="Specific version to use")
    variables: Optional[Dict[str, Any]] = Field(default={}, description="Variables to format into prompt")


class PromptRenderResponse(BaseModel):
    """Response model for rendered prompt."""
    prompt: str
    template_name: str
    version: str
    experiment_group: Optional[str]


# API Endpoints
@router.post("", response_model=PromptTemplateResponse, status_code=201)
async def create_prompt_template(
    template_data: PromptTemplateCreate,
    db: Session = Depends(get_db),
    client: ClientCredential = Depends(authenticate_client)
):
    """
    Create a new prompt template.
    
    Requires authentication via X-Client-Id and X-Client-Secret headers.
    """
    try:
        service = PromptService(db)
        template = service.create_template(
            name=template_data.name,
            config=template_data.config.dict(exclude_none=True),
            version=template_data.version,
            description=template_data.description,
            experiment_group=template_data.experiment_group,
            traffic_percentage=template_data.traffic_percentage,
            created_by=template_data.created_by or client.client_id,
            extra_metadata=template_data.extra_metadata
        )
        
        return PromptTemplateResponse.from_orm(template)
    except Exception as e:
        logger.error(f"Error creating prompt template: {str(e)}", exc_info=True)
        raise HTTPException(status_code=400, detail=str(e))


@router.get("", response_model=List[PromptTemplateResponse])
async def list_prompt_templates(
    name: Optional[str] = Query(None, description="Filter by name"),
    version: Optional[str] = Query(None, description="Filter by version"),
    experiment_group: Optional[str] = Query(None, description="Filter by experiment group"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    db: Session = Depends(get_db),
    client: ClientCredential = Depends(authenticate_client)
):
    """
    List prompt templates with optional filters.
    
    Requires authentication via X-Client-Id and X-Client-Secret headers.
    """
    try:
        service = PromptService(db)
        templates = service.list_templates(
            name=name,
            version=version,
            experiment_group=experiment_group,
            is_active=is_active
        )
        
        return [PromptTemplateResponse.from_orm(t) for t in templates]
    except Exception as e:
        logger.error(f"Error listing prompt templates: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{template_id}", response_model=PromptTemplateResponse)
async def get_prompt_template(
    template_id: int,
    db: Session = Depends(get_db),
    client: ClientCredential = Depends(authenticate_client)
):
    """
    Get a specific prompt template by ID.
    
    Requires authentication via X-Client-Id and X-Client-Secret headers.
    """
    try:
        service = PromptService(db)
        template = service.get_template(template_id)
        
        if not template:
            raise HTTPException(status_code=404, detail=f"Prompt template with ID {template_id} not found")
        
        return PromptTemplateResponse.from_orm(template)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting prompt template: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{template_id}", response_model=PromptTemplateResponse)
async def update_prompt_template(
    template_id: int,
    template_data: PromptTemplateUpdate,
    db: Session = Depends(get_db),
    client: ClientCredential = Depends(authenticate_client)
):
    """
    Update an existing prompt template.
    
    Requires authentication via X-Client-Id and X-Client-Secret headers.
    """
    try:
        service = PromptService(db)
        
        update_data = template_data.dict(exclude_none=True)
        if "config" in update_data:
            update_data["config"] = update_data["config"].dict(exclude_none=True)
        if "extra_metadata" in update_data and update_data["extra_metadata"] is None:
            # Handle None explicitly for metadata updates
            pass
        
        template = service.update_template(
            template_id=template_id,
            **update_data
        )
        
        return PromptTemplateResponse.from_orm(template)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error updating prompt template: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/render", response_model=PromptRenderResponse)
async def render_prompt(
    request: PromptRenderRequest,
    db: Session = Depends(get_db),
    client: ClientCredential = Depends(authenticate_client)
):
    """
    Render a prompt template with variables.
    
    Requires authentication via X-Client-Id and X-Client-Secret headers.
    """
    try:
        service = PromptService(db)
        prompt_text = service.get_prompt(
            name=request.name,
            user_id=request.user_id,
            version=request.version,
            **(request.variables or {})
        )
        
        # Get template info for response
        template = db.query(PromptTemplate).filter(
            PromptTemplate.name == request.name,
            PromptTemplate.is_active == True
        ).first()
        
        # Get experiment group if user_id provided
        experiment_group = None
        if request.user_id:
            experiment_group = service._assign_experiment_group(request.name, request.user_id)
        
        return PromptRenderResponse(
            prompt=prompt_text,
            template_name=request.name,
            version=template.version if template else "unknown",
            experiment_group=experiment_group
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error rendering prompt: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{template_id}/activate", response_model=PromptTemplateResponse)
async def activate_prompt_template(
    template_id: int,
    db: Session = Depends(get_db),
    client: ClientCredential = Depends(authenticate_client)
):
    """
    Activate a prompt template.
    
    Requires authentication via X-Client-Id and X-Client-Secret headers.
    """
    try:
        service = PromptService(db)
        template = service.activate_template(template_id)
        return PromptTemplateResponse.from_orm(template)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error activating prompt template: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{template_id}/deactivate", response_model=PromptTemplateResponse)
async def deactivate_prompt_template(
    template_id: int,
    db: Session = Depends(get_db),
    client: ClientCredential = Depends(authenticate_client)
):
    """
    Deactivate a prompt template.
    
    Requires authentication via X-Client-Id and X-Client-Secret headers.
    """
    try:
        service = PromptService(db)
        template = service.deactivate_template(template_id)
        return PromptTemplateResponse.from_orm(template)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error deactivating prompt template: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{template_id}", status_code=204)
async def delete_prompt_template(
    template_id: int,
    db: Session = Depends(get_db),
    client: ClientCredential = Depends(authenticate_client)
):
    """
    Delete a prompt template.
    
    Requires authentication via X-Client-Id and X-Client-Secret headers.
    """
    try:
        service = PromptService(db)
        deleted = service.delete_template(template_id)
        
        if not deleted:
            raise HTTPException(status_code=404, detail=f"Prompt template with ID {template_id} not found")
        
        return None
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting prompt template: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

