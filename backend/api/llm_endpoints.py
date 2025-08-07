"""
LLM Model Configuration API Endpoints.

Endpoints for managing LLM models via LiteLLM integration.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from database.database import get_db_session
from utils.logging import get_logger
from services.llm_service import llm_service

logger = get_logger(__name__)
router = APIRouter(prefix="/llm", tags=["llm"])


@router.get("/models")
async def list_models():
    """List available LLM models with categorization."""
    try:
        available_models = await llm_service.get_available_models()
        
        return {
            "models": available_models,  # This contains chat_models, embedding_models, all_models
            "total": len(available_models.get("all_models", []))
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
