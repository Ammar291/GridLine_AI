"""``observe``: deterministic risk signals (the latest banded reading per source) and live state facts."""

from gridline.agents.state import RiskSignal, StateFact, WorkflowState, WorkflowUpdate
from gridline.agents.steps import WorkflowObserveOutput, WorkflowSignal
from gridline.events.envelope import Event
from gridline.events.types import SEVERITY_ORDER, Severity
from gridline.kg.models import KgSubgraph
from gridline.simulation.world import WorldSnapshot

SIGNAL_PREFIXES = ("weather.", "environment.", "infrastructure.")
SUBJECT_KEYS = (
    "slope_id",
    "channel_id",
    "station_id",
    "probe_id",
    "gauge_id",
    "zone_id",
    "asset_id",
    "project_id",
    "road_id",
)


def _subject(event: Event) -> str:
    return next((str(event.payload[k]) for k in SUBJECT_KEYS if event.payload.get(k)), event.source)


def _summary(event: Event) -> str:
    numbers = [
        f"{k}={v}" for k, v in event.payload.items() if isinstance(v, int | float) and not isinstance(v, bool)
    ]
    detail = ", ".join(numbers[:4]) or ", ".join(f"{k}={v}" for k, v in event.payload.items())
    return f"{event.event_type} from {event.source}: {detail}"


def latest_signals(events: list[Event], minimum: Severity = Severity.MODERATE) -> list[RiskSignal]:
    """The last reading per (type, source), kept when its fixed sensor band is ``minimum`` or worse."""
    latest: dict[tuple[str, str], Event] = {}
    for event in events:
        if event.event_type.startswith(SIGNAL_PREFIXES):
            latest[(event.event_type, event.source)] = event
    floor = SEVERITY_ORDER.index(minimum)
    return [
        RiskSignal(
            id=f"event:{e.event_id}",
            event_type=e.event_type,
            source=e.source,
            zone_id=e.location,
            subject_id=_subject(e),
            severity=e.severity,
            summary=_summary(e),
        )
        for e in latest.values()
        if SEVERITY_ORDER.index(e.severity) >= floor
    ]


def state_facts(world: WorldSnapshot, graph: KgSubgraph) -> list[StateFact]:
    """Live world values for every entity the knowledge graph reached that the simulation tracks."""
    tracked = {
        "zones": world.zones,
        "slopes": world.slopes,
        "drainage_channels": world.channels,
        "rivers": world.rivers,
        "roads": world.roads,
        "bridges": world.bridges,
        "projects": world.projects,
        "crews": world.crews,
        "hospitals": world.hospitals,
        "shelters": world.shelters,
    }
    facts: list[StateFact] = []
    for entity in graph.entities.values():
        values = tracked.get(entity.ref.table, {}).get(entity.ref.id)
        if values is not None:
            facts.append(
                StateFact(
                    id=f"state:{entity.ref.table}.{entity.ref.id}",
                    entity=entity.ref,
                    values=values.model_dump(),
                )
            )
    return facts


READING_NAMES = {
    "weather.observation": "rainfall",
    "weather.forecast": "rain forecast",
    "environment.soil": "soil saturation",
    "environment.slope": "slope movement",
    "environment.river": "river level",
    "environment.drainage": "drainage load",
    "environment.water_accumulation": "standing water",
}


def reading_name(event_type: str) -> str:
    return READING_NAMES.get(event_type, event_type.split(".")[-1].replace("_", " "))


def headline(signals: list[RiskSignal]) -> str:
    """The three worst readings in plain words, e.g. ``soil saturation critical at SM-HV1``."""
    if not signals:
        return "No sensor reading is above its normal band."
    worst = sorted(signals, key=lambda s: (-SEVERITY_ORDER.index(s.severity), s.id))[:3]
    parts = [f"{reading_name(s.event_type)} {s.severity} at {s.source}" for s in worst]
    text = "; ".join(parts)
    return f"{len(signals)} elevated reading(s): {text[0].upper()}{text[1:]}."


async def observe(state: WorkflowState) -> WorkflowUpdate:
    signals = latest_signals(state.get("recent_events", []))
    out = WorkflowObserveOutput(
        headline=headline(signals),
        signals=[
            WorkflowSignal(
                id=s.id,
                event_type=s.event_type,
                source=s.source,
                zone_id=s.zone_id,
                severity=s.severity,
                summary=s.summary,
            )
            for s in signals
        ],
    )
    return {"signals": signals, "step_output": out}
