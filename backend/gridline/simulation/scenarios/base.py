"""Scenario scripts as data (spec §6.1): driver curves, stages, forecasts and scripted events.

A scenario never states a conclusion. It drives rain, wind, temperature, upstream river flow and excavation;
physics produces the observations. Scripted events are world facts, optionally conditional on the physics.
"""

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from gridline.events.types import EventType


class ScenarioName(StrEnum):
    NORMAL_CITY = "normal_city"
    HILLSIDE_LANDSLIDE = "hillside_landslide"
    FLASH_FLOOD = "flash_flood"
    CASCADING_LANDSLIDE_FLOOD = "cascading_landslide_flood"


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True)


class Keyframe(_Frozen):
    tick: int = Field(ge=0)
    value: float


class Curve(_Frozen):
    """Piecewise-linear in ticks; holds the first value before the start and the last after the end."""

    keyframes: tuple[Keyframe, ...] = Field(min_length=1)

    @classmethod
    def of(cls, *points: tuple[int, float]) -> "Curve":
        return cls(keyframes=tuple(Keyframe(tick=t, value=v) for t, v in points))

    @model_validator(mode="after")
    def _increasing(self) -> "Curve":
        ticks = [k.tick for k in self.keyframes]
        if ticks != sorted(set(ticks)):
            raise ValueError("keyframe ticks must be strictly increasing")
        return self

    def at(self, tick: int) -> float:
        frames = self.keyframes
        if tick <= frames[0].tick:
            return frames[0].value
        for left, right in zip(frames, frames[1:], strict=False):
            if tick <= right.tick:
                share = (tick - left.tick) / (right.tick - left.tick)
                return left.value + share * (right.value - left.value)
        return frames[-1].value


class Stage(_Frozen):
    name: str
    start_tick: int = Field(ge=0)
    description: str


class ForecastUpdate(_Frozen):
    """A forecast issued at ``tick``; the engine stamps it with the sim time of issue."""

    tick: int = Field(ge=0)
    horizon_h: float = Field(gt=0)
    expected_total_mm: float = Field(ge=0)
    peak_intensity_mm_h: float = Field(ge=0)
    confidence: float = Field(ge=0, le=1)
    summary: str


Metric = Literal["saturation", "water_depth_cm", "river_level_m", "slope_cumulative_mm"]


class Condition(_Frozen):
    """``metric`` of ``target_id`` must reach ``min_value``: saturation and water depth of a zone, level of a
    river, cumulative movement of a slope."""

    target_id: str
    metric: Metric
    min_value: float


class ScriptedEvent(_Frozen):
    tick: int = Field(ge=0)
    event_type: EventType
    payload: dict[str, Any]
    condition: Condition | None = None
    deadline_ticks: int = Field(default=36, ge=0)  # re-check each tick until tick + deadline, then drop


class Excavation(_Frozen):
    project_id: str
    start_tick: int = Field(ge=0)
    rate_m_per_h: float = Field(gt=0)


class Scenario(_Frozen):
    name: ScenarioName
    title: str
    description: str
    duration_ticks: int = Field(gt=0)
    antecedent_saturation: float = Field(ge=0, le=1)
    rainfall: dict[str, Curve]  # mm/h per zone id; zones without an entry use "default"
    temperature: Curve
    wind_speed: Curve
    wind_direction_deg: float = Field(ge=0, lt=360)
    river_flow_factor: Curve  # upstream river flow as a multiple of each river's ordinary flow
    forecasts: tuple[ForecastUpdate, ...] = ()
    excavation: Excavation | None = None
    stages: tuple[Stage, ...] = Field(min_length=1)
    scripted: tuple[ScriptedEvent, ...] = ()

    @model_validator(mode="after")
    def _check(self) -> "Scenario":
        starts = [s.start_tick for s in self.stages]
        if starts[0] != 0 or starts != sorted(set(starts)):
            raise ValueError("stages must start at tick 0 and be strictly increasing")
        if "default" not in self.rainfall:
            raise ValueError("rainfall needs a 'default' curve")
        return self

    def rain_at(self, zone_id: str, tick: int) -> float:
        return max(0.0, self.rainfall.get(zone_id, self.rainfall["default"]).at(tick))

    def stage_index_at(self, tick: int) -> int:
        return max(i for i, stage in enumerate(self.stages) if stage.start_tick <= tick)
