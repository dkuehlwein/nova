"""
LLM Model Configuration API Endpoints.

Endpoints for managing LLM models via LiteLLM integration.
"""

from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
import aiohttp

from database.database import get_db_session
from utils.logging import get_logger
from services.llm_service import llm_service
from config import settings

logger = get_logger(__name__)
router = APIRouter(prefix="/llm", tags=["llm"])


@router.get("/models")
async def list_models():
    """List available LLM models, filtered by what's actually usable."""
    try:
        # Use the enhanced service method that filters models
        available_models = await llm_service.get_available_models()
        
        # Flatten the categorized models for compatibility
        all_models = []
        all_models.extend(available_models.get("local", []))
        all_models.extend(available_models.get("cloud", []))
        
        return {
            "models": all_models,
            "total": len(all_models)
        }
    
    except Exception as e:
        logger.error(f"Error listing LLM models: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to list LLM models")




@router.post("/models/initialize")
async def initialize_default_models(
    db: AsyncSession = Depends(get_db_session)
):
    """Initialize default LLM models in LiteLLM with conditional Gemini support."""
    try:
        success = await llm_service.initialize_default_models_in_litellm(db)
        
        if success:
            return {"message": "Successfully initialized models in LiteLLM (conditional on API key validity)"}
        else:
            raise HTTPException(status_code=500, detail="Failed to initialize models")
    
    except Exception as e:
        logger.error(f"Error initializing models: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to initialize models")


@router.get("/models/categorized")
async def list_models_categorized():
    """List available LLM models categorized by type (local/cloud)."""
    try:
        available_models = await llm_service.get_available_models()
        
        return {
            "models": available_models,
            "total": len(available_models.get("all_models", []))
        }
    
    except Exception as e:
        logger.error(f"Error listing categorized models: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to list categorized models")


