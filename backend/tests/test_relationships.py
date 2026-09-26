from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from gridline.city.references import ASSET_KINDS
from gridline.db.models import (
    Base,
    CriticalInfrastructure,
    Document,
    DocumentSection,
    DrainageChannel,
    HistoricalIncidentImpact,
    Hospital,
    InfrastructureChange,
    PolicyThreshold,
    Project,
    Shelter,
    Zone,
)


async def _ids(session: AsyncSession, table: str) -> set[str]:
    model = Base.metadata.tables[table]
    return set((await session.execute(select(model.c.id))).scalars())


async def test_hillview_drains_through_d7_into_riverside(session: AsyncSession) -> None:
    zone = await session.get(Zone, "Z-HV")
    assert zone is not None and zone.drains_to_channel_id == "D-7"
    channel = await zone.awaitable_attrs.channel
    assert channel is not None and channel.downstream_zone_id == "Z-RS"
    d7 = await session.get(DrainageChannel, "D-7")
    assert d7 is not None and (await d7.awaitable_attrs.downstream_zone).name == "Riverside"


async def test_project_slope_zone_and_permit_resolve(session: AsyncSession) -> None:
    ht2 = await session.get(Project, "PR-HT2")
    assert ht2 is not None
    slope = await ht2.awaitable_attrs.slope
    assert slope is not None and slope.mean_angle_deg == 32
    assert (await ht2.awaitable_attrs.zone).id == "Z-HV"
    assert ht2.permit_doc_id == "permit-ht-2026-014"
    assert await session.get(Document, ht2.permit_doc_id) is not None


async def test_incident_impacts_and_changes_resolve(session: AsyncSession) -> None:
    ids = {table: await _ids(session, table) for table in set(ASSET_KINDS.values())}
    impacts = (await session.execute(select(HistoricalIncidentImpact))).scalars().all()
    changes = (await session.execute(select(InfrastructureChange))).scalars().all()
    assert impacts and changes
    for row in [*impacts, *changes]:
        assert row.asset_id in ids[ASSET_KINDS[row.asset_kind]], (row.id, row.asset_kind, row.asset_id)


async def test_critical_infrastructure_dependencies_resolve(session: AsyncSession) -> None:
    rows = (await session.execute(select(CriticalInfrastructure))).scalars().all()
    assert len(rows) == 15
    for row in rows:
        assert row.asset_id in await _ids(session, ASSET_KINDS[row.asset_kind]), row.id


async def test_shelter_school_link(session: AsyncSession) -> None:
    shelter = await session.get(Shelter, "S-5")
    assert shelter is not None
    school = await shelter.awaitable_attrs.school
    assert school is not None and school.id == "SC-08" and school.shelter_id == "S-5"


async def test_hospital_substation_feed(session: AsyncSession) -> None:
    h2 = await session.get(Hospital, "H-2")
    assert h2 is not None
    substation = await h2.awaitable_attrs.substation
    assert substation.id == "PS-2" and substation.fed_from_substation_id == "PS-1"


async def test_threshold_values_appear_in_cited_sections(session: AsyncSession) -> None:
    rows = (
        await session.execute(
            select(PolicyThreshold, DocumentSection).join(
                DocumentSection,
                (DocumentSection.document_id == PolicyThreshold.document_id)
                & (DocumentSection.section == PolicyThreshold.section),
            )
        )
    ).all()
    assert len(rows) == 25  # every threshold cites an existing section
    for threshold, section in rows:
        assert f"{threshold.value:g}" in section.text, (threshold.id, section.id)
