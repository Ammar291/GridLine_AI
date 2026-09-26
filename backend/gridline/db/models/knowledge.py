"""Knowledge tables: documents, document sections, RAG chunks and policy thresholds.

``documents`` is shared by the city data layer (which seeds document metadata and per-section text) and the RAG
layer (which fills ``content_hash``/``embedding_model`` and writes ``chunks``). ``chunks`` keeps the RAG layer's
definition unchanged (ARCHITECTURE.md §4, §7); chunk ids and section ids share the ``<document_id>#s4.2`` form so
a citation id resolves in both tables.
"""

import datetime as dt
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import Date, DateTime, Float, ForeignKey, Index, Integer, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from gridline.db.base import Base

EMBEDDING_DIMENSION = 384


class Document(Base):
    """One row per corpus file in ``backend/data/corpus``."""

    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(Text, primary_key=True)  # front-matter document_id / slug, e.g. "dmp-2024"
    title: Mapped[str] = mapped_column(Text, nullable=False)
    kind: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    source_path: Mapped[str] = mapped_column(Text, nullable=False)
    date: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    # Data-layer document metadata (spec §6).
    version: Mapped[str | None] = mapped_column(Text, nullable=True)
    effective_date: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    supersedes: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    zone_ids: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, default=list)
    hazards: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, default=list)
    # RAG ingestion state. The seed writes "" for both; ingestion fills them in.
    content_hash: Mapped[str] = mapped_column(Text, nullable=False, default="")
    embedding_model: Mapped[str] = mapped_column(Text, nullable=False, default="")
    metadata_: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, nullable=False, default=dict)
    ingested_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    chunks: Mapped[list["Chunk"]] = relationship(back_populates="document", cascade="all, delete-orphan")
    sections: Mapped[list["DocumentSection"]] = relationship(
        back_populates="document", cascade="all, delete-orphan", lazy="selectin", order_by="DocumentSection.position"
    )


class DocumentSection(Base):
    """A numbered ``##`` section of a corpus document; ``id`` is the citation id ``<document_id>#<section>``."""

    __tablename__ = "document_sections"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    document_id: Mapped[str] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    section: Mapped[str] = mapped_column(Text, nullable=False)  # "s4.2", "s2018", "intro"
    heading: Mapped[str] = mapped_column(Text, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)

    document: Mapped[Document] = relationship(back_populates="sections")


class Chunk(Base):
    """RAG retrieval unit with its embedding (owned by the RAG layer)."""

    __tablename__ = "chunks"
    __table_args__ = (
        Index(
            "ix_chunks_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    document_id: Mapped[str] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    section_id: Mapped[str] = mapped_column(Text, nullable=False)
    section_title: Mapped[str] = mapped_column(Text, nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIMENSION), nullable=False)
    kind: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    zone_ids: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, default=list)
    hazards: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, default=list)
    metadata_: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, nullable=False, default=dict)

    document: Mapped[Document] = relationship(back_populates="chunks")


class PolicyThreshold(Base):
    """A numeric threshold stated in a policy section, so the detector can use the number the model can cite."""

    __tablename__ = "policy_thresholds"

    id: Mapped[str] = mapped_column(Text, primary_key=True)  # "PT-01"
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    section: Mapped[str] = mapped_column(Text, nullable=False)
    hazard: Mapped[str] = mapped_column(Text, nullable=False)
    metric: Mapped[str] = mapped_column(Text, nullable=False)
    band: Mapped[str] = mapped_column(Text, nullable=False)
    applies_to: Mapped[str] = mapped_column(Text, nullable=False)
    operator: Mapped[str] = mapped_column(Text, nullable=False)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[str] = mapped_column(Text, nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    document: Mapped[Document] = relationship(lazy="selectin")
