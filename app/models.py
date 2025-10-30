"""Pydantic models for request and response payloads."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, HttpUrl


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
