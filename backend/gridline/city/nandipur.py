"""Build the simulation's Nandipur from the one validated data layer (``backend/data/city/*.yaml``).

Nothing here is a second dataset: every id and number comes from ``load_city_data``. The only choices made
here are which records the simulation models (gauged rivers, active excavation projects, observed sensor
kinds) and how a few simulation fields are derived (zone area from its bbox, ordinary river stage from the
surface level over gauge zero, fixed-pump capacity per channel, policy thresholds by hazard/metric/band).
"""

from pathlib import Path
from typing import cast, get_args

from gridline.city.dataset import CityData, load_city_data
from gridline.city.model import (
    Ambulance,
    Bridge,
    City,
    Crew,
    DrainageChannel,
    Hospital,
    PermeabilityClass,
    PolicyThresholds,
    Project,
    River,
    Road,
    Sensor,
    SensorKind,
    Shelter,
    Slope,
    Substation,
    Zone,
)
from gridline.city.schema_history import PolicyThresholdRecord
from gridline.city.schema_infra import SensorRecord
from gridline.config import BACKEND_DIR
from gridline.events.payloads import (
    AmbulanceStatusValue,
    CrewStatusValue,
    RoadStatusValue,
    ShelterStatusValue,
)

DEFAULT_DATA_DIR = BACKEND_DIR / "data"
STEEP_SLOPE_DEG = 25.0  # dmp-2024 s4.2 and s5 apply landslide rainfall rules to "slopes above 25 degrees"

# PolicyThresholds field -> (hazard, metric, band) in policy_thresholds.yaml
_THRESHOLD_KEYS: dict[str, tuple[str, str, str]] = {
    "rain_1h_watch_mm_h": ("flash_flood", "rain_1h_mm", "watch"),
    "rain_1h_warning_mm_h": ("flash_flood", "rain_1h_mm", "warning"),
    "rain_24h_watch_mm": ("landslide", "rain_24h_mm", "watch"),
    "rain_24h_warning_mm": ("landslide", "rain_24h_mm", "warning"),
    "rain_24h_critical_mm": ("landslide", "rain_24h_mm", "critical"),
    "saturation_warning": ("landslide", "saturation", "warning"),
    "saturation_critical": ("landslide", "saturation", "critical"),
    "channel_ratio_watch": ("flood", "channel_flow_ratio", "watch"),
    "channel_ratio_critical": ("flood", "channel_flow_ratio", "critical"),
    "wind_watch_kmh": ("cyclone", "wind_kmh", "watch"),
    "wind_warning_kmh": ("cyclone", "wind_kmh", "warning"),
    "wind_critical_kmh": ("cyclone", "wind_kmh", "critical"),
}


def build_nandipur(data_dir: Path = DEFAULT_DATA_DIR) -> City:
    """Load ``data_dir/city/*.yaml`` and convert it into the simulation's ``City``. No database access."""
    return city_from_data(load_city_data(data_dir))


def city_from_data(data: CityData) -> City:
    return City(
        name=data.city.name,
        zones=tuple(_zones(data)),
        slopes=tuple(
            Slope(
                id=s.id,
                name=s.name,
                zone_id=s.zone_id,
                mean_angle_deg=s.mean_angle_deg,
                soil_depth_m=s.soil_depth_m,
                stability_class=s.stability_class,
                toe_channel_id=s.toe_channel_id,
            )
            for s in data.slopes
        ),
        channels=tuple(_channels(data)),
        rivers=tuple(_rivers(data)),
        roads=tuple(
            Road(
                id=r.id,
                name=r.name,
                zone_id=r.zone_id,
                is_evacuation_route=r.is_evacuation_route,
                is_only_access=r.is_only_access,
                status=cast(RoadStatusValue, r.status),
            )
            for r in data.roads
        ),
        bridges=tuple(
            Bridge(
                id=b.id,
                name=b.name,
                zone_id=b.zone_id,
                road_id=b.road_id,
                crosses_id=b.crosses_id,
                closes_at_river_stage_m=b.closes_at_river_stage_m,
            )
            for b in data.bridges
        ),
        projects=tuple(
            Project(
                id=p.id,
                name=p.name,
                zone_id=p.zone_id,
                slope_id=p.slope_id,
                permit_number=p.permit_number,
                excavation_depth_m=p.excavation_depth_m,
                planned_depth_m=p.planned_depth_m,
            )
            for p in data.projects
            if p.status == "active" and p.excavation_depth_m is not None and p.planned_depth_m is not None
        ),
        sensors=tuple(
            _sensor(s) for s in data.sensors if s.status == "active" and s.kind in get_args(SensorKind)
        ),
        substations=tuple(
            Substation(id=s.id, name=s.name, zone_id=s.zone_id) for s in data.power_substations
        ),
        crews=tuple(
            Crew(
                id=c.id,
                name=c.name,
                kind=c.kind,
                base_zone_id=c.base_zone_id,
                location_zone_id=c.location_zone_id,
                status=cast(CrewStatusValue, c.status),
            )
            for c in data.crews
        ),
        ambulances=tuple(
            Ambulance(
                id=a.id,
                hospital_id=a.hospital_id,
                location_zone_id=a.location_zone_id,
                status=cast(AmbulanceStatusValue, a.status),
            )
            for a in data.ambulances
        ),
        hospitals=tuple(_hospitals(data)),
        shelters=tuple(
            Shelter(
                id=s.id,
                name=s.name,
                zone_id=s.zone_id,
                capacity=s.capacity_persons,
                occupancy=s.current_occupancy,
                status=cast(ShelterStatusValue, s.status),
            )
            for s in data.shelters
        ),
        pump_units_available=sum(
            1 for p in data.pump_units if p.kind == "mobile" and p.status == "available"
        ),
        thresholds=_thresholds(data),
    )


def _zones(data: CityData) -> list[Zone]:
    permeability = {p.zone_id: p.permeability_class for p in data.soil_profiles}
    year = data.city.as_of_date.year
    impervious = {s.zone_id: s.impermeable_surface_pct for s in data.zone_yearly_stats if s.year == year}
    zones: list[Zone] = []
    for z in data.zones:
        x0, y0, x1, y1 = z.bbox
        zones.append(
            Zone(
                id=z.id,
                name=z.name,
                kind=z.kind,
                slope_deg=z.slope_deg,
                soil_type=z.soil_type,
                permeability_class=cast(PermeabilityClass, permeability[z.id]),
                impervious_fraction=impervious[z.id] / 100,
                area_km2=(x1 - x0) * (y1 - y0) / 1e6,
                drains_to_channel_id=z.drains_to_channel_id,
            )
        )
    return zones


def _channels(data: CityData) -> list[DrainageChannel]:
    pumped: dict[str, float] = {}
    for p in data.pump_units:
        if p.kind == "fixed" and p.status == "available" and p.channel_id is not None:
            pumped[p.channel_id] = pumped.get(p.channel_id, 0.0) + p.capacity_m3s
    return [
        DrainageChannel(
            id=c.id,
            name=c.name,
            zone_id=c.upstream_zone_id,
            downstream_zone_id=c.downstream_zone_id,
            design_capacity_m3s=c.design_capacity_m3s,
            current_capacity_m3s=c.current_capacity_m3s,
            blocked_fraction=c.blocked_fraction,
            outfall_channel_id=c.outfall_channel_id,
            outfall_river_id=c.outfall_river_id,
            gate_closes_at_river_stage_m=c.gate_closes_at_river_stage_m,
            pumped_capacity_m3s=pumped.get(c.id, 0.0),
        )
        for c in data.drainage_channels
    ]


def _rivers(data: CityData) -> list[River]:
    """Rivers with a gauge, stages and flows; the warning stage is the policy's (dmp-2024 s4.3)."""
    warning = _threshold(data.policy_thresholds, ("flood", "river_stage_m", "warning"))
    rivers: list[River] = []
    for r in data.rivers:
        if (
            r.gauge_zero_m is None
            or r.surface_level_m is None
            or r.flood_stage_m is None
            or r.danger_stage_m is None
            or r.ordinary_flow_m3s is None
            or r.bankfull_flow_m3s is None
        ):
            continue
        rivers.append(
            River(
                id=r.id,
                name=r.name,
                ordinary_flow_m3s=r.ordinary_flow_m3s,
                bankfull_flow_m3s=r.bankfull_flow_m3s,
                ordinary_stage_m=round(r.surface_level_m - r.gauge_zero_m, 2),
                flood_stage_m=r.flood_stage_m,
                warning_stage_m=warning,
                danger_stage_m=r.danger_stage_m,
            )
        )
    return rivers


def _sensor(s: SensorRecord) -> Sensor:
    kind = cast(SensorKind, s.kind)
    target = {"soil_moisture": s.slope_id, "channel_level": s.channel_id, "river_level": s.river_id}.get(
        kind, s.zone_id
    )
    if target is None:
        raise ValueError(f"sensor {s.id}: no target for kind {kind}")
    return Sensor(id=s.id, kind=kind, zone_id=s.zone_id, target_id=target)


def _hospitals(data: CityData) -> list[Hospital]:
    total: dict[str, int] = {}
    available: dict[str, int] = {}
    for bed in data.hospital_beds:
        total[bed.hospital_id] = total.get(bed.hospital_id, 0) + bed.total
        available[bed.hospital_id] = available.get(bed.hospital_id, 0) + bed.available
    return [
        Hospital(
            id=h.id,
            name=h.name,
            zone_id=h.zone_id,
            beds_total=total[h.id],
            beds_occupied=total[h.id] - available[h.id],
        )
        for h in data.hospitals
    ]


def _thresholds(data: CityData) -> PolicyThresholds:
    values = {field: _threshold(data.policy_thresholds, key) for field, key in _THRESHOLD_KEYS.items()}
    closure_m = _threshold(data.policy_thresholds, ("all", "water_depth_m", "close"))
    steep_zones = {s.zone_id for s in data.slopes if s.mean_angle_deg > STEEP_SLOPE_DEG}
    gauges = tuple(sorted(s.id for s in data.sensors if s.kind == "rain_gauge" and s.zone_id in steep_zones))
    return PolicyThresholds.model_validate(
        {**values, "road_closure_depth_cm": closure_m * 100, "landslide_rain_gauge_ids": gauges}
    )


def _threshold(records: list[PolicyThresholdRecord], key: tuple[str, str, str]) -> float:
    matches = [r.value for r in records if (r.hazard, r.metric, r.band) == key]
    if len(matches) != 1:
        raise ValueError(f"policy_thresholds: expected one row for {key}, found {len(matches)}")
    return matches[0]
