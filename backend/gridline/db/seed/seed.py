"""Seed the database from ``data/city/*.yaml`` and ``data/corpus/*.md`` (spec §8).

Everything is validated first (``validate_references``); rows are then added table by table and flushed after
each table, because the unit of work orders inserts by relationships, not by bare foreign keys. The two
circular references (zones <-> drainage_channels, schools <-> shelters) are deferred to commit, so both
sides are inserted with their final values. Self-references (channel outfalls, substation feeds) insert
parents first.
"""

from collections.abc import Callable, Sequence
from pathlib import Path

from pydantic import BaseModel
from sqlalchemy import func, select, table
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from gridline.city.dataset import CityData, load_city_data, validate_references
from gridline.city.schema_common import Record
from gridline.city.terrain import elevation_grid
from gridline.db import models as m
from gridline.db.base import Base
from gridline.db.engine import session_factory
from gridline.db.schema import create_schema, drop_schema
from gridline.db.seed import rows
from gridline.db.seed.corpus import ParsedDocument, load_corpus

Batch = tuple[str, Sequence[Base]]


class SeedSummary(BaseModel):
    """Row count per seeded table, in insert order."""

    counts: dict[str, int]


def parents_first[R: Record](records: Sequence[R], parent: Callable[[R], str | None]) -> list[list[R]]:
    """Split self-referencing records into levels so that every parent is in an earlier level."""
    placed: set[str] = set()
    levels: list[list[R]] = []
    remaining = list(records)
    while remaining:
        level = [r for r in remaining if (p := parent(r)) is None or p in placed]
        if not level:
            raise ValueError(f"cycle among {[r.id for r in remaining]}")
        levels.append(level)
        placed |= {r.id for r in level}
        remaining = [r for r in remaining if r.id not in placed]
    return levels


def build_rows(data: CityData, docs: list[ParsedDocument]) -> list[Batch]:
    """(table, rows) batches in foreign-key order; each batch is flushed before the next."""
    grid = elevation_grid()
    areas = {z.id: rows.zone_area_km2(z.bbox) for z in data.zones}
    loc, plain = rows.located, rows.plain
    batches: list[Batch] = [
        ("city", [plain(m.City, data.city)]),
        ("geological_zones", [plain(m.GeologicalZone, r) for r in data.geological_zones]),
        ("rivers", [plain(m.River, r) for r in data.rivers]),
        ("catchments", [plain(m.Catchment, r) for r in data.catchments]),
        ("zones", [rows.zone_row(r, grid) for r in data.zones]),
    ]
    for level in parents_first(data.drainage_channels, lambda r: r.outfall_channel_id):
        batches.append(("drainage_channels", [loc(m.DrainageChannel, r) for r in level]))
    batches += [
        ("soil_profiles", [plain(m.SoilProfile, r) for r in data.soil_profiles]),
        ("hills", [rows.hill_row(r) for r in data.hills]),
        ("flood_plains", [plain(m.FloodPlain, r) for r in data.flood_plains]),
        ("pump_units", [loc(m.PumpUnit, r) for r in data.pump_units]),
        ("roads", [rows.road_row(r) for r in data.roads]),
        ("slopes", [loc(m.Slope, r) for r in data.slopes]),
        ("bridges", [loc(m.Bridge, r) for r in data.bridges]),
        ("tunnels", [rows.tunnel_row(r) for r in data.tunnels]),
        ("dams", [loc(m.Dam, r) for r in data.dams]),
    ]
    for level in parents_first(data.power_substations, lambda r: r.fed_from_substation_id):
        batches.append(("power_substations", [loc(m.PowerSubstation, r) for r in level]))
    batches += [
        ("water_facilities", [loc(m.WaterFacility, r) for r in data.water_facilities]),
        ("documents", [rows.document_row(d) for d in docs]),
        ("document_sections", [s for d in docs for s in rows.section_rows(d)]),
        ("projects", [loc(m.Project, r) for r in data.projects]),
        (
            "critical_infrastructure",
            [plain(m.CriticalInfrastructure, r) for r in data.critical_infrastructure],
        ),
        ("sensors", [loc(m.Sensor, r) for r in data.sensors]),
        ("hospitals", [loc(m.Hospital, r) for r in data.hospitals]),
        ("hospital_beds", [plain(m.HospitalBed, r) for r in data.hospital_beds]),
        ("ambulances", [plain(m.Ambulance, r) for r in data.ambulances]),
        ("fire_stations", [loc(m.FireStation, r) for r in data.fire_stations]),
        ("fire_trucks", [plain(m.FireTruck, r) for r in data.fire_trucks]),
        ("police_stations", [loc(m.PoliceStation, r) for r in data.police_stations]),
        ("crews", [loc(m.Crew, r) for r in data.crews]),
        ("schools", [loc(m.School, r) for r in data.schools]),
        ("shelters", [loc(m.Shelter, r) for r in data.shelters]),
        ("zone_yearly_stats", [rows.yearly_stats_row(r, areas[r.zone_id]) for r in data.zone_yearly_stats]),
        ("residential_areas", [loc(m.ResidentialArea, r) for r in data.residential_areas]),
        ("historical_incidents", [i for d in docs if (i := rows.incident_row(d)) is not None]),
        ("historical_incident_impacts", [i for d in docs for i in rows.impact_rows(d)]),
        ("infrastructure_changes", [plain(m.InfrastructureChange, r) for r in data.infrastructure_changes]),
        ("policy_thresholds", [plain(m.PolicyThreshold, r) for r in data.policy_thresholds]),
        ("elevation_points", list(rows.elevation_rows(grid))),
    ]
    return batches


async def seed(session: AsyncSession, data_dir: Path) -> SeedSummary:
    """Validate and insert the whole dataset into an empty schema. The caller commits."""
    data = load_city_data(data_dir)
    docs = load_corpus(data_dir / "corpus")
    problems = validate_references(data, docs)
    if problems:
        raise ValueError("city dataset is inconsistent:\n  " + "\n  ".join(problems))
    order: list[str] = []
    for name, batch in build_rows(data, docs):
        session.add_all(batch)
        await session.flush()
        if name not in order:
            order.append(name)
    counts = {name: (await session.execute(select(func.count()).select_from(table(name)))).scalar_one()
              for name in order}  # fmt: skip
    return SeedSummary(counts=counts)


async def is_seeded(engine: AsyncEngine) -> bool:
    async with session_factory(engine)() as session:
        return (await session.execute(select(func.count()).select_from(m.City))).scalar_one() > 0


async def reset_and_seed(engine: AsyncEngine, data_dir: Path) -> SeedSummary:
    """Drop and recreate every table, then seed and commit."""
    await drop_schema(engine)
    await create_schema(engine)
    async with session_factory(engine)() as session, session.begin():
        return await seed(session, data_dir)
