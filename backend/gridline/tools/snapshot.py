"""JSON-safe before/after snapshots of the rows an action touches, keyed ``"kind:id"``."""

from collections.abc import Iterable, Mapping
from types import MappingProxyType
from typing import Any

from pydantic_core import to_jsonable_python
from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import AsyncSession

from gridline.db.base import Base
from gridline.db.models import (
    Alert,
    Ambulance,
    BedReservation,
    ConstructionRestriction,
    Crew,
    EvacuationOrder,
    Hospital,
    HospitalBed,
    Incident,
    Project,
    Road,
    Shelter,
    Task,
    Zone,
)
from gridline.tools.base import EntityKind, EntityRef

ENTITY_MODELS: Mapping[EntityKind, type[Base]] = MappingProxyType(
    {
        "zone": Zone,
        "road": Road,
        "project": Project,
        "crew": Crew,
        "ambulance": Ambulance,
        "shelter": Shelter,
        "hospital": Hospital,
        "hospital_bed": HospitalBed,
        "bed_reservation": BedReservation,
        "incident": Incident,
        "alert": Alert,
        "evacuation_order": EvacuationOrder,
        "construction_restriction": ConstructionRestriction,
        "task": Task,
    }
)


def row_to_dict(row: Base) -> dict[str, Any]:
    """Every mapped column of ``row`` as JSON-safe values (datetimes and dates become ISO strings)."""
    return {attr.key: to_jsonable_python(getattr(row, attr.key)) for attr in inspect(row).mapper.column_attrs}


async def snapshot(session: AsyncSession, refs: Iterable[EntityRef]) -> dict[str, dict[str, Any]]:
    """Current state (including unflushed changes in the session) of each referenced row that exists."""
    out: dict[str, dict[str, Any]] = {}
    for ref in refs:
        row = await session.get(ENTITY_MODELS[ref.kind], ref.id)
        if row is not None:
            out[ref.key] = row_to_dict(row)
    return out
