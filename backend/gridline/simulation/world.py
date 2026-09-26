"""Live state of the simulated city (spec §5.1) and its frozen export ``WorldSnapshot``.

``WorldState`` is mutated only by the engine's physics step and by ``apply_event``. Per-asset states are small
Pydantic models so the snapshot can copy them into a JSON-safe, typed export.
"""

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime

from pydantic import AwareDatetime, BaseModel, ConfigDict

from gridline.city.model import City
from gridline.events.payloads import (
    AmbulanceStatusValue,
    BridgeStatusValue,
    CrewStatusValue,
    ErStatusValue,
    ProjectActivityValue,
    ProjectStatusValue,
    RoadStatusValue,
    ShelterStatusValue,
    Trend,
    WeatherForecast,
)


class WeatherState(BaseModel):
    temperature_c: float
    wind_speed_kmh: float
    wind_direction_deg: float


class RainOverride(BaseModel):
    """Operator rain on one zone until a sim time (``weather.rainfall``); internal, not in the snapshot."""

    intensity_mm_h: float
    until: AwareDatetime


class ZoneConditions(BaseModel):
    saturation: float
    rainfall_intensity_mm_h: float = 0.0
    rain_24h_mm: float = 0.0
    water_depth_cm: float = 0.0
    water_trend: Trend = "steady"


class SlopeState(BaseModel):
    saturation: float
    movement_rate_mm_h: float = 0.0
    cumulative_movement_mm: float = 0.0


class ChannelState(BaseModel):
    blocked_fraction: float
    capacity_m3s: float
    extra_capacity_m3s: float = 0.0  # mobile pumps, added by the tool layer later
    gate_closed: bool = False
    flow_m3s: float = 0.0
    overflow_m3s: float = 0.0


class RiverState(BaseModel):
    level_m: float
    inflow_m3s: float
    trend: Trend = "steady"


class RoadState(BaseModel):
    status: RoadStatusValue
    reason: str = ""


class BridgeState(BaseModel):
    status: BridgeStatusValue = "open"
    reason: str = ""


class ProjectState(BaseModel):
    status: ProjectStatusValue = "active"
    activity: ProjectActivityValue = "idle"
    excavation_depth_m: float


class CrewState(BaseModel):
    status: CrewStatusValue
    location_zone_id: str
    task: str = ""


class AmbulanceState(BaseModel):
    status: AmbulanceStatusValue
    location_zone_id: str


class HospitalState(BaseModel):
    beds_occupied: int
    er_status: ErStatusValue = "normal"


class ShelterState(BaseModel):
    status: ShelterStatusValue
    occupancy: int


class FireState(BaseModel):
    site: str
    exposed_zone_ids: list[str]
    exposed_population: int


class WorldSnapshot(BaseModel):
    """Frozen, JSON-safe export of the whole world (``sim.snapshot`` and ``GET /api/simulation/snapshot``)."""

    model_config = ConfigDict(frozen=True)

    tick: int
    sim_time: AwareDatetime
    stage_index: int
    weather: WeatherState
    forecast: WeatherForecast | None
    zones: dict[str, ZoneConditions]
    slopes: dict[str, SlopeState]
    channels: dict[str, ChannelState]
    rivers: dict[str, RiverState]
    roads: dict[str, RoadState]
    bridges: dict[str, BridgeState]
    projects: dict[str, ProjectState]
    crews: dict[str, CrewState]
    ambulances: dict[str, AmbulanceState]
    hospitals: dict[str, HospitalState]
    shelters: dict[str, ShelterState]
    fires: dict[str, FireState]


def _copies[M: BaseModel](states: dict[str, M]) -> dict[str, M]:
    return {key: state.model_copy() for key, state in states.items()}


@dataclass
class WorldState:
    tick: int
    sim_time: datetime
    stage_index: int
    weather: WeatherState
    zones: dict[str, ZoneConditions]
    rain_window: dict[str, deque[float]]  # per zone: rain in mm per tick over the last 24 simulated hours
    slopes: dict[str, SlopeState]
    channels: dict[str, ChannelState]
    rivers: dict[str, RiverState]
    roads: dict[str, RoadState]
    bridges: dict[str, BridgeState]
    projects: dict[str, ProjectState]
    crews: dict[str, CrewState]
    ambulances: dict[str, AmbulanceState]
    hospitals: dict[str, HospitalState]
    shelters: dict[str, ShelterState]
    forecast: WeatherForecast | None = field(default=None)
    rain_overrides: dict[str, RainOverride] = field(default_factory=dict[str, RainOverride])
    fires: dict[str, FireState] = field(default_factory=dict[str, FireState])  # keyed by zone id

    @classmethod
    def from_city(
        cls,
        city: City,
        *,
        start: datetime,
        weather: WeatherState,
        antecedent_saturation: float,
        window_ticks: int,
    ) -> "WorldState":
        return cls(
            tick=0,
            sim_time=start,
            stage_index=0,
            weather=weather,
            zones={z.id: ZoneConditions(saturation=antecedent_saturation) for z in city.zones},
            rain_window={z.id: deque([0.0] * window_ticks, maxlen=window_ticks) for z in city.zones},
            slopes={s.id: SlopeState(saturation=antecedent_saturation) for s in city.slopes},
            channels={
                c.id: ChannelState(
                    blocked_fraction=c.blocked_fraction,
                    capacity_m3s=c.current_capacity_m3s * (1 - c.blocked_fraction),
                )
                for c in city.channels
            },
            rivers={
                r.id: RiverState(level_m=r.ordinary_stage_m, inflow_m3s=r.ordinary_flow_m3s)
                for r in city.rivers
            },
            roads={r.id: RoadState(status=r.status) for r in city.roads},
            bridges={b.id: BridgeState() for b in city.bridges},
            projects={p.id: ProjectState(excavation_depth_m=p.excavation_depth_m) for p in city.projects},
            crews={c.id: CrewState(status=c.status, location_zone_id=c.location_zone_id) for c in city.crews},
            ambulances={
                a.id: AmbulanceState(status=a.status, location_zone_id=a.location_zone_id)
                for a in city.ambulances
            },
            hospitals={h.id: HospitalState(beds_occupied=h.beds_occupied) for h in city.hospitals},
            shelters={s.id: ShelterState(status=s.status, occupancy=s.occupancy) for s in city.shelters},
        )

    def snapshot(self) -> WorldSnapshot:
        return WorldSnapshot(
            tick=self.tick,
            sim_time=self.sim_time,
            stage_index=self.stage_index,
            weather=self.weather.model_copy(),
            forecast=self.forecast,
            zones=_copies(self.zones),
            slopes=_copies(self.slopes),
            channels=_copies(self.channels),
            rivers=_copies(self.rivers),
            roads=_copies(self.roads),
            bridges=_copies(self.bridges),
            projects=_copies(self.projects),
            crews=_copies(self.crews),
            ambulances=_copies(self.ambulances),
            hospitals=_copies(self.hospitals),
            shelters=_copies(self.shelters),
            fires=_copies(self.fires),
        )
