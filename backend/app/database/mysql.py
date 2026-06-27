import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import declarative_base, sessionmaker

load_dotenv()


def _resolve_sqlite_path(database_url: str):
    if not database_url.startswith("sqlite"):
        return None

    path_part = database_url[len("sqlite:///"):]
    if not path_part or path_part == ":memory:":
        return None

    if path_part.startswith("/"):
        return path_part

    return os.path.abspath(path_part)


def _needs_sqlite_reset(engine) -> bool:
    if not str(engine.url).startswith("sqlite"):
        return False

    db_path = _resolve_sqlite_path(str(engine.url))
    if not db_path or not os.path.exists(db_path):
        return False

    try:
        with engine.connect() as conn:
            tables = conn.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
            if not any(name[0] == "recommendations" for name in tables):
                return False

            columns = conn.exec_driver_sql("PRAGMA table_info(recommendations)").fetchall()
            column_names = {row[1] for row in columns}
            return "customer_id" not in column_names
    except Exception:
        return False


def _build_database_url() -> str:
    database_url = os.getenv("DATABASE_URL") or os.getenv("MYSQL_URL")
    if database_url:
        return database_url

    mysql_host = os.getenv("MYSQL_HOST")
    mysql_port = os.getenv("MYSQL_PORT")
    mysql_database = os.getenv("MYSQL_DATABASE")
    mysql_user = os.getenv("MYSQL_USER", "root")
    mysql_password = os.getenv("MYSQL_PASSWORD", "")

    if mysql_host and mysql_database:
        return (
            f"mysql+pymysql://"
            f"{mysql_user}:"
            f"{mysql_password}@"
            f"{mysql_host}:"
            f"{mysql_port or '3306'}/"
            f"{mysql_database}"
        )

    return "sqlite:///./insightflow.db"


DATABASE_URL = _build_database_url()


def _create_engine(database_url: str):
    if database_url.startswith("sqlite"):
        return create_engine(database_url, connect_args={"check_same_thread": False})
    return create_engine(database_url, pool_pre_ping=True)


engine = _create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    global engine, SessionLocal

    from app.models import approval, customer, interaction, recommendation  # noqa: F401

    if _needs_sqlite_reset(engine):
        db_path = _resolve_sqlite_path(str(engine.url))
        if db_path and os.path.exists(db_path):
            os.remove(db_path)
            engine = _create_engine("sqlite:///./insightflow.db")
            SessionLocal.configure(bind=engine)

    try:
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
    except SQLAlchemyError:
        if not str(engine.url).startswith("sqlite"):
            sqlite_url = "sqlite:///./insightflow.db"
            engine = _create_engine(sqlite_url)
            SessionLocal.configure(bind=engine)
            Base.metadata.drop_all(bind=engine)
            Base.metadata.create_all(bind=engine)
        else:
            raise