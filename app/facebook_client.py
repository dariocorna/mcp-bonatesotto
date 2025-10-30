"""Facebook Graph API client utilities."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import requests
from requests import Response

from .settings import settings

logger = logging.getLogger(__name__)


class FacebookConfigError(RuntimeError):
    """Raised when a configuration required for the Facebook connector is missing or invalid."""


class FacebookRequestError(RuntimeError):
    """Raised when a Facebook Graph API request fails."""

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


def _log_debug(message: str, payload: Any | None = None) -> None:
    """Log debug messages when enabled in settings."""
    if not settings.facebook_enable_debug:
        return
    if payload is None:
        logger.debug("[facebook] %s", message)
    else:
        logger.debug("[facebook] %s: %s", message, payload)


def _require_access_token() -> str:
    """Ensure an access token is configured."""
    if not settings.facebook_access_token:
        raise FacebookConfigError(
            "FACEBOOK_ACCESS_TOKEN is not configured. Please update your .env file.",
        )
    return settings.facebook_access_token


def _build_url(path: str) -> str:
    """Create the full Graph API URL respecting the configured version."""
    path = path.lstrip("/")
    return f"{settings.facebook_base_url}/{settings.facebook_graph_api_version}/{path}"


def _as_unix_timestamp(value: Optional[datetime]) -> Optional[int]:
    """Convert a datetime to a Unix timestamp (UTC)."""
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return int(value.timestamp())


def _request(
    method: str,
    path: str,
    *,
    params: Optional[Dict[str, Any]] = None,
    data: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Perform an HTTP request against the Graph API."""
    token = _require_access_token()
    url = _build_url(path)
    params = dict(params or {})
    params["access_token"] = token

    _log_debug(
        f"Request {method.upper()} {url}",
        {"params": params, "data": data},
    )

    try:
        response: Response = requests.request(
            method=method.upper(),
            url=url,
            params=params,
            data=data,
            timeout=settings.facebook_timeout,
        )
    except requests.RequestException as exc:  # pragma: no cover - network errors
        _log_debug("Request failed with exception", {"error": str(exc)})
        raise FacebookRequestError(f"Facebook API request failed: {exc}") from exc

    _log_debug(f"Response status {response.status_code}")

    try:
        payload = response.json()
    except ValueError as exc:
        _log_debug("Non-JSON response body", {"body": response.text})
        raise FacebookRequestError(
            "Facebook API returned a non-JSON response",
            status_code=response.status_code,
        ) from exc

    if not response.ok:
        details = payload.get("error") if isinstance(payload, dict) else None
        message = (
            details.get("message")
            if isinstance(details, dict) and "message" in details
            else "Facebook API request failed"
        )
        _log_debug("API responded with error", {"message": message, "details": details})
        raise FacebookRequestError(
            message,
            status_code=response.status_code,
            details=details or (payload if isinstance(payload, dict) else {}),
        )

    _log_debug("API responded with payload", payload)
    if isinstance(payload, dict):
        return payload

    # The Graph API should always return a dict, but we normalise just in case.
    return {"data": payload}


def fetch_profile(
    *,
    target_id: str = "me",
    fields: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Fetch basic profile information for a user or page."""
    params: Dict[str, Any] = {}
    if fields:
        params["fields"] = ",".join(fields)
    elif settings.facebook_default_fields:
        params["fields"] = ",".join(settings.facebook_default_fields)
    return _request("GET", target_id, params=params)


def get_feed(
    *,
    target_id: str = "me",
    limit: Optional[int] = None,
    fields: Optional[List[str]] = None,
    since: Optional[datetime] = None,
    until: Optional[datetime] = None,
    before: Optional[str] = None,
    after: Optional[str] = None,
) -> Dict[str, Any]:
    """Fetch feed entries for a user or page."""
    params: Dict[str, Any] = {}
    field_list = fields or settings.facebook_default_fields
    if field_list:
        params["fields"] = ",".join(field_list)
    params["limit"] = str(limit or settings.facebook_default_feed_limit)
    since_ts = _as_unix_timestamp(since)
    until_ts = _as_unix_timestamp(until)
    if since_ts:
        params["since"] = str(since_ts)
    if until_ts:
        params["until"] = str(until_ts)
    if before:
        params["before"] = before
    if after:
        params["after"] = after
    return _request("GET", f"{target_id}/feed", params=params)


def create_post(
    *,
    target_id: str,
    message: str,
    link: Optional[str],
    published: bool,
    scheduled_publish_time: Optional[datetime],
    privacy: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """Create a new post on a user or page feed."""
    if scheduled_publish_time is not None and published:
        raise FacebookConfigError(
            "Scheduled posts require `published` to be set to false.",
        )

    data: Dict[str, Any] = {
        "message": message,
        "published": "true" if published else "false",
    }
    if link:
        data["link"] = link
    if scheduled_publish_time is not None:
        data["scheduled_publish_time"] = str(_as_unix_timestamp(scheduled_publish_time))
    if privacy is not None:
        data["privacy"] = json.dumps(privacy)

    return _request("POST", f"{target_id}/feed", data=data)
