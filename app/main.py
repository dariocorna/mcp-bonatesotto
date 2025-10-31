"""FastAPI entrypoint for the personal MCP server."""

from __future__ import annotations

import base64
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
from .google_drive_client import (
    GoogleDriveConfigError,
    GoogleDriveRequestError,
    download_file as drive_download_file,
    list_files as drive_list_files,
    upload_file as drive_upload_file,
)
from .models import (
    FacebookCreatePostRequest,
    FacebookCreatePostResponse,
    FacebookFeedRequest,
    FacebookFeedResponse,
    FacebookProfileRequest,
    FacebookProfileResponse,
    GoogleDriveDownloadRequest,
    GoogleDriveDownloadResponse,
    GoogleDriveListFilesRequest,
    GoogleDriveListFilesResponse,
    GoogleDriveUploadRequest,
    GoogleDriveUploadResponse,
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


def _handle_drive_exception(exc: Exception) -> None:
    """Normalize Google Drive exceptions to HTTP errors."""
    if isinstance(exc, GoogleDriveConfigError):
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    if isinstance(exc, GoogleDriveRequestError):
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


@app.post("/google-drive/files", response_model=GoogleDriveListFilesResponse)
def google_drive_list_files(
    request: GoogleDriveListFilesRequest,
) -> GoogleDriveListFilesResponse:
    """List files accessible to the configured Google Drive credentials."""
    try:
        result = drive_list_files(
            query=request.query,
            page_size=request.page_size,
            page_token=request.page_token,
            fields=request.fields,
            order_by=request.order_by,
            spaces=request.spaces,
            include_trashed=request.include_trashed,
        )
    except Exception as exc:
        _handle_drive_exception(exc)
    files = result.get("files", []) if isinstance(result, dict) else []
    next_token = result.get("nextPageToken") if isinstance(result, dict) else None
    return GoogleDriveListFilesResponse(files=files, next_page_token=next_token)


@app.post("/google-drive/files/download", response_model=GoogleDriveDownloadResponse)
def google_drive_download_file(
    request: GoogleDriveDownloadRequest,
) -> GoogleDriveDownloadResponse:
    """Download the content of a Google Drive file."""
    try:
        metadata, content = drive_download_file(request.file_id)
    except Exception as exc:
        _handle_drive_exception(exc)
    encoded = base64.b64encode(content).decode("ascii")
    return GoogleDriveDownloadResponse(
        file_id=metadata.get("id", request.file_id),
        name=metadata.get("name"),
        mime_type=metadata.get("mimeType"),
        size=metadata.get("size"),
        md5_checksum=metadata.get("md5Checksum"),
        content_base64=encoded,
    )


@app.post("/google-drive/files/upload", response_model=GoogleDriveUploadResponse, status_code=201)
def google_drive_upload_file(
    request: GoogleDriveUploadRequest,
) -> GoogleDriveUploadResponse:
    """Upload a new file to Google Drive."""
    try:
        data = base64.b64decode(request.content_base64.encode("ascii"), validate=True)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="content_base64 is not valid Base64 data.") from exc

    try:
        file_metadata = drive_upload_file(
            name=request.name,
            data=data,
            mime_type=request.mime_type,
            parents=request.parents,
            make_public=request.make_public,
        )
    except Exception as exc:
        _handle_drive_exception(exc)
    return GoogleDriveUploadResponse(file=file_metadata)
