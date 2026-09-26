"""Turn a parsed corpus document into citable chunks (spec §6 as revised in §15).

The input is the city data layer's ``ParsedDocument`` (``gridline.db.seed.corpus``), so a chunk id is
exactly the section citation id the seed stores in ``document_sections``, e.g. ``dmp-2024#s4.2``; the
preamble is ``s0`` and ``###`` headings stay inside their parent section. Only a section longer than
``max_words`` is split, at paragraph boundaries: its first part keeps the section id and later parts get
``-p2``, ``-p3``, ... so every section id is also a chunk id. Chunk ids are a pure function of the file.
"""

import re

from gridline.db.seed.corpus import ParsedDocument
from gridline.rag.citations import citation_id
from gridline.rag.models import ChunkDraft

PARAGRAPH_BREAK = re.compile(r"\n[ \t]*\n")


def split_paragraphs(text: str, max_words: int) -> list[str]:
    """Pack whole paragraphs into parts of at most ``max_words`` words; a longer paragraph stays whole."""
    parts: list[str] = []
    current: list[str] = []
    count = 0
    for paragraph in (p.strip() for p in PARAGRAPH_BREAK.split(text)):
        if not paragraph:
            continue
        words = len(paragraph.split())
        if current and count + words > max_words:
            parts.append("\n\n".join(current))
            current, count = [], 0
        current.append(paragraph)
        count += words
    if current:
        parts.append("\n\n".join(current))
    return parts


def chunk_document(doc: ParsedDocument, *, max_words: int = 350) -> list[ChunkDraft]:
    meta = doc.meta
    chunks: list[ChunkDraft] = []
    for section in doc.sections:
        too_long = len(section.text.split()) > max_words
        parts = split_paragraphs(section.text, max_words) if too_long else [section.text]
        for part, text in enumerate(parts, start=1):
            section_id = section.section if part == 1 else f"{section.section}-p{part}"
            chunks.append(
                ChunkDraft(
                    chunk_id=citation_id(meta.document_id, section_id),
                    document_id=meta.document_id,
                    section_id=section_id,
                    section_title=section.heading,
                    position=len(chunks),
                    text=text,
                    embedding_text=f"{meta.title} — {section.heading}\n{text}",
                    kind=meta.kind,
                    zone_ids=list(meta.zone_ids),
                    hazards=list(meta.hazards),
                    metadata={
                        "category": meta.category,
                        "section_title": section.heading,
                        "part": part,
                        "word_count": len(text.split()),
                        "source_path": doc.source_path,
                        "version": meta.version,
                        "effective_date": meta.effective_date.isoformat(),
                    },
                )
            )
    seen: set[str] = set()
    for chunk in chunks:
        if chunk.chunk_id in seen:
            raise ValueError(f"colliding chunk id {chunk.chunk_id}: section ids must be unique per document")
        seen.add(chunk.chunk_id)
    return chunks
