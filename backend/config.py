import os
from typing import Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # API Keys
    groq_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None
    openai_api_base: Optional[str] = None

    # Database
    database_url: str = "sqlite:///./agent_platform.db"
    redis_url: str = "redis://localhost:6379"

    # LLM Settings
    default_model: str = "llama3-8b-8192"  # Groq model
    fallback_model: str = "gpt-4.1-mini"  # OpenAI model (supported)
    max_tokens: int = 1000
    temperature: float = 0.7

    # Agent Settings
    max_orchestrator_steps: int = 10
    session_timeout: int = 3600  # 1 hour

    # Security
    secret_key: str = "your-secret-key-change-in-production"

    # Logging
    log_level: str = "INFO"

    class Config:
        env_file = ".env"


# Global settings instance
settings = Settings()


# Load environment variables
def load_env():
    """Load environment variables from .env file"""
    from dotenv import load_dotenv
    load_dotenv()

    # Update settings with environment variables
    settings.groq_api_key = os.getenv("GROQ_API_KEY")
    settings.openai_api_key = os.getenv("OPENAI_API_KEY", os.getenv("OPENAI_API_KEY"))
    settings.openai_api_base = os.getenv("OPENAI_API_BASE", os.getenv("OPENAI_API_BASE"))
    settings.database_url = os.getenv("DATABASE_URL", settings.database_url)
    settings.redis_url = os.getenv("REDIS_URL", settings.redis_url)


# Initialize on import
load_env()