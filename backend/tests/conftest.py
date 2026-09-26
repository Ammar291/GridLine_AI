"""Shared fixtures. DB tests need TEST_DATABASE_URL (default: localhost:5433/gridline_test)."""

import asyncio
import os
from collections.abc import AsyncIterator, Callable
from pathlib import Path
from typing import Any

import psycopg
import pytest
from sqlalchemy import bindparam, delete, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from gridline.city.model import City
from gridline.city.nandipur import build_nandipur
from gridline.config import Settings
from gridline.db.engine import create_engine, session_factory
from gridline.db.models import OPERATIONS_TABLES, Base, Document
from gridline.db.schema import create_schema, drop_schema, truncate_corpus
from gridline.db.seed import SeedSummary, reset_and_seed
from gridline.db.seed.corpus import load_corpus
from gridline.db.seed.rows import document_row
from gridline.tools.base import ToolContext

LoopFactory = Callable[[], asyncio.AbstractEventLoop]

DEFAULT_TEST_URL = "postgresql+psycopg://gridline:gridline@localhost:5433/gridline_test"
DATA_DIR = Path(__file__).resolve().parents[1] / "data"
RAG_FIXTURES = Path(__file__).resolve().parent / "fixtures" / "corpus"


def pytest_asyncio_loop_factories(config: pytest.Config, item: pytest.Item) -> dict[str, LoopFactory]:
    """Run every async test on a selector loop: psycopg's async driver cannot use Windows' Proactor loop."""
    return {"selector": asyncio.SelectorEventLoop}


@pytest.fixture(scope="session")
def city() -> City:
    """The simulation's Nandipur, built once per session from backend/data (no database needed)."""
    return build_nandipur(DATA_DIR)


@pytest.fixture
def settings() -> Settings:
    """Fast simulation settings for tests: no .env file, 10 ms ticks, 50 ms WebSocket heartbeat."""
    return Settings(_env_file=None, sim_tick_seconds=0.01, ws_heartbeat_seconds=0.05)


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


# --- city operations tools ----------------------------------------------------------------------------------
# Tools commit for real, so a tool test starts and ends on the freshly seeded city. A reseed costs about a
# second, so instead the live tables the tools write are restored row by row from a baseline read once after
# seeding, and the operations tables are emptied children-first. These fixtures live here, not in
# tests/tools/conftest.py, so they resolve however pytest is handed the test files.

LIVE_TABLES = ("roads", "projects", "crews", "ambulances", "shelters", "hospital_beds")

Baseline = dict[str, list[dict[str, Any]]]


@pytest.fixture(scope="session")
async def baseline(db_engine: AsyncEngine, seeded: SeedSummary) -> Baseline:
    async with db_engine.connect() as conn:
        tables = {name: Base.metadata.tables[name] for name in LIVE_TABLES}
        return {
            name: [dict(r) for r in (await conn.execute(select(t))).mappings()] for name, t in tables.items()
        }


async def restore(engine: AsyncEngine, baseline: Baseline) -> None:
    """Put the live tables back to their seeded values and delete every operations row."""
    async with engine.begin() as conn:
        for name, rows in baseline.items():
            table = Base.metadata.tables[name]
            cols = [c.name for c in table.columns if not c.primary_key]
            stmt = (
                table.update()
                .where(table.c.id == bindparam("pk_"))
                .values({c: bindparam(f"v_{c}") for c in cols})
            )
            await conn.execute(stmt, [{"pk_": r["id"], **{f"v_{c}": r[c] for c in cols}} for r in rows])
        for table in reversed(Base.metadata.sorted_tables):
            if table.name in OPERATIONS_TABLES:
                await conn.execute(table.delete())


@pytest.fixture
async def tool_session(db_engine: AsyncEngine, baseline: Baseline) -> AsyncIterator[AsyncSession]:
    """The session tools run on, over a freshly restored city; the city is restored again afterwards.

    Not autouse: pytest-asyncio cannot run an async autouse fixture for a sync test that follows async ones,
    and pure tests need no database.
    """
    await restore(db_engine, baseline)
    async with session_factory(db_engine)() as s:
        yield s
    await restore(db_engine, baseline)


@pytest.fixture
async def check_session(db_engine: AsyncEngine, tool_session: AsyncSession) -> AsyncIterator[AsyncSession]:
    """A second session, used only to read state back (proves the commit reached the database)."""
    async with session_factory(db_engine)() as s:
        yield s


@pytest.fixture
def ctx(tool_session: AsyncSession) -> ToolContext:
    """An approved agent call on the tool session."""
    return ToolContext(session=tool_session, approval_id="apr_test", run_id="run_test")


@pytest.fixture
def ctx_no_approval(tool_session: AsyncSession) -> ToolContext:
    return ToolContext(session=tool_session)
