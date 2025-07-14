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
    
    async def validate_google_api_key(self, api_key: str) -> bool:
        """Validate Google API key by making a test request."""
        try:
            import google.generativeai as genai
            genai.configure(api_key=api_key)
            
            # Simple test request with proper response validation
            model = genai.GenerativeModel("gemini-2.5-flash")
            response = model.generate_content("Hello", request_options={"timeout": 10})
            
            # Check if response has valid content
            if response and response.text and len(response.text.strip()) > 0:
                logger.info("Google API key validation successful - received valid response")
                return True
            else:
                logger.warning("Google API key validation failed - empty or invalid response")
                return False
            
        except Exception as e:
            logger.warning(f"Google API key validation failed: {e}")
            return False
    
    async def is_google_api_key_valid(self) -> bool:
        """Check if the current Google API key is valid."""
        api_key = self.get_google_api_key()
        if not api_key:
            return False
        
        return await self.validate_google_api_key(api_key)
    
    async def initialize_default_models_in_litellm(self, db: AsyncSession) -> bool:
        """
        Initialize models in LiteLLM conditionally based on API key availability.
        
        Only adds Gemini models if Google API key is valid.
        Local models are configured in configs/litellm_config.yaml.
        """
        try:
            # Check if Google API key is valid before adding models
            if await self.is_google_api_key_valid():
                google_api_key = self.get_google_api_key()
                
                # Check existing models to avoid duplicates
                existing_models = await self._get_existing_models()
                existing_model_names = {model.get("model_name") for model in existing_models}
                
                # Add Gemini models to LiteLLM (only if not already present)
                gemini_models = [
                    {
                        "model_name": "gemini-2.5-flash",
                        "litellm_params": {
                            "model": "gemini/gemini-2.5-flash",
                            "api_key": google_api_key
                        }
                    },
                    {
                        "model_name": "gemini-2.5-flash-preview-04-17",
                        "litellm_params": {
                            "model": "gemini/gemini-2.5-flash-preview-04-17",
                            "api_key": google_api_key
                        }
                    }
                ]
                
                success_count = 0
                for model_config in gemini_models:
                    model_name = model_config["model_name"]
                    if model_name not in existing_model_names:
                        if await self._add_model_to_litellm(model_config):
                            success_count += 1
                            logger.info(f"Added new model: {model_name}")
                    else:
                        logger.info(f"Model {model_name} already exists, skipping")
                        success_count += 1  # Count as success since it exists
                
                # Also update fallback configuration
                if success_count > 0:
                    await self._update_fallback_config()
                
                logger.info(f"Successfully initialized {success_count}/{len(gemini_models)} Google models")
                return success_count > 0
            else:
                logger.info("Google API key not valid - using only local models")
                return True
            
        except Exception as e:
            logger.error(f"Error initializing dynamic models: {e}")
            return False
    
    async def _get_existing_models(self) -> List[Dict]:
        """Get existing models from LiteLLM."""
        try:
            url = f"{self.litellm_base_url}/model/info"
            headers = {"Authorization": f"Bearer {self.litellm_master_key}"}
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get("data", [])
                    else:
                        logger.warning(f"Failed to get existing models: {response.status}")
                        return []
        except Exception as e:
            logger.error(f"Error getting existing models: {e}")
            return []
    
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
    
    async def _update_fallback_config(self) -> bool:
        """Update LiteLLM fallback configuration when Gemini models are available."""
        try:
            fallback_config = {
                "fallbacks": {
                    "SmolLM3-3B-128K-BF16": ["gemini-2.5-flash"],
                    "phi-4-Q4_K_M": ["gemini-2.5-flash"],
                    "gemini-2.5-flash": ["gemini-2.5-flash-preview-04-17"]
                }
            }
            
            url = f"{self.litellm_base_url}/config/update"
            headers = {
                "Authorization": f"Bearer {self.litellm_master_key}",
                "Content-Type": "application/json"
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=fallback_config) as response:
                    if response.status == 200:
                        logger.info("Successfully updated LiteLLM fallback configuration")
                        return True
                    else:
                        logger.warning(f"Failed to update fallback config: {response.status}")
                        return False
        
        except Exception as e:
            logger.error(f"Error updating fallback configuration: {e}")
            return False
    
    async def get_available_models(self) -> Dict[str, List[str]]:
        """Get list of available models categorized by type."""
        try:
            url = f"{self.litellm_base_url}/model/info"
            headers = {"Authorization": f"Bearer {self.litellm_master_key}"}
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        models = data.get("data", [])
                        
                        # Categorize models
                        local_models = []
                        cloud_models = []
                        
                        for model in models:
                            model_name = model.get("model_name", "")
                            if ("phi-4" in model_name.lower() or 
                                "llama" in model_name.lower() or 
                                "smollm3" in model_name.lower()):
                                local_models.append({"model_name": model_name})
                            elif "gemini" in model_name.lower():
                                cloud_models.append({"model_name": model_name})
                        
                        return {
                            "local": local_models,
                            "cloud": cloud_models
                        }
                    else:
                        logger.error(f"Failed to get models from LiteLLM: {response.status}")
                        return {"local": [], "cloud": []}
        
        except Exception as e:
            logger.error(f"Error getting available models: {e}")
            return {"local": [], "cloud": []}
    
    async def refresh_models_after_api_key_update(self, db: AsyncSession) -> bool:
        """Refresh available models after API keys are updated."""
        try:
            # Re-initialize models based on current API key availability
            success = await self.initialize_default_models_in_litellm(db)
            
            if success:
                logger.info("Successfully refreshed models after API key update")
            else:
                logger.warning("Failed to refresh models after API key update")
            
            return success
        
        except Exception as e:
            logger.error(f"Error refreshing models after API key update: {e}")
            return False


# Global service instance
llm_service = LLMModelService()