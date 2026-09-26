"""The event contract as clients see it: one envelope model per event type and their discriminated union.

``gridline.events.envelope.Event`` is the runtime envelope (its payload is validated against
``PAYLOAD_MODELS`` and kept as a JSON-safe dict). The models here describe the same JSON with the payload
typed per ``event_type``, so ``/openapi.json`` (and the frontend types generated from it) carry every
payload. The union is exported as the ``Event`` schema through the inject route; the WebSocket sends exactly
these shapes.
"""

from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, RootModel

from gridline.api.city_map import CityMap
from gridline.events import envelope
from gridline.events import payloads as p
from gridline.events.types import EventType, Severity
from gridline.simulation.world import WorldSnapshot


class EventBase(BaseModel):
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)

    event_id: str
    timestamp: AwareDatetime
    sim_time: AwareDatetime
    source: str
    location: str | None = None
    severity: Severity
    incident_id: str | None = None


class SimSnapshotPayload(BaseModel):
    """Typed view of the ``sim.snapshot`` payload (``payloads.SimSnapshot`` keeps world and city as dicts)."""

    status: p.SimStatus
    world: WorldSnapshot
    city: CityMap


class SimTickEvent(EventBase):
    event_type: Literal[EventType.SIM_TICK]
    payload: p.SimTick


class SimStatusEvent(EventBase):
    event_type: Literal[EventType.SIM_STATUS]
    payload: p.SimStatus


class SimSnapshotEvent(EventBase):
    event_type: Literal[EventType.SIM_SNAPSHOT]
    payload: SimSnapshotPayload


class HeartbeatEvent(EventBase):
    event_type: Literal[EventType.SIM_HEARTBEAT]
    payload: p.Heartbeat


class ScenarioStageEvent(EventBase):
    event_type: Literal[EventType.SCENARIO_STAGE]
    payload: p.ScenarioStage


class WeatherObservationEvent(EventBase):
    event_type: Literal[EventType.WEATHER_OBSERVATION]
    payload: p.WeatherObservation


class WeatherForecastEvent(EventBase):
    event_type: Literal[EventType.WEATHER_FORECAST]
    payload: p.WeatherForecast


class SoilObservationEvent(EventBase):
    event_type: Literal[EventType.ENVIRONMENT_SOIL]
    payload: p.SoilObservation


class RiverObservationEvent(EventBase):
    event_type: Literal[EventType.ENVIRONMENT_RIVER]
    payload: p.RiverObservation


class DrainageObservationEvent(EventBase):
    event_type: Literal[EventType.ENVIRONMENT_DRAINAGE]
    payload: p.DrainageObservation


class SlopeObservationEvent(EventBase):
    event_type: Literal[EventType.ENVIRONMENT_SLOPE]
    payload: p.SlopeObservation


class WaterAccumulationEvent(EventBase):
    event_type: Literal[EventType.ENVIRONMENT_WATER_ACCUMULATION]
    payload: p.WaterAccumulation


class RoadStatusEvent(EventBase):
    event_type: Literal[EventType.INFRASTRUCTURE_ROAD]
    payload: p.RoadStatus


class BridgeStatusEvent(EventBase):
    event_type: Literal[EventType.INFRASTRUCTURE_BRIDGE]
    payload: p.BridgeStatus


class DrainageObstructionEvent(EventBase):
    event_type: Literal[EventType.INFRASTRUCTURE_DRAINAGE_OBSTRUCTION]
    payload: p.DrainageObstruction


class ConstructionActivityEvent(EventBase):
    event_type: Literal[EventType.INFRASTRUCTURE_CONSTRUCTION]
    payload: p.ConstructionActivity


class InfrastructureFailureEvent(EventBase):
    event_type: Literal[EventType.INFRASTRUCTURE_FAILURE]
    payload: p.InfrastructureFailure


class RescueTeamStatusEvent(EventBase):
    event_type: Literal[EventType.EMERGENCY_RESCUE_TEAM]
    payload: p.RescueTeamStatus


class AmbulanceStatusEvent(EventBase):
    event_type: Literal[EventType.EMERGENCY_AMBULANCE]
    payload: p.AmbulanceStatus


class HospitalCapacityEvent(EventBase):
    event_type: Literal[EventType.EMERGENCY_HOSPITAL]
    payload: p.HospitalCapacity


class ShelterCapacityEvent(EventBase):
    event_type: Literal[EventType.EMERGENCY_SHELTER]
    payload: p.ShelterCapacity


EVENT_MODELS: dict[EventType, type[EventBase]] = {
    EventType.SIM_TICK: SimTickEvent,
    EventType.SIM_STATUS: SimStatusEvent,
    EventType.SIM_SNAPSHOT: SimSnapshotEvent,
    EventType.SIM_HEARTBEAT: HeartbeatEvent,
    EventType.SCENARIO_STAGE: ScenarioStageEvent,
    EventType.WEATHER_OBSERVATION: WeatherObservationEvent,
    EventType.WEATHER_FORECAST: WeatherForecastEvent,
    EventType.ENVIRONMENT_SOIL: SoilObservationEvent,
    EventType.ENVIRONMENT_RIVER: RiverObservationEvent,
    EventType.ENVIRONMENT_DRAINAGE: DrainageObservationEvent,
    EventType.ENVIRONMENT_SLOPE: SlopeObservationEvent,
    EventType.ENVIRONMENT_WATER_ACCUMULATION: WaterAccumulationEvent,
    EventType.INFRASTRUCTURE_ROAD: RoadStatusEvent,
    EventType.INFRASTRUCTURE_BRIDGE: BridgeStatusEvent,
    EventType.INFRASTRUCTURE_DRAINAGE_OBSTRUCTION: DrainageObstructionEvent,
    EventType.INFRASTRUCTURE_CONSTRUCTION: ConstructionActivityEvent,
    EventType.INFRASTRUCTURE_FAILURE: InfrastructureFailureEvent,
    EventType.EMERGENCY_RESCUE_TEAM: RescueTeamStatusEvent,
    EventType.EMERGENCY_AMBULANCE: AmbulanceStatusEvent,
    EventType.EMERGENCY_HOSPITAL: HospitalCapacityEvent,
    EventType.EMERGENCY_SHELTER: ShelterCapacityEvent,
}

AnyEvent = Annotated[
    SimTickEvent
    | SimStatusEvent
    | SimSnapshotEvent
    | HeartbeatEvent
    | ScenarioStageEvent
    | WeatherObservationEvent
    | WeatherForecastEvent
    | SoilObservationEvent
    | RiverObservationEvent
    | DrainageObservationEvent
    | SlopeObservationEvent
    | WaterAccumulationEvent
    | RoadStatusEvent
    | BridgeStatusEvent
    | DrainageObstructionEvent
    | ConstructionActivityEvent
    | InfrastructureFailureEvent
    | RescueTeamStatusEvent
    | AmbulanceStatusEvent
    | HospitalCapacityEvent
    | ShelterCapacityEvent,
    Field(discriminator="event_type"),
]


class Event(RootModel[AnyEvent]):
    """Any event on the bus or the WebSocket, discriminated by ``event_type``."""


def typed_event(event: envelope.Event) -> Event:
    return Event.model_validate(event.model_dump(mode="json"))
