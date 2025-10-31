"""Client utilities for scraping the Comune di Bonate Sotto institutional site."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from .settings import settings


class BonateSottoError(RuntimeError):
    """Base error for Bonate Sotto connector."""


class BonateSottoRequestError(BonateSottoError):
    """Raised when the remote site cannot be reached."""


class BonateSottoParsingError(BonateSottoError):
    """Raised when the expected structure cannot be parsed."""


@dataclass
class TransparencySection:
    """Represents a subsection entry within Amministrazione Trasparente."""

    category: str
    name: str
    url: str


def _http_get(path: str, *, timeout: Optional[int] = None) -> str:
    """Perform an HTTP GET resolving relative paths against the configured base URL."""
    base_url = str(settings.bonate_base_url)
    url = urljoin(base_url + "/", path)
    try:
        response = requests.get(url, timeout=timeout or settings.bonate_timeout)
        response.raise_for_status()
    except requests.RequestException as exc:  # pragma: no cover - network
        raise BonateSottoRequestError(str(exc)) from exc
    return response.text


def list_transparency_sections(query: Optional[str] = None) -> List[TransparencySection]:
    """Scrape the transparency landing page and extract all section links."""
    html = _http_get("/amministrazione/trasparenza/trasparenza.html")
    soup = BeautifulSoup(html, "html.parser")

    matches: List[TransparencySection] = []
    normalized_query = query.lower() if query else None

    for collapse in soup.select("ul.link-sublist"):
        parent = collapse.find_previous("div", class_="d-flex")
        title_span = parent.select_one(".list-item-title") if parent else None
        category = title_span.get_text(strip=True) if title_span else "Senza categoria"

        for anchor in collapse.select("a.text-decoration-none"):
            href = anchor.get("href")
            name = anchor.get_text(strip=True)
            if not href or not name:
                continue
            url = urljoin(str(settings.bonate_base_url) + "/", href)
            if normalized_query and normalized_query not in name.lower() and normalized_query not in category.lower():
                continue
            matches.append(TransparencySection(category=category, name=name, url=url))

    if normalized_query and not matches:
        raise BonateSottoParsingError(
            f"Nessuna sezione trovata per la query '{query}'. Verificare il filtro o consultare manualmente il sito.",
        )
    return matches


def load_section_text(section_url: str) -> str:
    """Download a transparency subpage and return raw text content."""
    html = _http_get(section_url)
    soup = BeautifulSoup(html, "html.parser")
    # Remove script and style tags to shrink text
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    text = soup.get_text("\n")
    lines = [line.strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line)


def search_section_text(section_url: str, query: str, limit: int = 5) -> List[str]:
    """Search for a keyword inside the raw text of a transparency subpage and return snippets."""
    if not query:
        raise ValueError("La query di ricerca non può essere vuota.")
    text = load_section_text(section_url)
    lowered = query.lower()
    snippets: List[str] = []
    for paragraph in _split_paragraphs(text):
        if lowered in paragraph.lower():
            snippets.append(paragraph.strip())
            if len(snippets) >= limit:
                break
    return snippets


def _split_paragraphs(text: str) -> Iterable[str]:
    """Split a text block into paragraphs removing duplicates."""
    seen = set()
    for block in text.split("\n\n"):
        normalized = block.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        yield normalized
