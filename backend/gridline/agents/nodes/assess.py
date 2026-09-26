"""``reason`` (the LLM explains the threat from the evidence) and ``assess`` (grounding and threat band).

``reason`` joins signals, knowledge-graph edges, RAG chunks and live state into a ``ReasoningContext``
and asks the model; the JSON schema only admits citation ids present in that context. ``assess``
validates every citation anyway (non-negotiable 4), drops claims that cite anything else, and states the band.
"""

# pyright: reportTypedDictNotRequiredAccess=false
# (each node reads keys its predecessors set; the graph's edges guarantee they ran)

from gridline.agents.candidates import downstream_zones
from gridline.agents.nodes.llm_call import ask
from gridline.agents.nodes.observe import state_facts
from gridline.agents.reasoner import HeuristicReasoner, evidence_lines
from gridline.agents.state import (
    Node,
    ReasoningContext,
    ReasoningResult,
    RiskSignal,
    ThreatAssessment,
    WorkflowState,
    WorkflowUpdate,
)
from gridline.agents.steps import WorkflowAssessmentOutput, WorkflowClaim, WorkflowReasoningOutput
from gridline.kg.models import KgSubgraph
from gridline.llm.base import LLMProvider
from gridline.rag.citations import validate_citation_ids


def relevant_signals(signals: list[RiskSignal], graph: KgSubgraph) -> list[RiskSignal]:
    """Signals located in a zone the graph reached, or about an entity it reached."""
    ids = {e.ref.id for e in graph.entities.values()}
    return [s for s in signals if s.subject_id in ids or (s.zone_id is not None and s.zone_id in ids)]


def cited_ids(assessment: ThreatAssessment) -> list[str]:
    return [c for f in assessment.contributing_factors for c in f.citation_ids] + [
        c for claim in assessment.claims for c in claim.citation_ids
    ]


def make_reason(provider: LLMProvider | None) -> Node:
    async def reason(state: WorkflowState) -> WorkflowUpdate:
        trigger, graph = state["trigger"], state["graph"]
        context = ReasoningContext(
            trigger=trigger,
            signals=relevant_signals(state.get("signals", []), graph),
            graph=graph,
            evidence=state.get("retrieved", []),
            state=state_facts(state["world"], graph),
        )
        result, meta = await ask(
            provider,
            prompt="reason",
            fields={"hazard": trigger.hazard, "evidence": "\n".join(evidence_lines(context))},
            output=ReasoningResult,
            enums={"citation_ids": sorted(context.citation_ids())},
            fallback=lambda: HeuristicReasoner().reason(context),
        )
        out = WorkflowReasoningOutput(
            provider=meta.provider,
            model=meta.model,
            fallback_reason=meta.fallback_reason,
            duration_ms=meta.duration_ms,
            summary=result.summary,
            claims=[WorkflowClaim(text=c.text, citation_ids=c.citation_ids) for c in result.claims],
        )
        return {"context": context, "reasoning": result, "step_output": out}

    return reason


async def assess(state: WorkflowState) -> WorkflowUpdate:
    context, reasoning, trigger = state["context"], state["reasoning"], state["trigger"]
    allowed = context.citation_ids()
    cited = [c for claim in reasoning.claims for c in claim.citation_ids]
    unknown = validate_citation_ids(cited, allowed)
    grounded = [
        claim for claim in reasoning.claims if set(claim.citation_ids) <= allowed and claim.citation_ids
    ]
    zones = [trigger.zone_id, *(zone.id for zone, _ in downstream_zones(context.graph, trigger.zone_id))]
    out = WorkflowAssessmentOutput(
        hazard=trigger.hazard,
        band=reasoning.band,
        confidence=round(reasoning.confidence, 2),
        grounded=not unknown,
        cited_count=len(set(cited) & allowed),
        ungrounded_ids=unknown,
        affected_zone_ids=[z for z in dict.fromkeys(zones) if z],
    )
    return {
        "reasoning": reasoning.model_copy(update={"claims": grounded}),
        "assessment": out,
        "step_output": out,
    }
