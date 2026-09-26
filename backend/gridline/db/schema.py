"""Schema management. No Alembic: tables are created at startup (ARCHITECTURE.md §4)."""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from gridline.db.models import Base


async def create_schema(engine: AsyncEngine) -> None:
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)


async def drop_schema(engine: AsyncEngine) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


async def truncate_corpus(engine: AsyncEngine) -> None:
    async with engine.begin() as conn:
        await conn.execute(text("TRUNCATE TABLE documents CASCADE"))
