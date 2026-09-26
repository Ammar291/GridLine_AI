import asyncio
import hashlib
import shutil

import pytest
from sqlalchemy import func, select

from gridline.db.models import Chunk, Document
from gridline.db.seed.corpus import CorpusError
from gridline.rag.embedder import HashedEmbedder
from gridline.rag.ingest import ingest, main
from gridline.rag.models import IngestError
from gridline.rag.store import ChunkStore
from tests.conftest import RAG_FIXTURES

FIXTURE_IDS = ["test-fire-sop", "test-policy", "test-riverside-report"]


class RenamedEmbedder(HashedEmbedder):
    @property
    def name(self) -> str:
        return "hashed:v2"


async def _chunk_ids(sessions) -> list[str]:
    async with sessions() as s:
        return list((await s.execute(select(Chunk.id).order_by(Chunk.id))).scalars())


async def _fixture_document_count(sessions) -> int:
    async with sessions() as s:
        stmt = select(func.count()).select_from(Document).where(Document.id.in_(FIXTURE_IDS))
        return (await s.execute(stmt)).scalar_one()


def _copy_fixtures(tmp_path):
    shutil.copytree(RAG_FIXTURES, tmp_path / "corpus")
    return tmp_path / "corpus"


async def test_ingest_fixture_corpus(rag_documents, db_url):
    report = await ingest(database_url=db_url, corpus_dir=RAG_FIXTURES, embedder=HashedEmbedder())
    assert report.documents_added == 3 and report.documents_updated == 0 and report.documents_unchanged == 0
    assert report.documents_removed == 0 and report.chunks_written == 9
    assert report.embedding_model == "hashed:v1" and report.duration_s >= 0
    store = ChunkStore(rag_documents)
    assert await store.count_chunks() == 9
    assert await store.get_chunk("test-policy#s4.2") is not None
    policy = next(r for r in await store.list_documents() if r.id == "test-policy")
    assert policy.content_hash == hashlib.sha256((RAG_FIXTURES / "test-policy.md").read_bytes()).hexdigest()
    assert policy.embedding_model == "hashed:v1"


async def test_reingest_unchanged_is_noop(rag_documents, db_url):
    await ingest(database_url=db_url, corpus_dir=RAG_FIXTURES, embedder=HashedEmbedder())
    before = await _chunk_ids(rag_documents)
    report = await ingest(database_url=db_url, corpus_dir=RAG_FIXTURES, embedder=HashedEmbedder())
    assert report.documents_unchanged == 3 and report.documents_added == 0 and report.documents_updated == 0
    assert report.chunks_written == 0
    assert await _chunk_ids(rag_documents) == before  # stored citations stay valid


async def test_edited_document_replaces_chunks(rag_documents, db_url, tmp_path):
    corpus = _copy_fixtures(tmp_path)
    await ingest(database_url=db_url, corpus_dir=corpus, embedder=HashedEmbedder())
    fire = corpus / "test-fire-sop.md"
    fire.write_text(
        fire.read_text(encoding="utf-8").replace("## 2 Evacuation of stalls", "## 3 Evacuation of stalls"),
        encoding="utf-8",
    )
    report = await ingest(database_url=db_url, corpus_dir=corpus, embedder=HashedEmbedder())
    assert report.documents_updated == 1 and report.documents_unchanged == 2 and report.chunks_written == 2
    store = ChunkStore(rag_documents)
    assert await store.get_chunk("test-fire-sop#s2") is None
    assert await store.get_chunk("test-fire-sop#s3") is not None


async def test_removed_document_is_unindexed_but_its_row_stays(rag_documents, db_url, tmp_path):
    corpus = _copy_fixtures(tmp_path)
    await ingest(database_url=db_url, corpus_dir=corpus, embedder=HashedEmbedder())
    (corpus / "test-fire-sop.md").unlink()
    report = await ingest(database_url=db_url, corpus_dir=corpus, embedder=HashedEmbedder())
    assert report.documents_removed == 1 and report.documents_unchanged == 2
    store = ChunkStore(rag_documents)
    assert await store.get_chunk("test-fire-sop#s1") is None
    assert await _fixture_document_count(rag_documents) == 3  # ingest never deletes seeded documents
    assert next(r for r in await store.list_documents() if r.id == "test-fire-sop").embedding_model == ""


async def test_changed_embedder_reindexes_everything(rag_documents, db_url):
    await ingest(database_url=db_url, corpus_dir=RAG_FIXTURES, embedder=HashedEmbedder())
    report = await ingest(database_url=db_url, corpus_dir=RAG_FIXTURES, embedder=RenamedEmbedder())
    assert report.documents_updated == 3 and report.chunks_written == 9
    assert await ChunkStore(rag_documents).embedding_models() == {"hashed:v2"}


async def test_reset_reindexes_from_scratch(rag_documents, db_url):
    await ingest(database_url=db_url, corpus_dir=RAG_FIXTURES, embedder=HashedEmbedder())
    report = await ingest(database_url=db_url, corpus_dir=RAG_FIXTURES, embedder=HashedEmbedder(), reset=True)
    assert report.documents_added == 3 and report.documents_unchanged == 0 and report.chunks_written == 9
    assert await _fixture_document_count(rag_documents) == 3


async def test_invalid_corpus_touches_nothing(rag_documents, db_url, tmp_path):
    corpus = _copy_fixtures(tmp_path)
    (corpus / "bad.md").write_text("---\ndocument_id: bad\ntitle: X\nkind: nope\n---\n\n## 1 A\n\nx\n")
    with pytest.raises(CorpusError, match="bad.md"):
        await ingest(database_url=db_url, corpus_dir=corpus, embedder=HashedEmbedder())
    assert await ChunkStore(rag_documents).count_chunks() == 0


async def test_duplicate_heading_fails_before_any_write(rag_documents, db_url, tmp_path):
    corpus = _copy_fixtures(tmp_path)
    fire = corpus / "test-fire-sop.md"
    fire.write_text(fire.read_text(encoding="utf-8").replace("## 2 Evacuation", "## 1 Evacuation"))
    with pytest.raises(CorpusError, match="duplicate section"):
        await ingest(database_url=db_url, corpus_dir=corpus, embedder=HashedEmbedder())
    assert await ChunkStore(rag_documents).count_chunks() == 0


async def test_unseeded_document_fails_before_any_write(rag_documents, db_url, tmp_path):
    corpus = _copy_fixtures(tmp_path)
    text = (corpus / "test-fire-sop.md").read_text(encoding="utf-8")
    (corpus / "test-unseeded.md").write_text(
        text.replace("document_id: test-fire-sop", "document_id: test-unseeded")
    )
    with pytest.raises(IngestError, match="test-unseeded"):
        await ingest(database_url=db_url, corpus_dir=corpus, embedder=HashedEmbedder())
    assert await ChunkStore(rag_documents).count_chunks() == 0


async def test_missing_or_empty_corpus_directory_is_refused(rag_documents, db_url, tmp_path):
    with pytest.raises(CorpusError, match="not found"):
        await ingest(database_url=db_url, corpus_dir=tmp_path / "nope", embedder=HashedEmbedder())
    with pytest.raises(CorpusError, match="no Markdown"):
        await ingest(database_url=db_url, corpus_dir=tmp_path, embedder=HashedEmbedder())


# main() runs its own event loop, so async tests call it from a worker thread.


async def test_cli_ingests_and_prints_report(rag_documents, db_url, capsys, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", db_url)
    monkeypatch.setenv("EMBEDDING_PROVIDER", "hashed")
    code = await asyncio.to_thread(main, ["--corpus", str(RAG_FIXTURES), "--reset"])
    out = capsys.readouterr().out
    assert code == 0
    assert "documents_added: 3" in out and "chunks_written: 9" in out and "embedding_model: hashed:v1" in out


def test_cli_reports_corpus_error(db_url, capsys, monkeypatch, tmp_path):
    monkeypatch.setenv("DATABASE_URL", db_url)
    (tmp_path / "bad.md").write_text("no front matter\n", encoding="utf-8")
    code = main(["--corpus", str(tmp_path), "--provider", "hashed"])
    assert code == 1 and "front matter" in capsys.readouterr().err


async def test_cli_reports_unseeded_documents(rag_documents, db_url, capsys, tmp_path):
    corpus = _copy_fixtures(tmp_path)
    text = (corpus / "test-policy.md").read_text(encoding="utf-8")
    (corpus / "test-ghost.md").write_text(text.replace("document_id: test-policy", "document_id: test-ghost"))
    code = await asyncio.to_thread(
        main, ["--corpus", str(corpus), "--provider", "hashed", "--database-url", db_url]
    )
    assert code == 1 and "gridline.db.seed" in capsys.readouterr().err
