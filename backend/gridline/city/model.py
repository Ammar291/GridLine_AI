"""The simulation's typed view of Nandipur (spec §4, rebuilt on the data layer).

Every asset is frozen; live values live in ``gridline.simulation.world``. ``gridline.city.nandipur`` builds a
``City`` from the validated YAML records, so ids and numbers are the data layer's, never re-typed here.
"""

from collections.abc import Iterable
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from gridline.errors import UnknownAsset
from gridline.events.payloads import (
    AmbulanceStatusValue,
    CrewStatusValue,
    RoadStatusValue,
    ShelterStatusValue,
)

PermeabilityClass = Literal["very_low", "low", "moderate", "high"]
SensorKind = Literal["rain_gauge", "soil_moisture", "channel_level", "river_level", "wind"]


class Asset(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str


class Zone(Asset):
    name: str
    kind: str
    slope_deg: float = Field(ge=0, le=90)
    soil_type: str
    permeability_class: PermeabilityClass  # from the zone's soil profile
    impervious_fraction: float = Field(
        ge=0, le=1
    )  # zone_yearly_stats impermeable_surface_pct for the as-of year
    area_km2: float = Field(gt=0)  # from the zone bbox
    drains_to_channel_id: str | None = None
    population: int = Field(default=0, ge=0)  # zone_yearly_stats population for the as-of year
    bbox: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)  # x0, y0, x1, y1 in metres


class Slope(Asset):
    name: str
    zone_id: str
    mean_angle_deg: float = Field(ge=0, le=90)
    soil_depth_m: float = Field(ge=0)
    stability_class: str = "stable"
    toe_channel_id: str | None = None


class DrainageChannel(Asset):
    name: str
    zone_id: str  # upstream zone
    downstream_zone_id: str  # where overflow ponds
    design_capacity_m3s: float = Field(gt=0)
    current_capacity_m3s: float = Field(gt=0)
    blocked_fraction: float = Field(default=0, ge=0, le=1)  # initial value from the data layer
    outfall_channel_id: str | None = None
    outfall_river_id: str | None = None
    gate_closes_at_river_stage_m: float | None = None
    pumped_capacity_m3s: float = Field(
        default=0, ge=0
    )  # available fixed pumps; all that drains a closed gate


class River(Asset):
    name: str
    ordinary_flow_m3s: float = Field(gt=0)
    bankfull_flow_m3s: float = Field(gt=0)
    ordinary_stage_m: float = Field(ge=0)  # surface level over gauge zero
    flood_stage_m: float = Field(gt=0)
    warning_stage_m: float = Field(gt=0)  # dmp-2024 s4.3 warning stage
    danger_stage_m: float = Field(gt=0)


class Road(Asset):
    name: str
    zone_id: str
    is_evacuation_route: bool = False
    is_only_access: bool = False
    status: RoadStatusValue = "open"


class Bridge(Asset):
    name: str
    zone_id: str
    road_id: str
    crosses_id: str  # a channel id or a river id
    closes_at_river_stage_m: float | None = None


class Project(Asset):
    name: str
    zone_id: str
    slope_id: str | None = None
    permit_number: str | None = None
    excavation_depth_m: float = Field(ge=0)  # depth reached when the scenario starts
    planned_depth_m: float = Field(gt=0)


class Sensor(Asset):
    kind: SensorKind
    zone_id: str | None
    target_id: str  # zone (rain_gauge, wind), slope (soil_moisture), channel or river


class Substation(Asset):
    name: str
    zone_id: str


class Crew(Asset):
    name: str
    kind: str
    base_zone_id: str
    location_zone_id: str
    status: CrewStatusValue = "available"


class Ambulance(Asset):
    hospital_id: str
    location_zone_id: str
    status: AmbulanceStatusValue = "available"


class Hospital(Asset):
    name: str
    zone_id: str
    beds_total: int = Field(gt=0)
    beds_occupied: int = Field(ge=0)  # baseline: total minus available over every bed type

    @model_validator(mode="after")
    def _occupancy_fits(self) -> "Hospital":
        if self.beds_occupied > self.beds_total:
            raise ValueError(f"hospital {self.id}: occupied beds exceed total")
        return self


class Shelter(Asset):
    name: str
    zone_id: str
    capacity: int = Field(gt=0)
    occupancy: int = Field(default=0, ge=0)
    status: ShelterStatusValue = "closed"


class PolicyThresholds(BaseModel):
    """The policy numbers the severity bands use, read from ``policy_thresholds.yaml`` (dmp-2024 and SOPs)."""

    model_config = ConfigDict(frozen=True)

    rain_1h_watch_mm_h: float
    rain_1h_warning_mm_h: float
    rain_24h_watch_mm: float
    rain_24h_warning_mm: float
    rain_24h_critical_mm: float
    saturation_warning: float
    saturation_critical: float
    channel_ratio_watch: float
    channel_ratio_critical: float
    wind_watch_kmh: float
    wind_warning_kmh: float
    wind_critical_kmh: float
    road_closure_depth_cm: float
    landslide_rain_gauge_ids: tuple[str, ...]  # gauges serving slopes above 25 degrees (dmp-2024 s4.2)


def _find[T: Asset](items: Iterable[T], item_id: str, kind: str) -> T:
    for item in items:
        if item.id == item_id:
            return item
    raise UnknownAsset(f"unknown {kind} id {item_id!r}")


class City(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    zones: tuple[Zone, ...]
    slopes: tuple[Slope, ...] = ()
    channels: tuple[DrainageChannel, ...] = ()
    rivers: tuple[River, ...] = ()
    roads: tuple[Road, ...] = ()
    bridges: tuple[Bridge, ...] = ()
    projects: tuple[Project, ...] = ()
    sensors: tuple[Sensor, ...] = ()
    substations: tuple[Substation, ...] = ()
    crews: tuple[Crew, ...] = ()
    ambulances: tuple[Ambulance, ...] = ()
    hospitals: tuple[Hospital, ...] = ()
    shelters: tuple[Shelter, ...] = ()
    pump_units_available: int = Field(default=0, ge=0)  # mobile pumps at the depot
    thresholds: PolicyThresholds

    def zone(self, zone_id: str) -> Zone:
        return _find(self.zones, zone_id, "zone")

    def slope(self, slope_id: str) -> Slope:
        return _find(self.slopes, slope_id, "slope")

    def channel(self, channel_id: str) -> DrainageChannel:
        return _find(self.channels, channel_id, "channel")

    def river(self, river_id: str) -> River:
        return _find(self.rivers, river_id, "river")

    def road(self, road_id: str) -> Road:
        return _find(self.roads, road_id, "road")

    def bridge(self, bridge_id: str) -> Bridge:
        return _find(self.bridges, bridge_id, "bridge")

    def project(self, project_id: str) -> Project:
        return _find(self.projects, project_id, "project")

    def sensor(self, sensor_id: str) -> Sensor:
        return _find(self.sensors, sensor_id, "sensor")

    def substation(self, substation_id: str) -> Substation:
        return _find(self.substations, substation_id, "substation")

    def crew(self, crew_id: str) -> Crew:
        return _find(self.crews, crew_id, "crew")

    def ambulance(self, ambulance_id: str) -> Ambulance:
        return _find(self.ambulances, ambulance_id, "ambulance")

    def hospital(self, hospital_id: str) -> Hospital:
        return _find(self.hospitals, hospital_id, "hospital")

    def shelter(self, shelter_id: str) -> Shelter:
        return _find(self.shelters, shelter_id, "shelter")

    def zones_draining_to(self, channel_id: str) -> list[Zone]:
        return [z for z in self.zones if z.drains_to_channel_id == channel_id]

    def channels_outfalling_to(self, channel_id: str) -> list[DrainageChannel]:
        return [c for c in self.channels if c.outfall_channel_id == channel_id]

    def roads_in(self, zone_id: str) -> list[Road]:
        return [r for r in self.roads if r.zone_id == zone_id]

    def bridges_in(self, zone_id: str) -> list[Bridge]:
        return [b for b in self.bridges if b.zone_id == zone_id]

    def projects_in(self, zone_id: str) -> list[Project]:
        return [p for p in self.projects if p.zone_id == zone_id]

    def channels_upstream_first(self) -> list[DrainageChannel]:
        """Channels ordered so every tributary comes before the channel it outfalls into."""
        ordered: list[DrainageChannel] = []
        remaining = list(self.channels)
        while remaining:
            done = {c.id for c in ordered}
            ready = [c for c in remaining if all(t.id in done for t in self.channels_outfalling_to(c.id))]
            if not ready:
                raise ValueError("channel outfalls form a cycle: " + ", ".join(c.id for c in remaining))
            ordered.extend(ready)
            remaining = [c for c in remaining if c not in ready]
        return ordered

    @model_validator(mode="after")
    def _check_references(self) -> "City":
        problems = _dangling_references(self)
        if problems:
            raise ValueError("dangling references: " + "; ".join(problems))
        self.channels_upstream_first()
        return self


def _dangling_references(city: City) -> list[str]:
    zones = {z.id for z in city.zones}
    slopes = {s.id for s in city.slopes}
    channels = {c.id for c in city.channels}
    rivers = {r.id for r in city.rivers}
    targets: dict[str, set[str]] = {
        "rain_gauge": zones,
        "wind": zones,
        "soil_moisture": slopes,
        "channel_level": channels,
        "river_level": rivers,
    }
    checks: list[tuple[str, str | None, set[str]]] = []
    checks += [(f"zone {z.id}", z.drains_to_channel_id, channels) for z in city.zones]
    checks += [(f"slope {s.id}", s.zone_id, zones) for s in city.slopes]
    checks += [(f"slope {s.id}", s.toe_channel_id, channels) for s in city.slopes]
    for c in city.channels:
        checks += [(f"channel {c.id}", ref, zones) for ref in (c.zone_id, c.downstream_zone_id)]
        checks += [
            (f"channel {c.id}", c.outfall_channel_id, channels),
            (f"channel {c.id}", c.outfall_river_id, rivers),
        ]
    checks += [(f"road {r.id}", r.zone_id, zones) for r in city.roads]
    for b in city.bridges:
        checks += [
            (f"bridge {b.id}", b.zone_id, zones),
            (f"bridge {b.id}", b.road_id, {r.id for r in city.roads}),
        ]
        checks += [(f"bridge {b.id}", b.crosses_id, channels | rivers)]
    checks += [(f"project {p.id}", p.zone_id, zones) for p in city.projects]
    checks += [(f"project {p.id}", p.slope_id, slopes) for p in city.projects]
    checks += [(f"sensor {s.id}", s.zone_id, zones) for s in city.sensors]
    checks += [(f"sensor {s.id}", s.target_id, targets[s.kind]) for s in city.sensors]
    checks += [(f"substation {s.id}", s.zone_id, zones) for s in city.substations]
    for crew in city.crews:
        checks += [(f"crew {crew.id}", ref, zones) for ref in (crew.base_zone_id, crew.location_zone_id)]
    hospitals = {h.id for h in city.hospitals}
    checks += [(f"ambulance {a.id}", a.hospital_id, hospitals) for a in city.ambulances]
    checks += [(f"ambulance {a.id}", a.location_zone_id, zones) for a in city.ambulances]
    checks += [(f"hospital {h.id}", h.zone_id, zones) for h in city.hospitals]
    checks += [(f"shelter {s.id}", s.zone_id, zones) for s in city.shelters]
    return [
        f"{owner}: unknown id {ref!r}" for owner, ref, known in checks if ref is not None and ref not in known
    ]
