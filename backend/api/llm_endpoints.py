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
    """List all LLM models from LiteLLM."""
    try:
        url = f"{settings.LITELLM_BASE_URL}/model/info"
        headers = {"Authorization": f"Bearer {settings.LITELLM_MASTER_KEY}"}
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    return {
                        "models": data.get("data", []),
                        "total": len(data.get("data", []))
                    }
                else:
                    raise HTTPException(status_code=response.status, detail="Failed to fetch models from LiteLLM")
    
    except Exception as e:
        logger.error(f"Error listing LLM models: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to list LLM models")




@router.post("/models/initialize")
async def initialize_default_models(
    db: AsyncSession = Depends(get_db_session)
):
    """Initialize default LLM models in LiteLLM."""
    try:
        success = await llm_service.initialize_default_models_in_litellm(db)
        
        if success:
            return {"message": "Successfully initialized default models in LiteLLM"}
        else:
            raise HTTPException(status_code=500, detail="Failed to initialize default models")
    
    except Exception as e:
        logger.error(f"Error initializing default models: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to initialize default models")