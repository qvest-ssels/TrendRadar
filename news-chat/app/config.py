"""
Configuration settings for News Chat
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings from environment variables."""
    
    # Ollama settings
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:7b"
    
    # MCP REST API settings (REST wrapper runs on 3334, MCP SSE on 3333)
    mcp_server_url: str = "http://localhost:3334"
    
    # Optional API fallback (ZhipuAI, DeepSeek, etc.)
    api_provider: str = ""  # "zhipu", "deepseek", "openai"
    api_key: str = ""
    api_model: str = ""
    
    # Chat settings
    max_history: int = 20  # Max messages to keep in context
    temperature: float = 0.7
    
    class Config:
        env_prefix = "NEWS_CHAT_"
        env_file = ".env"


settings = Settings()
