"""The live agent workflow contract: one ``agent.step`` payload per graph node, and the run it belongs to.

Eleven nodes, one per dashboard step. Each node's display output is a typed model discriminated by ``node``.
Schema names carry a ``Workflow`` prefix because the frontend's pending contract already defines
``ThreatAssessment``, ``Claim``, ``VerificationResult`` and friends. This module is a leaf (pydantic only) so
``gridline.events.payloads`` can import it.
"""

from typing import Annotated, Any, Literal

from pydantic import AwareDatetime, Field

from gridline.events.payload_base import Payload

WorkflowNode = Literal[
    "receive",
    "observe",
    "query_graph",
    "retrieve",
    "reason",
    "assess",
    "recommend",
    "approval_gate",
    "execute",
    "verify",
    "complete",
]
NODES: tuple[WorkflowNode, ...] = (
    "receive",
    "observe",
    "query_graph",
    "retrieve",
    "reason",
    "assess",
    "recommend",
    "approval_gate",
    "execute",
    "verify",
    "complete",
)
StepStatus = Literal["running", "done", "waiting", "failed"]
WorkflowHazard = Literal["landslide", "flood"]
WorkflowBand = Literal["normal", "watch", "warning", "critical"]
RunStatus = Literal["running", "waiting", "completed", "rejected", "failed"]


class StepModel(Payload):
    """Every workflow model is an event payload model: unknown keys rejected, all fields in the schema."""


class WorkflowEntity(StepModel):
    table: str
    id: str
    name: str


class WorkflowReceiveOutput(StepModel):
    node: Literal["receive"] = "receive"
    event_id: str
    hazard: WorkflowHazard
    failure_kind: str
    asset: WorkflowEntity
    zone_id: str
    zone_name: str
    description: str
    sim_time: AwareDatetime
    citation_id: str


class WorkflowSignal(StepModel):
    id: str
    event_type: str
    source: str
    zone_id: str | None
    severity: str
    summary: str


class WorkflowObserveOutput(StepModel):
    node: Literal["observe"] = "observe"
    headline: str
    signals: list[WorkflowSignal]


class WorkflowPath(StepModel):
    """``nodes[i] --relations[i]--> nodes[i+1]``, each hop backed by the KG edge in ``citation_ids[i]``."""

    nodes: list[WorkflowEntity]
    relations: list[str]
    citation_ids: list[str]


class WorkflowGraphOutput(StepModel):
    node: Literal["query_graph"] = "query_graph"
    start: WorkflowEntity
    entity_count: int
    edge_count: int
    paths: list[WorkflowPath]


class WorkflowChunk(StepModel):
    chunk_id: str
    document_id: str
    document_title: str
    section: str
    kind: str
    similarity: float


class WorkflowEvidenceOutput(StepModel):
    node: Literal["retrieve"] = "retrieve"
    queries: list[str]
    chunks: list[WorkflowChunk]


class WorkflowClaim(StepModel):
    text: str
    citation_ids: list[str]


class WorkflowReasoningOutput(StepModel):
    node: Literal["reason"] = "reason"
    provider: Literal["ollama", "mock"]
    model: str | None
    fallback_reason: str | None
    duration_ms: int
    summary: str
    claims: list[WorkflowClaim]


class WorkflowAssessmentOutput(StepModel):
    node: Literal["assess"] = "assess"
    hazard: WorkflowHazard
    band: WorkflowBand
    confidence: float
    grounded: bool
    cited_count: int
    ungrounded_ids: list[str]
    affected_zone_ids: list[str]


class WorkflowAction(StepModel):
    action_id: str
    candidate_id: str
    tool: str
    input: dict[str, Any]
    label: str
    rationale: str
    citation_ids: list[str]
    requires_approval: bool


class WorkflowPlanOutput(StepModel):
    node: Literal["recommend"] = "recommend"
    provider: Literal["ollama", "mock"]
    model: str | None
    fallback_reason: str | None
    duration_ms: int
    candidate_count: int
    actions: list[WorkflowAction]


class WorkflowApprovalOutput(StepModel):
    node: Literal["approval_gate"] = "approval_gate"
    approval_id: str
    action_ids: list[str]
    decision: Literal["approve", "reject"] | None = None
    note: str | None = None
    decided_at: AwareDatetime | None = None


class WorkflowActionResult(StepModel):
    action_id: str
    tool: str
    status: Literal["executed", "unchanged", "rejected", "failed"]
    message: str
    affected_entities: list[str]


class WorkflowExecutionOutput(StepModel):
    node: Literal["execute"] = "execute"
    results: list[WorkflowActionResult]


class WorkflowCheck(StepModel):
    name: str
    passed: bool
    expected: str
    observed: str


class WorkflowActionVerification(StepModel):
    action_id: str
    tool: str
    status: Literal["verified", "failed"]
    checks: list[WorkflowCheck]


class WorkflowVerificationOutput(StepModel):
    node: Literal["verify"] = "verify"
    status: Literal["verified", "partially_verified", "failed"]
    per_action: list[WorkflowActionVerification]


class WorkflowEntityState(StepModel):
    kind: str
    id: str
    name: str
    fields: dict[str, Any]


class WorkflowCompletionOutput(StepModel):
    node: Literal["complete"] = "complete"
    outcome: Literal["completed", "completed_with_failures", "rejected"]
    entities: list[WorkflowEntityState]


WorkflowOutput = Annotated[
    WorkflowReceiveOutput
    | WorkflowObserveOutput
    | WorkflowGraphOutput
    | WorkflowEvidenceOutput
    | WorkflowReasoningOutput
    | WorkflowAssessmentOutput
    | WorkflowPlanOutput
    | WorkflowApprovalOutput
    | WorkflowExecutionOutput
    | WorkflowVerificationOutput
    | WorkflowCompletionOutput,
    Field(discriminator="node"),
]


class WorkflowStep(StepModel):
    """The ``agent.step`` payload: the latest state of one node of one run."""

    run_id: str
    node: WorkflowNode
    index: int = Field(ge=1, le=len(NODES))
    status: StepStatus
    started_at: AwareDatetime
    finished_at: AwareDatetime | None = None
    duration_ms: int | None = None
    output: WorkflowOutput | None = None
    error: str | None = None


class WorkflowRun(StepModel):
    run_id: str
    trigger_event_id: str
    hazard: WorkflowHazard
    zone_id: str
    asset_id: str
    provider: str
    model: str | None
    started_at: AwareDatetime
    steps: list[WorkflowStep]


class WorkflowDecision(StepModel):
    decision: Literal["approve", "reject"]
    note: str | None = Field(default=None, max_length=500)


def run_status(steps: list[WorkflowStep]) -> RunStatus:
    """Derived from the steps, never stored: the same rule the dashboard applies."""
    by_node = {s.node: s for s in steps}
    if any(s.status == "failed" for s in steps):
        return "failed"
    gate = by_node.get("approval_gate")
    if gate is not None and gate.status == "waiting":
        return "waiting"
    done = by_node.get("complete")
    if done is not None and done.status == "done" and isinstance(done.output, WorkflowCompletionOutput):
        return "rejected" if done.output.outcome == "rejected" else "completed"
    return "running"
