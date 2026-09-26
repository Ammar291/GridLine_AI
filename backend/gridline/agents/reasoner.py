"""The offline reasoner (the mock provider of ARCHITECTURE section 9, for the ``assess`` node).

It knows no scenario. Every factor is read from the ``ReasoningContext`` (signals, knowledge-graph edges,
retrieved chunks, live state) and cites the ids it was read from, so a different city, graph or reading
gives a different answer. The Anthropic provider will fill the same ``ThreatAssessment`` from the same input.
"""

from collections.abc import Iterable

from gridline.agents.state import (
    Candidate,
    Claim,
    ContributingFactor,
    PlanChoice,
    PlanPick,
    ReasoningContext,
    ReasoningResult,
    StateFact,
    ThreatAssessment,
)
from gridline.agents.steps import WorkflowBand
from gridline.events.types import SEVERITY_ORDER, Severity
from gridline.kg.models import KgEdge, KgSubgraph, NodeRef

MAX_SIGNALS = 4
MAX_EVIDENCE = 3
MAX_ASSETS = 6
EXPOSED_ASSETS = ("shelters", "hospitals", "crews", "roads")
AREA_TABLES = ("zones", "hills")

CF = ContributingFactor


def _label(graph: KgSubgraph, ref: NodeRef) -> str:
    return f"{ref.id} {graph.entity(ref).name}"


def _fact(context: ReasoningContext, ref: NodeRef) -> StateFact | None:
    return next((f for f in context.state if f.entity == ref), None)


def _values(fact: StateFact) -> str:
    shown = [
        f"{k} {round(v, 2) if isinstance(v, float) else v}"
        for k, v in fact.values.items()
        if v not in ("", None)
    ]
    return ", ".join(shown)


def _unique(refs: Iterable[NodeRef]) -> list[NodeRef]:
    return list(dict.fromkeys(refs))


def _signal_factors(context: ReasoningContext) -> list[ContributingFactor]:
    start = context.graph.start
    factors = [
        CF(
            factor="Reported failure",
            value=f"{context.trigger.hazard} on {_label(context.graph, start)}"
            f" at {context.trigger.sim_time:%H:%M}",
            citation_ids=[context.trigger.citation_id],
        )
    ]
    others = [
        s for s in context.signals if s.id != context.trigger.citation_id
    ]  # the failure is listed above
    ranked = sorted(others, key=lambda s: (-SEVERITY_ORDER.index(s.severity), s.id))
    factors += [
        CF(factor=f"{s.severity} reading", value=s.summary, citation_ids=[s.id]) for s in ranked[:MAX_SIGNALS]
    ]
    return factors


def _state_factors(context: ReasoningContext) -> list[ContributingFactor]:
    fact = _fact(context, context.graph.start)
    if fact is None:
        return []
    return [CF(factor=f"Current state of {fact.entity.id}", value=_values(fact), citation_ids=[fact.id])]


def _construction(context: ReasoningContext) -> list[ContributingFactor]:
    graph, start = context.graph, context.graph.start
    factors: list[ContributingFactor] = []
    for edge in graph.edges_of(start):
        if edge.target == start and edge.source.table == "projects":
            fact = _fact(context, edge.source)
            state = f" ({_values(fact)})" if fact else ""
            factors.append(
                CF(
                    factor="Construction on the threatened asset",
                    value=f"{_label(graph, edge.source)} is {edge.relation} {_label(graph, start)}{state}",
                    citation_ids=[edge.citation_id, *([fact.id] if fact else [])],
                )
            )
    return factors


def _downstream(context: ReasoningContext) -> tuple[list[ContributingFactor], list[NodeRef]]:
    """Drains leaving the asset and the zones they flow to (other than the asset's own zone)."""
    graph, start = context.graph, context.graph.start
    factors: list[ContributingFactor] = []
    zones: list[NodeRef] = []
    for drain in (
        e for e in graph.edges_of(start) if e.source == start and e.target.table == "drainage_channels"
    ):
        for flow in graph.edges_of(drain.target):
            if (
                flow.source == drain.target
                and flow.relation == "flows to"
                and flow.target.id != context.trigger.zone_id
            ):
                zones.append(flow.target)
                fact = _fact(context, drain.target)
                factors.append(
                    CF(
                        factor="Downstream path",
                        value=(
                            f"{_label(graph, start)} {drain.relation} {_label(graph, drain.target)}, "
                            f"which {flow.relation} {_label(graph, flow.target)}"
                            + (f" (drain now: {_values(fact)})" if fact else "")
                        ),
                        citation_ids=[drain.citation_id, flow.citation_id, *([fact.id] if fact else [])],
                    )
                )
    return factors, _unique(zones)


def _into(graph: KgSubgraph, zone: NodeRef, tables: tuple[str, ...]) -> list[KgEdge]:
    return [e for e in graph.edges_of(zone) if e.target == zone and e.source.table in tables]


def _exposure(context: ReasoningContext, zones: list[NodeRef]) -> tuple[list[ContributingFactor], int]:
    graph = context.graph
    factors: list[ContributingFactor] = []
    residents = 0
    for zone in zones:
        people = _into(graph, zone, ("residential_areas",))
        if people:
            counts = [(e, int(graph.entity(e.source).attributes.get("population", 0))) for e in people]
            total = sum(n for _, n in counts)
            residents += total
            listed = ", ".join(f"{_label(graph, e.source)} ({n:,})" for e, n in counts)
            factors.append(
                CF(
                    factor="Population downstream",
                    value=f"{total:,} residents in {_label(graph, zone)}: {listed}",
                    citation_ids=[e.citation_id for e, _ in counts],
                )
            )
        assets = list({e.source.key: e for e in _into(graph, zone, EXPOSED_ASSETS)}.values())[:MAX_ASSETS]
        if assets:
            factors.append(
                CF(
                    factor="Emergency assets and access downstream",
                    value=f"in {_label(graph, zone)}: " + ", ".join(_label(graph, e.source) for e in assets),
                    citation_ids=[e.citation_id for e in assets],
                )
            )
    return factors, residents


def _history(context: ReasoningContext) -> list[ContributingFactor]:
    """Past incidents of the same hazard linked to the asset, its zone or its hill."""
    graph, start = context.graph, context.graph.start
    around = [e.other(start) for e in graph.edges_of(start) if e.other(start).table in AREA_TABLES]
    near = {start.key, *(ref.key for ref in around)}
    factors: list[ContributingFactor] = []
    for incident in sorted(graph.of_table("historical_incidents"), key=lambda i: i.ref.id):
        if incident.attributes.get("hazard") != context.trigger.hazard:
            continue
        links = [e for e in graph.edges_of(incident.ref) if e.other(incident.ref).key in near]
        if links:
            place = ", ".join(f"{e.relation} {_label(graph, e.other(incident.ref))}" for e in links)
            factors.append(
                CF(
                    factor=f"Past {context.trigger.hazard} in the same area",
                    value=f"{_label(graph, incident.ref)} ({incident.attributes.get('started_on')}), {place}",
                    citation_ids=[e.citation_id for e in links],
                )
            )
    return factors


def _evidence(context: ReasoningContext) -> list[ContributingFactor]:
    return [
        CF(factor="Documented guidance", value=f"{c.document_title}, {c.section}", citation_ids=[c.chunk_id])
        for c in context.evidence[:MAX_EVIDENCE]
    ]


class HeuristicReasoner:
    def assess(self, context: ReasoningContext) -> ThreatAssessment:
        graph, hazard = context.graph, context.trigger.hazard
        construction = _construction(context)
        downstream, zones = _downstream(context)
        exposure, residents = _exposure(context, zones)
        history = _history(context)
        evidence = _evidence(context)
        factors = [
            *_signal_factors(context),
            *_state_factors(context),
            *construction,
            *downstream,
            *exposure,
            *history,
            *evidence,
        ]
        severe = any(s.severity in (Severity.HIGH, Severity.CRITICAL) for s in context.signals)
        support = [severe, bool(construction), bool(downstream), bool(history), bool(evidence)]
        confidence = round(min(0.95, 0.3 + 0.13 * sum(support)), 2)
        where = ", ".join(_label(graph, z) for z in zones) or "no downstream zone"
        summary = (
            f"{hazard.capitalize()} on {_label(graph, graph.start)}. "
            f"The knowledge graph links it to {where}, "
            f"{residents:,} residents downstream and {len(history)} past {hazard} event(s) in the same area; "
            f"{len(context.signals)} elevated reading(s) and {len(evidence)} document section(s) "
            "support this."
        )
        claims = [Claim(text=f"{f.factor}: {f.value}", citation_ids=f.citation_ids) for f in factors]
        return ThreatAssessment(
            hazard=hazard, summary=summary, contributing_factors=factors, confidence=confidence, claims=claims
        )

    def reason(self, context: ReasoningContext) -> ReasoningResult:
        """The ``reason`` step offline: band from the worst relevant reading, claims from the factors."""
        assessment = self.assess(context)
        return ReasoningResult(
            summary=assessment.summary,
            band=band_of(context),
            confidence=assessment.confidence,
            claims=assessment.claims[:5]
            or [Claim(text=assessment.summary, citation_ids=[context.trigger.citation_id])],
        )

    def recommend(self, candidates: list[Candidate]) -> PlanChoice:
        """The ``recommend`` step offline: every candidate, justified by the evidence it was built from."""
        return PlanChoice(
            actions=[
                PlanPick(candidate_id=c.candidate_id, rationale=f"{c.why}.", citation_ids=c.citation_ids)
                for c in candidates[:6]
            ]
        )


BANDS: dict[Severity, WorkflowBand] = {
    Severity.CRITICAL: "critical",
    Severity.HIGH: "warning",
    Severity.MODERATE: "watch",
}


def band_of(context: ReasoningContext) -> WorkflowBand:
    """The worst relevant sensor band mapped to a threat band (a reported failure is at least ``warning``)."""
    worst = max((SEVERITY_ORDER.index(s.severity) for s in context.signals), default=0)
    band = BANDS.get(SEVERITY_ORDER[worst], "normal")
    return "warning" if band in ("normal", "watch") else band


def evidence_lines(context: ReasoningContext) -> list[str]:
    """The facts the model may use, one per line, each led by the ids it may cite."""
    factors = HeuristicReasoner().assess(context).contributing_factors
    lines = [f"[{', '.join(f.citation_ids)}] {f.factor}: {f.value}" for f in factors]
    lines += [
        f"[{c.chunk_id}] {c.document_title}, {c.section}: {' '.join(c.text.split())[:420]}"
        for c in context.evidence[:6]
    ]
    return lines
