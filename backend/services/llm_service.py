"""
LLM Model Management Service.

Service for managing LLM model configurations and LiteLLM integration.
"""

from typing import Dict, List, Optional
import aiohttp
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from models.models import LLMModel
from utils.logging import get_logger
from config import settings

logger = get_logger(__name__)


class LLMModelService:
    """Service for managing LLM model configurations."""
    
    def __init__(self):
        self.litellm_base_url = settings.LITELLM_BASE_URL
        self.litellm_master_key = settings.LITELLM_MASTER_KEY
    
    async def get_all_models(self, db: AsyncSession, active_only: bool = False) -> List[LLMModel]:
        """Get all LLM models from database."""
        query = select(LLMModel)
        if active_only:
            query = query.where(LLMModel.is_active == True)
        
        query = query.order_by(LLMModel.created_at.desc())
        result = await db.execute(query)
        return result.scalars().all()
    
    async def get_default_model(self, db: AsyncSession) -> Optional[LLMModel]:
        """Get the default LLM model."""
        query = select(LLMModel).where(LLMModel.is_default == True)
        result = await db.execute(query)
        return result.scalar_one_or_none()
    
    async def set_default_model(self, db: AsyncSession, model_id: int) -> LLMModel:
        """Set a model as default, unsetting others."""
        # Unset all current defaults
        await db.execute(
            select(LLMModel).where(LLMModel.is_default == True).update({LLMModel.is_default: False})
        )
        
        # Set the new default
        model = await db.get(LLMModel, model_id)
        if not model:
            raise ValueError(f"Model with ID {model_id} not found")
        
        if not model.is_active:
            raise ValueError("Cannot set inactive model as default")
        
        model.is_default = True
        await db.commit()
        await db.refresh(model)
        
        return model
    
    def _generate_model_config(self, model: LLMModel) -> Dict:
        """Generate LiteLLM model configuration for a single model."""
        litellm_params = {
            "model": f"{model.provider}/{model.model_name}",
        }
        
        # Add provider-specific configuration
        if model.config:
            if model.provider == "ollama":
                litellm_params["api_base"] = model.config.get("api_base", "http://ollama:11434")
            elif model.provider == "google":
                litellm_params["model"] = f"gemini/{model.model_name}"
                if "api_key" in model.config:
                    litellm_params["api_key"] = model.config["api_key"]
            elif model.provider == "openai":
                if "api_key" in model.config:
                    litellm_params["api_key"] = model.config["api_key"]
                if "api_base" in model.config:
                    litellm_params["api_base"] = model.config["api_base"]
            
            # Add common optional parameters
            for param in ["temperature", "max_tokens", "top_p", "frequency_penalty", "presence_penalty"]:
                if param in model.config:
                    litellm_params[param] = model.config[param]
        
        return {
            "model_name": model.model_name,
            "litellm_params": litellm_params
        }
    
    async def generate_litellm_config(self, db: AsyncSession) -> Dict:
        """Generate complete LiteLLM configuration from database models."""
        models = await self.get_all_models(db, active_only=True)
        
        if not models:
            raise ValueError("No active LLM models found")
        
        # Generate model list
        model_list = []
        for model in models:
            model_config = self._generate_model_config(model)
            model_list.append(model_config)
        
        # Generate full configuration
        config = {
            "model_list": model_list,
            "general_settings": {
                "database_url": f"postgresql://{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}@{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}",
                "master_key": self.litellm_master_key,
                "ui_access_mode": "admin_only",
            },
            "litellm_settings": {
                "set_verbose": True,
                "request_timeout": 60,
                "num_retries": 3
            }
        }
        
        return config
    
    async def update_litellm_config(self, config: Dict) -> bool:
        """Update LiteLLM configuration via API (following ADR-008 Tier 3 approach)."""
        try:
            url = f"{self.litellm_base_url}/config/update"
            headers = {
                "Authorization": f"Bearer {self.litellm_master_key}",
                "Content-Type": "application/json"
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=config) as response:
                    if response.status == 200:
                        logger.info("LiteLLM configuration updated successfully via API")
                        return True
                    else:
                        logger.error(f"Failed to update LiteLLM config via API: {response.status}")
                        return False
        
        except Exception as e:
            logger.error(f"Error updating LiteLLM config via API: {e}")
            return False
    
    async def reload_litellm_config(self) -> bool:
        """Reload LiteLLM configuration via API."""
        try:
            url = f"{self.litellm_base_url}/config/reload"
            headers = {"Authorization": f"Bearer {self.litellm_master_key}"}
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers) as response:
                    if response.status == 200:
                        logger.info("LiteLLM configuration reloaded successfully")
                        return True
                    else:
                        logger.error(f"Failed to reload LiteLLM config: {response.status}")
                        return False
        
        except Exception as e:
            logger.error(f"Error reloading LiteLLM config: {e}")
            return False
    
    async def sync_config_to_litellm(self, db: AsyncSession) -> bool:
        """Generate and sync configuration to LiteLLM (database-driven approach per ADR-008)."""
        try:
            # Generate configuration from database (Tier 3)
            config = await self.generate_litellm_config(db)
            
            # Update LiteLLM configuration via API
            update_success = await self.update_litellm_config(config)
            
            if update_success:
                logger.info("LiteLLM configuration synchronized successfully from database")
                return True
            else:
                logger.error("Failed to update LiteLLM configuration via API")
                return False
            
        except Exception as e:
            logger.error(f"Failed to sync configuration to LiteLLM: {e}")
            return False
    
    async def create_default_models(self, db: AsyncSession) -> List[LLMModel]:
        """Create default LLM models if none exist."""
        existing_models = await self.get_all_models(db)
        if existing_models:
            logger.info("LLM models already exist, skipping default creation")
            return existing_models
        
        # Create default models
        default_models = [
            LLMModel(
                name="Gemini 2.5 Flash",
                model_name="gemini-2.5-flash",
                provider="google",
                is_default=True,
                is_active=True,
                config={"api_key": "env:GOOGLE_API_KEY"}
            ),
            LLMModel(
                name="Gemma 3 12B Local",
                model_name="gemma3:12b-it-qat",
                provider="ollama",
                is_default=False,
                is_active=True,
                config={"api_base": "http://ollama:11434"}
            )
        ]
        
        for model in default_models:
            db.add(model)
        
        await db.commit()
        
        # Refresh models to get IDs
        for model in default_models:
            await db.refresh(model)
        
        logger.info(f"Created {len(default_models)} default LLM models")
        return default_models


# Global service instance
llm_service = LLMModelService()