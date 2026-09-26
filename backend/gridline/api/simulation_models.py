"""Request and response bodies of ``/api/simulation/*`` (spec §8.2), shared with ``GET /api/city``."""

from typing import Any

from pydantic import BaseModel, Field

from gridline.events.types import EventType, Severity
from gridline.simulation.runner import MAX_SPEED, MIN_SPEED, SimulationStatus, StageInfo
from gridline.simulation.scenarios import SCENARIOS, ScenarioName


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


def scenario_infos() -> list[ScenarioInfo]:
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
