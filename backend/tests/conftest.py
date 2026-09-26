"""Shared fixtures. DB tests need TEST_DATABASE_URL (default: localhost:5433/gridline_test)."""

import asyncio
import os
from collections.abc import AsyncIterator, Callable

import psycopg
import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from gridline.db.engine import create_engine, session_factory
from gridline.db.schema import create_schema, truncate_corpus

LoopFactory = Callable[[], asyncio.AbstractEventLoop]

DEFAULT_TEST_URL = "postgresql+psycopg://gridline:gridline@localhost:5433/gridline_test"


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
    await create_schema(engine)
    yield engine
    await engine.dispose()


@pytest.fixture
async def db_sessions(db_engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    await truncate_corpus(db_engine)
    return session_factory(db_engine)
