"""
LLM Model Management Service.

Service for managing LLM model configurations and LiteLLM integration.
"""

from typing import Dict, List, Optional, Set, Tuple
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
    
    # ============= Google API Key Management =============
    
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
    
    # ============= Model Configuration Management =============
    
    def _get_expected_models_from_config(self) -> Set[str]:
        """Get the set of model names that should be available based on config files."""
        expected_models = set()
        
        try:
            # Read local models from litellm_config.yaml
            if os.path.exists(self._config_path):
                with open(self._config_path, 'r') as f:
                    config = yaml.safe_load(f)
                    
                model_list = config.get("model_list", [])
                for model in model_list:
                    model_name = model.get("model_name")
                    if model_name:
                        expected_models.add(model_name)
                        
                logger.info(f"Found {len(expected_models)} models in litellm_config.yaml: {expected_models}")
            
            # Add dynamically created Gemini models if Google API key is valid
            gemini_model_names = {model["model_name"] for model in self.GEMINI_MODELS}
            
            # Only add Gemini models to expected set if Google API key is available
            if self.get_google_api_key():
                expected_models.update(gemini_model_names)
                logger.info(f"Google API key available, including Gemini models: {gemini_model_names}")
            else:
                logger.info("No Google API key available, excluding Gemini models from expected set")
                
        except Exception as e:
            logger.error(f"Error reading model configuration: {e}")
            
        return expected_models
    
    def _is_embedding_model(self, model_name: str) -> bool:
        """Determine if a model is an embedding model based on its name."""
        return "embedding" in model_name.lower()
    
    # ============= LiteLLM API Operations =============
    
    async def get_existing_models(self) -> List[Dict]:
        """Get existing models from LiteLLM."""
        success, result = await self._make_litellm_request("GET", "/model/info")
        return result.get("data", []) if success else []
    
    async def add_model_to_litellm(self, model_config: Dict) -> bool:
        """Add a single model to LiteLLM via API."""
        success, _ = await self._make_litellm_request("POST", "/model/new", model_config)
        if success:
            logger.info(f"Successfully added model {model_config['model_name']} to LiteLLM")
        else:
            logger.error(f"Failed to add model {model_config['model_name']} to LiteLLM")
        return success
    
    async def delete_model_from_litellm(self, model_id: str, model_name: str) -> bool:
        """Delete a specific model from LiteLLM by ID."""
        success, _ = await self._make_litellm_request("POST", "/model/delete", {"id": model_id})
        if success:
            logger.info(f"Successfully deleted orphaned model: {model_name} (ID: {model_id})")
        else:
            logger.error(f"Failed to delete model {model_name} (ID: {model_id})")
        return success
    
    async def update_fallback_config(self) -> bool:
        """Update LiteLLM fallback configuration when Gemini models are available."""
        success, _ = await self._make_litellm_request("POST", "/config/update", self.FALLBACK_CONFIG)
        if success:
            logger.info("Successfully updated LiteLLM fallback configuration")
        else:
            logger.warning("Failed to update fallback configuration")
        return success
    
    # ============= Model Management Operations =============
    
    async def cleanup_orphaned_models(self) -> int:
        """
        Remove models from LiteLLM that are no longer defined in configuration.
        Returns the number of models successfully removed.
        """
        try:
            # Get expected models from configuration
            expected_models = self._get_expected_models_from_config()
            
            # Get current models from LiteLLM
            current_models = await self.get_existing_models()
            
            orphaned_models = []
            for model in current_models:
                model_name = model.get("model_name", "")
                model_id = model.get("model_info", {}).get("id", "")
                
                if model_name not in expected_models:
                    orphaned_models.append((model_id, model_name))
            
            if not orphaned_models:
                logger.info("No orphaned models found - all models are properly configured")
                return 0
                
            logger.info(f"Found {len(orphaned_models)} orphaned models to remove: {[name for _, name in orphaned_models]}")
            
            # Delete orphaned models
            deleted_count = 0
            for model_id, model_name in orphaned_models:
                if model_id and await self.delete_model_from_litellm(model_id, model_name):
                    deleted_count += 1
                    
            logger.info(f"Successfully removed {deleted_count}/{len(orphaned_models)} orphaned models")
            return deleted_count
            
        except Exception as e:
            logger.error(f"Error during orphaned model cleanup: {e}")
            return 0
    
    async def initialize_gemini_models(self) -> int:
        """Initialize Gemini models if API key is valid. Returns count of successful additions."""
        if not await self.is_google_api_key_valid():
            logger.info("Google API key not valid - skipping Gemini model initialization")
            return 0
        
        google_api_key = self.get_google_api_key()
        existing_models = await self.get_existing_models()
        existing_model_names = {model.get("model_name") for model in existing_models}
        
        success_count = 0
        for model_config in self.GEMINI_MODELS:
            # Add API key to model config
            enhanced_config = model_config.copy()
            enhanced_config["litellm_params"]["api_key"] = google_api_key
            
            model_name = model_config["model_name"]
            if model_name not in existing_model_names:
                if await self.add_model_to_litellm(enhanced_config):
                    success_count += 1
                    logger.info(f"Added new model: {model_name}")
            else:
                logger.info(f"Model {model_name} already exists, skipping")
                success_count += 1  # Count as success since it exists
        
        return success_count
    
    async def initialize_default_models_in_litellm(self, db: AsyncSession) -> bool:
        """
        Initialize models in LiteLLM conditionally based on API key availability.
        
        Only adds Gemini models if Google API key is valid.
        Local models are configured in configs/litellm_config.yaml.
        
        Also performs automatic cleanup of orphaned models.
        """
        try:
            # First, cleanup any orphaned models that are no longer in configuration
            logger.info("Starting automatic cleanup of orphaned models...")
            cleanup_count = await self.cleanup_orphaned_models()
            if cleanup_count > 0:
                logger.info(f"Cleaned up {cleanup_count} orphaned models")
            
            # Initialize Gemini models
            gemini_count = await self.initialize_gemini_models()
            
            # Update fallback configuration if we have Gemini models
            if gemini_count > 0:
                await self.update_fallback_config()
                logger.info(f"Successfully initialized {gemini_count}/{len(self.GEMINI_MODELS)} Google models")
                return True
            else:
                logger.info("Using only local models")
                return True
            
        except Exception as e:
            logger.error(f"Error initializing dynamic models: {e}")
            return False
    
    async def get_available_models(self) -> Dict[str, List[Dict[str, str]]]:
        """
        Get available models directly from LiteLLM API.
        
        Returns models categorized by type for UI display:
        - chat_models: Models suitable for conversational AI
        - embedding_models: Models for text embeddings 
        - all_models: Complete list of available models
        """
        try:
            # Use LiteLLM's /models endpoint directly
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
                    
            logger.info(f"Retrieved {len(all_models)} models from LiteLLM: {len(chat_models)} chat, {len(embedding_models)} embedding")
            
            return {
                "chat_models": chat_models,
                "embedding_models": embedding_models, 
                "all_models": all_models
            }
        
        except Exception as e:
            logger.error(f"Error getting available models from LiteLLM: {e}")
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