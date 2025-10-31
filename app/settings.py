"""Application settings for the personal MCP server."""

from __future__ import annotations

from typing import List, Optional

from pydantic import AnyHttpUrl, Field, field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Configuration loaded from environment variables or .env file."""

    host: str = Field(default="127.0.0.1", description="IPv4/IPv6 interface to bind the server to.")
    port: int = Field(default=8000, description="Port for the FastAPI application.")

    facebook_access_token: Optional[str] = Field(
        default=None,
        description="Facebook Graph API access token (user or page).",
    )
    facebook_graph_api_version: str = Field(
        default="v19.0",
        description="Version of the Facebook Graph API to use, e.g. v19.0.",
    )
    facebook_base_url: AnyHttpUrl = Field(
        default="https://graph.facebook.com",
        description="Base URL for the Facebook Graph API.",
    )
    facebook_timeout: int = Field(
        default=10,
        description="Timeout in seconds for outgoing Facebook requests.",
    )
    facebook_default_fields: List[str] = Field(
        default_factory=lambda: ["id", "name"],
        description="Default field list to request when fetching profile/feed data.",
    )
    facebook_default_feed_limit: int = Field(
        default=25,
        description="Default number of feed items to fetch when a limit is not provided.",
    )
    facebook_enable_debug: bool = Field(
        default=False,
        description="Enable verbose logging of Facebook requests and responses.",
    )

    google_drive_service_account_file: Optional[str] = Field(
        default=None,
        description="Path to the Google service account JSON credentials file.",
    )
    google_drive_delegated_user: Optional[str] = Field(
        default=None,
        description="Optional user to impersonate when using domain-wide delegation.",
    )
    google_drive_scopes: List[str] = Field(
        default_factory=lambda: ["https://www.googleapis.com/auth/drive"],
        description="OAuth scopes requested for Google Drive access.",
    )
    google_drive_download_chunk_size: int = Field(
        default=4 * 1024 * 1024,
        description="Chunk size in bytes for Drive file downloads.",
    )

    @field_validator("facebook_timeout")
    @classmethod
    def validate_timeout(cls, value: int) -> int:
        """Ensure the timeout is positive."""
        if value <= 0:
            raise ValueError("FACEBOOK_TIMEOUT must be a positive integer")
        return value

    @field_validator("facebook_default_feed_limit")
    @classmethod
    def validate_feed_limit(cls, value: int) -> int:
        """Ensure the feed limit stays within API bounds."""
        if value < 1 or value > 100:
            raise ValueError("FACEBOOK_DEFAULT_FEED_LIMIT must be between 1 and 100")
        return value

    @field_validator("facebook_default_fields", mode="before")
    @classmethod
    def parse_field_list(cls, value: str | List[str] | None) -> List[str]:
        """Support comma separated strings in the environment."""
        if value is None:
            return []
        if isinstance(value, str):
            return [part.strip() for part in value.split(",") if part.strip()]
        return list(value)

    @field_validator("google_drive_scopes", mode="before")
    @classmethod
    def parse_google_scope_list(cls, value: str | List[str] | None) -> List[str]:
        """Support comma separated scope lists."""
        return cls.parse_field_list(value)

    @field_validator("google_drive_download_chunk_size")
    @classmethod
    def validate_drive_chunk_size(cls, value: int) -> int:
        """Ensure the download chunk size is a positive integer."""
        if value <= 0:
            raise ValueError("GOOGLE_DRIVE_DOWNLOAD_CHUNK_SIZE must be positive")
        return value

    class Config:
        env_file = ".env"
        env_prefix = ""


settings = Settings()
