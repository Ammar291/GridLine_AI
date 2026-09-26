"""Chunk persistence and vector search on PostgreSQL + pgvector (spec §4, §8).

The RAG layer owns ``chunks`` plus the ingestion fingerprint of each ``documents`` row (``content_hash``,
``embedding_model``, ``ingested_at``). It never inserts or deletes documents: the city seed owns them and
projects, incidents and infrastructure changes reference them. Title and source come from ``documents``.
"""

from collections.abc import Sequence
from typing import Any, cast

from sqlalchemy import (
    ColumnElement,
    Float,
    Select,
    Text,
    delete,
    func,
    insert,
    literal,
    or_,
    select,
    text,
    update,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import InstrumentedAttribute

from gridline.db.models import Chunk, Document
from gridline.rag.citations import build_citation
from gridline.rag.models import (
    ChunkDraft,
    DocumentRecord,
    IngestError,
    RetrievalFilters,
    RetrievedChunk,
    StoredChunk,
)

AnySelect = Select[*tuple[Any, ...]]

# HNSW applies WHERE filters after the index scan and yields at most ef_search candidates. A wide candidate
# list keeps filtered and large-top_k searches complete for a corpus of this size (hundreds of chunks).
HNSW_EF_SEARCH = 1000


class ChunkStore:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def replace_chunks(
        self,
        document_id: str,
        content_hash: str,
        embedding_model: str,
        chunks: list[ChunkDraft],
        embeddings: list[list[float]],
    ) -> None:
        """In one transaction: stamp the document's fingerprint, drop its old chunks, insert the new ones."""
        if len(chunks) != len(embeddings):
            raise ValueError(f"{document_id}: {len(chunks)} chunks but {len(embeddings)} embeddings")
        if foreign := sorted({c.document_id for c in chunks} - {document_id}):
            raise ValueError(f"{document_id}: chunks belong to other documents {foreign}")
        async with self._sessions() as session, session.begin():
            stamped = await session.execute(
                update(Document)
                .where(Document.id == document_id)
                .values(content_hash=content_hash, embedding_model=embedding_model, ingested_at=func.now())
                .returning(Document.id)
            )
            if stamped.first() is None:
                raise IngestError(
                    f"document {document_id!r} is not in the documents table; "
                    "seed the database first (uv run python -m gridline.db.seed)"
                )
            await session.execute(delete(Chunk).where(Chunk.document_id == document_id))
            if chunks:
                await session.execute(
                    insert(Chunk), [_chunk_row(c, v) for c, v in zip(chunks, embeddings, strict=True)]
                )

    async def remove_chunks(self, document_id: str) -> bool:
        """Drop a document's chunks and clear its fingerprint (the row stays). True if it was indexed."""
        async with self._sessions() as session, session.begin():
            deleted = await session.execute(
                delete(Chunk).where(Chunk.document_id == document_id).returning(Chunk.id)
            )
            cleared = await session.execute(
                update(Document)
                .where(Document.id == document_id, Document.embedding_model != "")
                .values(content_hash="", embedding_model="")
                .returning(Document.id)
            )
            return bool(deleted.all()) or cleared.first() is not None

    async def list_documents(self) -> list[DocumentRecord]:
        async with self._sessions() as session:
            rows = await session.execute(
                select(
                    Document.id,
                    Document.title,
                    Document.kind,
                    Document.content_hash,
                    Document.embedding_model,
                ).order_by(Document.id)
            )
            return [
                DocumentRecord(
                    id=r.id,
                    title=r.title,
                    kind=r.kind,
                    content_hash=r.content_hash,
                    embedding_model=r.embedding_model,
                )
                for r in rows
            ]

    async def embedding_models(self) -> set[str]:
        """Embedders whose vectors are in ``chunks`` right now."""
        async with self._sessions() as session:
            rows = await session.execute(
                select(Document.embedding_model).join(Chunk, Chunk.document_id == Document.id).distinct()
            )
            return {r[0] for r in rows}

    async def count_chunks(self) -> int:
        async with self._sessions() as session:
            return (await session.execute(select(func.count()).select_from(Chunk))).scalar_one()

    async def get_chunk(self, chunk_id: str) -> StoredChunk | None:
        async with self._sessions() as session:
            row = (await session.execute(_base_select().where(Chunk.id == chunk_id))).first()
            return _to_stored(row) if row is not None else None

    async def search(
        self, query_embedding: list[float], *, top_k: int, filters: RetrievalFilters | None = None
    ) -> list[RetrievedChunk]:
        """Nearest chunks by cosine similarity, best first. A zero vector has no direction, so no match."""
        if top_k <= 0 or not any(query_embedding):
            return []
        cosine_distance = Chunk.embedding.op("<=>", return_type=Float)  # pgvector's indexed operator
        distance = cast(ColumnElement[float], cosine_distance(query_embedding))
        stmt = _apply_filters(
            _base_select().add_columns((literal(1.0) - distance).label("similarity")), filters
        )
        async with self._sessions() as session:
            await session.execute(text(f"SET LOCAL hnsw.ef_search = {HNSW_EF_SEARCH}"))
            rows = (await session.execute(stmt.order_by(distance).limit(top_k))).all()
        results: list[RetrievedChunk] = []
        for row in rows:
            stored = _to_stored(row)
            results.append(
                RetrievedChunk(
                    **stored.model_dump(), similarity=float(row.similarity), citation=build_citation(stored)
                )
            )
        return results


def _chunk_row(chunk: ChunkDraft, embedding: list[float]) -> dict[str, Any]:
    return {
        "id": chunk.chunk_id,
        "document_id": chunk.document_id,
        "section_id": chunk.section_id,
        "section_title": chunk.section_title,
        "position": chunk.position,
        "text": chunk.text,
        "embedding": embedding,
        "kind": chunk.kind,
        "zone_ids": chunk.zone_ids,
        "hazards": list(chunk.hazards),
        "metadata_": chunk.metadata,
    }


def _base_select() -> AnySelect:
    return select(
        Chunk.id,
        Chunk.document_id,
        Document.title.label("document_title"),
        Chunk.section_id,
        Chunk.section_title,
        Document.source,
        Chunk.kind,
        Chunk.zone_ids,
        Chunk.hazards,
        Chunk.text,
        Chunk.metadata_.label("metadata"),
    ).join(Document, Document.id == Chunk.document_id)


def _overlaps_or_empty(
    column: InstrumentedAttribute[list[str]], wanted: Sequence[str]
) -> ColumnElement[bool]:
    """Array overlap (any-of), where an empty array means "all" (city-wide, every hazard)."""
    overlap = column.bool_op("&&")(literal(list(wanted), type_=ARRAY(Text)))
    return or_(overlap, func.cardinality(column) == 0)


def _apply_filters(stmt: AnySelect, filters: RetrievalFilters | None) -> AnySelect:
    if filters is None:
        return stmt
    if filters.kinds:
        stmt = stmt.where(Chunk.kind.in_(filters.kinds))
    if filters.categories:
        stmt = stmt.where(Chunk.metadata_["category"].astext.in_(filters.categories))
    if filters.document_ids:
        stmt = stmt.where(Chunk.document_id.in_(filters.document_ids))
    if filters.hazards:
        stmt = stmt.where(_overlaps_or_empty(Chunk.hazards, filters.hazards))
    if filters.zone_ids:
        stmt = stmt.where(_overlaps_or_empty(Chunk.zone_ids, filters.zone_ids))
    return stmt


def _to_stored(row: Any) -> StoredChunk:
    return StoredChunk(
        chunk_id=row.id,
        document_id=row.document_id,
        document_title=row.document_title,
        section_id=row.section_id,
        section=row.section_title,
        source=row.source,
        kind=row.kind,
        category=row.metadata["category"],
        zone_ids=list(row.zone_ids),
        hazards=list(row.hazards),
        text=row.text,
        metadata=dict(row.metadata),
    )
