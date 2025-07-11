"""
LLM Model Management Service.

Service for managing LLM model configurations and LiteLLM integration.
"""

from typing import Dict, List, Optional
import aiohttp
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from models.user_settings import UserSettings
from utils.logging import get_logger
from config import settings

logger = get_logger(__name__)


class LLMModelService:
    """Service for managing LLM model configurations."""
    
    def __init__(self):
        self.litellm_base_url = settings.LITELLM_BASE_URL
        self.litellm_master_key = settings.LITELLM_MASTER_KEY
    
    
    def get_google_api_key(self) -> Optional[str]:
        """Get Google API key from environment only (ADR-008 Tier 2)."""
        try:
            env_key = settings.GOOGLE_API_KEY.get_secret_value() if settings.GOOGLE_API_KEY else None
            if env_key:
                logger.info("Using Google API key from environment (ADR-008 Tier 2)")
                return env_key
                
            logger.info("No Google API key found in environment - local-only mode")
            return None
            
        except Exception as e:
            logger.error(f"Error getting Google API key: {e}")
            return None
    
    async def initialize_default_models_in_litellm(self, db: AsyncSession) -> bool:
        """
        Initialize models in LiteLLM. 
        
        Note: Static models are configured in configs/litellm_config.yaml.
        This method only handles dynamic Google API key configuration.
        """
        try:
            # Only add Google model if API key is available in environment
            # Local models are configured in litellm_config.yaml
            google_api_key = self.get_google_api_key()
            if google_api_key:
                google_success = await self._add_model_to_litellm({
                    "model_name": "gemini-2.5-flash",
                    "litellm_params": {
                        "model": "gemini/gemini-2.5-flash-preview-04-17",
                        "api_key": google_api_key
                    }
                })
                
                if google_success:
                    logger.info("Successfully initialized Google model with runtime API key")
                else:
                    logger.warning("Failed to add Google model with runtime API key")
                    
                return google_success
            else:
                logger.info("Google API key not available - using only models from config file")
                return True
            
        except Exception as e:
            logger.error(f"Error initializing dynamic models: {e}")
            return False
    
    async def _add_model_to_litellm(self, model_config: Dict) -> bool:
        """Add a single model to LiteLLM via API."""
        try:
            url = f"{self.litellm_base_url}/model/new"
            headers = {
                "Authorization": f"Bearer {self.litellm_master_key}",
                "Content-Type": "application/json"
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=model_config) as response:
                    if response.status == 200:
                        result = await response.json()
                        logger.info(f"Successfully added model {model_config['model_name']} to LiteLLM")
                        return True
                    else:
                        error_text = await response.text()
                        logger.error(f"Failed to add model {model_config['model_name']}: {response.status} - {error_text}")
                        return False
                        
        except Exception as e:
            logger.error(f"Error adding model {model_config.get('model_name', 'unknown')} to LiteLLM: {e}")
            return False


# Global service instance
llm_service = LLMModelService()