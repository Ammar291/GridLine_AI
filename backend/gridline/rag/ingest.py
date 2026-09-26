"""Index the corpus: parse, chunk, embed, store. Console script ``gridline-ingest`` (spec §9).

Documents are parsed by the city seed's parser (``gridline.db.seed.corpus``) and must already be seeded
(``python -m gridline.db.seed``). Ingestion writes only ``chunks`` and each document's fingerprint
(``content_hash``, ``embedding_model``); it never inserts or deletes ``documents`` rows. A document whose
file hash and embedder are unchanged is skipped, so chunk ids and stored citations stay stable.
"""

import argparse
import asyncio
import hashlib
import logging
import sys
import time
from collections.abc import Sequence
from pathlib import Path

from gridline.config import Settings
from gridline.db.engine import create_engine, session_factory
from gridline.db.schema import create_schema, truncate_corpus
from gridline.db.seed.corpus import CorpusError, ParsedDocument, parse_document
from gridline.rag.chunker import chunk_document
from gridline.rag.embedder import Embedder, build_embedder
from gridline.rag.models import ChunkDraft, IngestError, IngestReport
from gridline.rag.store import ChunkStore

log = logging.getLogger(__name__)
EMBED_BATCH = 64


def read_corpus(corpus_dir: Path) -> list[tuple[ParsedDocument, str]]:
    """Every ``*.md`` file, parsed by the shared corpus parser, with the sha256 of its bytes."""
    if not corpus_dir.is_dir():
        raise CorpusError(str(corpus_dir), "corpus directory not found")
    paths = sorted(corpus_dir.glob("*.md"))
    if not paths:
        raise CorpusError(str(corpus_dir), "no Markdown (*.md) documents found")
    return [(parse_document(p), hashlib.sha256(p.read_bytes()).hexdigest()) for p in paths]


async def _embed(embedder: Embedder, chunks: list[ChunkDraft]) -> list[list[float]]:
    texts = [c.embedding_text for c in chunks]
    vectors: list[list[float]] = []
    for i in range(0, len(texts), EMBED_BATCH):
        vectors.extend(await asyncio.to_thread(embedder.embed_documents, texts[i : i + EMBED_BATCH]))
    return vectors


async def ingest(
    *, database_url: str, corpus_dir: Path, embedder: Embedder, reset: bool = False
) -> IngestReport:
    """Bring ``chunks`` in line with ``corpus_dir``. Every check runs before the first write."""
    started = time.perf_counter()
    corpus = [(doc, digest, chunk_document(doc)) for doc, digest in read_corpus(corpus_dir)]
    engine = create_engine(database_url)
    try:
        await create_schema(engine)
        store = ChunkStore(session_factory(engine))
        known = {r.id: r for r in await store.list_documents()}
        if missing := [doc.meta.document_id for doc, _, _ in corpus if doc.meta.document_id not in known]:
            raise IngestError(
                f"documents not in the database: {missing}; seed first (uv run python -m gridline.db.seed)"
            )
        if reset:
            await truncate_corpus(engine)
            known = {r.id: r for r in await store.list_documents()}
        report = IngestReport(embedding_model=embedder.name)
        for doc, digest, chunks in corpus:
            prior = known.pop(doc.meta.document_id)
            if prior.content_hash == digest and prior.embedding_model == embedder.name:
                report.documents_unchanged += 1
                continue
            vectors = await _embed(embedder, chunks)
            await store.replace_chunks(doc.meta.document_id, digest, embedder.name, chunks, vectors)
            report.chunks_written += len(chunks)
            if prior.embedding_model:
                report.documents_updated += 1
            else:
                report.documents_added += 1
            log.info("indexed %s (%d chunks)", doc.meta.document_id, len(chunks))
        for stale in known.values():  # seeded documents that are not in this corpus: unindex, keep the row
            if await store.remove_chunks(stale.id):
                report.documents_removed += 1
        report.duration_s = round(time.perf_counter() - started, 3)
        return report
    finally:
        await engine.dispose()


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="gridline-ingest", description="Index the Nandipur knowledge corpus."
    )
    parser.add_argument("--corpus", type=Path, default=None, help="corpus directory (default: CORPUS_DIR)")
    parser.add_argument("--reset", action="store_true", help="clear every chunk and fingerprint first")
    parser.add_argument("--provider", choices=["auto", "fastembed", "hashed"], default=None)
    parser.add_argument("--database-url", default=None, help="SQLAlchemy URL (default: DATABASE_URL)")
    parser.add_argument("-v", "--verbose", action="store_true", help="log each indexed document")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING, format="%(levelname)s %(message)s"
    )
    settings = Settings()
    embedder = build_embedder(args.provider or settings.embedding_provider, settings.embedding_model)
    job = ingest(
        database_url=args.database_url or settings.database_url,
        corpus_dir=args.corpus or settings.resolved_corpus_dir(),
        embedder=embedder,
        reset=args.reset,
    )
    loop_factory = asyncio.SelectorEventLoop if sys.platform == "win32" else None  # psycopg async on Windows
    try:
        report = asyncio.run(job, loop_factory=loop_factory)
    except (CorpusError, IngestError) as exc:
        print(f"ingest failed: {exc}", file=sys.stderr)
        return 1
    for key, value in report.model_dump().items():
        print(f"{key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
