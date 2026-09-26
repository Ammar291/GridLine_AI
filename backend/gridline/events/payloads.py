"""One Pydantic model per event type (spec §3.2, adapted to the Nandipur data layer).

PAYLOAD_MODELS maps every EventType to its model. Payloads forbid unknown keys so a typo in an injected
event fails validation. Fields documented as "filled by the apply handler" may be omitted on injection.
"""

from typing import Any, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from gridline.events.types import EventType

Trend = Literal["rising", "steady", "falling"]
RunnerState = Literal["idle", "running", "paused"]
RoadStatusValue = Literal["open", "blocked", "closed"]
BridgeStatusValue = Literal["open", "restricted", "closed"]
ProjectStatusValue = Literal["active", "halted"]
ProjectActivityValue = Literal["excavating", "idle", "halted"]
CrewStatusValue = Literal["available", "dispatched", "en_route", "on_site", "blocked", "busy", "off_duty"]
AmbulanceStatusValue = Literal["available", "dispatched", "maintenance"]
ErStatusValue = Literal["normal", "busy", "overwhelmed"]
ShelterStatusValue = Literal["closed", "open", "full"]
FailureAssetKind = Literal["slope", "channel", "bridge", "road", "power"]
FailureKind = Literal["landslide", "culvert_collapse", "embankment_breach", "power_outage"]


class Payload(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SimTick(Payload):
    tick: int = Field(ge=0)
    sim_time: AwareDatetime
    scenario: str
    stage: str
    speed: float = Field(gt=0)
    running: bool = False


class SimStatus(Payload):
    state: RunnerState
    running: bool = False
    scenario: str
    seed: int
    speed: float = Field(gt=0)
    tick: int = Field(ge=0)
    sim_time: AwareDatetime
    stage: str


class SimSnapshot(Payload):
    status: SimStatus
    world: dict[str, Any]


class Heartbeat(Payload):
    tick: int = Field(ge=0)
    sim_time: AwareDatetime


class ScenarioStage(Payload):
    scenario: str
    stage_index: int = Field(ge=0)
    stage: str
    description: str
    tick: int = Field(ge=0)


class WeatherObservation(Payload):
    """A rain gauge reports rainfall, the wind station wind and temperature; unmeasured fields are None."""

    station_id: str
    rainfall_intensity_mm_h: float | None = Field(default=None, ge=0)
    cumulative_rainfall_24h_mm: float | None = Field(default=None, ge=0)
    temperature_c: float | None = None
    wind_speed_kmh: float | None = Field(default=None, ge=0)
    wind_direction_deg: float | None = Field(default=None, ge=0, lt=360)


class WeatherForecast(Payload):
    issued_sim_time: AwareDatetime
    horizon_h: float = Field(gt=0)
    expected_total_mm: float = Field(ge=0)
    peak_intensity_mm_h: float = Field(ge=0)
    confidence: float = Field(ge=0, le=1)
    summary: str


class SoilObservation(Payload):
    probe_id: str
    slope_id: str | None
    soil_moisture_pct: float = Field(ge=0, le=100)
    saturation: float = Field(ge=0, le=1)


class RiverObservation(Payload):
    gauge_id: str
    river_id: str
    level_m: float = Field(ge=0)
    flood_stage_m: float
    warning_level_m: float
    danger_level_m: float
    trend: Trend


class DrainageObservation(Payload):
    gauge_id: str
    channel_id: str
    flow_m3s: float = Field(ge=0)
    capacity_m3s: float = Field(ge=0)
    load_ratio: float = Field(ge=0)
    blocked_fraction: float = Field(ge=0, le=1)
    overflow_m3s: float = Field(ge=0)


class SlopeObservation(Payload):
    slope_id: str
    movement_rate_mm_h: float = Field(ge=0)
    cumulative_movement_mm: float = Field(ge=0)
    saturation: float = Field(ge=0, le=1)


class WaterAccumulation(Payload):
    zone_id: str
    depth_cm: float = Field(ge=0)
    trend: Trend


class RoadStatus(Payload):
    road_id: str
    status: RoadStatusValue
    reason: str = ""
    is_evacuation_route: bool = False  # filled from the city by the apply handler


class BridgeStatus(Payload):
    bridge_id: str
    status: BridgeStatusValue
    reason: str = ""


class DrainageObstruction(Payload):
    channel_id: str
    blocked_fraction: float = Field(ge=0, le=1)
    cause: str = ""


class ConstructionActivity(Payload):
    project_id: str
    status: ProjectStatusValue
    activity: ProjectActivityValue
    excavation_depth_m: float = Field(ge=0)
    planned_depth_m: float = Field(default=0, ge=0)  # filled from the city by the apply handler


class InfrastructureFailure(Payload):
    asset_id: str
    asset_kind: FailureAssetKind
    failure_kind: FailureKind
    description: str


class RescueTeamStatus(Payload):
    crew_id: str
    status: CrewStatusValue
    location_zone_id: str
    task: str = ""


class AmbulanceStatus(Payload):
    ambulance_id: str
    status: AmbulanceStatusValue
    location_zone_id: str
    hospital_id: str = ""  # filled from the city by the apply handler
    available_count: int = Field(default=0, ge=0)  # recomputed for the hospital's fleet by the apply handler
    total_count: int = Field(default=0, ge=0)  # recomputed for the hospital's fleet by the apply handler


class HospitalCapacity(Payload):
    hospital_id: str
    beds_total: int = Field(default=0, ge=0)  # filled from the city by the apply handler
    beds_occupied: int = Field(ge=0)
    beds_available: int = Field(default=0, ge=0)  # recomputed by the apply handler
    er_status: ErStatusValue


class ShelterCapacity(Payload):
    shelter_id: str
    status: ShelterStatusValue
    capacity: int = Field(default=0, ge=0)  # filled from the city by the apply handler
    occupancy: int = Field(ge=0)


PAYLOAD_MODELS: dict[EventType, type[Payload]] = {
    EventType.SIM_TICK: SimTick,
    EventType.SIM_STATUS: SimStatus,
    EventType.SIM_SNAPSHOT: SimSnapshot,
    EventType.SIM_HEARTBEAT: Heartbeat,
    EventType.SCENARIO_STAGE: ScenarioStage,
    EventType.WEATHER_OBSERVATION: WeatherObservation,
    EventType.WEATHER_FORECAST: WeatherForecast,
    EventType.ENVIRONMENT_SOIL: SoilObservation,
    EventType.ENVIRONMENT_RIVER: RiverObservation,
    EventType.ENVIRONMENT_DRAINAGE: DrainageObservation,
    EventType.ENVIRONMENT_SLOPE: SlopeObservation,
    EventType.ENVIRONMENT_WATER_ACCUMULATION: WaterAccumulation,
    EventType.INFRASTRUCTURE_ROAD: RoadStatus,
    EventType.INFRASTRUCTURE_BRIDGE: BridgeStatus,
    EventType.INFRASTRUCTURE_DRAINAGE_OBSTRUCTION: DrainageObstruction,
    EventType.INFRASTRUCTURE_CONSTRUCTION: ConstructionActivity,
    EventType.INFRASTRUCTURE_FAILURE: InfrastructureFailure,
    EventType.EMERGENCY_RESCUE_TEAM: RescueTeamStatus,
    EventType.EMERGENCY_AMBULANCE: AmbulanceStatus,
    EventType.EMERGENCY_HOSPITAL: HospitalCapacity,
    EventType.EMERGENCY_SHELTER: ShelterCapacity,
}
