"""Queries over the knowledge graph: plain SQL on the seeded city tables, one batch of queries per BFS level.

``neighbors`` returns every edge touching one entity, in both directions; ``traverse`` walks outwards from a
start entity and returns the entities reached, the tree that reached them, and every edge among them.
"""

from collections import defaultdict
from collections.abc import Iterable, Sequence
from datetime import date, datetime
from typing import Any, cast

from sqlalchemy import Table, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from gridline.db.models import Base
from gridline.kg.edges import ASSET_LINKS, ASSET_TABLES, EDGE_TYPES, KIND_OF_TABLE, SKIPPED_TABLES
from gridline.kg.models import KgEdge, KgEntity, KgSubgraph, NodeRef

NAME_COLUMNS = ("name", "title", "description")


def _table(name: str) -> Table:
    table = Base.metadata.tables.get(name)
    if table is None:
        raise LookupError(f"no table {name!r} in the city database")
    return table


def _scalar(value: Any) -> bool:
    return isinstance(value, str | int | float | bool | date | datetime)


def _targets(value: Any) -> list[str]:
    """A foreign-key value as target ids: a JSON list for ``*_ids`` columns, else one id (or none)."""
    if isinstance(value, list):
        return [str(v) for v in cast(list[Any], value) if v is not None]
    return [] if value is None else [str(value)]


def _sorted(edges: Iterable[KgEdge]) -> list[KgEdge]:
    """Stable order, so the same database always yields the same tree."""
    return sorted(set(edges), key=lambda e: (e.via, e.source.id, e.target.id))


class KnowledgeGraph:
    def __init__(
        self, sessions: async_sessionmaker[AsyncSession], *, skip: frozenset[str] = SKIPPED_TABLES
    ) -> None:
        self._sessions = sessions
        self._skip = skip

    async def neighbors(self, node: NodeRef) -> list[KgEdge]:
        async with self._sessions() as s:
            await self._require(s, node)
            return await self._edges(s, [node])

    async def traverse(self, start: NodeRef, *, max_depth: int = 3, max_nodes: int = 400) -> KgSubgraph:
        async with self._sessions() as s:
            await self._require(s, start)
            depth: dict[str, int] = {start.key: 0}
            reached: dict[str, NodeRef] = {start.key: start}
            parent: dict[str, KgEdge] = {}
            seen_edges: list[KgEdge] = []
            frontier = [start]
            for level in range(1, max_depth + 1):
                found: list[NodeRef] = []
                for edge in await self._edges(s, frontier):
                    seen_edges.append(edge)
                    for node in (edge.source, edge.target):
                        if node.key in depth or node.table in self._skip or len(depth) >= max_nodes:
                            continue
                        depth[node.key] = level
                        reached[node.key] = node
                        parent[node.key] = edge
                        found.append(node)
                if not found:
                    break
                frontier = found
            entities = await self._entities(s, list(reached.values()))
        inside = [e for e in seen_edges if e.source.key in entities and e.target.key in entities]
        return KgSubgraph(start=start, entities=entities, depth=depth, edges=_sorted(inside), parent=parent)

    # ---- SQL ----

    async def _require(self, s: AsyncSession, node: NodeRef) -> None:
        table = _table(node.table)
        if (await s.execute(select(table.c.id).where(table.c.id == node.id))).first() is None:
            raise LookupError(f"{node.key} is not in the city database")

    async def _edges(self, s: AsyncSession, nodes: Sequence[NodeRef]) -> list[KgEdge]:
        by_table: dict[str, set[str]] = defaultdict(set)
        for node in nodes:
            by_table[node.table].add(node.id)
        edges: list[KgEdge] = []
        for table_name, ids in by_table.items():
            edges += await self._outgoing(s, table_name, ids)
            edges += await self._incoming(s, table_name, ids)
            edges += await self._asset_links(s, table_name, ids)
        return _sorted(
            e for e in edges if e.source.table not in self._skip and e.target.table not in self._skip
        )

    async def _outgoing(self, s: AsyncSession, table_name: str, ids: set[str]) -> list[KgEdge]:
        types = [t for t in EDGE_TYPES if t.table == table_name]
        if not types:
            return []
        table = _table(table_name)
        rows = await s.execute(
            select(table.c.id, *(table.c[t.field] for t in types)).where(table.c.id.in_(ids))
        )
        edges: list[KgEdge] = []
        for row in rows:
            for t, value in zip(types, row[1:], strict=True):
                for target in _targets(value):
                    edges.append(
                        _edge(table_name, str(row[0]), t.label, t.target, target, f"{t.table}.{t.field}")
                    )
        return edges

    async def _incoming(self, s: AsyncSession, table_name: str, ids: set[str]) -> list[KgEdge]:
        edges: list[KgEdge] = []
        for t in (t for t in EDGE_TYPES if t.target == table_name and t.table not in self._skip):
            source = _table(t.table)
            column = source.c[t.field]
            query = select(source.c.id, column)
            query = query.where(column.is_not(None)) if t.many else query.where(column.in_(ids))
            for src_id, value in await s.execute(query):
                for target in _targets(value):
                    if target in ids:
                        edges.append(
                            _edge(t.table, str(src_id), t.label, table_name, target, f"{t.table}.{t.field}")
                        )
        return edges

    async def _asset_links(self, s: AsyncSession, table_name: str, ids: set[str]) -> list[KgEdge]:
        edges: list[KgEdge] = []
        kind = KIND_OF_TABLE.get(table_name)
        for link in ASSET_LINKS:
            rows = _table(link.table)
            owner = rows.c[link.owner_field]
            if kind is not None:  # assets in ``ids`` <- the incidents / changes that name them
                query = select(owner, rows.c.asset_id).where(
                    rows.c.asset_kind == kind, rows.c.asset_id.in_(ids)
                )
                for owner_id, asset_id in await s.execute(query):
                    edges.append(
                        _edge(
                            link.owner_table, str(owner_id), link.label, table_name, str(asset_id), link.table
                        )
                    )
            if table_name == link.owner_table:  # incidents / changes in ``ids`` -> the assets they name
                query = select(owner, rows.c.asset_kind, rows.c.asset_id).where(owner.in_(ids))
                for owner_id, asset_kind, asset_id in await s.execute(query):
                    target = ASSET_TABLES.get(str(asset_kind))
                    if target is not None:
                        edges.append(
                            _edge(table_name, str(owner_id), link.label, target, str(asset_id), link.table)
                        )
        return edges

    async def _entities(self, s: AsyncSession, refs: Sequence[NodeRef]) -> dict[str, KgEntity]:
        by_table: dict[str, set[str]] = defaultdict(set)
        for ref in refs:
            by_table[ref.table].add(ref.id)
        entities: dict[str, KgEntity] = {}
        for table_name, ids in by_table.items():
            table = _table(table_name)
            for row in (await s.execute(select(table).where(table.c.id.in_(ids)))).mappings():
                ref = NodeRef(table=table_name, id=str(row["id"]))
                name = next((str(row[c]) for c in NAME_COLUMNS if c in row and row[c]), ref.id)
                attributes = {k: v for k, v in row.items() if _scalar(v)}
                entities[ref.key] = KgEntity(ref=ref, name=name, attributes=attributes)
        return entities


def _edge(src_table: str, src_id: str, label: str, dst_table: str, dst_id: str, via: str) -> KgEdge:
    return KgEdge(
        source=NodeRef(table=src_table, id=src_id),
        relation=label,
        target=NodeRef(table=dst_table, id=dst_id),
        via=via,
    )
