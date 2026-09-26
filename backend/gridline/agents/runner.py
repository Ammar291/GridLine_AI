"""Runs the incident graph on each ``infrastructure.failure`` and publishes its execution as ``agent.step``.

The step events are LangGraph's own task stream (``stream_mode="tasks"``): a task start becomes ``running``,
its result ``done`` (with the node's ``step_output``), an interrupt ``waiting`` and an error ``failed``.
One run at a time (MVP); approvals live in an in-memory checkpointer, so a restart loses a waiting run.
"""

import asyncio
import contextlib
import enum
import logging
import typing
import uuid
from collections import deque
from datetime import UTC, datetime
from typing import Any

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.types import Command
from pydantic import BaseModel, TypeAdapter

from gridline.agents.graph import AgentDeps, build_workflow_graph
from gridline.agents.nodes.act import ProjectHalted
from gridline.agents.state import WorkflowState, trigger_from_failure
from gridline.agents.steps import (
    NODES,
    WorkflowDecision,
    WorkflowNode,
    WorkflowOutput,
    WorkflowRun,
    WorkflowStep,
    run_status,
)
from gridline.errors import InvalidTransition
from gridline.events.bus import EventBus, Subscription
from gridline.events.envelope import Event, new_event
from gridline.events.types import EventType, Severity
from gridline.simulation.runner import SimulationRunner

log = logging.getLogger(__name__)

RECENT_EVENTS = 500
WATCHED = ("weather.", "environment.", "infrastructure.")
OUTPUT = TypeAdapter[WorkflowOutput](WorkflowOutput)


def _classes(annotation: Any) -> list[type]:
    if isinstance(annotation, type) and issubclass(annotation, BaseModel | enum.Enum):
        return [annotation]
    return [c for arg in typing.get_args(annotation) for c in _classes(arg)]


def checkpoint_types() -> list[type]:
    """Every model and enum the graph state can hold, allow-listed for the checkpointer's deserializer."""
    seen: set[type] = set()
    stack = [c for hint in typing.get_type_hints(WorkflowState).values() for c in _classes(hint)]
    while stack:
        cls = stack.pop()
        if cls in seen:
            continue
        seen.add(cls)
        if issubclass(cls, BaseModel):
            stack += [c for f in cls.model_fields.values() for c in _classes(f.annotation)]
    return sorted(seen, key=lambda c: f"{c.__module__}.{c.__qualname__}")


class UnknownRun(KeyError):
    """No run with this id (HTTP 404)."""


class AgentRunner:
    def __init__(self, bus: EventBus, sim: SimulationRunner, deps: AgentDeps) -> None:
        self.bus = bus
        self.sim = sim
        self.deps = deps
        serde = JsonPlusSerializer(allowed_msgpack_modules=checkpoint_types())
        self._graph = build_workflow_graph(deps, InMemorySaver(serde=serde))
        self._recent: deque[Event] = deque(maxlen=RECENT_EVENTS)
        self._run: WorkflowRun | None = None
        self._started: dict[str, datetime] = {}
        self._seq = 0
        self._subscription: Subscription | None = None
        self._listener: asyncio.Task[None] | None = None
        self._task: asyncio.Task[None] | None = None

    @property
    def current(self) -> WorkflowRun | None:
        return self._run

    @property
    def active(self) -> bool:
        return self._run is not None and run_status(self._run.steps) in ("running", "waiting")

    async def start(self) -> None:
        self._subscription = self.bus.subscribe(list(WATCHED))
        self._listener = asyncio.create_task(self._listen())

    async def shutdown(self) -> None:
        for task in (self._listener, self._task):
            if task is not None:
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task
        if self._subscription is not None:
            self.bus.unsubscribe(self._subscription)

    async def _listen(self) -> None:
        assert self._subscription is not None
        while True:
            event = await self._subscription.queue.get()
            self._recent.append(event)
            if event.event_type == EventType.INFRASTRUCTURE_FAILURE:
                self.trigger(event)

    def trigger(self, event: Event) -> WorkflowRun | None:
        """Start a run for this failure; ``None`` while another run is active (one run at a time)."""
        if self.active:
            log.warning(
                "agent run %s is active; failure %s does not start a second run", self._run, event.event_id
            )
            return None
        trigger = trigger_from_failure(event)
        run_id = f"run-{uuid.uuid4().hex[:8]}"
        provider = self.deps.provider
        self._run = WorkflowRun(
            run_id=run_id,
            trigger_event_id=event.event_id,
            hazard=trigger.hazard,
            zone_id=trigger.zone_id,
            asset_id=trigger.asset.id,
            provider=provider.name if provider else "mock",
            model=provider.model if provider else None,
            started_at=datetime.now(UTC),
            steps=[],
        )
        state = {
            "run_id": run_id,
            "trigger_event": event,
            "world": self.sim.engine.snapshot(),
            "recent_events": list(self._recent),
        }
        self._task = asyncio.create_task(self._drive(state, run_id))
        return self._run

    async def decide(self, run_id: str, decision: WorkflowDecision) -> WorkflowRun:
        run = self._run
        if run is None or run.run_id != run_id:
            raise UnknownRun(run_id)
        if run_status(run.steps) != "waiting":
            raise InvalidTransition(f"run {run_id} is not waiting for approval")
        self._task = asyncio.create_task(
            self._drive(Command(resume=decision.model_dump(mode="json")), run_id)
        )
        return run

    async def wait(self) -> None:
        """Until the current graph task pauses or ends (tests and the smoke script)."""
        if self._task is not None:
            await self._task

    async def _drive(self, graph_input: Any, run_id: str) -> None:
        config = {"configurable": {"thread_id": run_id}}
        running: WorkflowNode | None = None
        try:
            async for chunk in self._graph.astream(graph_input, config, stream_mode="tasks"):
                node = chunk.get("name")
                if node not in NODES:
                    continue
                if "input" in chunk:
                    running = node
                    self._started[node] = datetime.now(UTC)
                    self._publish(run_id, node, "running")
                elif chunk.get("error") is not None:
                    self._publish(
                        run_id, node, "failed", error=f"{type(chunk['error']).__name__}: {chunk['error']}"
                    )
                    running = None
                elif chunk.get("interrupts"):
                    self._publish(run_id, node, "waiting", output=chunk["interrupts"][0]["value"])
                    running = None
                else:
                    result: dict[str, Any] = chunk.get("result") or {}
                    self._publish(run_id, node, "done", output=result.get("step_output"))
                    running = None
        except Exception as exc:  # never swallowed: the step that was running shows it
            log.exception("agent run %s failed", run_id)
            if running is not None:
                self._publish(run_id, running, "failed", error=f"{type(exc).__name__}: {exc}")

    def _publish(
        self, run_id: str, node: WorkflowNode, status: str, *, output: Any = None, error: str | None = None
    ) -> None:
        run = self._run
        if run is None or run.run_id != run_id:
            return
        now = datetime.now(UTC)
        started = self._started.get(node, now)
        finished = status in ("done", "failed")
        step = WorkflowStep.model_validate(
            {
                "run_id": run_id,
                "node": node,
                "index": NODES.index(node) + 1,
                "status": status,
                "started_at": started,
                "finished_at": now if finished else None,
                "duration_ms": int((now - started).total_seconds() * 1000) if finished else None,
                "output": None if output is None else OUTPUT.validate_python(output),
                "error": error,
            }
        )
        steps = [s for s in run.steps if s.node != node] + [step]
        self._run = run.model_copy(update={"steps": sorted(steps, key=lambda s: s.index)})
        self._seq += 1
        sim_time = self.sim.engine.status.sim_time
        self.bus.publish(
            new_event(
                EventType.AGENT_STEP,
                step,
                event_id=f"{run_id}-{self._seq:03d}",
                timestamp=now,
                sim_time=sim_time,
                source="agent",
                location=run.zone_id or None,
                severity=Severity.INFO,
            )
        )


def halt_in_simulation(sim: SimulationRunner) -> ProjectHalted:
    """Carry a halt the database now shows into the simulation, so the map and world match the database."""

    async def halt(project_id: str) -> None:
        live = sim.engine.snapshot().projects.get(project_id)
        if live is None or live.status == "halted":
            return
        await sim.inject(
            EventType.INFRASTRUCTURE_CONSTRUCTION,
            {
                "project_id": project_id,
                "status": "halted",
                "activity": "halted",
                "excavation_depth_m": live.excavation_depth_m,
            },
            source="agent:execute",
        )

    return halt
