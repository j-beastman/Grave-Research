from pydantic_settings import BaseSettings
from dotenv import load_dotenv
import os

load_dotenv()

class DatabaseSettings(BaseSettings):
    database_url: str = "postgresql://user:pass@localhost/dbname" # Default generic URL to avoid crash on init if missing
    pool_size: int = 10
    max_overflow: int = 20
    echo_sql: bool = False
    
    class Config:
        env_prefix = ""

    @property
    def async_database_url(self) -> str:
        """Convert postgres:// to postgresql+asyncpg:// and strip sslmode (asyncpg uses 'ssl')"""
        url = self.database_url
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql+asyncpg://", 1)
        elif url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        
        # Remove parameters that asyncpg doesn't recognize
        # (sslmode, channel_binding, etc. - SSL is handled via connect_args)
        incompatible_params = {"sslmode", "channel_binding"}
        if "?" in url:
            base, params = url.split("?", 1)
            filtered_params = "&".join(
                p for p in params.split("&") 
                if not any(p.startswith(f"{param}=") for param in incompatible_params)
            )
            url = f"{base}?{filtered_params}" if filtered_params else base
        
        return url

settings = DatabaseSettings()
