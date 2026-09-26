"""Knowledge-graph values: entities are city rows, edges are their foreign keys and asset links."""

from typing import Any

from pydantic import BaseModel, ConfigDict


class NodeRef(BaseModel):
    """One row of the city database: its table and primary key."""

    model_config = ConfigDict(frozen=True)

    table: str
    id: str

    @property
    def key(self) -> str:
        return f"{self.table}:{self.id}"


class KgEntity(BaseModel):
    ref: NodeRef
    name: str
    attributes: dict[str, Any]  # the row's scalar columns, as stored


class KgEdge(BaseModel):
    """``source`` holds the reference, pointing at ``target``; ``via`` is ``table.field`` or a link table."""

    model_config = ConfigDict(frozen=True)

    source: NodeRef
    relation: str
    target: NodeRef
    via: str

    @property
    def citation_id(self) -> str:
        """Cite-able id for the reasoning context, e.g. ``kg:projects.slope_id:PR-HT2->SL-HV-1``."""
        return f"kg:{self.via}:{self.source.id}->{self.target.id}"

    def other(self, node: NodeRef) -> NodeRef:
        return self.target if node == self.source else self.source


class KgSubgraph(BaseModel):
    """What a traversal discovered: every entity reached, and the edge that first reached it (a BFS tree)."""

    start: NodeRef
    entities: dict[str, KgEntity]  # keyed by NodeRef.key
    depth: dict[str, int]  # hops from ``start``, keyed by NodeRef.key
    edges: list[KgEdge]
    parent: dict[str, KgEdge]  # the edge that discovered each non-start entity

    def entity(self, ref: NodeRef) -> KgEntity:
        return self.entities[ref.key]

    def of_table(self, table: str) -> list[KgEntity]:
        return [e for e in self.entities.values() if e.ref.table == table]

    def edges_of(self, ref: NodeRef) -> list[KgEdge]:
        return [e for e in self.edges if ref in (e.source, e.target)]

    def edge(self, source_id: str, relation: str, target_id: str) -> KgEdge:
        """The discovered edge ``source --relation--> target``; raises ``KeyError`` if the graph has none."""
        for e in self.edges:
            if (e.source.id, e.relation, e.target.id) == (source_id, relation, target_id):
                return e
        raise KeyError(f"{source_id} --{relation}--> {target_id}")

    def path_to(self, ref: NodeRef) -> list[KgEdge]:
        """Edges from ``start`` to ``ref`` in walking order; raises ``KeyError`` if it was not reached."""
        if ref.key not in self.entities:
            raise KeyError(ref.key)
        path: list[KgEdge] = []
        node = ref
        while node != self.start:
            edge = self.parent[node.key]
            path.append(edge)
            node = edge.other(node)
        return path[::-1]

    def describe_path(self, path: list[KgEdge]) -> list[str]:
        """One line per hop, in edge direction: ``D-7 Kalinadi drain --flows to--> Z-RS Riverside``."""
        lines: list[str] = []
        for edge in path:
            src, dst = self.entity(edge.source), self.entity(edge.target)
            lines.append(f"{src.ref.id} {src.name} --{edge.relation}--> {dst.ref.id} {dst.name}")
        return lines
