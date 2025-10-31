"""Utilities for browsing local documentation folders."""

from __future__ import annotations

from pathlib import Path
from typing import List, Dict

from .settings import settings

# Hard-limit reads to avoid shipping large binaries through the API.
MAX_FILE_BYTES = 5 * 1024 * 1024  # 5 MiB


class LocalDocsError(RuntimeError):
    """Base class for local documentation errors."""


class LocalDocsConfigError(LocalDocsError):
    """Raised when DOCS_ROOT is missing or invalid."""


class LocalDocsPermissionError(LocalDocsError):
    """Raised when access falls outside the allowed DOCS_ROOT."""


class LocalDocsNotFoundError(LocalDocsError):
    """Raised when the requested path does not exist."""


def _resolve_root() -> Path:
    """Return the configured documentation root ensuring it exists."""
    docs_root = settings.docs_root
    if not docs_root:
        raise LocalDocsConfigError("DOCS_ROOT is not configured in the environment.")

    root = Path(docs_root).expanduser().resolve()
    if not root.exists():
        raise LocalDocsNotFoundError(f"DOCS_ROOT does not exist: {root}")
    if not root.is_dir():
        raise LocalDocsConfigError(f"DOCS_ROOT is not a directory: {root}")
    return root


def _resolve_path(relative_path: str) -> Path:
    """Return a safe path inside DOCS_ROOT, blocking traversal."""
    root = _resolve_root()
    target = (root / relative_path).resolve()

    if root == target:
        return target

    if root not in target.parents:
        raise LocalDocsPermissionError("Requested path escapes DOCS_ROOT.")
    return target


def list_entries(relative_path: str = "") -> List[Dict[str, str]]:
    """List files and folders inside the provided relative path."""
    directory = _resolve_path(relative_path)
    if not directory.exists():
        raise LocalDocsNotFoundError("Requested path not found.")
    if not directory.is_dir():
        raise LocalDocsPermissionError("Requested path is not a directory.")

    entries: List[Dict[str, str]] = []
    for child in sorted(directory.iterdir(), key=lambda p: p.name.lower()):
        if child.name.startswith("."):
            continue
        entries.append(
            {
                "name": child.name,
                "path": str(child.relative_to(_resolve_root())),
                "type": "directory" if child.is_dir() else "file",
            }
        )
    return entries


def read_file(relative_path: str, *, max_bytes: int | None = None) -> str:
    """Read a text file inside DOCS_ROOT with basic size checks."""
    file_path = _resolve_path(relative_path)
    if not file_path.exists() or not file_path.is_file():
        raise LocalDocsNotFoundError("File not found.")

    limit = max_bytes if max_bytes is not None else MAX_FILE_BYTES
    try:
        size = file_path.stat().st_size
    except OSError as exc:
        raise LocalDocsError(str(exc)) from exc
    if size > limit:
        raise LocalDocsError(
            f"File exceeds allowed size ({size} bytes > {limit} bytes).",
        )

    try:
        return file_path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise LocalDocsError("Unable to decode file as UTF-8 text.") from exc
    except OSError as exc:
        raise LocalDocsError(str(exc)) from exc
