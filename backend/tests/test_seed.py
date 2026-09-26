import shutil
from pathlib import Path

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from gridline.city.terrain import elevation_m, river_y
from gridline.db.models import (
    EXPECTED_TABLES,
    Document,
    DocumentSection,
    HistoricalIncidentImpact,
    Hospital,
    Project,
    River,
    Road,
    Tunnel,
    Zone,
    ZoneYearlyStats,
)
from gridline.db.schema import truncate_corpus
from gridline.db.seed import SeedSummary, reset_and_seed, seed
from gridline.db.seed.__main__ import main
from tests.conftest import DATA_DIR


async def test_seed_counts_match_dataset(seeded: SeedSummary) -> None:
    c = seeded.counts
    assert set(c) == EXPECTED_TABLES
    assert c["city"] == 1 and c["zones"] == 10 and c["drainage_channels"] == 9 and c["documents"] == 37
    assert (
        c["historical_incidents"] == 17 and c["infrastructure_changes"] == 29 and c["elevation_points"] == 475
    )
    assert c["zone_yearly_stats"] == 90 and c["residential_areas"] == 22 and c["policy_thresholds"] == 25
    assert c["historical_incident_impacts"] > 17 and c["document_sections"] > 33
    assert all(n > 0 for n in c.values())


async def test_reset_and_reseed_is_idempotent(db_engine: AsyncEngine, seeded: SeedSummary) -> None:
    again = await reset_and_seed(db_engine, DATA_DIR)
    assert again.counts == seeded.counts


async def test_elevations_come_from_terrain(session: AsyncSession) -> None:
    h = await session.get(Hospital, "H-1")
    assert h is not None and h.elevation_m == elevation_m(h.x_m, h.y_m)
    tunnel = await session.get(Tunnel, "TU-1")
    assert tunnel is not None
    assert tunnel.low_point_elevation_m == round(elevation_m(3300, 4600) - 4.5, 1)
    road = await session.get(Road, "RD-01")
    assert road is not None and road.min_elevation_m == min(elevation_m(x, y) for x, y in road.path)


async def test_zone_computed_columns(session: AsyncSession) -> None:
    zone = await session.get(Zone, "Z-HV")
    assert zone is not None
    assert zone.area_km2 == 3200 * 2000 / 1e6
    assert zone.svg_path == "M 8200 4400 H 11400 V 6400 H 8200 Z"
    assert zone.elevation_min_m <= zone.elevation_mean_m <= zone.elevation_max_m
    assert zone.drains_to_channel_id == "D-7"
    stats = await session.get(ZoneYearlyStats, "Z-HV-2026")
    assert stats is not None and stats.density_per_km2 == round(stats.population / zone.area_km2)


async def test_river_path_follows_centreline(session: AsyncSession) -> None:
    r1 = await session.get(River, "R-1")
    assert r1 is not None
    assert [x for x, _ in r1.path] == list(range(0, 12001, 500))
    assert all(abs(y - river_y(x)) <= 1 for x, y in r1.path)


async def test_corpus_rows(session: AsyncSession) -> None:
    doc = await session.get(Document, "dmp-2024")
    assert doc is not None and doc.version == "3.0" and doc.supersedes == "dmp-2019"
    assert doc.source_path == "data/corpus/dmp-2024.md" and doc.content_hash == ""
    section = await session.get(DocumentSection, "dmp-2024#s4.2")
    assert section is not None and section.heading == "Landslide thresholds"
    impact = await session.get(HistoricalIncidentImpact, "HI-2025-FF-01-1")
    assert impact is not None and impact.asset_id == "D-7" and impact.impact == "surcharged"


async def test_truncate_corpus_keeps_city_data(db_engine: AsyncEngine, seeded: SeedSummary) -> None:
    """The RAG reset clears only what the RAG layer owns (chunks); seeded documents and city rows stay."""
    await truncate_corpus(db_engine)
    async with db_engine.connect() as conn:
        assert (await conn.execute(text("select count(*) from chunks"))).scalar_one() == 0
        for table in ("documents", "document_sections", "projects", "historical_incidents"):
            count = (await conn.execute(text(f"select count(*) from {table}"))).scalar_one()
            assert count == seeded.counts[table], table
    async with AsyncSession(db_engine) as s:
        assert (await s.execute(select(func.count()).select_from(Project))).scalar_one() == 9


async def test_seed_rejects_bad_reference_before_writing(
    tmp_path: Path, db_engine: AsyncEngine, seeded: SeedSummary
) -> None:
    shutil.copytree(DATA_DIR, tmp_path / "data")
    emergency = tmp_path / "data" / "city" / "emergency.yaml"
    emergency.write_text(emergency.read_text().replace("school_id: SC-08", "school_id: SC-99"))
    async with AsyncSession(db_engine) as s:
        with pytest.raises(ValueError, match=r"shelters S-5: school_id .*SC-99"):
            await seed(s, tmp_path / "data")


def test_cli_reset_then_rerun_is_a_noop(
    db_url: str, seeded: SeedSummary, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["--reset", "--database-url", db_url]) == 0
    out = capsys.readouterr().out
    assert "zones" in out and "elevation_points" in out and "total" in out
    assert main(["--database-url", db_url]) == 0
    assert "already seeded" in capsys.readouterr().out
