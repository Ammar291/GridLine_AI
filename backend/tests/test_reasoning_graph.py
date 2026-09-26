"""The live agent workflow end to end on a simulated landslide.

Everything is real: the scenario's own events and world, the seeded knowledge graph, RAG over the Nandipur
corpus (offline hashed embedder), the tool executor and Postgres. Only the LLM is scripted; it answers
from the ids the JSON schema allows, which are exactly the ids in the run's input.
"""

import asyncio
from collections.abc import AsyncIterator
from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from gridline.agents.graph import AgentDeps
from gridline.agents.runner import AgentRunner, halt_in_simulation
from gridline.agents.state import PlanChoice, PlanPick, ReasoningResult
from gridline.agents.steps import (
    WorkflowCompletionOutput,
    WorkflowDecision,
    WorkflowGraphOutput,
    WorkflowPlanOutput,
    WorkflowReasoningOutput,
    WorkflowStep,
    run_status,
)
from gridline.city.model import City
from gridline.db.engine import session_factory
from gridline.db.schema import truncate_corpus
from gridline.db.seed import SeedSummary
from gridline.events.bus import EventBus
from gridline.events.types import EventType
from gridline.kg.query import KnowledgeGraph
from gridline.llm.base import LLMError
from gridline.rag.embedder import HashedEmbedder
from gridline.rag.ingest import ingest
from gridline.rag.retriever import Retriever
from gridline.rag.store import ChunkStore
from gridline.simulation.engine import SimulationEngine
from gridline.simulation.runner import SimulationRunner
from gridline.tools.registry import build_registry
from tests.conftest import DATA_DIR, Baseline, restore


def _enum(schema: dict[str, Any], field: str) -> list[str]:
    """The values a narrowed schema allows for ``field`` (anywhere in the schema)."""
    found: list[str] = []

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            props = node.get("properties", {})
            if field in props:
                prop = props[field]
                found.extend(prop.get("items", prop).get("enum", []))
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(schema)
    return found


class ScriptedLLM:
    """Answers from the schema's own enums, the way a grammar-constrained model can."""

    name = "ollama"
    model = "scripted"

    def __init__(self) -> None:
        self.schemas: list[dict[str, Any]] = []

    async def complete_structured(
        self, *, system: str, user: str, schema: dict[str, Any], output: type[Any]
    ) -> Any:
        self.schemas.append(schema)
        cites = _enum(schema, "citation_ids")
        if output is ReasoningResult:
            return ReasoningResult.model_validate(
                {
                    "summary": "The slope above D-7 failed; debris threatens Riverside downstream.",
                    "band": "critical",
                    "confidence": 0.9,
                    "claims": [{"text": "Evidence supports a slope failure.", "citation_ids": cites[:2]}],
                }
            )
        picks = [
            PlanPick(candidate_id=c, rationale=f"Because of {c}.", citation_ids=cites[:1])
            for c in _enum(schema, "candidate_id")
        ]
        return PlanChoice(actions=picks[:6])


class DownLLM:
    name = "ollama"
    model = "down"

    async def complete_structured(self, **_: Any) -> Any:
        raise LLMError("connection refused")


@pytest.fixture(scope="module")
async def indexed(seeded: SeedSummary, db_engine: AsyncEngine, db_url: str) -> AsyncIterator[None]:
    await truncate_corpus(db_engine)
    await ingest(database_url=db_url, corpus_dir=DATA_DIR / "corpus", embedder=HashedEmbedder())
    yield
    await truncate_corpus(db_engine)


@pytest.fixture
async def sessions(
    indexed: None, db_engine: AsyncEngine, baseline: Baseline
) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    await restore(db_engine, baseline)
    yield session_factory(db_engine)
    await restore(db_engine, baseline)


async def start_run(
    city: City, sessions: async_sessionmaker[AsyncSession], provider: Any
) -> tuple[AgentRunner, SimulationRunner, list[WorkflowStep]]:
    """Play the cascade to its landslide with the agent listening; returns once the run pauses."""
    bus = EventBus(maxsize=5000)
    sim = SimulationRunner(SimulationEngine(city), bus, tick_seconds=0.01)
    await sim.select_scenario("cascading_landslide_flood", 42)
    steps = bus.subscribe(["agent."], maxsize=5000)
    deps = AgentDeps(
        city=city,
        kg=KnowledgeGraph(sessions),
        retriever=Retriever(ChunkStore(sessions), HashedEmbedder()),
        sessions=sessions,
        registry=build_registry(),
        provider=provider,
        on_project_halted=halt_in_simulation(sim),
    )
    agent = AgentRunner(bus, sim, deps)
    await agent.start()
    for _ in range(300):
        batch = sim.engine.advance()
        for event in batch:
            bus.publish(event)
        await asyncio.sleep(0)
        if any(e.event_type == EventType.INFRASTRUCTURE_FAILURE for e in batch):
            break
    for _ in range(100):
        if agent.current is not None:
            break
        await asyncio.sleep(0.01)
    await agent.wait()
    collected: list[WorkflowStep] = []
    received = steps

    def drain() -> None:
        while not received.queue.empty():
            collected.append(WorkflowStep.model_validate(received.queue.get_nowait().payload))

    agent.drain = drain  # type: ignore[attr-defined]
    drain()
    return agent, sim, collected


async def count(sessions: async_sessionmaker[AsyncSession], sql: str) -> Any:
    async with sessions() as s:
        return (await s.execute(text(sql))).scalar_one()


async def test_run_pauses_for_approval_then_executes_verifies_and_halts_the_project(
    city: City, sessions: async_sessionmaker[AsyncSession]
) -> None:
    llm = ScriptedLLM()
    agent, sim, steps = await start_run(city, sessions, llm)
    try:
        # 1-8 in order, each running then done, the gate waiting; nothing touched the city yet.
        seen = [(s.node, s.status) for s in steps]
        expected = [
            (n, st)
            for n in ("receive", "observe", "query_graph", "retrieve", "reason", "assess", "recommend")
            for st in ("running", "done")
        ]
        assert seen == [*expected, ("approval_gate", "running"), ("approval_gate", "waiting")]
        run = agent.current
        assert run is not None and run_status(run.steps) == "waiting"
        assert await count(sessions, "select count(*) from actions") == 0

        by_node = {s.node: s for s in run.steps}
        graph_out = by_node["query_graph"].output
        assert isinstance(graph_out, WorkflowGraphOutput)
        chain = [[n.id for n in p.nodes] for p in graph_out.paths]
        assert ["PR-HT2", "SL-HV-1", "D-7", "Z-RS"] in chain
        reason_out = by_node["reason"].output
        assert isinstance(reason_out, WorkflowReasoningOutput) and reason_out.provider == "ollama"
        plan = by_node["recommend"].output
        assert isinstance(plan, WorkflowPlanOutput)
        assert {"halt:PR-HT2", "inspect:slope:SL-HV-1", "monitor:slope:SL-HV-1", "alert:Z-RS"} <= {
            a.candidate_id for a in plan.actions
        }
        # the model could only cite ids that were in its input
        assert _enum(llm.schemas[0], "citation_ids") and "state:slopes.SL-HV-1" in _enum(
            llm.schemas[0], "citation_ids"
        )

        await agent.decide(run.run_id, WorkflowDecision(decision="approve"))
        await agent.wait()
        agent.drain()  # type: ignore[attr-defined]
        run = agent.current
        assert run is not None and run_status(run.steps) == "completed", [
            (s.node, s.status, s.error) for s in run.steps
        ]
        done = {s.node: s for s in run.steps}
        assert all(done[n].status == "done" for n in ("approval_gate", "execute", "verify", "complete"))
        final = done["complete"].output
        assert isinstance(final, WorkflowCompletionOutput) and final.outcome == "completed"
        assert any(e.id == "PR-HT2" and e.fields.get("status") == "halted" for e in final.entities)

        # the database (fresh session) and the simulation's world both show the halt
        assert await count(sessions, "select status from projects where id = 'PR-HT2'") == "halted"
        assert sim.engine.snapshot().projects["PR-HT2"].status == "halted"
        assert await count(sessions, "select count(*) from actions where approval_id is not null") == len(
            plan.actions
        )
    finally:
        await agent.shutdown()


async def test_rejecting_the_plan_executes_nothing(
    city: City, sessions: async_sessionmaker[AsyncSession]
) -> None:
    agent, _, _ = await start_run(city, sessions, ScriptedLLM())
    try:
        run = agent.current
        assert run is not None
        await agent.decide(run.run_id, WorkflowDecision(decision="reject", note="not now"))
        await agent.wait()
        run = agent.current
        assert run is not None and run_status(run.steps) == "rejected"
        assert {s.node for s in run.steps}.isdisjoint({"execute", "verify"})
        assert await count(sessions, "select count(*) from actions") == 0
    finally:
        await agent.shutdown()


async def test_llm_failure_falls_back_to_the_heuristic_reasoner_and_says_so(
    city: City, sessions: async_sessionmaker[AsyncSession]
) -> None:
    agent, _, _ = await start_run(city, sessions, DownLLM())
    try:
        run = agent.current
        assert run is not None and run_status(run.steps) == "waiting"
        for node in ("reason", "recommend"):
            out = next(s for s in run.steps if s.node == node).output
            assert isinstance(out, WorkflowReasoningOutput | WorkflowPlanOutput)
            assert (
                out.provider == "mock" and out.fallback_reason and "connection refused" in out.fallback_reason
            )
    finally:
        await agent.shutdown()


async def test_a_second_decision_is_refused(city: City, sessions: async_sessionmaker[AsyncSession]) -> None:
    from gridline.agents.runner import UnknownRun
    from gridline.errors import InvalidTransition

    agent, _, _ = await start_run(city, sessions, None)
    try:
        run = agent.current
        assert run is not None
        with pytest.raises(UnknownRun):
            await agent.decide("run-nope", WorkflowDecision(decision="approve"))
        await agent.decide(run.run_id, WorkflowDecision(decision="reject"))
        await agent.wait()
        with pytest.raises(InvalidTransition):
            await agent.decide(run.run_id, WorkflowDecision(decision="approve"))
    finally:
        await agent.shutdown()
