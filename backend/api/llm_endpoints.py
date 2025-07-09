"""
LLM Model Configuration API Endpoints.

Endpoints for managing LLM model configurations and LiteLLM integration.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from database.database import get_db_session
from models.models import LLMModel
from models.llm import (
    LLMModelCreate,
    LLMModelUpdate,
    LLMModelResponse,
    LLMModelList,
    LLMModelSetDefault,
    LiteLLMConfigGenerate
)
from utils.logging import get_logger
from services.llm_service import llm_service

logger = get_logger(__name__)
router = APIRouter(prefix="/llm", tags=["llm"])


@router.get("/models", response_model=LLMModelList)
async def list_models(
    active_only: bool = False,
    db: AsyncSession = Depends(get_db_session)
):
    """List all LLM model configurations."""
    try:
        query = select(LLMModel)
        if active_only:
            query = query.where(LLMModel.is_active == True)
        
        query = query.order_by(LLMModel.created_at.desc())
        result = await db.execute(query)
        models = result.scalars().all()
        
        # Get default model
        default_query = select(LLMModel).where(LLMModel.is_default == True)
        default_result = await db.execute(default_query)
        default_model = default_result.scalar_one_or_none()
        
        # Convert to response models
        model_responses = [LLMModelResponse.from_orm(model) for model in models]
        default_response = LLMModelResponse.from_orm(default_model) if default_model else None
        
        return LLMModelList(
            models=model_responses,
            total=len(model_responses),
            active_count=len([m for m in model_responses if m.is_active]),
            default_model=default_response
        )
    
    except Exception as e:
        logger.error(f"Error listing LLM models: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to list LLM models")


@router.post("/models", response_model=LLMModelResponse)
async def create_model(
    model_data: LLMModelCreate,
    db: AsyncSession = Depends(get_db_session)
):
    """Create a new LLM model configuration."""
    try:
        # If this is set as default, unset other defaults
        if model_data.is_default:
            await db.execute(
                select(LLMModel).where(LLMModel.is_default == True).update({LLMModel.is_default: False})
            )
        
        # Create new model
        new_model = LLMModel(
            name=model_data.name,
            model_name=model_data.model_name,
            provider=model_data.provider,
            is_default=model_data.is_default,
            is_active=model_data.is_active,
            config=model_data.config
        )
        
        db.add(new_model)
        await db.commit()
        await db.refresh(new_model)
        
        logger.info(f"Created LLM model: {new_model.name} (ID: {new_model.id})")
        return LLMModelResponse.from_orm(new_model)
    
    except Exception as e:
        await db.rollback()
        logger.error(f"Error creating LLM model: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to create LLM model")


@router.get("/models/{model_id}", response_model=LLMModelResponse)
async def get_model(
    model_id: int,
    db: AsyncSession = Depends(get_db_session)
):
    """Get a specific LLM model configuration."""
    try:
        query = select(LLMModel).where(LLMModel.id == model_id)
        result = await db.execute(query)
        model = result.scalar_one_or_none()
        
        if not model:
            raise HTTPException(status_code=404, detail="LLM model not found")
        
        return LLMModelResponse.from_orm(model)
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting LLM model {model_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get LLM model")


@router.put("/models/{model_id}", response_model=LLMModelResponse)
async def update_model(
    model_id: int,
    model_data: LLMModelUpdate,
    db: AsyncSession = Depends(get_db_session)
):
    """Update an existing LLM model configuration."""
    try:
        # Get existing model
        query = select(LLMModel).where(LLMModel.id == model_id)
        result = await db.execute(query)
        model = result.scalar_one_or_none()
        
        if not model:
            raise HTTPException(status_code=404, detail="LLM model not found")
        
        # If setting as default, unset other defaults
        if model_data.is_default:
            await db.execute(
                select(LLMModel).where(LLMModel.is_default == True).update({LLMModel.is_default: False})
            )
        
        # Update model fields
        update_data = model_data.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(model, field, value)
        
        await db.commit()
        await db.refresh(model)
        
        logger.info(f"Updated LLM model: {model.name} (ID: {model.id})")
        return LLMModelResponse.from_orm(model)
    
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Error updating LLM model {model_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update LLM model")


@router.delete("/models/{model_id}")
async def delete_model(
    model_id: int,
    db: AsyncSession = Depends(get_db_session)
):
    """Delete an LLM model configuration."""
    try:
        # Get existing model
        query = select(LLMModel).where(LLMModel.id == model_id)
        result = await db.execute(query)
        model = result.scalar_one_or_none()
        
        if not model:
            raise HTTPException(status_code=404, detail="LLM model not found")
        
        # Don't allow deleting the default model
        if model.is_default:
            raise HTTPException(status_code=400, detail="Cannot delete the default model")
        
        await db.delete(model)
        await db.commit()
        
        logger.info(f"Deleted LLM model: {model.name} (ID: {model.id})")
        return {"message": f"LLM model {model.name} deleted successfully"}
    
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Error deleting LLM model {model_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to delete LLM model")


@router.post("/models/{model_id}/set-default", response_model=LLMModelResponse)
async def set_default_model(
    model_id: int,
    db: AsyncSession = Depends(get_db_session)
):
    """Set a model as the default LLM model."""
    try:
        # Get the model
        query = select(LLMModel).where(LLMModel.id == model_id)
        result = await db.execute(query)
        model = result.scalar_one_or_none()
        
        if not model:
            raise HTTPException(status_code=404, detail="LLM model not found")
        
        if not model.is_active:
            raise HTTPException(status_code=400, detail="Cannot set inactive model as default")
        
        # Unset all other defaults
        await db.execute(
            select(LLMModel).where(LLMModel.is_default == True).update({LLMModel.is_default: False})
        )
        
        # Set this model as default
        model.is_default = True
        await db.commit()
        await db.refresh(model)
        
        logger.info(f"Set default LLM model: {model.name} (ID: {model.id})")
        return LLMModelResponse.from_orm(model)
    
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Error setting default LLM model {model_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to set default LLM model")


@router.get("/config/generate", response_model=LiteLLMConfigGenerate)
async def generate_litellm_config(
    db: AsyncSession = Depends(get_db_session)
):
    """Generate LiteLLM configuration from database models."""
    try:
        # Get all active models
        query = select(LLMModel).where(LLMModel.is_active == True)
        result = await db.execute(query)
        models = result.scalars().all()
        
        if not models:
            raise HTTPException(status_code=400, detail="No active LLM models found")
        
        # Generate LiteLLM configuration
        model_list = []
        for model in models:
            litellm_params = {
                "model": f"{model.provider}/{model.model_name}",
            }
            
            # Add provider-specific configuration
            if model.config:
                if model.provider == "ollama":
                    litellm_params["api_base"] = model.config.get("api_base", "http://ollama:11434")
                elif model.provider in ["openai", "google"]:
                    if "api_key" in model.config:
                        litellm_params["api_key"] = model.config["api_key"]
                
                # Add optional parameters
                for param in ["temperature", "max_tokens", "top_p", "frequency_penalty", "presence_penalty"]:
                    if param in model.config:
                        litellm_params[param] = model.config[param]
            
            model_list.append({
                "model_name": model.model_name,
                "litellm_params": litellm_params
            })
        
        config = {
            "model_list": model_list,
            "general_settings": {
                "database_url": "env:DATABASE_URL",
                "master_key": "env:LITELLM_MASTER_KEY",
                "ui_access_mode": "admin_only",
            },
            "litellm_settings": {
                "set_verbose": True,
                "request_timeout": 60,
                "num_retries": 3
            }
        }
        
        return LiteLLMConfigGenerate(
            config=config,
            message=f"Generated configuration for {len(models)} active models",
            reload_required=True
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating LiteLLM config: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to generate LiteLLM configuration")


@router.post("/config/sync")
async def sync_config_to_litellm(
    db: AsyncSession = Depends(get_db_session)
):
    """Sync database configuration to LiteLLM service."""
    try:
        success = await llm_service.sync_config_to_litellm(db)
        
        if success:
            return {"message": "LiteLLM configuration synchronized successfully", "success": True}
        else:
            raise HTTPException(status_code=500, detail="Failed to sync configuration to LiteLLM")
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error syncing LiteLLM config: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to sync configuration")


@router.post("/models/initialize")
async def initialize_default_models(
    db: AsyncSession = Depends(get_db_session)
):
    """Initialize default LLM models if none exist."""
    try:
        models = await llm_service.create_default_models(db)
        
        # Sync configuration to LiteLLM
        await llm_service.sync_config_to_litellm(db)
        
        return {
            "message": f"Initialized {len(models)} default models",
            "models": [{"id": m.id, "name": m.name, "provider": m.provider} for m in models]
        }
    
    except Exception as e:
        logger.error(f"Error initializing default models: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to initialize default models")