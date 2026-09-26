"""``/api/simulation/*`` (spec §8.2): operator control of the runner. Every body and response is a model."""

from typing import Annotated

from fastapi import APIRouter, Body

from gridline.api.deps import DemoRunnerDep, RunnerDep
from gridline.api.event_models import Event, typed_event
from gridline.api.simulation_models import (
    AdvanceRequest,
    AdvanceResponse,
    InjectRequest,
    ScenarioInfo,
    SelectScenarioRequest,
    SimulationSpeed,
    SimulationStart,
    TriggerRequest,
    scenario_infos,
)
from gridline.simulation.runner import SimulationStatus
from gridline.simulation.world import WorldSnapshot

router = APIRouter(prefix="/simulation", tags=["simulation"])


@router.get("/status")
async def get_status(runner: RunnerDep) -> SimulationStatus:
    return runner.status()


@router.get("/scenarios")
async def list_scenarios() -> list[ScenarioInfo]:
    return scenario_infos()


@router.get("/snapshot")
async def get_snapshot(runner: RunnerDep) -> WorldSnapshot:
    return runner.engine.snapshot()


@router.post("/scenario")
async def select_scenario(body: SelectScenarioRequest, runner: RunnerDep) -> SimulationStatus:
    return await runner.select_scenario(body.scenario, body.seed)


@router.post("/start")
async def start(
    runner: DemoRunnerDep, body: Annotated[SimulationStart | None, Body()] = None
) -> SimulationStatus:
    request = body or SimulationStart()
    return await runner.start(request.scenario, request.seed, request.speed)


@router.post("/pause")
async def pause(runner: RunnerDep) -> SimulationStatus:
    return await runner.pause()


@router.post("/resume")
async def resume(runner: DemoRunnerDep) -> SimulationStatus:
    return await runner.resume()


@router.post("/reset")
async def reset(runner: RunnerDep) -> SimulationStatus:
    return await runner.reset()


@router.post("/advance")
async def advance(
    runner: DemoRunnerDep, body: Annotated[AdvanceRequest | None, Body()] = None
) -> AdvanceResponse:
    events = await runner.advance((body or AdvanceRequest()).ticks)
    return AdvanceResponse(events_emitted=len(events), status=runner.status())


@router.post("/speed")
async def set_speed(body: SimulationSpeed, runner: RunnerDep) -> SimulationStatus:
    return await runner.set_speed(body.speed)


@router.post("/inject")
async def inject(body: InjectRequest, runner: DemoRunnerDep) -> list[Event]:
    """Apply an operator event now; returns it plus any derived events (all published on the bus)."""
    events = await runner.inject(
        body.event_type, body.payload, location=body.location, source=body.source, severity=body.severity
    )
    return [typed_event(e) for e in events]


@router.post("/trigger")
async def trigger(body: TriggerRequest, runner: DemoRunnerDep) -> list[Event]:
    """Press a DEMO control: announcement, injected events and one simulated hour, all on the bus."""
    return [typed_event(e) for e in await runner.trigger(body.trigger)]
