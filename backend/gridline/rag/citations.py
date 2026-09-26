"""Citation ids are chunk ids, so a citation can only point at a stored chunk (spec §8)."""

from collections.abc import Iterable

from gridline.rag.models import Citation, StoredChunk


def citation_id(document_id: str, section_id: str) -> str:
    return f"{document_id}#{section_id}"


def build_citation(chunk: StoredChunk) -> Citation:
    return Citation(
        id=chunk.chunk_id,
        document_title=chunk.document_title,
        section=chunk.section,
        source=chunk.source,
        text=chunk.text,
    )


def format_citation(c: Citation) -> str:
    return f"[{c.id}] {c.document_title} — {c.section} ({c.source})"


def validate_citation_ids(cited: Iterable[str], allowed: Iterable[str]) -> list[str]:
    """Return the cited ids that are not in ``allowed``, deduplicated, in first-seen order."""
    allowed_set = set(allowed)
    unknown: list[str] = []
    for cid in cited:
        if cid not in allowed_set and cid not in unknown:
            unknown.append(cid)
    return unknown
