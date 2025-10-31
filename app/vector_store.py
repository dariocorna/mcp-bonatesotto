"""Vector store utilities for Google Drive document embeddings."""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

try:  # Optional dependency; only needed when encoding queries.
    from sentence_transformers import SentenceTransformer  # type: ignore
except ImportError:  # pragma: no cover - optional dependency
    SentenceTransformer = None  # type: ignore

from .settings import settings


class DriveVectorStoreError(RuntimeError):
    """Base class for vector store related errors."""


class DriveVectorStoreConfigError(DriveVectorStoreError):
    """Raised when configuration is incomplete."""


class DriveVectorStoreNotAvailable(DriveVectorStoreError):
    """Raised when the vector store is disabled or missing."""


@dataclass
class DriveVectorRecord:
    """Represents a single document entry in the vector store."""

    metadata: Dict[str, Any]
    text_extract: Optional[str]


class DriveVectorStore:
    """In-memory cosine similarity store for Drive documents."""

    def __init__(
        self,
        embeddings_path: Path,
        metadata_path: Path,
        documents_path: Path,
        model_name: Optional[str],
    ) -> None:
        if not embeddings_path.exists():
            raise DriveVectorStoreConfigError(f"Drive embeddings file not found: {embeddings_path}")
        if not metadata_path.exists():
            raise DriveVectorStoreConfigError(f"Drive metadata file not found: {metadata_path}")
        if not documents_path.exists():
            raise DriveVectorStoreConfigError(f"Drive documents file not found: {documents_path}")

        self.embeddings = self._load_embeddings(embeddings_path)
        self.records = self._load_records(metadata_path, documents_path)
        if len(self.embeddings) != len(self.records):
            raise DriveVectorStoreConfigError(
                f"Mismatch between embeddings ({len(self.embeddings)}) and records ({len(self.records)}).",
            )

        self.model_name = model_name
        self._model: Optional[SentenceTransformer] = None

    @staticmethod
    def _load_embeddings(path: Path) -> np.ndarray:
        embeddings = np.load(path)
        if embeddings.ndim == 1:
            embeddings = embeddings.reshape(1, -1)
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return embeddings / norms

    @staticmethod
    def _load_records(metadata_path: Path, documents_path: Path) -> List[DriveVectorRecord]:
        with metadata_path.open("r", encoding="utf-8") as f:
            metadata_content = json.load(f)

        if isinstance(metadata_content, dict):
            if "items" in metadata_content and isinstance(metadata_content["items"], list):
                metadata_entries = metadata_content["items"]
            else:
                metadata_entries = list(metadata_content.values())
        elif isinstance(metadata_content, list):
            metadata_entries = metadata_content
        else:
            raise DriveVectorStoreConfigError("Metadata JSON must be an object or a list.")

        documents: List[Optional[str]] = []
        with documents_path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    documents.append(None)
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    documents.append(None)
                    continue
                text_extract = (
                    obj.get("text_extract")
                    or obj.get("text")
                    or obj.get("content")
                    or obj.get("body")
                )
                documents.append(text_extract)

        if len(metadata_entries) != len(documents):
            raise DriveVectorStoreConfigError(
                f"Metadata entries ({len(metadata_entries)}) and document extracts ({len(documents)}) differ.",
            )

        records: List[DriveVectorRecord] = []
        for meta, text in zip(metadata_entries, documents):
            if not isinstance(meta, dict):
                meta = {"value": meta}
            records.append(DriveVectorRecord(metadata=meta, text_extract=text))
        return records

    def _ensure_model(self) -> SentenceTransformer:
        if self._model is not None:
            return self._model
        if SentenceTransformer is None:  # pragma: no cover - optional dependency guard
            raise DriveVectorStoreConfigError(
                "sentence-transformers non è installato. "
                "Installare il pacchetto o fornire 'query_embedding'.",
            )
        if not self.model_name:
            raise DriveVectorStoreConfigError(
                "Nessun modello configurato. Impostare DRIVE_VECTOR_MODEL_NAME oppure fornire 'query_embedding'.",
            )
        self._model = SentenceTransformer(self.model_name)
        return self._model

    def encode_query(self, query: str) -> np.ndarray:
        model = self._ensure_model()
        embedding = model.encode(query, normalize_embeddings=True)
        if embedding.ndim == 1:
            return embedding
        return embedding[0]

    def search(
        self,
        *,
        query: Optional[str],
        query_embedding: Optional[List[float]],
        top_k: int,
    ) -> List[Tuple[float, DriveVectorRecord]]:
        if query_embedding is not None:
            vector = np.asarray(query_embedding, dtype=np.float32)
            if vector.ndim != 1:
                raise DriveVectorStoreConfigError("query_embedding deve essere un vettore monodimensionale.")
            norm = np.linalg.norm(vector)
            if norm == 0:
                raise DriveVectorStoreConfigError("query_embedding non può essere il vettore nullo.")
            vector = vector / norm
        else:
            if not query:
                raise DriveVectorStoreConfigError("Fornire una query testuale oppure un query_embedding.")
            vector = self.encode_query(query)

        scores = self.embeddings @ vector
        if top_k < len(scores):
            top_indices = np.argpartition(scores, -top_k)[-top_k:]
            top_indices = top_indices[np.argsort(scores[top_indices])[::-1]]
        else:
            top_indices = np.argsort(scores)[::-1]

        results: List[Tuple[float, DriveVectorRecord]] = []
        for idx in top_indices:
            score = float(scores[idx])
            record = self.records[idx]
            results.append((score, record))
        return results


_DRIVE_VECTOR_STORE: Optional[DriveVectorStore] = None
_LOCK = threading.Lock()


def get_drive_vector_store() -> DriveVectorStore:
    """Return the singleton Drive vector store instance."""
    global _DRIVE_VECTOR_STORE

    if not settings.drive_vector_enabled:
        raise DriveVectorStoreNotAvailable("L'indice vettoriale Drive è disabilitato.")

    if _DRIVE_VECTOR_STORE is not None:
        return _DRIVE_VECTOR_STORE

    with _LOCK:
        if _DRIVE_VECTOR_STORE is None:
            embeddings_path = settings.drive_vector_embeddings_path
            metadata_path = settings.drive_vector_metadata_path
            documents_path = settings.drive_vector_documents_path

            if not embeddings_path or not metadata_path or not documents_path:
                raise DriveVectorStoreConfigError(
                    "Configurazione incompleta per l'indice Drive: "
                    "impostare DRIVE_VECTOR_EMBEDDINGS_PATH, DRIVE_VECTOR_METADATA_PATH e DRIVE_VECTOR_DOCUMENTS_PATH.",
                )

            _DRIVE_VECTOR_STORE = DriveVectorStore(
                embeddings_path=embeddings_path,
                metadata_path=metadata_path,
                documents_path=documents_path,
                model_name=settings.drive_vector_model_name,
            )
    return _DRIVE_VECTOR_STORE
