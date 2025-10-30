"""FastAPI entrypoint for the personal MCP server."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import PlainTextResponse

from .facebook_client import (
    FacebookConfigError,
    FacebookRequestError,
    create_post,
    fetch_profile,
    get_feed,
)
from .models import (
    FacebookCreatePostRequest,
    FacebookCreatePostResponse,
    FacebookFeedRequest,
    FacebookFeedResponse,
    FacebookProfileRequest,
    FacebookProfileResponse,
    HealthResponse,
)
app = FastAPI(title="Personal Facebook MCP Server")

# Ensure cache directory exists for compatibility with the reference server.
Path(".mcp_cache").mkdir(exist_ok=True)


@app.get("/", response_class=PlainTextResponse)
def root() -> str:
    """Simple textual landing page."""
    return "Facebook MCP server ready."


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Health-check endpoint."""
    return HealthResponse()


def _handle_facebook_exception(exc: Exception) -> None:
    """Raise an HTTPException based on connector errors."""
    if isinstance(exc, FacebookConfigError):
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    if isinstance(exc, FacebookRequestError):
        detail = {"message": exc.message}
        if exc.details:
            detail["details"] = exc.details
        raise HTTPException(status_code=exc.status_code or 502, detail=detail) from exc
    raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/facebook/profile", response_model=FacebookProfileResponse)
def facebook_profile(request: FacebookProfileRequest) -> FacebookProfileResponse:
    """Fetch information about a Facebook profile or page."""
    try:
        profile = fetch_profile(
            target_id=request.target_id,
            fields=request.fields,
        )
    except Exception as exc:
        _handle_facebook_exception(exc)
    return FacebookProfileResponse(profile=profile)


@app.post("/facebook/feed", response_model=FacebookFeedResponse)
def facebook_feed(request: FacebookFeedRequest) -> FacebookFeedResponse:
    """Fetch feed entries for a profile or page."""
    try:
        feed = get_feed(
            target_id=request.target_id,
            limit=request.limit,
            fields=request.fields,
            since=request.since,
            until=request.until,
            before=request.before,
            after=request.after,
        )
    except Exception as exc:
        _handle_facebook_exception(exc)
    posts = feed.get("data", []) if isinstance(feed, dict) else []
    paging = feed.get("paging") if isinstance(feed, dict) else None
    return FacebookFeedResponse(posts=posts, paging=paging)


@app.post("/facebook/posts", response_model=FacebookCreatePostResponse, status_code=201)
def facebook_create_post(
    request: FacebookCreatePostRequest,
) -> FacebookCreatePostResponse:
    """Create a new Facebook post."""
    try:
        result = create_post(
            target_id=request.target_id,
            message=request.message,
            link=str(request.link) if request.link else None,
            published=request.published,
            scheduled_publish_time=request.scheduled_publish_time,
            privacy=request.privacy,
        )
    except Exception as exc:
        _handle_facebook_exception(exc)
    post_id = result.get("id") if isinstance(result, dict) else None
    if not post_id:
        raise HTTPException(
            status_code=502,
            detail={"message": "Facebook API returned an unexpected response."},
        )
    return FacebookCreatePostResponse(id=post_id, raw=result)
