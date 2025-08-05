"""
LLM Model Management Service.

Service for managing LLM model configurations and LiteLLM integration.
"""

from typing import Dict, List, Optional, Tuple
import aiohttp
import yaml
import os
from sqlalchemy.ext.asyncio import AsyncSession

from utils.logging import get_logger
from config import settings

logger = get_logger(__name__)


class LLMModelService:
    """Service for managing LLM model configurations."""
    
    # Constants
    GEMINI_MODELS = [
        {
            "model_name": "gemini-2.5-flash",
            "litellm_params": {
                "model": "gemini/gemini-2.5-flash"
            }
        },
        {
            "model_name": "gemini-2.5-flash-lite-preview-06-17",
            "litellm_params": {
                "model": "gemini/gemini-2.5-flash-lite-preview-06-17"
            }
        },
        {
            "model_name": "gemma-3-27b-it",
            "litellm_params": {
                "model": "gemini/gemma-3-27b-it"
            }
        },
        {
            "model_name": "gemini-embedding-001",
            "litellm_params": {
                "model": "gemini/gemini-embedding-001"
            }
        }
    ]
    
    HUGGINGFACE_MODELS = [
        {
            "model_name": "smollm3-3b",
            "litellm_params": {
                "model": "openai/HuggingFaceTB/SmolLM3-3B",
                "api_base": "https://api-inference.huggingface.co/models/HuggingFaceTB/SmolLM3-3B/v1",
                "temperature": 0.6,
                "max_tokens": 2048
            }
        },
        {
            "model_name": "qwen3-embedding-4b",
            "litellm_params": {
                "model": "huggingface/Qwen/Qwen3-Embedding-4B"
            }
        }
    ]
    
    OPENROUTER_MODELS = [
        {
            "model_name": "openrouter/horizon-beta",
            "litellm_params": {
                "model": "openrouter/horizon-beta",
                "api_base": "https://openrouter.ai/api/v1",
                "temperature": 0.7,
                "max_tokens": 2048
            }
        }
    ]
    
    FALLBACK_CONFIG = {
        "fallbacks": {
            "SmolLM3-3B-128K-BF16": ["gemini-2.5-flash"],
            "phi-4-Q4_K_M": ["gemini-2.5-flash"],
            "gemini-2.5-flash": ["gemini-2.5-flash-lite-preview-06-17"]
        }
    }
    
    def __init__(self):
        self._config_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), 
            "configs", 
            "litellm_config.yaml"
        )
    
    # ============= HTTP Client Methods =============
    
    async def _make_litellm_request(
        self, 
        method: str, 
        endpoint: str, 
        data: Optional[Dict] = None
    ) -> Tuple[bool, Optional[Dict]]:
        """Make authenticated request to LiteLLM API."""
        try:
            # Get current LiteLLM connection settings
            from utils.llm_factory import get_litellm_config
            litellm_config = get_litellm_config()
            url = f"{litellm_config['base_url']}/{endpoint.lstrip('/')}"
            headers = {"Authorization": f"Bearer {litellm_config['api_key']}"}
            
            if data:
                headers["Content-Type"] = "application/json"
            
            async with aiohttp.ClientSession() as session:
                async with session.request(method, url, headers=headers, json=data) as response:
                    if response.status == 200:
                        result = await response.json() if response.content_type == "application/json" else {}
                        return True, result
                    else:
                        error_text = await response.text()
                        logger.error(f"LiteLLM API error [{method} {endpoint}]: {response.status} - {error_text}")
                        return False, None
                        
        except Exception as e:
            logger.error(f"Error making LiteLLM request [{method} {endpoint}]: {e}")
            return False, None
    
    
    
    # ============= Model Configuration Management =============
    
    
    def _is_embedding_model(self, model_name: str) -> bool:
        """Determine if a model is an embedding model based on its name."""
        return "embedding" in model_name.lower()
    
    # ============= LiteLLM API Operations =============
    
    async def add_model_to_litellm(self, model_config: Dict) -> bool:
        """Add a single model to LiteLLM via API if it doesn't already exist."""
        model_name = model_config['model_name']
        
        # Check if model already exists
        if await self._model_exists_in_litellm(model_name):
            logger.info(f"Model {model_name} already exists in LiteLLM - skipping")
            return True  # Return True since the model is available
        
        success, _ = await self._make_litellm_request("POST", "/model/new", model_config)
        if success:
            logger.info(f"Successfully added model {model_name} to LiteLLM")
        else:
            logger.error(f"Failed to add model {model_name} to LiteLLM")
        return success
    
    async def _model_exists_in_litellm(self, model_name: str) -> bool:
        """Check if a model already exists in LiteLLM."""
        try:
            success, result = await self._make_litellm_request("GET", "/models")
            if success and result:
                existing_models = [model.get("id", "") for model in result.get("data", [])]
                return model_name in existing_models
            return False
        except Exception as e:
            logger.warning(f"Failed to check if model {model_name} exists: {e}")
            return False  # Assume it doesn't exist if we can't check
    
    async def update_fallback_config(self) -> bool:
        """Update LiteLLM fallback configuration when Gemini models are available."""
        success, _ = await self._make_litellm_request("POST", "/config/update", self.FALLBACK_CONFIG)
        if success:
            logger.info("Successfully updated LiteLLM fallback configuration")
        else:
            logger.warning("Failed to update fallback configuration")
        return success
    
    # ============= Model Management Operations =============
    
    async def initialize_gemini_models(self, session) -> int:
        """Initialize Gemini models if API key is valid. Returns count of successful additions."""
        from api.settings_endpoints import get_google_api_status
        
        try:
            status_response = await get_google_api_status(force_refresh=True, session=session)
            if not status_response.get("google_api_key_valid", False):
                logger.info("Google API key not valid - skipping Gemini model initialization")
                return 0
        except Exception as e:
            logger.info(f"Google API key validation failed: {e} - skipping Gemini model initialization")
            return 0
        
        google_api_key = settings.GOOGLE_API_KEY.get_secret_value() if settings.GOOGLE_API_KEY else None
        
        success_count = 0
        for model_config in self.GEMINI_MODELS:
            enhanced_config = model_config.copy()
            enhanced_config["litellm_params"]["api_key"] = google_api_key
            
            model_name = model_config["model_name"]
            if await self.add_model_to_litellm(enhanced_config):
                success_count += 1
                logger.info(f"Added new model: {model_name}")
        
        return success_count
    
    async def initialize_huggingface_models(self, session) -> int:
        """Initialize HuggingFace models if token is valid. Returns count of successful additions."""
        from api.settings_endpoints import get_huggingface_api_status
        
        try:
            status_response = await get_huggingface_api_status(force_refresh=True, session=session)
            if not status_response.get("huggingface_api_key_valid", False):
                logger.info("HuggingFace token not valid - skipping HF model initialization")
                return 0
        except Exception as e:
            logger.info(f"HuggingFace token validation failed: {e} - skipping HF model initialization")
            return 0
        
        hf_token = settings.HF_TOKEN.get_secret_value() if settings.HF_TOKEN else None
        
        success_count = 0
        for model_config in self.HUGGINGFACE_MODELS:
            enhanced_config = model_config.copy()
            enhanced_config["litellm_params"]["api_key"] = hf_token
            
            model_name = model_config["model_name"]
            if await self.add_model_to_litellm(enhanced_config):
                success_count += 1
                logger.info(f"Added new model: {model_name}")
        
        return success_count
    
    async def initialize_openrouter_models(self, session) -> int:
        """Initialize OpenRouter models if API key is valid. Returns count of successful additions."""
        from api.settings_endpoints import get_openrouter_api_status
        
        try:
            status_response = await get_openrouter_api_status(force_refresh=True, session=session)
            if not status_response.get("openrouter_api_key_valid", False):
                logger.info("OpenRouter API key not valid - skipping OpenRouter model initialization")
                return 0
        except Exception as e:
            logger.info(f"OpenRouter API key validation failed: {e} - skipping OpenRouter model initialization")
            return 0
        
        openrouter_api_key = settings.OPENROUTER_API_KEY.get_secret_value() if settings.OPENROUTER_API_KEY else None
        
        success_count = 0
        for model_config in self.OPENROUTER_MODELS:
            enhanced_config = model_config.copy()
            enhanced_config["litellm_params"]["api_key"] = openrouter_api_key
            
            model_name = model_config["model_name"]
            if await self.add_model_to_litellm(enhanced_config):
                success_count += 1
                logger.info(f"Added new model: {model_name}")
        
        return success_count
    
    async def initialize_default_models_in_litellm(self, db: AsyncSession) -> bool:
        """
        Initialize working models in LiteLLM based on API key availability.
        
        Only adds models for services that are actually available.
        """
        try:
            total_models = 0
            
            # Initialize Gemini models
            gemini_count = await self.initialize_gemini_models(db)
            total_models += gemini_count
            
            # Initialize HuggingFace models
            hf_count = await self.initialize_huggingface_models(db)
            total_models += hf_count
            
            # Initialize OpenRouter models
            openrouter_count = await self.initialize_openrouter_models(db)
            total_models += openrouter_count
            
            # Update fallback configuration if we have any models
            if total_models > 0:
                await self.update_fallback_config()
                logger.info(f"Successfully initialized {total_models} models: {gemini_count} Gemini, {hf_count} HuggingFace, {openrouter_count} OpenRouter")
                return True
            else:
                logger.info("No working models available - check API keys")
                return True
            
        except Exception as e:
            logger.error(f"Error initializing models: {e}")
            return False
    
    async def get_available_models(self) -> Dict[str, List[Dict[str, str]]]:
        """
        Get all configured models from LiteLLM API.
        
        Returns all models configured in LiteLLM - let LiteLLM handle availability/fallbacks.
        
        Returns models categorized by type for UI display:
        - chat_models: Models suitable for conversational AI
        - embedding_models: Models for text embeddings 
        - all_models: Complete list of configured models
        """
        try:
            # Get all configured models from LiteLLM
            success, result = await self._make_litellm_request("GET", "models")
            
            if not success or not result:
                logger.error("Failed to fetch models from LiteLLM API")
                return {"chat_models": [], "embedding_models": [], "all_models": []}
            
            models_data = result.get("data", [])
            
            # Categorize models for UI
            chat_models = []
            embedding_models = []
            all_models = []
            
            for model in models_data:
                model_id = model.get("id", "")
                model_dict = {
                    "model_name": model_id,
                    "id": model_id,
                    "owned_by": model.get("owned_by", "unknown")
                }
                
                all_models.append(model_dict)
                
                # Categorize by model type
                if "embedding" in model_id.lower():
                    embedding_models.append(model_dict)
                else:
                    chat_models.append(model_dict)
                    
            logger.info(f"Retrieved {len(all_models)} configured models from LiteLLM: {len(chat_models)} chat, {len(embedding_models)} embedding")
            
            return {
                "chat_models": chat_models,
                "embedding_models": embedding_models, 
                "all_models": all_models
            }
        
        except Exception as e:
            logger.error(f"Error getting models from LiteLLM: {e}")
            return {"chat_models": [], "embedding_models": [], "all_models": []}
    
    # Health checks now handled by system_endpoints.py - no duplication
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
    
    def get_available_models_sync(self) -> Optional[dict]:
        """Get available models synchronously for use in non-async contexts."""
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If we're already in an async context, we need to use a new event loop
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(asyncio.run, self.get_available_models())
                    return future.result()
            else:
                return asyncio.run(self.get_available_models())
        except Exception as e:
            print(f"Warning: Could not get available models sync: {e}")
            return None


# Global service instance
llm_service = LLMModelService()