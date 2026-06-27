from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    mysql_host: str
    mysql_port: int
    mysql_database: str
    mysql_user: str
    mysql_password: str

    class Config:
        env_file = ".env"


settings = Settings()