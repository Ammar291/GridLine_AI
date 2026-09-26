"""The tool contract (ARCHITECTURE.md §10): typed inputs, results, verification and the two tool kinds.

An ``ActionTool`` never commits: ``check`` loads rows and validates the current city state (raising
``ToolRejected``), ``apply`` mutates through the session, and ``verify`` re-reads the database against the
tool's post-condition. ``gridline.tools.executor.execute_action`` owns validation, idempotency, approval,
snapshots, the audit row and the commit. A ``ReadTool`` returns a typed view and writes nothing.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

Actor = Literal["agent", "operator", "system"]
ActionStatus = Literal["executed", "unchanged", "rejected", "failed"]
EntityKind = Literal[
    "zone",
    "road",
    "project",
    "crew",
    "ambulance",
    "shelter",
    "hospital",
    "hospital_bed",
    "bed_reservation",
    "incident",
    "alert",
    "evacuation_order",
    "construction_restriction",
    "task",
]


@dataclass
class ToolContext:
    """Built per call by the caller. The executor owns commit/rollback on ``session``."""

    session: AsyncSession
    actor: Actor = "agent"
    approval_id: str | None = None
    run_id: str | None = None
    sim_time: datetime | None = None


class EntityRef(BaseModel):
    model_config = ConfigDict(frozen=True)

    kind: EntityKind
    id: str

    @property
    def key(self) -> str:
        """The ``"kind:id"`` key used in before/after snapshots."""
        return f"{self.kind}:{self.id}"


class ActionResult(BaseModel):
    """What every action returns, rebuilt from its ``actions`` audit row."""

    action_id: str
    action_type: str
    status: ActionStatus
    before: dict[str, dict[str, Any]]
    after: dict[str, dict[str, Any]]
    timestamp: datetime
    sim_time: datetime | None
    affected_entities: list[EntityRef]
    message: str
    actor: Actor
    approval_id: str | None
    idempotency_key: str | None
    incident_id: str | None
    replayed: bool = False


class VerificationCheck(BaseModel):
    name: str
    passed: bool
    expected: Any
    observed: Any


class VerificationResult(BaseModel):
    status: Literal["verified", "failed"]
    checks: list[VerificationCheck]


class ToolRejected(Exception):
    """The input is well-formed but the city state does not allow the action (or an id does not exist)."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class Plan[P]:
    """What ``check`` found: entities to snapshot, typed data for ``apply``, and the incident if known."""

    refs: list[EntityRef]
    data: P
    incident_id: str | None = None


@dataclass(frozen=True)
class Applied:
    """``changed=False`` means the city was already in the requested state (result status ``unchanged``)."""

    changed: bool
    message: str
    created: list[EntityRef] = field(default_factory=list[EntityRef])
    incident_id: str | None = None


class ActionInput(BaseModel):
    """Base of every action input: unknown keys are rejected and every call may carry an idempotency key."""

    model_config = ConfigDict(extra="forbid")

    idempotency_key: str | None = Field(
        default=None,
        min_length=1,
        max_length=128,
        description="Caller-chosen key; repeating it returns the first result instead of acting twice.",
    )


class ReadInput(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ActionTool[I: ActionInput, P](ABC):
    name: ClassVar[str]
    description: ClassVar[str]
    approval_required: ClassVar[bool]
    Input: type[I]

    def requires_approval(self, inp: I) -> bool:
        """Override when approval depends on the input (reported as ``conditional`` by the registry)."""
        return self.approval_required

    @abstractmethod
    async def check(self, inp: I, ctx: ToolContext) -> Plan[P]: ...

    @abstractmethod
    async def apply(self, inp: I, ctx: ToolContext, plan: Plan[P]) -> Applied: ...

    @abstractmethod
    async def verify(self, inp: I, ctx: ToolContext, result: ActionResult) -> VerificationResult:
        """Re-read the database (never model output) and compare it with the declared post-condition."""


class ReadTool[I: ReadInput, O: BaseModel](ABC):
    name: ClassVar[str]
    description: ClassVar[str]
    Input: type[I]
    Output: type[O]

    @abstractmethod
    async def run(self, inp: I, ctx: ToolContext) -> O: ...
