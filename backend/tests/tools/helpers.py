"""Helpers for tool tests: setup and tampering go through ``check_session``, never the tool session."""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from gridline.db.base import Base
from gridline.db.models import Incident

NOW = datetime(2026, 7, 14, 6, 0, tzinfo=UTC)


async def fresh[M: Base](session: AsyncSession, model: type[M], row_id: str) -> M:
    """The row as committed in the database right now."""
    row = await session.get(model, row_id, populate_existing=True)
    assert row is not None, f"{model.__tablename__} {row_id} missing"
    return row


async def tamper(session: AsyncSession, model: type[Base], row_id: str, **values: Any) -> None:
    """Change a row behind the tool's back (another actor, or the simulation) and commit."""
    row = await fresh(session, model, row_id)
    for name, value in values.items():
        setattr(row, name, value)
    await session.commit()


async def add_incident(
    session: AsyncSession,
    incident_id: str = "inc_test",
    *,
    zone_id: str = "Z-HV",
    hazard: str = "landslide",
    status: str = "open",
) -> str:
    session.add(
        Incident(
            id=incident_id, zone_id=zone_id, hazard=hazard, band="warning", status=status,
            title="Test incident", summary="Synthetic test incident.", opened_at=NOW, updated_at=NOW,
            closed_at=NOW if status == "closed" else None,
        )
    )  # fmt: skip
    await session.commit()
    return incident_id


async def count(session: AsyncSession, model: type[Base], *where: Any) -> int:
    stmt = select(func.count()).select_from(model).where(*where)
    return (await session.execute(stmt)).scalar_one()
