"""
Application Configuration Management
"""

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application configuration class"""
    
    # Application info
    APP_NAME: str = "Quant Agent Backend"
    APP_VERSION: str = "3.1.0"
    DEBUG: bool = False
    
    # Server settings
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    
    # API authentication (leave empty to disable auth in local dev)
    API_TOKEN: str = ""
    
    # PostgreSQL (Railway provides DATABASE_URL automatically)
    DATABASE_URL: str = ""
    
    # OpenAI configuration
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"
    
    # Telegram alerts (optional)
    TG_BOT_TOKEN: str = ""
    TG_CHAT_ID: str = ""
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    """Get configuration singleton"""
    return Settings()


settings = get_settings()
