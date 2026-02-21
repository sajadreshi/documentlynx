"""Configuration management for the application."""

import os
from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

# Load environment variables from .env file
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=env_path)


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Google Cloud Storage Configuration
    google_cloud_project_id: str
    google_cloud_storage_bucket: str
    google_application_credentials: str
    signed_url_expiration_seconds: int = 604800  # Default: 7 days (max allowed by GCS)

    # API Configuration
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_base_url: str = "http://localhost:8000"  # Base URL for generating public links

    # Database Configuration
    database_url: str
    
    # LLM API Keys (optional - for LLM integrations)
    openai_api_key: Optional[str] = None
    google_api_key: Optional[str] = None
    groq_api_key: Optional[str] = None
    
    # Docling API Configuration (loaded from .env)
    docling_api_url: str  # URL-based conversion endpoint
    docling_file_api_url: str  # File-based conversion endpoint
    docling_timeout_seconds: int
    docling_temp_dir: str  # Temp directory for file operations
    
    # Validation Configuration
    validation_llm_model: str = "llama-3.3-70b-versatile"  # LLM model for markdown validation
    max_validation_attempts: int = 3  # Maximum retry attempts for validation
    
    # Embedding Configuration
    embedding_provider: str = "huggingface"  # "huggingface" or "openai"
    embedding_model: str = "all-MiniLM-L6-v2"  # Model name for embeddings
    embedding_dimensions: int = 384  # Must match model output dimensions

    # LangSmith Configuration (optional)
    langsmith_api_key: Optional[str] = None
    langsmith_project: str = "doculord"
    langsmith_tracing_v2: bool = False

    class Config:
        """Pydantic config."""

        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False

    def __init__(self, **kwargs):
        """Initialize settings and validate Google credentials path."""
        super().__init__(**kwargs)
        self._validate_credentials()
        self._validate_signed_url_expiration()
        self._ensure_temp_dir()

    def _validate_credentials(self) -> None:
        """Validate that the Google credentials file exists."""
        credentials_path = Path(self.google_application_credentials)
        
        # If path is relative, check relative to project root
        if not credentials_path.is_absolute():
            project_root = Path(__file__).parent.parent
            credentials_path = project_root / credentials_path
        
        if not credentials_path.exists():
            raise FileNotFoundError(
                f"Google credentials file not found at: {credentials_path}"
            )
        
        # Update to absolute path for use
        self.google_application_credentials = str(credentials_path)

    def _validate_signed_url_expiration(self) -> None:
        """Validate that signed URL expiration is within Google Cloud Storage limits."""
        # Google Cloud Storage maximum is 7 days (604800 seconds)
        MAX_EXPIRATION_SECONDS = 604800
        if self.signed_url_expiration_seconds > MAX_EXPIRATION_SECONDS:
            raise ValueError(
                f"Signed URL expiration cannot exceed {MAX_EXPIRATION_SECONDS} seconds (7 days). "
                f"Current value: {self.signed_url_expiration_seconds}"
            )
        if self.signed_url_expiration_seconds <= 0:
            raise ValueError(
                f"Signed URL expiration must be greater than 0. "
                f"Current value: {self.signed_url_expiration_seconds}"
            )

    def _ensure_temp_dir(self) -> None:
        """Ensure the temp directory exists, create if necessary."""
        temp_path = Path(self.docling_temp_dir)
        
        # If path is relative, make it relative to project root
        if not temp_path.is_absolute():
            project_root = Path(__file__).parent.parent
            temp_path = project_root / temp_path
        
        # Create directory if it doesn't exist
        temp_path.mkdir(parents=True, exist_ok=True)
        
        # Update to absolute path for use
        self.docling_temp_dir = str(temp_path)


# Global settings instance
settings = Settings()

