from sqlalchemy import create_engine, Engine, event, exc
from sqlalchemy.engine import URL
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import NullPool, QueuePool
from typing import Generator
from config.settings import settings
from config.logging import get_logger
from database.base import Base

logger = get_logger(__name__)


class DatabaseManager:
    """Manages MySQL database connection and session lifecycle."""

    _engine: Engine | None = None
    _session_factory: sessionmaker | None = None

    @classmethod
    def initialize(cls) -> None:
        """Initialize database engine and session factory."""
        if cls._engine is not None:
            logger.warning("Database already initialized")
            return

        database_url = URL.create(
            drivername="mysql+pymysql",
            username=settings.MYSQL_USER,
            password=settings.MYSQL_PASSWORD,
            host=settings.MYSQL_HOST,
            port=settings.MYSQL_PORT,
            database=settings.MYSQL_DATABASE,
        )

        try:
            cls._engine = create_engine(
                database_url,
                pool_size=settings.MYSQL_POOL_SIZE,
                max_overflow=settings.MYSQL_MAX_OVERFLOW,
                pool_recycle=settings.MYSQL_POOL_RECYCLE,
                pool_pre_ping=True,
                echo=settings.DEBUG,
            )

            # Configure event listeners for connection management
            @event.listens_for(cls._engine, "connect")
            def receive_connect(dbapi_conn, connection_record):
                """Set session variables on connection."""
                cursor = dbapi_conn.cursor()
                cursor.execute("SET SESSION sql_mode='STRICT_TRANS_TABLES'")
                cursor.close()

            cls._session_factory = sessionmaker(
                bind=cls._engine,
                expire_on_commit=False,
                autoflush=False,
            )

            logger.info("Database initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize database: {str(e)}")
            raise

    @classmethod
    def get_session(cls) -> Session:
        """Get a new database session."""
        if cls._session_factory is None:
            raise RuntimeError("Database not initialized. Call DatabaseManager.initialize() first.")
        return cls._session_factory()

    @classmethod
    async def close(cls) -> None:
        """Close database connection pool."""
        if cls._engine:
            cls._engine.dispose()
            logger.info("Database connection closed")

    @classmethod
    def create_tables(cls) -> None:
        """Create all tables defined in Base metadata."""
        if cls._engine is None:
            raise RuntimeError("Database not initialized. Call DatabaseManager.initialize() first.")

        try:
            Base.metadata.create_all(bind=cls._engine)
            logger.info("All tables created successfully")
        except Exception as e:
            logger.error(f"Failed to create tables: {str(e)}")
            raise

    @classmethod
    def drop_tables(cls) -> None:
        """Drop all tables. Use with caution!"""
        if cls._engine is None:
            raise RuntimeError("Database not initialized. Call DatabaseManager.initialize() first.")

        try:
            Base.metadata.drop_all(bind=cls._engine)
            logger.warning("All tables dropped")
        except Exception as e:
            logger.error(f"Failed to drop tables: {str(e)}")
            raise


def get_db() -> Generator[Session, None, None]:
    """Dependency for getting database session in FastAPI routes."""
    session = DatabaseManager.get_session()
    try:
        yield session
    except Exception as e:
        logger.error(f"Database session error: {str(e)}")
        session.rollback()
        raise
    finally:
        session.close()