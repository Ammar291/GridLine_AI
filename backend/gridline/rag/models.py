"""Typed boundary models for the RAG layer (spec §8).

The document vocabulary (``DocumentKind``, ``DocumentCategory``, ``Hazard``) is the city data layer's front
matter, so ``chunks.kind`` always equals ``documents.kind`` and filters use the same words as the corpus.
A chunk's category lives in its ``metadata["category"]``. Zone ids are plain strings (``Z-HV``).
"""

from typing import Any

from pydantic import BaseModel, Field

from gridline.city.schema_history import DocumentCategory, DocumentKind, Hazard

__all__ = [
    "ChunkDraft",
    "Citation",
    "DocumentCategory",
    "DocumentKind",
    "DocumentRecord",
    "EmbeddingModelMismatchError",
    "Hazard",
    "IngestError",
    "IngestReport",
    "RetrievalFilters",
    "RetrievedChunk",
    "StoredChunk",
]


class EmbeddingModelMismatchError(Exception):
    """The live embedder differs from the one the corpus was indexed with. Re-run ingestion."""


class IngestError(Exception):
    """The database cannot take this corpus (e.g. a document is not seeded). Nothing was written."""


class ChunkDraft(BaseModel):
    """A chunk ready to embed and store; ``chunk_id`` is the citation id ``<document_id>#<section_id>``."""

    chunk_id: str
    document_id: str
    section_id: str
    section_title: str
    position: int
    text: str
    embedding_text: str
    kind: DocumentKind
    zone_ids: list[str]
    hazards: list[Hazard]
    metadata: dict[str, Any] = Field(default_factory=dict)


class RetrievalFilters(BaseModel):
    """Any-of filters; ``None`` or ``[]`` means no filter. City-wide chunks (empty list) match every zone
    filter, and chunks with no hazards match every hazard filter."""

    kinds: list[DocumentKind] | None = None
    categories: list[DocumentCategory] | None = None
    hazards: list[Hazard] | None = None
    zone_ids: list[str] | None = None
    document_ids: list[str] | None = None


class Citation(BaseModel):
    id: str
    document_title: str
    section: str
    source: str
    text: str


class StoredChunk(BaseModel):
    chunk_id: str
    document_id: str
    document_title: str
    section_id: str
    section: str
    source: str
    kind: DocumentKind
    category: DocumentCategory
    zone_ids: list[str]
    hazards: list[Hazard]
    text: str
    metadata: dict[str, Any]


class RetrievedChunk(StoredChunk):
    similarity: float
    citation: Citation


class DocumentRecord(BaseModel):
    """A ``documents`` row as the RAG layer sees it; an empty ``embedding_model`` means not indexed."""

    id: str
    title: str
    kind: DocumentKind
    content_hash: str
    embedding_model: str


class IngestReport(BaseModel):
    documents_added: int = 0
    documents_updated: int = 0
    documents_unchanged: int = 0
    documents_removed: int = 0
    chunks_written: int = 0
    embedding_model: str
    duration_s: float = 0.0
