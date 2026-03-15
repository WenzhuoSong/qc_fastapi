"""
Application Configuration Management
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    """Application configuration class"""
    
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")
    
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
    OPENAI_MODEL_HEAVY: str = "gpt-4o"
    
    # Finnhub market data
    FINNHUB_API_KEY: str = ""
    
    # Telegram alerts (optional)
    TG_BOT_TOKEN: str = ""
    TG_CHAT_ID: str = ""


@lru_cache()
def get_settings() -> Settings:
    """Get configuration singleton"""
    return Settings()


settings = get_settings()
