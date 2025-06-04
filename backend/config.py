from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional, Any, Dict, List
from pydantic import SecretStr


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file="../.env", env_file_encoding="utf-8", extra="ignore"
    )

    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/1"

    # Gmail MCP Server individual components
    GMAIL_MCP_SERVER_HOST: str = "localhost"
    GMAIL_MCP_SERVER_PORT: int = 8002
    GMAIL_MCP_SERVER_URL: Optional[str] = None
    
    # Google Generative AI Settings (using API Key)
    GOOGLE_API_KEY: Optional[SecretStr] = None
    GOOGLE_MODEL_NAME: Optional[str] = None  # e.g., gemini-pro, gemini-1.5-flash

    # Database Configuration
    DATABASE_URL: Optional[str] = None  # PostgreSQL connection string for checkpointer
    
    # LangSmith Configuration
    USE_LANGSMITH: bool = False
    LANGCHAIN_TRACING_V2: Optional[str] = "true"
    LANGCHAIN_ENDPOINT: Optional[str] = "https://api.smith.langchain.com"
    LANGCHAIN_API_KEY: Optional[SecretStr] = None
    LANGCHAIN_PROJECT: Optional[str] = None

    # Agent Loop Settings
    AGENT_POLLING_INTERVAL_SECONDS: int = 30
    AGENT_ERROR_RETRY_INTERVAL_SECONDS: int = 60

    @model_validator(mode="after")
    def compute_urls(self):
        """Compute MCP server URLs if not explicitly provided"""
        if not self.GMAIL_MCP_SERVER_URL:
            self.GMAIL_MCP_SERVER_URL = f"http://{self.GMAIL_MCP_SERVER_HOST}:{self.GMAIL_MCP_SERVER_PORT}"
        
        return self

    @property
    def MCP_SERVERS(self) -> List[Dict[str, Any]]:
        """List of MCP servers to connect to"""
        servers = []
        
        # Gmail MCP Server
        if self.GMAIL_MCP_SERVER_URL:
            servers.append({
                "name": "gmail",
                "url": f"{self.GMAIL_MCP_SERVER_URL}/mcp",
                "health_url": f"{self.GMAIL_MCP_SERVER_URL}/health",
                "description": "Gmail MCP Server for email operations"
            })
        
        return servers


settings = Settings()
