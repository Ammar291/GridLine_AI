"""The questions the agent will ask of the data layer, answered with plain SQL over the seeded tables."""

from typing import Any

from sqlalchemy import Result, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from gridline.db.models import (
    Document,
    DrainageChannel,
    HistoricalIncident,
    Hospital,
    InfrastructureChange,
    PowerSubstation,
    Project,
    ResidentialArea,
    Shelter,
    Slope,
    ZoneYearlyStats,
)


def _pairs(result: Result[Any]) -> dict[Any, Any]:
    return {key: value for key, value in result.all()}


async def test_floodplain_residents_exceed_shelter_capacity_in_riverside(session: AsyncSession) -> None:
    capacity = _pairs(
        await session.execute(
            select(Shelter.zone_id, func.sum(Shelter.capacity_persons)).group_by(Shelter.zone_id)
        )
    )
    on_plain = _pairs(
        await session.execute(
            select(ResidentialArea.zone_id, func.sum(ResidentialArea.population))
            .where(ResidentialArea.flood_plain_id.is_not(None))
            .group_by(ResidentialArea.zone_id)
        )
    )
    assert on_plain["Z-RS"] - capacity.get("Z-RS", 0) > 0


async def test_channels_below_design_capacity(session: AsyncSession) -> None:
    ids = set(
        (
            await session.execute(
                select(DrainageChannel.id).where(
                    DrainageChannel.current_capacity_m3s < DrainageChannel.design_capacity_m3s
                )
            )
        ).scalars()
    )
    assert {"D-7", "D-3", "D-11", "D-12"} <= ids
    assert "D-9" not in ids


async def test_steep_slopes_with_active_projects(session: AsyncSession) -> None:
    ids = set(
        (
            await session.execute(
                select(Slope.id)
                .join(Project, Project.slope_id == Slope.id)
                .where(Slope.mean_angle_deg > 25, Project.status == "active")
            )
        ).scalars()
    )
    assert ids == {"SL-HV-1", "SL-TH-1"}


async def test_hospitals_on_unprotected_substations(session: AsyncSession) -> None:
    ids = set(
        (
            await session.execute(
                select(Hospital.id)
                .join(PowerSubstation, Hospital.substation_id == PowerSubstation.id)
                .where(PowerSubstation.flood_protected.is_(False))
            )
        ).scalars()
    )
    assert "H-2" in ids and "H-1" not in ids


async def test_incidents_by_hazard(session: AsyncSession) -> None:
    rows = await session.execute(
        select(HistoricalIncident.hazard, func.count()).group_by(HistoricalIncident.hazard)
    )
    assert _pairs(rows) == {"flood": 3, "flash_flood": 3, "landslide": 4, "cyclone": 3, "urban_fire": 4}


async def test_changes_touching_d7(session: AsyncSession) -> None:
    ids = set(
        (
            await session.execute(
                select(InfrastructureChange.id).where(
                    (InfrastructureChange.asset_id == "D-7") | (InfrastructureChange.project_id == "PR-HRW")
                )
            )
        ).scalars()
    )
    assert "CH-2025-02" in ids


async def test_documents_by_kind(session: AsyncSession) -> None:
    rows = await session.execute(select(Document.kind, func.count()).group_by(Document.kind))
    assert _pairs(rows) == {
        "policy": 8,
        "sop": 4,
        "report": 17,
        "permit": 1,
        "change_log": 1,
        "profile": 6,
    }


async def test_new_colony_population_growth(session: AsyncSession) -> None:
    rows = await session.execute(
        select(ZoneYearlyStats.year, ZoneYearlyStats.population).where(ZoneYearlyStats.zone_id == "Z-NC")
    )
    by_year = _pairs(rows)
    assert sorted(by_year) == list(range(2018, 2027))
    assert by_year[2026] > 5 * by_year[2018]
