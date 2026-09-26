"""Operations tables and live columns added by the city operations tool layer (plan Task 1)."""

from datetime import UTC, datetime

import pytest
from sqlalchemy import inspect, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from gridline.db.models import (
    EXPECTED_TABLES,
    OPERATIONS_TABLES,
    Base,
    Crew,
    EvacuationOrder,
    HospitalBed,
    Incident,
    Road,
    Shelter,
)


def test_operations_tables_are_registered_on_the_single_base():
    expected = {
        "incidents",
        "alerts",
        "evacuation_orders",
        "construction_restrictions",
        "tasks",
        "bed_reservations",
        "actions",
    }
    assert expected == OPERATIONS_TABLES
    assert not OPERATIONS_TABLES & EXPECTED_TABLES
    assert set(Base.metadata.tables) == EXPECTED_TABLES | {"chunks"} | OPERATIONS_TABLES


async def test_operations_tables_exist(db_engine):
    async with db_engine.connect() as conn:
        names = await conn.run_sync(lambda c: set(inspect(c).get_table_names()))
    assert names >= OPERATIONS_TABLES


async def _columns(db_engine, table: str) -> set[str]:
    async with db_engine.connect() as conn:
        return await conn.run_sync(lambda c: {col["name"] for col in inspect(c).get_columns(table)})


async def _fks(db_engine, table: str) -> set[tuple[tuple[str, ...], str]]:
    async with db_engine.connect() as conn:
        fks = await conn.run_sync(lambda c: inspect(c).get_foreign_keys(table))
    return {(tuple(fk["constrained_columns"]), fk["referred_table"]) for fk in fks}


async def test_live_columns_on_seeded_tables(db_engine):
    assert {"closure_reason", "closed_at", "incident_id"} <= await _columns(db_engine, "roads")
    assert "depth_limit_m" in await _columns(db_engine, "projects")
    assert {"target_zone_id", "task", "incident_id", "dispatched_at"} <= await _columns(db_engine, "crews")
    ambulance = await _columns(db_engine, "ambulances")
    assert {"target_zone_id", "destination_hospital_id", "incident_id", "dispatched_at"} <= ambulance
    assert {"opened_at", "incident_id"} <= await _columns(db_engine, "shelters")
    assert "reserved" in await _columns(db_engine, "hospital_beds")


async def test_operations_columns(db_engine):
    expected = {
        "incidents": {"zone_id", "hazard", "band", "status", "title", "summary", "opened_at", "closed_at"},
        "alerts": {"zone_id", "level", "message", "incident_id", "issued_at"},
        "evacuation_orders": {"zone_id", "level", "reason", "shelter_id", "incident_id", "status"},
        "construction_restrictions": {"project_id", "kind", "max_depth_m", "reason", "status", "issued_at"},
        "tasks": {
            "kind", "title", "description", "priority", "status", "zone_id", "target_kind", "target_id",
            "metric", "interval_minutes", "assigned_crew_id", "incident_id", "evacuation_order_id",
            "created_by", "created_at", "completed_at",
        },
        "bed_reservations": {"hospital_id", "hospital_bed_id", "bed_type", "incident_id", "beds", "status"},
        "actions": {
            "tool", "status", "idempotency_key", "actor", "approval_id", "run_id", "incident_id",
            "input_json", "before_json", "after_json", "affected_entities_json", "message", "sim_time",
            "executed_at", "verification_json",
        },
    }  # fmt: skip
    for table, cols in expected.items():
        assert cols <= await _columns(db_engine, table), table


async def test_operations_foreign_keys(db_engine):
    assert (("incident_id",), "incidents") in await _fks(db_engine, "crews")
    assert (("target_zone_id",), "zones") in await _fks(db_engine, "crews")
    assert (("destination_hospital_id",), "hospitals") in await _fks(db_engine, "ambulances")
    assert (("incident_id",), "incidents") in await _fks(db_engine, "roads")
    task_fks = await _fks(db_engine, "tasks")
    assert (("evacuation_order_id",), "evacuation_orders") in task_fks
    assert (("assigned_crew_id",), "crews") in task_fks
    assert (("hospital_bed_id",), "hospital_beds") in await _fks(db_engine, "bed_reservations")
    assert (("project_id",), "projects") in await _fks(db_engine, "construction_restrictions")
    # A rejected attempt may name an incident that does not exist, so the audit row keeps a plain string.
    assert await _fks(db_engine, "actions") == set()


async def test_action_idempotency_key_is_unique(db_engine):
    async with db_engine.connect() as conn:
        indexes = await conn.run_sync(lambda c: inspect(c).get_indexes("actions"))
        uniques = await conn.run_sync(lambda c: inspect(c).get_unique_constraints("actions"))
    unique_cols = [tuple(i["column_names"]) for i in indexes if i["unique"]]
    unique_cols += [tuple(u["column_names"]) for u in uniques]
    assert ("idempotency_key",) in unique_cols


async def test_seeded_live_columns_start_empty(session: AsyncSession):
    crews = (await session.execute(select(Crew))).scalars().all()
    assert crews and all(c.target_zone_id is None and c.incident_id is None for c in crews)
    road = await session.get(Road, "RD-01")
    assert road is not None and road.closure_reason is None and road.closed_at is None
    shelter = await session.get(Shelter, "S-1")
    assert shelter is not None and shelter.opened_at is None
    beds = (await session.execute(select(HospitalBed))).scalars().all()
    assert beds and all(b.reserved == 0 for b in beds)


async def test_one_active_evacuation_order_and_one_open_incident_per_key(db_engine, seeded):
    """The invariants the tools' "unchanged" rules rely on also hold under concurrent inserts."""
    now = datetime.now(UTC)

    def order(order_id: str, status: str = "active") -> EvacuationOrder:
        return EvacuationOrder(
            id=order_id, zone_id="Z-RS", level="voluntary", reason="t", status=status, issued_at=now,
            updated_at=now,
        )  # fmt: skip

    def incident(incident_id: str, status: str = "open") -> Incident:
        return Incident(
            id=incident_id, zone_id="Z-RS", hazard="flood", band="watch", status=status, title="t",
            summary="t", opened_at=now, updated_at=now,
        )  # fmt: skip

    async with AsyncSession(db_engine) as session:
        session.add_all(
            [order("evac_a", "lifted"), order("evac_b"), incident("inc_a", "closed"), incident("inc_b")]
        )
        await session.flush()  # a lifted order / closed incident does not count
        for duplicate in (order("evac_c"), incident("inc_c")):
            async with session.begin_nested():
                session.add(duplicate)
                with pytest.raises(IntegrityError):
                    await session.flush()
        await session.rollback()
