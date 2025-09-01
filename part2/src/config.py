import os
from enum import Enum
from typing import Optional, List
from pydantic import Field, validator
from pydantic_settings import BaseSettings
class Environment(str, Enum):
    """Environment types for configuration validation."""
    DEVELOPMENT = "development"
    TESTING = "testing"
    PRODUCTION = "production"


class LogLevel(str, Enum):
    """Supported log levels."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"

class Settings(BaseSettings):
    """
    Application settings with validation and type safety.
    Environment-based configuration with comprehensive validation.
    """
    
    # Application Environment
    environment: Environment = Field(
        default=Environment.DEVELOPMENT,
        description="Application environment"
    )
    
    # API Configuration
    api_host: str = Field(default="0.0.0.0", description="API host address")
    api_port: int = Field(default=8000, ge=1000, le=65535, description="API port")
    api_title: str = Field(default="Insurance Agentic RAG API", description="API title")
    api_version: str = Field(default="1.0.0", description="API version")
    
    # Google Gemini Configuration
    google_api_key: str = Field(..., description="Google AI API key (required)")
    gemini_model: str = Field(
        default="gemini-pro", 
        description="Google Gemini model name"
    )
    gemini_temperature: float = Field(
        default=0.1,
        ge=0.0,
        le=2.0,   #this range is suitable for deterministic properties
        description="Temperature for Gemini responses"
    )
    gemini_max_tokens: int = Field(
        default=2048, #performance trade off cut zone
        ge=100, #ensures non trivial response
        le=8192,
        description="Maximum tokens for Gemini responses"
    )
    gemini_top_p: float = Field(
        default=0.8,
        ge=0.0,
        le=1.0,
        description="Top-p sampling for Gemini"
    )
    gemini_top_k: int = Field(
        default=40,
        ge=1,
        le=100,
        description="Top-k sampling for Gemini"
    )
    
    # PostgreSQL Database Configuration
    database_url: Optional[str] = Field(
        default=None,
        description="Complete PostgreSQL connection URL"
    )
    db_host: str = Field(default="localhost", description="Database host")
    db_port: int = Field(default=5432, ge=1, le=65535, description="Database port")
    db_name: str = Field(default="insurance_rag", description="Database name")
    db_user: str = Field(default="postgres", description="Database username")
    db_password: str = Field(default="postgres", description="Database password")
    db_pool_size: int = Field(default=10, ge=1, le=100, description="Connection pool size")
    db_max_overflow: int = Field(default=20, ge=0, le=100, description="Max pool overflow")
    db_pool_timeout: int = Field(default=30, ge=1, le=300, description="Pool timeout seconds")
    db_echo: bool = Field(default=False, description="Echo SQL queries (development)")
    
    # LangGraph Configuration
    langgraph_checkpointer: str = Field(
        default="memory",
        description="LangGraph checkpointer type (memory/postgres)"
    )
    langgraph_max_steps: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Maximum steps for LangGraph workflows"
    )
    langgraph_timeout: int = Field(
        default=300,
        ge=30,
        le=600,
        description="LangGraph execution timeout in seconds"
    )
    
    # Excel Processing Configuration
    max_excel_rows: int = Field(
        default=100000,
        ge=1,
        le=1000000,
        description="Maximum Excel rows to process"
    )
    excel_chunk_size: int = Field(
        default=1000,
        ge=100,
        le=10000,
        description="Chunk size for Excel processing"
    )
    
    # Performance Configuration
    max_concurrent_requests: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Maximum concurrent API requests"
    )
    request_timeout: int = Field(
        default=30,
        ge=5,
        le=300,
        description="Request timeout in seconds"
    )
    query_timeout: int = Field(
        default=60,
        ge=10,
        le=600,
        description="Database query timeout in seconds"
    )
    
    # Caching Configuration
    redis_url: Optional[str] = Field(
        default=None,
        description="Redis connection URL for caching"
    )
    cache_ttl: int = Field(
        default=3600,
        ge=60,
        le=86400,
        description="Cache TTL in seconds"
    )
    enable_caching: bool = Field(
        default=True,
        description="Enable response caching"
    )
    
    # Logging Configuration
    log_level: LogLevel = Field(
        default=LogLevel.INFO,
        description="Application log level"
    )
    log_format: str = Field(
        default="json",
        description="Log format (json or text)"
    )
    enable_request_logging: bool = Field(
        default=True,
        description="Enable request/response logging"
    )
    
    # Security Configuration  
    allowed_file_types: List[str] = Field(
        default=["xlsx", "xls"],
        description="Allowed file extensions for upload"
    )
    max_file_size_mb: int = Field(
        default=50,
        ge=1,
        le=500,
        description="Maximum file size in MB"
    )
    
    # Authentication Configuration
    secret_key: str = Field(
        default="your-secret-key-change-in-production",
        description="Secret key for JWT tokens"
    )
    access_token_expire_minutes: int = Field(
        default=30,
        ge=5,
        le=10080,
        description="Access token expiration in minutes"
    )
    
    @validator('google_api_key')
    def validate_google_api_key(cls, v):
        """Validate Google API key format."""
        if not v:
            raise ValueError('Google API key is required')
        # Google API keys typically start with 'AIza'
        if not v.startswith('AIza') and len(v) < 20:
            raise ValueError('Invalid Google API key format')
        return v
    
    @validator('database_url', always=True)
    def build_database_url(cls, v, values):
        """Build database URL if not provided."""
        if v:
            return v
        
        # Build from components
        db_host = values.get('db_host', 'localhost')
        db_port = values.get('db_port', 5432)
        db_user = values.get('db_user', 'postgres')
        db_password = values.get('db_password', 'postgres')
        db_name = values.get('db_name', 'insurance_rag')
        
        return f"postgresql+asyncpg://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
    
    @validator('secret_key')
    def validate_secret_key(cls, v, values):
        """Validate secret key in production."""
        environment = values.get('environment', Environment.DEVELOPMENT)
        if environment == Environment.PRODUCTION and v == "your-secret-key-change-in-production":
            raise ValueError('Must set SECRET_KEY in production environment')
        return v
    
    @property
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.environment == Environment.DEVELOPMENT
    
    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.environment == Environment.PRODUCTION
    
    @property
    def gemini_config(self) -> dict:
        """Get Gemini configuration for LangChain."""
        return {
            "model": self.gemini_model,
            "temperature": self.gemini_temperature,
            "max_output_tokens": self.gemini_max_tokens,
            "top_p": self.gemini_top_p,
            "top_k": self.gemini_top_k,
            "google_api_key": self.google_api_key
        }
    
    @property
    def database_config(self) -> dict:
        """Get database configuration."""
        return {
            "url": self.database_url,
            "pool_size": self.db_pool_size,
            "max_overflow": self.db_max_overflow,
            "pool_timeout": self.db_pool_timeout,
            "echo": self.db_echo and self.is_development
        }
    
    class Config:
        """Pydantic configuration."""
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        # Don't expose sensitive values in error messages
        hide_input_in_errors = True


# Global settings instance
settings = Settings()


def get_settings() -> Settings:
    """
    Dependency injection function for FastAPI.
    Allows easy testing and configuration override.
    """
    return settings


def get_database_url() -> str:
    """Get the database connection URL."""
    return settings.database_url


def get_gemini_config() -> dict:
    """Get Gemini LLM configuration."""
    return settings.gemini_config