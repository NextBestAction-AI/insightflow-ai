from pydantic_settings import BaseSettings
from typing import Literal


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Application
    APP_NAME: str = "InsightFlow AI"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: Literal["development", "staging", "production"] = "development"
    DEBUG: bool = False

    # API
    API_PREFIX: str = "/api/v1"
    ALLOWED_HOSTS: list[str] = ["*"]

    # MySQL Database
    MYSQL_HOST: str = "localhost"
    MYSQL_PORT: int = 3306
    MYSQL_DATABASE: str = "insightflow_ai"
    MYSQL_USER: str = "root"
    MYSQL_PASSWORD: str = "bairava@123"
    MYSQL_POOL_SIZE: int = 5
    MYSQL_MAX_OVERFLOW: int = 10
    MYSQL_POOL_RECYCLE: int = 3600

    # Logging
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    LOG_FILE: str = "logs/app.log"
    LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    # LLM Services (external teams)
    GEMINI_API_KEY: str = ""
    OPENAI_API_KEY: str = ""

    # AI Integration Endpoints (for teammate's AI module)
    AI_PLANNER_URL: str = "http://localhost:8001"
    AI_AGENT_TIMEOUT: int = 30

    # Analytics
    ENABLE_ANALYTICS: bool = True

    class Config:
        """Pydantic config."""
        env_file = ".env"
        case_sensitive = True


settings = Settings()