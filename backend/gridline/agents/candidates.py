"""Candidate actions for ``recommend``: valid tool calls read off the knowledge graph around the failure.

The model chooses among these and writes each rationale; it never invents a tool, an argument or an id. The
rules are generic (projects on the failed asset, the asset itself, drains leaving it, zones downstream), so a
different city or graph gives different candidates.
"""

from gridline.agents.state import Candidate, ReasoningContext
from gridline.kg.models import KgSubgraph, NodeRef
from gridline.simulation.world import WorldSnapshot

MAX_CANDIDATES = 10
TARGET_KINDS = {"slopes": "slope", "drainage_channels": "channel", "bridges": "bridge", "roads": "road"}
METRICS = {"slope": "soil_saturation", "channel": "flow_capacity", "bridge": "scour", "road": "debris"}


def _label(graph: KgSubgraph, ref: NodeRef) -> str:
    return f"{ref.id} {graph.entity(ref).name}"


def _halts(context: ReasoningContext, world: WorldSnapshot) -> list[Candidate]:
    graph, start = context.graph, context.graph.start
    out: list[Candidate] = []
    for edge in graph.edges_of(start):
        project = edge.source
        if edge.target != start or project.table != "projects":
            continue
        if graph.entity(project).attributes.get("status") == "halted":  # the database row, which tools act on
            continue
        state_ids = [f"state:projects.{project.id}"] if project.id in world.projects else []
        out.append(
            Candidate(
                candidate_id=f"halt:{project.id}",
                tool="create_construction_restriction",
                input={"project_id": project.id, "kind": "halt"},
                text_field="reason",
                label=f"Pause excavation at {_label(graph, project)}",
                why=f"{_label(graph, project)} is {edge.relation} {_label(graph, start)}",
                citation_ids=[edge.citation_id, *state_ids],
            )
        )
    return out


def _inspect_and_monitor(context: ReasoningContext) -> list[Candidate]:
    graph, start, trigger = context.graph, context.graph.start, context.trigger
    kind = TARGET_KINDS.get(start.table)
    if kind is None:
        return []
    out = [
        Candidate(
            candidate_id=f"inspect:{kind}:{start.id}",
            tool="create_inspection_order",
            input={"target_kind": kind, "target_id": start.id, "priority": "high"},
            text_field="reason",
            label=f"Create inspection order for {_label(graph, start)}",
            why=f"{trigger.hazard} reported on {_label(graph, start)}",
            citation_ids=[trigger.citation_id],
        ),
        Candidate(
            candidate_id=f"monitor:{kind}:{start.id}",
            tool="create_monitoring_task",
            input={
                "target_kind": kind,
                "target_id": start.id,
                "metric": METRICS[kind],
                "interval_minutes": 15,
            },
            text_field="reason",
            label=f"Monitor {METRICS[kind].replace('_', ' ')} on {_label(graph, start)} every 15 min",
            why=f"{trigger.hazard} reported on {_label(graph, start)}",
            citation_ids=[trigger.citation_id],
        ),
    ]
    for edge in graph.edges_of(start):
        if edge.source == start and edge.target.table == "drainage_channels":
            out.append(
                Candidate(
                    candidate_id=f"inspect:channel:{edge.target.id}",
                    tool="create_inspection_order",
                    input={"target_kind": "channel", "target_id": edge.target.id, "priority": "high"},
                    text_field="reason",
                    label=f"Create inspection order for {_label(graph, edge.target)}",
                    why=f"{_label(graph, start)} {edge.relation} {_label(graph, edge.target)}",
                    citation_ids=[edge.citation_id],
                )
            )
    return out


def downstream_zones(graph: KgSubgraph, trigger_zone: str) -> list[tuple[NodeRef, list[str]]]:
    """Zones that drains leaving the start asset flow to, with the two edges that lead there."""
    start = graph.start
    found: dict[str, tuple[NodeRef, list[str]]] = {}
    for drain in graph.edges_of(start):
        if drain.source != start or drain.target.table != "drainage_channels":
            continue
        for flow in graph.edges_of(drain.target):
            if (
                flow.source == drain.target
                and flow.target.table == "zones"
                and flow.target.id != trigger_zone
            ):
                found.setdefault(flow.target.id, (flow.target, [drain.citation_id, flow.citation_id]))
    return list(found.values())


def _alerts(context: ReasoningContext) -> list[Candidate]:
    graph, trigger = context.graph, context.trigger
    zones: list[tuple[NodeRef, list[str]]] = []
    home = NodeRef(table="zones", id=trigger.zone_id)
    if trigger.zone_id and home.key in graph.entities:
        zones.append((home, [trigger.citation_id]))
    zones += downstream_zones(graph, trigger.zone_id)
    return [
        Candidate(
            candidate_id=f"alert:{zone.id}",
            tool="issue_preventive_alert",
            input={"zone_id": zone.id, "level": "warning"},
            text_field="message",
            label=f"Issue warning alert for {_label(graph, zone)}",
            why=f"{_label(graph, zone)} is {'where the failure is' if zone == home else 'downstream'}",
            citation_ids=cites,
        )
        for zone, cites in zones
    ]


def build_candidates(context: ReasoningContext, world: WorldSnapshot) -> list[Candidate]:
    return [*_halts(context, world), *_inspect_and_monitor(context), *_alerts(context)][:MAX_CANDIDATES]
