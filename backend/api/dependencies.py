from fastapi import Depends
from sqlalchemy.orm import Session
from database.mysql import get_db
from config.settings import settings
from config.logging import get_logger

logger = get_logger(__name__)


async def get_db_session() -> Session:
    """Get database session dependency."""
    session = next(get_db())
    return session


def get_settings() -> object:
    """Get application settings dependency."""
    return settings


def verify_api_key() -> None:
    """Verify API key for protected endpoints."""
    # This is a placeholder for API key verification
    # Can be enhanced with actual API key management
    pass
