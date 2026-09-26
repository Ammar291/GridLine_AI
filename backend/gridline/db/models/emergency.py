"""Hospitals, ambulances, fire, police, crews and shelters (spec §5.7)."""

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from gridline.db.base import Base

if TYPE_CHECKING:
    from gridline.db.models.population import School
    from gridline.db.models.utilities import PowerSubstation


class Hospital(Base):
    __tablename__ = "hospitals"

    id: Mapped[str] = mapped_column(primary_key=True)
    name: Mapped[str]
    kind: Mapped[str]
    zone_id: Mapped[str] = mapped_column(ForeignKey("zones.id"))
    x_m: Mapped[int]
    y_m: Mapped[int]
    elevation_m: Mapped[float]
    year_built: Mapped[int]
    floors: Mapped[int]
    has_burn_unit: Mapped[bool]
    has_helipad: Mapped[bool]
    backup_power_hours: Mapped[float]
    access_road_id: Mapped[str] = mapped_column(ForeignKey("roads.id"))
    substation_id: Mapped[str] = mapped_column(ForeignKey("power_substations.id"))
    water_facility_id: Mapped[str] = mapped_column(ForeignKey("water_facilities.id"))
    status: Mapped[str]
    description: Mapped[str]

    substation: Mapped["PowerSubstation"] = relationship()
    beds: Mapped[list["HospitalBed"]] = relationship(back_populates="hospital", lazy="selectin")


class HospitalBed(Base):
    """Bed capacity by type; id is ``"<hospital>-<type>"`` (e.g. ``H-1-icu``)."""

    __tablename__ = "hospital_beds"

    id: Mapped[str] = mapped_column(primary_key=True)
    hospital_id: Mapped[str] = mapped_column(ForeignKey("hospitals.id"))
    bed_type: Mapped[str]
    total: Mapped[int]
    available: Mapped[int]

    hospital: Mapped[Hospital] = relationship(back_populates="beds")


class Ambulance(Base):
    __tablename__ = "ambulances"

    id: Mapped[str] = mapped_column(primary_key=True)
    hospital_id: Mapped[str] = mapped_column(ForeignKey("hospitals.id"))
    kind: Mapped[str]
    status: Mapped[str]
    location_zone_id: Mapped[str] = mapped_column(ForeignKey("zones.id"))


class FireStation(Base):
    __tablename__ = "fire_stations"

    id: Mapped[str] = mapped_column(primary_key=True)
    name: Mapped[str]
    zone_id: Mapped[str] = mapped_column(ForeignKey("zones.id"))
    x_m: Mapped[int]
    y_m: Mapped[int]
    elevation_m: Mapped[float]
    year_built: Mapped[int]
    staff_on_shift: Mapped[int]
    coverage_zone_ids: Mapped[list[str]]
    access_road_id: Mapped[str] = mapped_column(ForeignKey("roads.id"))
    has_foam_capability: Mapped[bool]
    description: Mapped[str]


class FireTruck(Base):
    __tablename__ = "fire_trucks"

    id: Mapped[str] = mapped_column(primary_key=True)
    station_id: Mapped[str] = mapped_column(ForeignKey("fire_stations.id"))
    kind: Mapped[str]
    water_capacity_l: Mapped[int]
    foam_capacity_l: Mapped[int]
    min_road_width_m: Mapped[float]
    status: Mapped[str]
    location_zone_id: Mapped[str] = mapped_column(ForeignKey("zones.id"))


class PoliceStation(Base):
    __tablename__ = "police_stations"

    id: Mapped[str] = mapped_column(primary_key=True)
    name: Mapped[str]
    zone_id: Mapped[str] = mapped_column(ForeignKey("zones.id"))
    x_m: Mapped[int]
    y_m: Mapped[int]
    elevation_m: Mapped[float]
    personnel: Mapped[int]
    jurisdiction_zone_ids: Mapped[list[str]]
    has_control_room: Mapped[bool]
    description: Mapped[str]


class Crew(Base):
    __tablename__ = "crews"

    id: Mapped[str] = mapped_column(primary_key=True)
    name: Mapped[str]
    kind: Mapped[str]
    members: Mapped[int]
    base_zone_id: Mapped[str] = mapped_column(ForeignKey("zones.id"))
    location_zone_id: Mapped[str] = mapped_column(ForeignKey("zones.id"))
    x_m: Mapped[int]
    y_m: Mapped[int]
    elevation_m: Mapped[float]
    status: Mapped[str]
    capabilities: Mapped[list[str]]
    equipment: Mapped[str]
    baseline_response_min: Mapped[int]
    description: Mapped[str]


class Shelter(Base):
    __tablename__ = "shelters"

    id: Mapped[str] = mapped_column(primary_key=True)
    name: Mapped[str]
    kind: Mapped[str]
    zone_id: Mapped[str] = mapped_column(ForeignKey("zones.id"))
    x_m: Mapped[int]
    y_m: Mapped[int]
    elevation_m: Mapped[float]
    capacity_persons: Mapped[int]
    current_occupancy: Mapped[int]
    status: Mapped[str]
    floors: Mapped[int]
    has_generator: Mapped[bool]
    water_supply_days: Mapped[int]
    has_kitchen: Mapped[bool]
    flood_plain_id: Mapped[str | None] = mapped_column(ForeignKey("flood_plains.id"))
    school_id: Mapped[str | None] = mapped_column(ForeignKey("schools.id"))
    access_road_id: Mapped[str] = mapped_column(ForeignKey("roads.id"))
    managed_by: Mapped[str]
    description: Mapped[str]

    school: Mapped["School | None"] = relationship(foreign_keys=[school_id])
