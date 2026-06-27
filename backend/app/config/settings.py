try:
    from pydantic_settings import BaseSettings
except ImportError:  # pragma: no cover - compatibility fallback
    from pydantic import BaseSettings


class Settings(BaseSettings):
    mysql_host: str = "localhost"
    mysql_port: int = 3306
    mysql_database: str = "insightflow"
    mysql_user: str = "root"
    mysql_password: str = ""

    class Config:
        env_file = ".env"


settings = Settings()