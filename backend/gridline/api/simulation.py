"""``/api/simulation/*`` (spec §8.2): operator control of the runner. Every body and response is a model."""

from typing import Annotated, Any

from fastapi import APIRouter, Body
from pydantic import BaseModel, Field

from gridline.api.deps import RunnerDep
from gridline.events.envelope import Event
from gridline.events.types import EventType, Severity
from gridline.simulation.runner import MAX_SPEED, MIN_SPEED, SimulationStatus, StageInfo
from gridline.simulation.scenarios import SCENARIOS, ScenarioName
from gridline.simulation.world import WorldSnapshot

router = APIRouter(prefix="/simulation", tags=["simulation"])


class ScenarioInfo(BaseModel):
    name: ScenarioName
    title: str
    description: str
    duration_ticks: int
    stages: list[StageInfo]


class SelectScenarioRequest(BaseModel):
    scenario: ScenarioName
    seed: int | None = None


class SimulationStart(BaseModel):
    scenario: ScenarioName | None = None
    seed: int | None = None
    speed: float | None = Field(default=None, ge=MIN_SPEED, le=MAX_SPEED)


class AdvanceRequest(BaseModel):
    ticks: int = Field(default=1, ge=1, le=1000)


class AdvanceResponse(BaseModel):
    events_emitted: int
    status: SimulationStatus


class SimulationSpeed(BaseModel):
    speed: float = Field(ge=MIN_SPEED, le=MAX_SPEED)


class InjectRequest(BaseModel):
    event_type: EventType
    location: str | None = None
    payload: dict[str, Any]
    source: str = "operator:api"
    severity: Severity | None = None


@router.get("/status")
async def get_status(runner: RunnerDep) -> SimulationStatus:
    return runner.status()


@router.get("/scenarios")
async def list_scenarios() -> list[ScenarioInfo]:
    return [
        ScenarioInfo(
            name=s.name,
            title=s.title,
            description=s.description,
            duration_ticks=s.duration_ticks,
            stages=[
                StageInfo(index=i, name=st.name, description=st.description, start_tick=st.start_tick)
                for i, st in enumerate(s.stages)
            ],
        )
        for s in SCENARIOS.values()
    ]


@router.get("/snapshot")
async def get_snapshot(runner: RunnerDep) -> WorldSnapshot:
    return runner.engine.snapshot()


@router.post("/scenario")
async def select_scenario(body: SelectScenarioRequest, runner: RunnerDep) -> SimulationStatus:
    return await runner.select_scenario(body.scenario, body.seed)


@router.post("/start")
async def start(
    runner: RunnerDep, body: Annotated[SimulationStart | None, Body()] = None
) -> SimulationStatus:
    request = body or SimulationStart()
    return await runner.start(request.scenario, request.seed, request.speed)


@router.post("/pause")
async def pause(runner: RunnerDep) -> SimulationStatus:
    return await runner.pause()


@router.post("/resume")
async def resume(runner: RunnerDep) -> SimulationStatus:
    return await runner.resume()


@router.post("/reset")
async def reset(runner: RunnerDep) -> SimulationStatus:
    return await runner.reset()


@router.post("/advance")
async def advance(
    runner: RunnerDep, body: Annotated[AdvanceRequest | None, Body()] = None
) -> AdvanceResponse:
    events = await runner.advance((body or AdvanceRequest()).ticks)
    return AdvanceResponse(events_emitted=len(events), status=runner.status())


@router.post("/speed")
async def set_speed(body: SimulationSpeed, runner: RunnerDep) -> SimulationStatus:
    return await runner.set_speed(body.speed)


@router.post("/inject")
async def inject(body: InjectRequest, runner: RunnerDep) -> list[Event]:
    """Apply an operator event now; returns it plus any derived events (all published on the bus)."""
    return await runner.inject(
        body.event_type, body.payload, location=body.location, source=body.source, severity=body.severity
    )
