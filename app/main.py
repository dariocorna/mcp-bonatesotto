"""FastAPI entrypoint for the personal MCP server."""

from __future__ import annotations

import base64
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, PlainTextResponse

from .bonatesotto_client import (
    BonateSottoError,
    BonateSottoParsingError,
    BonateSottoRequestError,
    TransparencySection,
    list_transparency_sections,
    search_section_text,
)
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
from .local_docs import (
    LocalDocsConfigError,
    LocalDocsError,
    LocalDocsNotFoundError,
    LocalDocsPermissionError,
    list_entries as docs_list_entries,
    read_file as docs_read_file,
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
    BonateTransparencySearchRequest,
    BonateTransparencySearchResponse,
    BonateTransparencySectionsResponse,
    BonateTransparencySection,
    DriveVectorSearchRequest,
    DriveVectorSearchResponse,
    DriveVectorSearchHit,
    GoogleDriveUploadRequest,
    GoogleDriveUploadResponse,
    HealthResponse,
)
from .vector_store import (
    DriveVectorStoreConfigError,
    DriveVectorStoreError,
    DriveVectorStoreNotAvailable,
    get_drive_vector_store,
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


def _handle_docs_exception(exc: Exception) -> None:
    """Normalize local docs exceptions to HTTP errors."""
    if isinstance(exc, LocalDocsConfigError):
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if isinstance(exc, LocalDocsPermissionError):
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    if isinstance(exc, LocalDocsNotFoundError):
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if isinstance(exc, LocalDocsError):
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    raise HTTPException(status_code=500, detail=str(exc)) from exc


def _handle_bonate_exception(exc: Exception) -> None:
    """Normalize Bonate Sotto connector exceptions."""
    if isinstance(exc, BonateSottoRequestError):
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    if isinstance(exc, BonateSottoParsingError):
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if isinstance(exc, BonateSottoError):
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    raise HTTPException(status_code=500, detail=str(exc)) from exc


def _handle_drive_vector_exception(exc: Exception) -> None:
    """Normalize Drive vector store errors."""
    if isinstance(exc, DriveVectorStoreNotAvailable):
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if isinstance(exc, DriveVectorStoreConfigError):
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if isinstance(exc, DriveVectorStoreError):
        raise HTTPException(status_code=500, detail=str(exc)) from exc
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


@app.get("/local-docs/tree")
def local_docs_tree(path: str = "") -> dict:
    """List directories and files under the configured DOCS_ROOT."""
    try:
        entries = docs_list_entries(path)
    except Exception as exc:  # noqa: BLE001 - handled centrally
        _handle_docs_exception(exc)
    return {"path": path or ".", "entries": entries}


@app.get("/local-docs/file")
def local_docs_file(path: str, max_bytes: int = 1_048_576) -> dict:
    """Return the textual content of a file stored under DOCS_ROOT."""
    if max_bytes < 1 or max_bytes > 5 * 1024 * 1024:
        raise HTTPException(
            status_code=400,
            detail="max_bytes must be between 1 and 5242880 bytes.",
        )
    try:
        content = docs_read_file(path, max_bytes=max_bytes)
    except Exception as exc:  # noqa: BLE001 - handled centrally
        _handle_docs_exception(exc)
    return {"path": path, "content": content}


@app.get(
    "/bonatesotto/transparency/sections",
    response_model=BonateTransparencySectionsResponse,
)
def bonate_transparency_sections(q: str | None = None) -> BonateTransparencySectionsResponse:
    """Return the Amministrazione Trasparente sections and sub links."""
    try:
        sections = list_transparency_sections(query=q)
    except Exception as exc:  # noqa: BLE001 - handled centrally
        _handle_bonate_exception(exc)
    payload = [
        BonateTransparencySection(category=section.category, name=section.name, url=section.url)
        for section in sections
    ]
    return BonateTransparencySectionsResponse(sections=payload)


@app.post(
    "/bonatesotto/transparency/search",
    response_model=BonateTransparencySearchResponse,
)
def bonate_transparency_search(
    payload: BonateTransparencySearchRequest,
) -> BonateTransparencySearchResponse:
    """Search for a keyword inside a specific transparency section."""
    try:
        hits = search_section_text(
            payload.section_url,
            payload.query,
            limit=payload.limit,
        )
    except Exception as exc:  # noqa: BLE001 - handled centrally
        _handle_bonate_exception(exc)
    return BonateTransparencySearchResponse(
        section_url=payload.section_url,
        query=payload.query,
        hits=hits,
    )


@app.post("/google-drive/vector-search", response_model=DriveVectorSearchResponse)
def google_drive_vector_search(
    payload: DriveVectorSearchRequest,
) -> DriveVectorSearchResponse:
    """Perform a vector similarity search over Drive document embeddings."""
    try:
        store = get_drive_vector_store()
        limit = payload.limit or settings.drive_vector_default_k
        results = store.search(
            query=payload.query,
            query_embedding=payload.query_embedding,
            top_k=limit,
        )
    except Exception as exc:  # noqa: BLE001 - handled centrally
        _handle_drive_vector_exception(exc)

    hits: list[DriveVectorSearchHit] = []
    for score, record in results:
        hits.append(
            DriveVectorSearchHit(
                score=float(score),
                metadata=record.metadata,
                text_extract=record.text_extract,
            )
        )
    return DriveVectorSearchResponse(query=payload.query, hits=hits)


@app.get("/ui/instructions")
def ui_instructions():
    """Serve a lightweight HTML page for editing supplemental instructions."""
    page_path = Path(__file__).resolve().parent.parent / "static" / "instructions.html"
    return FileResponse(page_path)


@app.get("/api/instructions")
def get_instructions():
    """Return the bundled static instructions alongside editable extras."""
    import json

    store = Path(".mcp_cache") / "instructions.json"

    static_path = Path(__file__).resolve().parent.parent / "static" / "instructions_static.md"
    if not static_path.exists():
        static_path = Path(".mcp_cache") / "instructions_static.md"

    try:
        static_text = static_path.read_text(encoding="utf-8")
    except OSError:
        static_text = ""

    extra = ""
    if store.exists():
        try:
            payload = json.loads(store.read_text(encoding="utf-8"))
            extra = payload.get("extra") or payload.get("instructions") or ""
        except (OSError, json.JSONDecodeError):
            extra = ""

    return {"static": static_text, "extra": extra}


@app.post("/api/instructions")
def post_instructions(payload: dict):
    """Persist editable instructions to the cache directory."""
    import json

    if not isinstance(payload, dict) or "extra" not in payload:
        raise HTTPException(
            status_code=400,
            detail="Missing 'extra' field; post JSON like {'extra': '...'}",
        )

    store = Path(".mcp_cache") / "instructions.json"
    try:
        store.write_text(
            json.dumps({"extra": payload.get("extra")}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except OSError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return {"status": "ok"}
