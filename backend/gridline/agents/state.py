"""Reasoning-slice state (ARCHITECTURE section 8): the trigger, the four kinds of input, and the assessment.

Every input carries a citation id, and the assessment may cite only those ids:
``event:<id>`` a deterministic sensor band, ``kg:<table.field>:<src>-><dst>`` a knowledge-graph edge,
``<doc>#<section>`` a RAG chunk, and ``state:<table>.<id>`` a live world value.
"""

from collections.abc import Awaitable
from typing import Any, Literal, Protocol, Required, TypedDict

from pydantic import AwareDatetime, BaseModel, Field, field_validator

from gridline.agents.steps import (
    WorkflowAction,
    WorkflowAssessmentOutput,
    WorkflowBand,
    WorkflowDecision,
    WorkflowOutput,
    WorkflowVerificationOutput,
)
from gridline.events.envelope import Event
from gridline.events.payloads import InfrastructureFailure
from gridline.events.types import Severity
from gridline.kg.edges import ASSET_TABLES
from gridline.kg.models import KgSubgraph, NodeRef
from gridline.rag.models import RetrievedChunk
from gridline.simulation.world import WorldSnapshot
from gridline.tools.base import ActionResult

Hazard = Literal["landslide", "flood"]
FAILURE_TABLES = {**ASSET_TABLES, "channel": "drainage_channels", "power": "power_substations"}


class ThreatTrigger(BaseModel):
    hazard: Hazard
    zone_id: str
    asset: NodeRef
    event_id: str
    sim_time: AwareDatetime

    @property
    def citation_id(self) -> str:
        return f"event:{self.event_id}"


def trigger_from_failure(event: Event) -> ThreatTrigger:
    failure = InfrastructureFailure.model_validate(event.payload)
    return ThreatTrigger(
        hazard="landslide" if failure.failure_kind == "landslide" else "flood",
        zone_id=event.location or "",
        asset=NodeRef(table=FAILURE_TABLES[failure.asset_kind], id=failure.asset_id),
        event_id=event.event_id,
        sim_time=event.sim_time,
    )


class RiskSignal(BaseModel):
    """The latest reading of one source whose fixed sensor band is moderate or worse."""

    id: str
    event_type: str
    source: str
    zone_id: str | None
    subject_id: str
    severity: Severity
    summary: str


class StateFact(BaseModel):
    id: str
    entity: NodeRef
    values: dict[str, Any]


class Claim(BaseModel):
    text: str
    citation_ids: list[str]


class ContributingFactor(BaseModel):
    factor: str
    value: str
    citation_ids: list[str]


class ThreatAssessment(BaseModel):
    """The ``assess`` node's output, shaped like the dashboard's pending ``ThreatAssessment`` contract."""

    node: Literal["assess"] = "assess"
    hazard: Hazard
    summary: str
    contributing_factors: list[ContributingFactor]
    confidence: float = Field(ge=0, le=1)
    claims: list[Claim] = Field(default_factory=list[Claim])


class ReasoningContext(BaseModel):
    """Everything the Reasoning node hands the reasoner, all read from the city, the graph and the corpus."""

    trigger: ThreatTrigger
    signals: list[RiskSignal]
    graph: KgSubgraph
    evidence: list[RetrievedChunk]
    state: list[StateFact]

    def citation_ids(self) -> set[str]:
        return (
            {self.trigger.citation_id}
            | {s.id for s in self.signals}
            | {e.citation_id for e in self.graph.edges}
            | {c.chunk_id for c in self.evidence}
            | {f.id for f in self.state}
        )


class ReasoningResult(BaseModel):
    """What the ``reason`` step asks the model for (the heuristic reasoner fills the same shape offline)."""

    summary: str
    band: WorkflowBand
    confidence: float = Field(ge=0, le=1)
    claims: list[Claim] = Field(min_length=1, max_length=5)

    @field_validator("confidence", mode="before")
    @classmethod
    def _percent_to_fraction(cls, value: Any) -> Any:
        """Local models often answer 85 for 0.85; a grammar enforces the type but not the bounds."""
        return value / 100 if isinstance(value, int | float) and 1 < value <= 100 else value


class PlanPick(BaseModel):
    candidate_id: str
    rationale: str
    citation_ids: list[str]


class PlanChoice(BaseModel):
    """What the ``recommend`` step asks the model for: which candidates to take, why, and on what evidence."""

    actions: list[PlanPick] = Field(min_length=1, max_length=6)


class Candidate(BaseModel):
    """A valid tool call the plan may include; the chosen rationale fills ``text_field``."""

    candidate_id: str
    tool: str
    input: dict[str, Any]
    text_field: Literal["reason", "message"]
    label: str
    why: str
    citation_ids: list[str]


class WorkflowUpdate(TypedDict, total=False):
    """What nodes return: LangGraph merges each node's partial update into the state."""

    trigger: ThreatTrigger
    signals: list[RiskSignal]
    graph: KgSubgraph
    retrieved: list[RetrievedChunk]
    context: ReasoningContext
    reasoning: ReasoningResult
    assessment: WorkflowAssessmentOutput
    plan: list[WorkflowAction]
    decision: WorkflowDecision
    results: list[ActionResult]
    verification: WorkflowVerificationOutput
    step_output: WorkflowOutput  # the display output of the node that just ran (the runner publishes it)


class WorkflowState(WorkflowUpdate, total=False):
    """Graph state: the runner supplies the four inputs, the nodes add the rest."""

    run_id: Required[str]
    trigger_event: Required[Event]
    world: Required[WorldSnapshot]
    recent_events: Required[list[Event]]


class Node(Protocol):
    """A LangGraph node (a named ``state`` parameter, as LangGraph's node protocol expects)."""

    def __call__(self, state: WorkflowState) -> Awaitable[WorkflowUpdate]: ...
