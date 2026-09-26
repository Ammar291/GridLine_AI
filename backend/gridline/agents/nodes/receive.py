"""``receive`` (the failure that started the run) and ``query_graph`` (the knowledge graph around it)."""

# pyright: reportTypedDictNotRequiredAccess=false
# (each node reads keys its predecessors set; the graph's edges guarantee they ran)

from gridline.agents.state import Node, WorkflowState, WorkflowUpdate, trigger_from_failure
from gridline.agents.steps import (
    WorkflowEntity,
    WorkflowGraphOutput,
    WorkflowPath,
    WorkflowReceiveOutput,
)
from gridline.city.model import City
from gridline.errors import UnknownAsset
from gridline.events.payloads import InfrastructureFailure
from gridline.kg.models import KgSubgraph, NodeRef
from gridline.kg.query import KnowledgeGraph

GRAPH_DEPTH = 3


def asset_name(city: City, asset_id: str) -> str:
    groups = (city.slopes, city.channels, city.bridges, city.roads, city.substations, city.projects)
    return next((a.name for group in groups for a in group if a.id == asset_id), asset_id)


def zone_name(city: City, zone_id: str) -> str:
    try:
        return city.zone(zone_id).name
    except UnknownAsset:
        return zone_id


def make_receive(city: City) -> Node:
    async def receive(state: WorkflowState) -> WorkflowUpdate:
        event = state["trigger_event"]
        trigger = trigger_from_failure(event)
        failure = InfrastructureFailure.model_validate(event.payload)
        out = WorkflowReceiveOutput(
            event_id=event.event_id,
            hazard=trigger.hazard,
            failure_kind=failure.failure_kind,
            asset=WorkflowEntity(
                table=trigger.asset.table, id=trigger.asset.id, name=asset_name(city, trigger.asset.id)
            ),
            zone_id=trigger.zone_id,
            zone_name=zone_name(city, trigger.zone_id),
            description=failure.description,
            sim_time=trigger.sim_time,
            citation_id=trigger.citation_id,
        )
        return {"trigger": trigger, "step_output": out}

    return receive


def _entity(graph: KgSubgraph, ref: NodeRef) -> WorkflowEntity:
    return WorkflowEntity(table=ref.table, id=ref.id, name=graph.entity(ref).name)


def graph_paths(graph: KgSubgraph, trigger_zone: str) -> list[WorkflowPath]:
    """``project -> asset -> drain -> downstream zone`` chains; each part only where the graph has it."""
    start = graph.start
    projects = [e for e in graph.edges_of(start) if e.target == start and e.source.table == "projects"]
    chains: list[tuple[list[NodeRef], list[str], list[str]]] = []
    for drain in graph.edges_of(start):
        if drain.source != start or drain.target.table != "drainage_channels":
            continue
        for flow in graph.edges_of(drain.target):
            zone = flow.target
            if flow.source == drain.target and zone.table == "zones" and zone.id != trigger_zone:
                chains.append(
                    (
                        [drain.target, zone],
                        [drain.relation, flow.relation],
                        [drain.citation_id, flow.citation_id],
                    )
                )
    heads = [([p.source], [p.relation], [p.citation_id]) for p in projects] or [([], [], [])]
    paths: list[WorkflowPath] = []
    for head_nodes, head_rel, head_cite in heads:
        for tail_nodes, tail_rel, tail_cite in chains or [([], [], [])]:
            nodes = [*head_nodes, start, *tail_nodes]
            if len(nodes) > 1:
                paths.append(
                    WorkflowPath(
                        nodes=[_entity(graph, n) for n in nodes],
                        relations=[*head_rel, *tail_rel],
                        citation_ids=[*head_cite, *tail_cite],
                    )
                )
    return paths


def make_query_graph(kg: KnowledgeGraph) -> Node:
    async def query_graph(state: WorkflowState) -> WorkflowUpdate:
        trigger = state["trigger"]
        graph = await kg.traverse(trigger.asset, max_depth=GRAPH_DEPTH)
        out = WorkflowGraphOutput(
            start=_entity(graph, graph.start),
            entity_count=len(graph.entities),
            edge_count=len(graph.edges),
            paths=graph_paths(graph, trigger.zone_id),
        )
        return {"graph": graph, "step_output": out}

    return query_graph
