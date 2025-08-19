from pydantic_settings import BaseSettings
from typing import Optional
import os


class Settings(BaseSettings):
    # Database settings
    DB_URL: str = "postgresql+asyncpg://user:pass@pg:5432/analytics"
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_POOL_RECYCLE: int = 1800
    
    # API settings
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    API_WORKERS: int = 4
    
    # Security settings
    MAX_BULK_SIZE: int = 1000  # Maximum items per bulk request
    MAX_GZIP_SIZE: int = 10 * 1024 * 1024  # 10MB max gzip size
    RATE_LIMIT_PER_MINUTE: int = 1000
    
    # TimescaleDB settings
    COMPRESSION_AFTER_DAYS: int = 7
    RETENTION_DAYS: int = 180
    CHUNK_TIME_INTERVAL: str = "1 day"
    
    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"
    
    class Config:
        env_file = ".env"
        case_sensitive = True


# Global settings instance
settings = Settings()
