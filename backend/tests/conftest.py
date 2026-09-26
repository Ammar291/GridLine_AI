"""Shared fixtures. DB tests need TEST_DATABASE_URL (default: localhost:5433/gridline_test)."""

import asyncio
import os
from collections.abc import AsyncIterator, Callable
from pathlib import Path

import psycopg
import pytest
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from gridline.db.engine import create_engine, session_factory
from gridline.db.models import Document
from gridline.db.schema import create_schema, drop_schema, truncate_corpus
from gridline.db.seed import SeedSummary, reset_and_seed
from gridline.db.seed.corpus import load_corpus
from gridline.db.seed.rows import document_row

LoopFactory = Callable[[], asyncio.AbstractEventLoop]

DEFAULT_TEST_URL = "postgresql+psycopg://gridline:gridline@localhost:5433/gridline_test"
DATA_DIR = Path(__file__).resolve().parents[1] / "data"
RAG_FIXTURES = Path(__file__).resolve().parent / "fixtures" / "corpus"


def pytest_asyncio_loop_factories(config: pytest.Config, item: pytest.Item) -> dict[str, LoopFactory]:
    """Run every async test on a selector loop: psycopg's async driver cannot use Windows' Proactor loop."""
    return {"selector": asyncio.SelectorEventLoop}


@pytest.fixture(scope="session")
def db_url() -> str:
    """SQLAlchemy URL of the test database; skips the test when Postgres is not reachable."""
    url = os.environ.get("TEST_DATABASE_URL", DEFAULT_TEST_URL)
    try:
        with psycopg.connect(url.replace("postgresql+psycopg://", "postgresql://", 1), connect_timeout=3):
            pass
    except psycopg.OperationalError as exc:
        pytest.skip(f"Postgres not reachable at {url}: {exc}")
    return url


@pytest.fixture(scope="session")
async def db_engine(db_url: str) -> AsyncIterator[AsyncEngine]:
    engine = create_engine(db_url)
    await drop_schema(engine)  # fresh tables every session, so model changes always reach the test database
    await create_schema(engine)
    yield engine
    await engine.dispose()


@pytest.fixture
async def db_sessions(db_engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    await truncate_corpus(db_engine)
    return session_factory(db_engine)


@pytest.fixture(scope="session")
async def seeded(db_engine: AsyncEngine) -> SeedSummary:
    """Drop, recreate and seed the test database once per session with the full Nandipur dataset."""
    return await reset_and_seed(db_engine, DATA_DIR)


@pytest.fixture
async def session(db_engine: AsyncEngine, seeded: SeedSummary) -> AsyncIterator[AsyncSession]:
    """A session on the seeded database; rolled back afterwards so tests cannot leak writes."""
    async with session_factory(db_engine)() as s:
        yield s
        await s.rollback()


@pytest.fixture
async def rag_documents(
    db_engine: AsyncEngine, db_sessions: async_sessionmaker[AsyncSession]
) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    """``documents`` rows for the RAG test corpus (tests/fixtures/corpus), written as the seed writes them.

    RAG ingestion never creates or deletes documents (the city seed owns them), so these three are added
    here and removed afterwards (their chunks cascade); seeded Nandipur documents are left untouched.
    """
    docs = load_corpus(RAG_FIXTURES)
    ids = [d.meta.document_id for d in docs]
    async with db_engine.begin() as conn:
        await conn.execute(delete(Document).where(Document.id.in_(ids)))
    async with db_sessions() as s, s.begin():
        s.add_all([document_row(d) for d in docs])
    yield db_sessions
    async with db_engine.begin() as conn:
        await conn.execute(delete(Document).where(Document.id.in_(ids)))
