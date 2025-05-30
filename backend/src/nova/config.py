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
    GMAIL_MCP_SERVER_PORT: int = 8001
    GMAIL_MCP_SERVER_URL: Optional[str] = None
    
    # Tasks MCP Server individual components
    TASKS_MCP_SERVER_HOST: str = "localhost"
    TASKS_MCP_SERVER_PORT: int = 8002
    TASKS_MCP_SERVER_URL: Optional[str] = None
    
    # Google Generative AI Settings (using API Key)
    GOOGLE_API_KEY: Optional[SecretStr] = None
    GOOGLE_MODEL_NAME: Optional[str] = None  # e.g., gemini-pro, gemini-1.5-flash

    # LangSmith Configuration
    USE_LANGSMITH: bool = False
    LANGCHAIN_TRACING_V2: Optional[str] = "true"
    LANGCHAIN_ENDPOINT: Optional[str] = "https://api.smith.langchain.com"
    LANGCHAIN_API_KEY: Optional[SecretStr] = None
    LANGCHAIN_PROJECT: Optional[str] = None

    # Agent Loop Settings
    AGENT_POLLING_INTERVAL_SECONDS: int = 30
    AGENT_ERROR_RETRY_INTERVAL_SECONDS: int = 60

    @model_validator(mode='after')
    def assemble_urls_if_not_set(cls, values: Any) -> Any:
        if values.GMAIL_MCP_SERVER_URL is None:
            host = values.GMAIL_MCP_SERVER_HOST
            port = values.GMAIL_MCP_SERVER_PORT
            values.GMAIL_MCP_SERVER_URL = f"http://{host}:{port}/mcp/"
        
        if values.TASKS_MCP_SERVER_URL is None:
            host = values.TASKS_MCP_SERVER_HOST
            port = values.TASKS_MCP_SERVER_PORT
            values.TASKS_MCP_SERVER_URL = f"http://{host}:{port}/mcp/"
        
        return values

    @property
    def active_mcp_servers(self) -> Dict[str, Dict[str, str]]:
        """
        Returns a dictionary of active MCP servers for the agent to connect to.
        Each server entry contains the URL and description.
        """
        return {
            "gmail": {
                "url": self.GMAIL_MCP_SERVER_URL,
                "transport": "streamable_http",
                "description": "Gmail integration server for email operations via Google API"
            },
            "tasks": {
                "url": self.TASKS_MCP_SERVER_URL,
                "transport": "streamable_http", 
                "description": "Tasks.md file management server for task operations"
            }
        }

    @property
    def enabled_mcp_servers(self) -> List[str]:
        """
        Returns a list of enabled MCP server names.
        Useful for conditional logic based on which servers are available.
        """
        enabled = []
        if self.GMAIL_MCP_SERVER_URL:
            enabled.append("gmail")
        if self.TASKS_MCP_SERVER_URL:
            enabled.append("tasks")
        return enabled


settings = Settings()
