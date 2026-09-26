"""Typed views returned by the read tools (built from ORM rows with ``from_attributes``)."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, computed_field


class View(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class CrewView(View):
    id: str
    name: str
    kind: str
    members: int
    status: str
    capabilities: list[str]
    base_zone_id: str
    location_zone_id: str
    baseline_response_min: int
    target_zone_id: str | None
    task: str | None
    incident_id: str | None


class AmbulanceView(View):
    id: str
    kind: str
    status: str
    hospital_id: str
    location_zone_id: str
    target_zone_id: str | None
    destination_hospital_id: str | None
    incident_id: str | None


class ShelterView(View):
    id: str
    name: str
    kind: str
    zone_id: str
    status: str
    capacity_persons: int
    current_occupancy: int
    has_generator: bool
    access_road_id: str
    incident_id: str | None

    @computed_field
    @property
    def available(self) -> int:
        return self.capacity_persons - self.current_occupancy


class BedView(View):
    bed_type: str
    total: int
    available: int
    reserved: int

    @computed_field
    @property
    def occupied(self) -> int:
        return self.total - self.available - self.reserved


class HospitalView(View):
    id: str
    name: str
    kind: str
    zone_id: str
    status: str
    access_road_id: str
    beds: list[BedView]

    @computed_field
    @property
    def available_beds(self) -> int:
        return sum(b.available for b in self.beds)

    @computed_field
    @property
    def reserved_beds(self) -> int:
        return sum(b.reserved for b in self.beds)


class RoadView(View):
    id: str
    name: str
    kind: str
    zone_id: str
    from_zone_id: str
    to_zone_id: str
    status: str
    is_evacuation_route: bool
    is_only_access: bool
    closure_reason: str | None
    closed_at: datetime | None
    incident_id: str | None


class RescueTeamsResult(BaseModel):
    items: list[CrewView]


class AmbulancesResult(BaseModel):
    items: list[AmbulanceView]


class SheltersResult(BaseModel):
    items: list[ShelterView]


class HospitalsResult(BaseModel):
    items: list[HospitalView]


class RoadsResult(BaseModel):
    items: list[RoadView]
