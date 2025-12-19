
from pydantic_settings import BaseSettings

class DatabaseSettings(BaseSettings):
    database_url: str = "postgresql://user:pass@localhost/dbname" # Default generic URL to avoid crash on init if missing
    pool_size: int = 10
    max_overflow: int = 20
    echo_sql: bool = False
    
    class Config:
        env_prefix = ""

    @property
    def async_database_url(self) -> str:
        """Convert postgres:// to postgresql+asyncpg://"""
        url = self.database_url
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql+asyncpg://", 1)
        elif url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return url

settings = DatabaseSettings()
