"""Drainage, transport, utilities, projects, critical infrastructure and sensor records (spec §5.4-§5.6)."""

import datetime as dt

from gridline.city.schema_common import Located, Record


class DrainageChannelRecord(Located):
    name: str
    kind: str
    catchment_id: str
    upstream_zone_id: str
    downstream_zone_id: str
    length_m: float
    year_built: int
    year_relined: int | None
    design_capacity_m3s: float
    current_capacity_m3s: float
    blocked_fraction: float
    condition: str
    last_desilted: dt.date | None
    outfall_river_id: str | None
    outfall_channel_id: str | None
    limiting_structure_id: str | None
    limiting_structure_kind: str | None
    gate_closes_at_river_stage_m: float | None
    description: str


class PumpUnitRecord(Located):
    name: str
    kind: str
    capacity_m3s: float
    status: str
    location_zone_id: str
    channel_id: str | None
    year_installed: int
    notes: str | None = None


class RoadRecord(Record):
    name: str
    kind: str
    zone_id: str
    from_zone_id: str
    to_zone_id: str
    length_m: float
    lanes: int
    width_m: float
    surface: str
    year_built: int
    last_major_work_year: int | None
    status: str
    is_evacuation_route: bool
    is_only_access: bool
    floods_at_river_stage_m: float | None
    path: list[list[int]]
    description: str


class BridgeRecord(Located):
    name: str
    road_id: str
    crosses_kind: str
    crosses_id: str
    zone_id: str
    year_built: int
    year_rebuilt: int | None
    length_m: float
    load_rating_t: float
    condition: str
    scour_risk: str
    clearance_m: float | None
    waterway_area_m2: float | None
    closes_at_river_stage_m: float | None
    last_inspection: dt.date | None
    description: str


class TunnelRecord(Located):
    name: str
    kind: str
    road_id: str | None
    zone_id: str
    length_m: float
    year_built: int
    depth_below_grade_m: float
    condition: str
    sump_pump_ids: list[str]
    floods_when: str | None
    description: str


class DamRecord(Located):
    name: str
    kind: str
    river_id: str
    channel_id: str | None
    zone_id: str | None
    year_built: int
    height_m: float
    storage_mcm: float
    spillway_capacity_m3s: float
    gates: int
    condition: str
    silted_pct: float
    closes_at_river_stage_m: float | None
    downstream_zone_ids: list[str]
    operator: str | None
    description: str


class PowerSubstationRecord(Located):
    name: str
    zone_id: str
    voltage_kv: str
    capacity_mva: float
    year_built: int
    serves_zone_ids: list[str]
    fed_from_substation_id: str | None
    flood_protected: bool
    platform_raised_m: float
    status: str
    description: str


class WaterFacilityRecord(Located):
    name: str
    kind: str
    zone_id: str
    capacity_mld: float | None
    storage_ml: float | None
    year_built: int
    year_expanded: int | None
    serves_zone_ids: list[str]
    substation_id: str | None
    backup_power_hours: float | None
    flood_exposure: str
    description: str


class ProjectRecord(Located):
    name: str
    kind: str
    zone_id: str
    slope_id: str | None
    status: str
    start_date: dt.date
    planned_end_date: dt.date | None
    completed_date: dt.date | None
    excavation_depth_m: float | None
    planned_depth_m: float | None
    area_m2: float | None
    permit_number: str | None
    permit_doc_id: str | None
    developer: str | None
    flood_plain_id: str | None
    nearest_channel_id: str | None
    distance_to_channel_m: float | None
    hazard_review_status: str
    description: str


class CriticalInfrastructureRecord(Record):
    name: str
    category: str
    asset_kind: str
    asset_id: str
    zone_id: str
    tier: int
    backup_power_hours: float | None
    depends_on_substation_id: str | None
    depends_on_water_facility_id: str | None
    access_road_id: str | None
    flood_exposure: str
    notes: str | None = None


class SensorRecord(Located):
    kind: str
    name: str
    zone_id: str | None
    unit: str
    installed_year: int
    channel_id: str | None
    slope_id: str | None
    river_id: str | None
    status: str
    description: str
