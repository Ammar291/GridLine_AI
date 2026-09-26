"""City, zones, geology, soils, catchments and geography records (spec §5.1-§5.3)."""

import datetime as dt

from gridline.city.schema_common import Located, Record


class CityRecord(Record):
    name: str
    region: str
    country: str
    founded_year: int
    area_km2: float
    population_2026: int
    bbox: list[int]
    crs: str
    river_datum_m: float
    gauge_zero_m: float
    as_of_date: dt.date
    administration: str
    disaster_authority: str
    emergency_number: str
    description: str


class ZoneRecord(Record):
    name: str
    kind: str
    bbox: list[int]
    slope_deg: float
    soil_type: str
    geological_zone_id: str
    catchment_id: str
    drains_to_channel_id: str | None
    description: str


class GeologicalZoneRecord(Record):
    name: str
    lithology: str
    description: str
    permeability_class: str
    bearing_capacity_class: str
    hazard_notes: str


class SoilProfileRecord(Record):
    zone_id: str
    soil_type: str
    depth_to_bedrock_m: float
    permeability_class: str
    infiltration_rate_mm_h: float
    field_capacity: float
    plasticity_index: float
    shrink_swell: str
    liquefaction_susceptibility: str
    bearing_capacity_kpa: float
    water_table_depth_m: float
    notes: str | None = None


class CatchmentRecord(Record):
    name: str
    zone_ids: list[str]
    area_km2: float
    outlet_river_id: str
    outlet_description: str
    impervious_pct_2018: float
    impervious_pct_2026: float


class RiverRecord(Record):
    name: str
    kind: str
    description: str
    length_km: float | None
    ordinary_flow_m3s: float | None
    bankfull_flow_m3s: float | None
    gauge_sensor_id: str | None
    gauge_zero_m: float | None
    flood_stage_m: float | None
    danger_stage_m: float | None
    record_stage_m: float | None
    record_date: dt.date | None
    surface_level_m: float | None
    path: list[list[int]]


class HillRecord(Record):
    name: str
    summit_x_m: int
    summit_y_m: int
    zone_ids: list[str]
    geological_zone_id: str
    description: str


class SlopeRecord(Located):
    name: str
    zone_id: str
    hill_id: str
    mean_angle_deg: float
    max_angle_deg: float
    aspect: str
    length_m: float
    height_m: float
    soil_depth_m: float
    vegetation_cover_pct: float
    stability_class: str
    retaining_structures: str | None
    toe_channel_id: str | None
    toe_distance_to_channel_m: float | None
    has_active_construction: bool
    description: str


class FloodPlainRecord(Record):
    name: str
    river_id: str
    zone_ids: list[str]
    area_km2: float
    return_period_years: int
    typical_depth_m: float
    protection_type: str | None
    protection_crest_m: float | None
    protection_year_built: int | None
    protection_year_raised: int | None
    residents_2018: int
    residents_2026: int
    description: str
