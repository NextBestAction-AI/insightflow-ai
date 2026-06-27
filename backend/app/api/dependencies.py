from sqlalchemy.orm import Session
from fastapi import Depends
from app.database import get_db

def get_database_session(db: Session = Depends(get_db)) -> Session:
    """
    Dependency provider that yields a clean relational database session 
    per request context, ensuring correct connection disposal.
    """
    try:
        yield db
    finally:
        # FastAPI handles the lifecycle cleanup via the database module's
        # context manager, but this wrapper isolates your dependency mappings.
        pass