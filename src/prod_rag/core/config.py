"""
Configuration management for the production RAG pipeline.
"""

import os
from functools import lru_cache
from typing import List, Optional

from pydantic import BaseSettings, validator


class Settings(BaseSettings):
    """Application settings with validation and environment variable support."""
    
    # API Configuration
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_workers: int = 4
    api_reload: bool = False
    
    # OpenAI Configuration
    openai_api_key: Optional[str] = None
    
    # Milvus Configuration
    milvus_host: str = "localhost"
    milvus_port: int = 19530
    milvus_user: str = ""
    milvus_password: str = ""
    milvus_secure: bool = False
    milvus_collection_name: str = "documents"
    
    # Redis Configuration
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_password: str = ""
    redis_db: int = 0
    
    # PostgreSQL Configuration
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "prod_rag"
    postgres_user: str = "rag_user"
    postgres_password: str = "rag_password"
    
    # Embedding Model Configuration
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_device: str = "cpu"
    embedding_batch_size: int = 32
    embedding_dimension: int = 384  # all-MiniLM-L6-v2 dimension
    
    # LLM Configuration
    llm_model_name: str = "microsoft/DialoGPT-medium"
    llm_device: str = "cuda"
    llm_max_length: int = 512
    llm_temperature: float = 0.7
    
    # Document Processing
    chunk_size: int = 1000
    chunk_overlap: int = 200
    max_file_size_mb: int = 50
    
    # Caching
    cache_ttl: int = 3600
    enable_cache: bool = True
    
    # Monitoring
    prometheus_port: int = 9090
    grafana_port: int = 3000
    jaeger_port: int = 16686
    
    # Logging
    log_level: str = "INFO"
    log_format: str = "json"
    
    # Security
    secret_key: str = "your_secret_key_here"
    access_token_expire_minutes: int = 30
    
    # Scaling Configuration
    max_concurrent_requests: int = 100
    rate_limit_per_minute: int = 60
    
    # Storage
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket_name: str = "rag-documents"
    
    @validator("log_level")
    def validate_log_level(cls, v):
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in valid_levels:
            raise ValueError(f"Log level must be one of {valid_levels}")
        return v.upper()
    
    @validator("embedding_device")
    def validate_device(cls, v):
        valid_devices = ["cpu", "cuda", "mps"]
        if v not in valid_devices:
            raise ValueError(f"Device must be one of {valid_devices}")
        return v
    
    @property
    def milvus_uri(self) -> str:
        """Get Milvus connection URI."""
        if self.milvus_secure:
            protocol = "https"
        else:
            protocol = "http"
        return f"{protocol}://{self.milvus_host}:{self.milvus_port}"
    
    @property
    def redis_url(self) -> str:
        """Get Redis connection URL."""
        if self.redis_password:
            return f"redis://:{self.redis_password}@{self.redis_host}:{self.redis_port}/{self.redis_db}"
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"
    
    @property
    def postgres_url(self) -> str:
        """Get PostgreSQL connection URL."""
        return f"postgresql://{self.postgres_user}:{self.postgres_password}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
