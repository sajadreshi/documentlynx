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

    # Database Configuration
    database_url: str
    
    # LLM API Keys (optional - for LLM integrations)
    openai_api_key: Optional[str] = None
    google_api_key: Optional[str] = None
    groq_api_key: Optional[str] = None

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


# Global settings instance
settings = Settings()

