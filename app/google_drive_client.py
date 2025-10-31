"""Google Drive API client utilities."""

from __future__ import annotations

import io
import json
from typing import Any, Dict, List, Optional, Tuple

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload

from .settings import settings

# Cached Drive service instance reused across requests.
_drive_service = None


class GoogleDriveConfigError(RuntimeError):
    """Raised when the Google Drive integration is missing configuration."""


class GoogleDriveRequestError(RuntimeError):
    """Raised when a Google Drive API request fails."""

    def __init__(
        self,
        message: str,
        *,
        status_code: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.details = details or {}


def _get_credentials():
    """Create service account credentials configured for Google Drive."""
    if not settings.google_drive_service_account_file:
        raise GoogleDriveConfigError(
            "GOOGLE_DRIVE_SERVICE_ACCOUNT_FILE is not configured. Update your .env file.",
        )
    credentials = service_account.Credentials.from_service_account_file(
        settings.google_drive_service_account_file,
        scopes=settings.google_drive_scopes,
    )
    if settings.google_drive_delegated_user:
        credentials = credentials.with_subject(settings.google_drive_delegated_user)
    return credentials


def _get_drive_service():
    """Return a cached Drive API client instance."""
    global _drive_service  # noqa: PLW0603 - module level cache
    if _drive_service is None:
        credentials = _get_credentials()
        _drive_service = build(
            "drive",
            "v3",
            credentials=credentials,
            cache_discovery=False,
        )
    return _drive_service


def _handle_http_error(error: HttpError) -> GoogleDriveRequestError:
    """Normalize a googleapiclient HttpError into our custom exception."""
    status = getattr(error, "status_code", None)
    message = "Google Drive API request failed"
    details: Dict[str, Any] = {}

    if error.resp is not None:
        status = getattr(error.resp, "status", status)
    if error.content:
        try:
            details = json.loads(error.content.decode("utf-8"))
        except ValueError:
            details = {"raw": error.content.decode("utf-8", "replace")}
        if isinstance(details, dict):
            if isinstance(details.get("error"), dict):
                message = details["error"].get("message", message)
            else:
                message = details.get("error_description", message) or message
    return GoogleDriveRequestError(
        message,
        status_code=status,
        details=details,
    )


def list_files(
    *,
    query: Optional[str],
    page_size: int,
    page_token: Optional[str],
    fields: Optional[str],
    order_by: Optional[str],
    spaces: Optional[str],
    include_trashed: bool,
) -> Dict[str, Any]:
    """List files visible to the service account."""
    service = _get_drive_service()
    effective_query = query or ""
    if not include_trashed:
        clause = "trashed = false"
        effective_query = f"{effective_query} and {clause}" if effective_query else clause
    try:
        request = service.files().list(
            q=effective_query or None,
            pageSize=page_size,
            pageToken=page_token,
            orderBy=order_by,
            spaces=spaces,
            includeItemsFromAllDrives=True,
            supportsAllDrives=True,
            corpora="allDrives",
            fields=fields
            or "nextPageToken, files(id, name, mimeType, modifiedTime, parents, size)",
        )
        return request.execute()
    except HttpError as error:
        raise _handle_http_error(error) from error


def download_file(file_id: str) -> Tuple[Dict[str, Any], bytes]:
    """Download a file's metadata and binary content."""
    service = _get_drive_service()
    try:
        metadata = service.files().get(
            fileId=file_id,
            fields="id, name, mimeType, size, modifiedTime, md5Checksum",
            supportsAllDrives=True,
        ).execute()
        request = service.files().get_media(fileId=file_id, supportsAllDrives=True)
        buffer = io.BytesIO()
        downloader = MediaIoBaseDownload(
            buffer,
            request,
            chunksize=settings.google_drive_download_chunk_size,
        )
        done = False
        while not done:
            _, done = downloader.next_chunk()
        buffer.seek(0)
        return metadata, buffer.read()
    except HttpError as error:
        raise _handle_http_error(error) from error


def upload_file(
    *,
    name: str,
    data: bytes,
    mime_type: Optional[str],
    parents: Optional[List[str]],
    make_public: bool,
) -> Dict[str, Any]:
    """Upload a new file to Google Drive."""
    service = _get_drive_service()
    body: Dict[str, Any] = {"name": name}
    if parents:
        body["parents"] = parents

    media = MediaIoBaseUpload(
        io.BytesIO(data),
        mimetype=mime_type or "application/octet-stream",
        resumable=False,
    )

    try:
        file_metadata = service.files().create(
            body=body,
            media_body=media,
            supportsAllDrives=True,
            fields="id, name, mimeType, webViewLink, webContentLink, parents",
        ).execute()
        if make_public:
            service.permissions().create(
                fileId=file_metadata["id"],
                body={"role": "reader", "type": "anyone"},
                fields="id",
            ).execute()
        return file_metadata
    except HttpError as error:
        raise _handle_http_error(error) from error
