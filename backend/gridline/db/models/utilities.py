"""Power, water, projects, critical infrastructure register and sensors (spec §5.6)."""

import datetime as dt
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from gridline.db.base import Base

if TYPE_CHECKING:
    from gridline.db.models.city import Zone
    from gridline.db.models.geography import Slope


class PowerSubstation(Base):
    __tablename__ = "power_substations"

    id: Mapped[str] = mapped_column(primary_key=True)
    name: Mapped[str]
    zone_id: Mapped[str] = mapped_column(ForeignKey("zones.id"))
    x_m: Mapped[int]
    y_m: Mapped[int]
    elevation_m: Mapped[float]
    voltage_kv: Mapped[str]  # e.g. "132/33"
    capacity_mva: Mapped[float]
    year_built: Mapped[int]
    serves_zone_ids: Mapped[list[str]]
    fed_from_substation_id: Mapped[str | None] = mapped_column(ForeignKey("power_substations.id"))
    flood_protected: Mapped[bool]
    platform_raised_m: Mapped[float]
    status: Mapped[str]
    description: Mapped[str]


class WaterFacility(Base):
    __tablename__ = "water_facilities"

    id: Mapped[str] = mapped_column(primary_key=True)
    name: Mapped[str]
    kind: Mapped[str]
    zone_id: Mapped[str] = mapped_column(ForeignKey("zones.id"))
    x_m: Mapped[int]
    y_m: Mapped[int]
    elevation_m: Mapped[float]
    capacity_mld: Mapped[float | None]
    storage_ml: Mapped[float | None]
    year_built: Mapped[int]
    year_expanded: Mapped[int | None]
    serves_zone_ids: Mapped[list[str]]
    substation_id: Mapped[str | None] = mapped_column(ForeignKey("power_substations.id"))
    backup_power_hours: Mapped[float | None]
    flood_exposure: Mapped[str]
    description: Mapped[str]


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(primary_key=True)
    name: Mapped[str]
    kind: Mapped[str]
    zone_id: Mapped[str] = mapped_column(ForeignKey("zones.id"))
    slope_id: Mapped[str | None] = mapped_column(ForeignKey("slopes.id"))
    status: Mapped[str]
    start_date: Mapped[dt.date]
    planned_end_date: Mapped[dt.date | None]
    completed_date: Mapped[dt.date | None]
    excavation_depth_m: Mapped[float | None]
    planned_depth_m: Mapped[float | None]
    area_m2: Mapped[float | None]
    permit_number: Mapped[str | None]
    permit_doc_id: Mapped[str | None] = mapped_column(ForeignKey("documents.id"))
    developer: Mapped[str | None]
    flood_plain_id: Mapped[str | None] = mapped_column(ForeignKey("flood_plains.id"))
    nearest_channel_id: Mapped[str | None] = mapped_column(ForeignKey("drainage_channels.id"))
    distance_to_channel_m: Mapped[float | None]
    hazard_review_status: Mapped[str]
    x_m: Mapped[int]
    y_m: Mapped[int]
    elevation_m: Mapped[float]
    description: Mapped[str]

    slope: Mapped["Slope | None"] = relationship()
    zone: Mapped["Zone"] = relationship()


class CriticalInfrastructure(Base):
    """Register of critical assets; ``asset_kind`` + ``asset_id`` is a polymorphic reference."""

    __tablename__ = "critical_infrastructure"

    id: Mapped[str] = mapped_column(primary_key=True)
    name: Mapped[str]
    category: Mapped[str]
    asset_kind: Mapped[str]
    asset_id: Mapped[str]
    zone_id: Mapped[str] = mapped_column(ForeignKey("zones.id"))
    tier: Mapped[int]
    backup_power_hours: Mapped[float | None]
    depends_on_substation_id: Mapped[str | None] = mapped_column(ForeignKey("power_substations.id"))
    depends_on_water_facility_id: Mapped[str | None] = mapped_column(ForeignKey("water_facilities.id"))
    access_road_id: Mapped[str | None] = mapped_column(ForeignKey("roads.id"))
    flood_exposure: Mapped[str]
    notes: Mapped[str | None]


class Sensor(Base):
    __tablename__ = "sensors"

    id: Mapped[str] = mapped_column(primary_key=True)
    kind: Mapped[str]
    name: Mapped[str]
    zone_id: Mapped[str | None] = mapped_column(ForeignKey("zones.id"))
    x_m: Mapped[int]
    y_m: Mapped[int]
    elevation_m: Mapped[float]
    unit: Mapped[str]
    installed_year: Mapped[int]
    channel_id: Mapped[str | None] = mapped_column(ForeignKey("drainage_channels.id"))
    slope_id: Mapped[str | None] = mapped_column(ForeignKey("slopes.id"))
    river_id: Mapped[str | None] = mapped_column(ForeignKey("rivers.id"))
    status: Mapped[str]
    description: Mapped[str]
