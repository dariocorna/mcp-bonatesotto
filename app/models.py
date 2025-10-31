"""Pydantic models for request and response payloads."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import AnyHttpUrl, BaseModel, Field, HttpUrl


class HealthResponse(BaseModel):
    """Simple health-check response."""

    status: str = "ok"


class FacebookProfileRequest(BaseModel):
    """Request payload for fetching profile information."""

    fields: Optional[List[str]] = Field(
        default=None,
        description="Graph API fields to request for the profile (comma separated if provided).",
    )
    target_id: str = Field(
        default="me",
        description="Graph API node to query (defaults to `me`).",
        min_length=1,
    )


class FacebookProfileResponse(BaseModel):
    """Response payload wrapping the Facebook profile information."""

    profile: Dict[str, Any]


class FacebookFeedRequest(BaseModel):
    """Request payload for retrieving a feed from the Graph API."""

    target_id: str = Field(
        default="me",
        description="Graph API node to read the feed from.",
        min_length=1,
    )
    limit: Optional[int] = Field(
        default=None,
        ge=1,
        le=100,
        description="Maximum number of feed entries to fetch (Graph API limit: 1-100).",
    )
    fields: Optional[List[str]] = Field(
        default=None,
        description="Specific fields to fetch for each feed item.",
    )
    since: Optional[datetime] = Field(
        default=None,
        description="Only return feed entries updated after this time.",
    )
    until: Optional[datetime] = Field(
        default=None,
        description="Only return feed entries updated before this time.",
    )
    before: Optional[str] = Field(
        default=None,
        description="Cursor for paging backward.",
    )
    after: Optional[str] = Field(
        default=None,
        description="Cursor for paging forward.",
    )


class FacebookFeedResponse(BaseModel):
    """Normalized feed response."""

    posts: List[Dict[str, Any]]
    paging: Optional[Dict[str, Any]] = None


class FacebookCreatePostRequest(BaseModel):
    """Request payload for creating a post on a user or page feed."""

    target_id: str = Field(
        default="me",
        description="Graph API node where the post will be created.",
        min_length=1,
    )
    message: str = Field(
        ...,
        min_length=1,
        max_length=63206,
        description="Post message body.",
    )
    link: Optional[HttpUrl] = Field(
        default=None,
        description="Optional URL to attach to the post.",
    )
    published: bool = Field(
        default=True,
        description="Whether the post should be published immediately.",
    )
    scheduled_publish_time: Optional[datetime] = Field(
        default=None,
        description="Schedule the post for a future time (requires published to be false).",
    )
    privacy: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Privacy settings map; will be JSON-encoded for the Graph API.",
    )


class FacebookCreatePostResponse(BaseModel):
    """Response payload returned after creating a post."""

    id: str = Field(..., description="Identifier of the post returned by the Graph API.")
    raw: Dict[str, Any] = Field(
        default_factory=dict,
        description="Unmodified payload returned by the Graph API.",
    )


class GoogleDriveListFilesRequest(BaseModel):
    """Request payload for listing Google Drive files."""

    query: Optional[str] = Field(
        default=None,
        description="Advanced search query per Google Drive API syntax.",
    )
    page_size: int = Field(
        default=20,
        ge=1,
        le=1000,
        description="Maximum number of files to return in a single request.",
    )
    page_token: Optional[str] = Field(
        default=None,
        description="Token for fetching the next page of results.",
    )
    fields: Optional[str] = Field(
        default=None,
        description="Custom fields to request from the Drive API; defaults to a useful subset.",
    )
    order_by: Optional[str] = Field(
        default=None,
        description="Sort expression, e.g. `modifiedTime desc`.",
    )
    spaces: Optional[str] = Field(
        default="drive",
        description="Comma separated list of spaces to query, e.g. `drive,appDataFolder`.",
    )
    include_trashed: bool = Field(
        default=False,
        description="Include items that are in the trash.",
    )


class GoogleDriveListFilesResponse(BaseModel):
    """Response wrapper for Google Drive file listings."""

    files: List[Dict[str, Any]] = Field(default_factory=list)
    next_page_token: Optional[str] = Field(default=None, description="Token for fetching the next result page.")


class GoogleDriveDownloadRequest(BaseModel):
    """Request payload for downloading a specific Drive file."""

    file_id: str = Field(..., description="Identifier of the file to download.", min_length=1)


class GoogleDriveDownloadResponse(BaseModel):
    """Response payload containing a downloaded Drive file."""

    file_id: str = Field(..., description="Identifier of the downloaded file.")
    name: Optional[str] = Field(default=None, description="Original filename as stored in Drive.")
    mime_type: Optional[str] = Field(default=None, description="MIME type reported by Drive.")
    size: Optional[str] = Field(default=None, description="File size in bytes if known.")
    md5_checksum: Optional[str] = Field(
        default=None,
        description="MD5 checksum provided by Drive, useful for integrity checks.",
    )
    content_base64: str = Field(..., description="Base64 encoded file contents.")


class GoogleDriveUploadRequest(BaseModel):
    """Request payload for uploading a new file to Drive."""

    name: str = Field(..., description="Destination filename.", min_length=1)
    content_base64: str = Field(
        ...,
        description="Base64 encoded content to upload.",
    )
    mime_type: Optional[str] = Field(
        default=None,
        description="MIME type of the uploaded file.",
    )
    parents: Optional[List[str]] = Field(
        default=None,
        description="List of parent folder IDs. Defaults to the account's root.",
    )
    make_public: bool = Field(
        default=False,
        description="Whether to create a public read-only link for the uploaded file.",
    )


class GoogleDriveUploadResponse(BaseModel):
    """Response payload returned after uploading a file to Drive."""

    file: Dict[str, Any]


class BonateTransparencySection(BaseModel):
    """Single entry within the Amministrazione Trasparente navigation."""

    category: str = Field(..., description="Categoria principale della sezione.")
    name: str = Field(..., description="Titolo della sotto-sezione.")
    url: AnyHttpUrl = Field(..., description="URL assoluto della sezione.")


class BonateTransparencySectionsResponse(BaseModel):
    """Response listing the available transparency sections."""

    sections: List[BonateTransparencySection] = Field(default_factory=list)


class BonateTransparencySearchRequest(BaseModel):
    """Request payload to search inside a transparency section."""

    section_url: AnyHttpUrl = Field(
        ...,
        description="URL della sezione Egò da consultare.",
    )
    query: str = Field(..., min_length=1, description="Testo da ricercare all'interno della sezione.")
    limit: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Numero massimo di risultati di contesto da restituire.",
    )


class BonateTransparencySearchResponse(BaseModel):
    """Snippets extracted from the raw section text."""

    section_url: AnyHttpUrl = Field(..., description="Sezione su cui è stata effettuata la ricerca.")
    query: str = Field(..., description="Testo ricercato.")
    hits: List[str] = Field(default_factory=list, description="Estratti di testo che contengono la query.")
