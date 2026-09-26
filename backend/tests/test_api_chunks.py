"""GET /api/chunks/{chunk_id}: the source behind a citation chip, read from the RAG store."""

from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from gridline.city.model import City
from gridline.config import Settings
from gridline.db.seed.corpus import load_corpus
from gridline.main import create_app
from gridline.rag.chunker import chunk_document
from gridline.rag.embedder import HashedEmbedder
from gridline.rag.store import ChunkStore
from tests.conftest import RAG_FIXTURES


@pytest.fixture
async def client(
    settings: Settings, city: City, db_url: str, rag_documents: async_sessionmaker[AsyncSession]
) -> AsyncIterator[AsyncClient]:
    embedder = HashedEmbedder()
    doc = next(d for d in load_corpus(RAG_FIXTURES) if d.meta.document_id == "test-policy")
    chunks = chunk_document(doc)
    vectors = embedder.embed_documents([c.embedding_text for c in chunks])
    await ChunkStore(rag_documents).replace_chunks("test-policy", "h", embedder.name, chunks, vectors)
    app = create_app(settings.model_copy(update={"database_url": db_url}), city=city)
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client,
    ):
        yield client


async def test_chunk_is_served_by_its_citation_id(client: AsyncClient) -> None:
    response = await client.get("/api/chunks/test-policy%23s4.2")
    assert response.status_code == 200, response.text
    body = response.json()
    assert (body["chunk_id"], body["document_id"], body["document_title"]) == (
        "test-policy#s4.2",
        "test-policy",
        "Test Disaster Policy",
    )
    assert body["section_id"] == "s4.2" and "Excavation on any slope" in body["text"]
    assert (body["kind"], body["category"]) == ("policy", "policy")


async def test_unknown_chunk_is_404(client: AsyncClient) -> None:
    response = await client.get("/api/chunks/test-policy%23s99")
    assert response.status_code == 404


async def test_unreachable_knowledge_base_is_503(settings: Settings, city: City) -> None:
    dead = settings.model_copy(update={"database_url": "postgresql+psycopg://nobody:x@127.0.0.1:1/none"})
    app = create_app(dead, city=city)
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client,
    ):
        response = await client.get("/api/chunks/dmp-2024%23s4.2")
    assert response.status_code == 503
