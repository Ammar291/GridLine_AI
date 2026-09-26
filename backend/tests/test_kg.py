"""The knowledge graph is the seeded city database read through its own foreign keys; nothing is mocked."""

from typing import Any

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from gridline.city.model import City
from gridline.db.engine import session_factory
from gridline.db.models import Base
from gridline.db.seed import SeedSummary
from gridline.events.envelope import Event
from gridline.events.types import EventType
from gridline.kg.edges import ASSET_LINKS, EDGE_TYPES
from gridline.kg.models import KgEdge, NodeRef
from gridline.kg.query import KnowledgeGraph
from gridline.simulation.engine import SimulationEngine

REQUIRED_KINDS = {
    "zones",  # locations and population zones
    "roads",
    "hills",
    "slopes",
    "drainage_channels",
    "rivers",
    "projects",  # construction sites
    "hospitals",
    "shelters",
    "crews",  # rescue teams
    "residential_areas",  # population
    "historical_incidents",
    "critical_infrastructure",
    "power_substations",
    "bridges",
}


@pytest.fixture
async def sessions(db_engine: AsyncEngine, seeded: SeedSummary) -> async_sessionmaker[AsyncSession]:
    return session_factory(db_engine)


@pytest.fixture
def kg(sessions: async_sessionmaker[AsyncSession]) -> KnowledgeGraph:
    return KnowledgeGraph(sessions)


def simulated_landslide(city: City) -> Event:
    """Run the primary scenario until the engine reports the slope failure (no scripted shortcut)."""
    engine = SimulationEngine(city)
    engine.reset("cascading_landslide_flood", 42)
    for _ in range(300):
        for event in engine.advance():
            if event.event_type == EventType.INFRASTRUCTURE_FAILURE:
                return event
    raise AssertionError("the scenario produced no infrastructure failure")


async def edge_exists(sessions: async_sessionmaker[AsyncSession], edge: KgEdge) -> bool:
    """Re-read the database for one edge, independently of the graph code."""
    table, _, field = edge.via.partition(".")
    async with sessions() as s:
        if field:  # a foreign-key column on the source row
            column = Base.metadata.tables[table].c[field]
            row = (
                await s.execute(select(column).where(Base.metadata.tables[table].c.id == edge.source.id))
            ).one()
            value: Any = row[0]
            return value == edge.target.id or (isinstance(value, list) and edge.target.id in value)
        owner = "incident_id" if table == "historical_incident_impacts" else "id"
        query = text(f"select count(*) from {table} where {owner} = :src and asset_id = :dst")  # noqa: S608
        return (await s.execute(query, {"src": edge.source.id, "dst": edge.target.id})).scalar_one() > 0


def test_edge_schema_is_the_database_schema() -> None:
    tables = Base.metadata.tables
    for edge in EDGE_TYPES:
        assert edge.table in tables and edge.target in tables and edge.field in tables[edge.table].c, edge
    for link in ASSET_LINKS:
        assert {"asset_kind", "asset_id", link.owner_field} <= set(tables[link.table].c.keys())
    linked = (
        {e.table for e in EDGE_TYPES} | {e.target for e in EDGE_TYPES} | {a.owner_table for a in ASSET_LINKS}
    )
    assert linked >= REQUIRED_KINDS


async def test_neighbors_of_the_hillview_slope(kg: KnowledgeGraph) -> None:
    edges = await kg.neighbors(NodeRef(table="slopes", id="SL-HV-1"))
    found = {(e.source.id, e.relation, e.target.id) for e in edges}
    assert ("PR-HT2", "located on", "SL-HV-1") in found  # construction site on the hillside
    assert ("SL-HV-1", "toe drains into", "D-7") in found  # hillside connected to drainage
    assert ("SL-HV-1", "on hill", "HL-2") in found
    assert ("SL-HV-1", "in zone", "Z-HV") in found


async def test_simulated_landslide_traverses_the_knowledge_graph(
    kg: KnowledgeGraph, sessions: async_sessionmaker[AsyncSession], city: City
) -> None:
    failure = simulated_landslide(city)
    assert failure.payload["failure_kind"] == "landslide"
    start = NodeRef(table="slopes", id=str(failure.payload["asset_id"]))
    graph = await kg.traverse(start, max_depth=3)

    # the landslide reaches the downstream zone through the drain at its toe (3 entities, 2 hops)
    downstream = graph.path_to(NodeRef(table="zones", id="Z-RS"))
    assert [(e.source.id, e.relation, e.target.id) for e in downstream] == [
        ("SL-HV-1", "toe drains into", "D-7"),
        ("D-7", "flows to", "Z-RS"),
    ]
    # construction site -> hillside -> drainage -> downstream zone <- population: 5 entities, 4 relations
    chain = [
        graph.edge("PR-HT2", "located on", "SL-HV-1"),
        *downstream,
        graph.edge("RA-03", "population in", "Z-RS"),
    ]
    assert graph.entity(NodeRef(table="residential_areas", id="RA-03")).attributes["population"] == 22000
    # a past landslide on the same hillside is discovered too
    history = graph.edge("HI-2022-LS-01", "occurred in", "Z-HV")
    assert graph.entity(history.source).attributes["hazard"] == "landslide"
    # every edge the traversal reports is really in the database
    for edge in graph.edges:
        assert await edge_exists(sessions, edge), edge
    print(f"\n{len(graph.entities)} entities, {len(graph.edges)} edges")
    print("\n".join(graph.describe_path([*chain, history])))


async def test_traversal_respects_depth_and_unknown_nodes(kg: KnowledgeGraph) -> None:
    shallow = await kg.traverse(NodeRef(table="slopes", id="SL-HV-1"), max_depth=1)
    assert max(shallow.depth.values()) == 1
    assert NodeRef(table="zones", id="Z-RS").key not in shallow.entities
    with pytest.raises(LookupError):
        await kg.traverse(NodeRef(table="slopes", id="SL-NOPE"))
