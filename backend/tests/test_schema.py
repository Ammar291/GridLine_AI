from sqlalchemy import inspect, text

from gridline.db.models import EXPECTED_TABLES, Base
from gridline.db.schema import create_schema


async def test_schema_has_documents_and_chunks(db_engine):
    async with db_engine.connect() as conn:
        rows = await conn.execute(
            text("select table_name from information_schema.tables where table_schema = 'public' order by 1")
        )
        names = {r[0] for r in rows}
    assert {"documents", "chunks"} <= names


async def test_chunks_have_vector_column_and_hnsw_index(db_engine):
    async with db_engine.connect() as conn:
        col = await conn.execute(
            text(
                "select udt_name from information_schema.columns "
                "where table_name='chunks' and column_name='embedding'"
            )
        )
        assert col.scalar_one() == "vector"
        idx = await conn.execute(text("select indexdef from pg_indexes where tablename = 'chunks'"))
        defs = " ".join(r[0] for r in idx)
    assert "hnsw" in defs and "vector_cosine_ops" in defs


# --- city data layer (plan Task 2) -------------------------------------------------------------------------


def test_expected_tables_are_the_38_city_and_knowledge_tables():
    assert len(EXPECTED_TABLES) == 38
    assert set(Base.metadata.tables) >= EXPECTED_TABLES


async def test_all_expected_tables_exist(db_engine):
    async with db_engine.connect() as conn:
        names = await conn.run_sync(lambda c: set(inspect(c).get_table_names()))
    assert names >= EXPECTED_TABLES


async def test_key_columns_present(db_engine):
    expected = {
        "zones": {"slope_deg", "soil_type", "catchment_id", "drains_to_channel_id", "svg_path", "area_km2"},
        "roads": {"status", "is_evacuation_route", "path", "min_elevation_m"},
        "drainage_channels": {
            "design_capacity_m3s",
            "current_capacity_m3s",
            "blocked_fraction",
            "downstream_zone_id",
        },
        "projects": {"excavation_depth_m", "planned_depth_m", "permit_doc_id", "slope_id"},
        "slopes": {"mean_angle_deg", "toe_channel_id", "elevation_m"},
        "tunnels": {"low_point_elevation_m", "sump_pump_ids"},
        "zone_yearly_stats": {"year", "population", "density_per_km2"},
        "historical_incidents": {"hazard", "started_on", "rainfall_24h_mm", "document_id"},
        "historical_incident_impacts": {"incident_id", "asset_kind", "asset_id", "impact"},
        "infrastructure_changes": {"effective_date", "value_before", "value_after", "related_incident_id"},
        "elevation_points": {"x_m", "y_m", "elevation_m"},
        "documents": {"title", "kind", "source", "version", "effective_date", "source_path"},
        "document_sections": {"document_id", "section", "heading", "text", "position"},
        "policy_thresholds": {"document_id", "section", "metric", "band", "operator", "value"},
    }
    async with db_engine.connect() as conn:
        for table, cols in expected.items():
            names = await conn.run_sync(lambda c, t=table: {col["name"] for col in inspect(c).get_columns(t)})
            assert cols <= names, table


async def _referred(db_engine, table):
    async with db_engine.connect() as conn:
        fks = await conn.run_sync(lambda c: inspect(c).get_foreign_keys(table))
    return {(tuple(fk["constrained_columns"]), fk["referred_table"]) for fk in fks}


async def test_zone_channel_fk_is_present(db_engine):
    assert (("drains_to_channel_id",), "drainage_channels") in await _referred(db_engine, "zones")


async def test_cross_table_fks_are_present(db_engine):
    assert (("slope_id",), "slopes") in await _referred(db_engine, "projects")
    assert (("permit_doc_id",), "documents") in await _referred(db_engine, "projects")
    assert (("downstream_zone_id",), "zones") in await _referred(db_engine, "drainage_channels")
    assert (("school_id",), "schools") in await _referred(db_engine, "shelters")
    assert (("shelter_id",), "shelters") in await _referred(db_engine, "schools")
    ps_fks = await _referred(db_engine, "power_substations")
    assert (("fed_from_substation_id",), "power_substations") in ps_fks
    impact_fks = await _referred(db_engine, "historical_incident_impacts")
    assert (("incident_id",), "historical_incidents") in impact_fks
    assert (("document_id",), "documents") in await _referred(db_engine, "infrastructure_changes")
    # rivers.gauge_sensor_id is deliberately a plain string (sensors -> rivers exists; avoids a cycle).
    assert not any(cols == ("gauge_sensor_id",) for cols, _ in await _referred(db_engine, "rivers"))


async def test_elevation_points_has_composite_primary_key(db_engine):
    async with db_engine.connect() as conn:
        pk = await conn.run_sync(lambda c: inspect(c).get_pk_constraint("elevation_points"))
    assert set(pk["constrained_columns"]) == {"x_m", "y_m"}


async def test_create_schema_is_idempotent(db_engine):
    await create_schema(db_engine)
    async with db_engine.connect() as conn:
        names = await conn.run_sync(lambda c: set(inspect(c).get_table_names()))
    assert names >= EXPECTED_TABLES


async def test_zone_channel_cycle_round_trips_through_relationships(db_engine):
    """Zones and channels reference each other; the deferred FK lets both go in one transaction."""
    from sqlalchemy.ext.asyncio import AsyncSession

    from gridline.db.models import Catchment, DrainageChannel, GeologicalZone, River, Zone

    async with AsyncSession(db_engine, expire_on_commit=False) as session, session.begin():
        session.add(
            GeologicalZone(
                id="GZ-T",
                name="t",
                lithology="t",
                description="t",
                permeability_class="t",
                bearing_capacity_class="t",
                hazard_notes="t",
            )
        )
        session.add(River(id="R-T", name="t", kind="river", description="t", path=[[0, 0], [1, 1]]))
        await session.flush()  # the unit of work orders inserts by relationships only, not by bare FKs
        session.add(
            Catchment(
                id="CT-T",
                name="t",
                zone_ids=["Z-T"],
                area_km2=1.0,
                outlet_river_id="R-T",
                outlet_description="t",
                impervious_pct_2018=1.0,
                impervious_pct_2026=2.0,
            )
        )
        await session.flush()
        zone = dict(
            kind="t", slope_deg=1.0, soil_type="t", geological_zone_id="GZ-T", catchment_id="CT-T",
            description="t", area_km2=1.0, elevation_min_m=1.0, elevation_max_m=2.0, elevation_mean_m=1.5,
            svg_path="M0 0",
        )  # fmt: skip
        session.add(Zone(id="Z-T", name="up", bbox=[0, 0, 1, 1], drains_to_channel_id="D-T", **zone))
        session.add(Zone(id="Z-T2", name="down", bbox=[1, 1, 2, 2], **zone))
        await session.flush()  # the zone row references a channel that does not exist yet
        session.add(
            DrainageChannel(
                id="D-T", name="t", kind="t", catchment_id="CT-T", upstream_zone_id="Z-T",
                downstream_zone_id="Z-T2", x_m=0, y_m=0, elevation_m=212.0, length_m=1.0, year_built=2000,
                design_capacity_m3s=42.0, current_capacity_m3s=27.0, blocked_fraction=0.0, condition="fair",
                description="t",
            )
        )  # fmt: skip
        await session.flush()
        session.expunge_all()
        loaded = await session.get(Zone, "Z-T")
        assert loaded is not None
        channel = await loaded.awaitable_attrs.channel
        assert channel is not None and channel.id == "D-T"
        downstream = await channel.awaitable_attrs.downstream_zone
        assert downstream.name == "down"
        await session.rollback()
