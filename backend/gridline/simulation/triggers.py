"""DEMO controls (docs/superpowers/specs/2026-09-26-demo-controls-design.md).

Each trigger is an ordered list of operator events (world facts: rain, a cut, a blocked drain, a fire) applied
through the normal injection path; one simulated hour then lets physics and sensors show the consequences.
A trigger never states a conclusion: the risk bands come from ``gridline.threats.indices``.
"""

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict

from gridline.events.envelope import Event
from gridline.events.payloads import ScenarioTrigger
from gridline.events.types import EventType
from gridline.simulation.engine import SimulationEngine

TRIGGER_SOURCE = "operator:demo"
TRIGGER_ADVANCE_TICKS = 12  # one simulated hour at five minutes per tick


class TriggerName(StrEnum):
    HEAVY_RAIN = "heavy_rain"
    LANDSLIDE = "landslide"
    DRAINAGE_BLOCK = "drainage_block"
    FLASH_FLOOD = "flash_flood"
    INDUSTRIAL_FIRE = "industrial_fire"
    CASCADING_DISASTER = "cascading_disaster"


class TriggerStep(BaseModel):
    model_config = ConfigDict(frozen=True)

    event_type: EventType
    payload: dict[str, Any]


class Trigger(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: TriggerName
    label: str
    description: str
    steps: tuple[TriggerStep, ...]


class TriggerInfo(BaseModel):
    """A DEMO button as the dashboard lists it (``GET /api/city``)."""

    id: TriggerName
    label: str
    description: str


def _rain(zone_ids: tuple[str, ...], mm_h: float, hours: float, why: str) -> TriggerStep:
    payload = {"zone_ids": list(zone_ids), "intensity_mm_h": mm_h, "duration_h": hours, "description": why}
    return TriggerStep(event_type=EventType.WEATHER_RAINFALL, payload=payload)


_ALL = (
    Trigger(
        name=TriggerName.HEAVY_RAIN,
        label="Heavy Rain",
        description="A monsoon cell brings 20 mm/h over the whole city for three hours",
        steps=(_rain((), 20, 3, "monsoon cell over Nandipur"),),
    ),
    Trigger(
        name=TriggerName.LANDSLIDE,
        label="Landslide",
        description="PR-HT2 cuts SL-HV-1 to its planned 6 m while 60 mm/h of rain falls on Hillview",
        steps=(
            TriggerStep(
                event_type=EventType.INFRASTRUCTURE_CONSTRUCTION,
                payload={
                    "project_id": "PR-HT2",
                    "status": "active",
                    "activity": "excavating",
                    "excavation_depth_m": 6.0,
                },
            ),
            _rain(("Z-HV",), 60, 3, "cloudburst over Hillview"),
        ),
    ),
    Trigger(
        name=TriggerName.DRAINAGE_BLOCK,
        label="Drainage Block",
        description="Debris blocks 70 % of the Kalinadi drain D-7 above Riverside",
        steps=(
            TriggerStep(
                event_type=EventType.INFRASTRUCTURE_DRAINAGE_OBSTRUCTION,
                payload={
                    "channel_id": "D-7",
                    "blocked_fraction": 0.7,
                    "cause": "debris jammed at the BR-4 culvert",
                },
            ),
        ),
    ),
    Trigger(
        name=TriggerName.FLASH_FLOOD,
        label="Flash Flood",
        description="A 70 mm/h cloudburst over Hillview and Riverside for two hours",
        steps=(_rain(("Z-HV", "Z-RS"), 70, 2, "cloudburst over Hillview and Riverside"),),
    ),
    Trigger(
        name=TriggerName.INDUSTRIAL_FIRE,
        label="Industrial Fire",
        description="A solvent warehouse catches fire in Mill Road Industrial",
        steps=(
            TriggerStep(
                event_type=EventType.EMERGENCY_FIRE,
                payload={
                    "zone_id": "Z-MI",
                    "site": "Mill Road solvent warehouse",
                    "description": "Warehouse fire on Mill Road (RD-08)",
                },
            ),
        ),
    ),
    Trigger(
        name=TriggerName.CASCADING_DISASTER,
        label="Cascading Disaster",
        description="SL-HV-1 fails, its debris blocks D-7, then 40 mm/h of rain floods Riverside",
        steps=(
            TriggerStep(
                event_type=EventType.INFRASTRUCTURE_FAILURE,
                payload={
                    "asset_id": "SL-HV-1",
                    "asset_kind": "slope",
                    "failure_kind": "landslide",
                    "description": "Hillview Terrace slope SL-HV-1 fails above D-7",
                },
            ),
            _rain(("Z-HV", "Z-RS"), 40, 3, "storm over the blocked drain"),
        ),
    ),
)
TRIGGERS: dict[TriggerName, Trigger] = {t.name: t for t in _ALL}


def trigger_infos() -> list[TriggerInfo]:
    return [TriggerInfo(id=t.name, label=t.label, description=t.description) for t in _ALL]


def run_trigger(engine: SimulationEngine, name: TriggerName) -> list[Event]:
    """Announce the press, inject its steps as the operator, then advance one simulated hour."""
    chosen = TRIGGERS[name]
    announcement = ScenarioTrigger(
        trigger=chosen.name, label=chosen.label, description=chosen.description, tick=engine.world.tick
    )
    events = [
        engine.make_event(EventType.SCENARIO_TRIGGER, announcement, source=TRIGGER_SOURCE, location=None)
    ]
    for step in chosen.steps:
        events += engine.inject(step.event_type, step.payload, source=TRIGGER_SOURCE)
    return events + engine.advance(TRIGGER_ADVANCE_TICKS)
