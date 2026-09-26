"""Emergency resources and population records (spec §5.7-§5.8)."""

from gridline.city.schema_common import Located, Record


class HospitalRecord(Located):
    name: str
    kind: str
    zone_id: str
    year_built: int
    floors: int
    has_burn_unit: bool
    has_helipad: bool
    backup_power_hours: float
    access_road_id: str
    substation_id: str
    water_facility_id: str
    status: str
    description: str


class HospitalBedRecord(Record):
    hospital_id: str
    bed_type: str
    total: int
    available: int


class AmbulanceRecord(Record):
    hospital_id: str
    kind: str
    status: str
    location_zone_id: str


class FireStationRecord(Located):
    name: str
    zone_id: str
    year_built: int
    staff_on_shift: int
    coverage_zone_ids: list[str]
    access_road_id: str
    has_foam_capability: bool
    description: str


class FireTruckRecord(Record):
    station_id: str
    kind: str
    water_capacity_l: int
    foam_capacity_l: int
    min_road_width_m: float
    status: str
    location_zone_id: str


class PoliceStationRecord(Located):
    name: str
    zone_id: str
    personnel: int
    jurisdiction_zone_ids: list[str]
    has_control_room: bool
    description: str


class CrewRecord(Located):
    name: str
    kind: str
    members: int
    base_zone_id: str
    location_zone_id: str
    status: str
    capabilities: list[str]
    equipment: str
    baseline_response_min: int
    description: str


class ShelterRecord(Located):
    name: str
    kind: str
    zone_id: str
    capacity_persons: int
    current_occupancy: int
    status: str
    floors: int
    has_generator: bool
    water_supply_days: int
    has_kitchen: bool
    flood_plain_id: str | None
    school_id: str | None
    access_road_id: str
    managed_by: str
    description: str


class ZoneYearlyStatsRecord(Record):
    zone_id: str
    year: int
    population: int
    households: int
    children_under_5: int
    elderly_over_65: int
    persons_with_disability: int
    informal_settlement_population: int
    low_income_households: int
    impermeable_surface_pct: float
    built_up_pct: float
    green_cover_pct: float
    avg_building_storeys: float


class ResidentialAreaRecord(Located):
    name: str
    zone_id: str
    kind: str
    households: int
    population: int
    year_established: int | None
    storeys: int | None
    building_quality: str
    slope_id: str | None
    flood_plain_id: str | None
    nearest_channel_id: str | None
    distance_to_channel_m: float | None
    description: str


class SchoolRecord(Located):
    name: str
    zone_id: str
    level: str
    students: int
    staff: int
    floors: int
    shelter_id: str | None
    flood_plain_id: str | None
    slope_id: str | None
    description: str
