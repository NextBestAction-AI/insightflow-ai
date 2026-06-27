from sqlalchemy.orm import declarative_base
from sqlalchemy import MetaData

# Create metadata and declarative base for SQLAlchemy models
metadata = MetaData()
Base = declarative_base(metadata=metadata)
