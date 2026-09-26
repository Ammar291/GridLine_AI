"""Drainage channels, pumps, roads, bridges, tunnels and dams (spec §5.4-§5.6)."""

import datetime as dt
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from gridline.db.base import Base

if TYPE_CHECKING:
    from gridline.db.models.city import Zone


class DrainageChannel(Base):
    __tablename__ = "drainage_channels"

    id: Mapped[str] = mapped_column(primary_key=True)
    name: Mapped[str]
    kind: Mapped[str]
    catchment_id: Mapped[str] = mapped_column(ForeignKey("catchments.id"))
    upstream_zone_id: Mapped[str] = mapped_column(ForeignKey("zones.id"))
    downstream_zone_id: Mapped[str] = mapped_column(ForeignKey("zones.id"))
    x_m: Mapped[int]
    y_m: Mapped[int]
    elevation_m: Mapped[float]
    length_m: Mapped[float]
    year_built: Mapped[int]
    year_relined: Mapped[int | None]
    design_capacity_m3s: Mapped[float]
    current_capacity_m3s: Mapped[float]
    blocked_fraction: Mapped[float]
    condition: Mapped[str]
    last_desilted: Mapped[dt.date | None]
    outfall_river_id: Mapped[str | None] = mapped_column(ForeignKey("rivers.id"))
    outfall_channel_id: Mapped[str | None] = mapped_column(ForeignKey("drainage_channels.id"))
    # Polymorphic (bridge|tunnel|dam): resolved by tests, not by an FK.
    limiting_structure_id: Mapped[str | None]
    limiting_structure_kind: Mapped[str | None]
    gate_closes_at_river_stage_m: Mapped[float | None]
    description: Mapped[str]

    downstream_zone: Mapped["Zone"] = relationship(foreign_keys=[downstream_zone_id])


class PumpUnit(Base):
    __tablename__ = "pump_units"

    id: Mapped[str] = mapped_column(primary_key=True)
    name: Mapped[str]
    kind: Mapped[str]
    capacity_m3s: Mapped[float]
    status: Mapped[str]
    location_zone_id: Mapped[str] = mapped_column(ForeignKey("zones.id"))
    channel_id: Mapped[str | None] = mapped_column(ForeignKey("drainage_channels.id"))
    x_m: Mapped[int]
    y_m: Mapped[int]
    elevation_m: Mapped[float]
    year_installed: Mapped[int]
    notes: Mapped[str | None]


class Road(Base):
    """A road; ``path`` is a list of ``[x_m, y_m]`` vertices and may cross zones other than ``zone_id``."""

    __tablename__ = "roads"

    id: Mapped[str] = mapped_column(primary_key=True)
    name: Mapped[str]
    kind: Mapped[str]
    zone_id: Mapped[str] = mapped_column(ForeignKey("zones.id"))
    from_zone_id: Mapped[str] = mapped_column(ForeignKey("zones.id"))
    to_zone_id: Mapped[str] = mapped_column(ForeignKey("zones.id"))
    length_m: Mapped[float]
    lanes: Mapped[int]
    width_m: Mapped[float]
    surface: Mapped[str]
    year_built: Mapped[int]
    last_major_work_year: Mapped[int | None]
    status: Mapped[str]
    is_evacuation_route: Mapped[bool]
    is_only_access: Mapped[bool]
    floods_at_river_stage_m: Mapped[float | None]
    path: Mapped[list[list[int]]]
    min_elevation_m: Mapped[float]  # computed over path vertices
    description: Mapped[str]
    # Live state written by close_road / reopen_road; NULL in the seed.
    closure_reason: Mapped[str | None]
    closed_at: Mapped[dt.datetime | None]
    incident_id: Mapped[str | None] = mapped_column(ForeignKey("incidents.id"))


class Bridge(Base):
    __tablename__ = "bridges"

    id: Mapped[str] = mapped_column(primary_key=True)
    name: Mapped[str]
    road_id: Mapped[str] = mapped_column(ForeignKey("roads.id"))
    crosses_kind: Mapped[str]  # river|channel; polymorphic with crosses_id
    crosses_id: Mapped[str]
    zone_id: Mapped[str] = mapped_column(ForeignKey("zones.id"))
    x_m: Mapped[int]
    y_m: Mapped[int]
    elevation_m: Mapped[float]
    year_built: Mapped[int]
    year_rebuilt: Mapped[int | None]
    length_m: Mapped[float]
    load_rating_t: Mapped[float]
    condition: Mapped[str]
    scour_risk: Mapped[str]
    clearance_m: Mapped[float | None]
    waterway_area_m2: Mapped[float | None]
    closes_at_river_stage_m: Mapped[float | None]
    last_inspection: Mapped[dt.date | None]
    description: Mapped[str]


class Tunnel(Base):
    __tablename__ = "tunnels"

    id: Mapped[str] = mapped_column(primary_key=True)
    name: Mapped[str]
    kind: Mapped[str]
    road_id: Mapped[str | None] = mapped_column(ForeignKey("roads.id"))
    zone_id: Mapped[str] = mapped_column(ForeignKey("zones.id"))
    x_m: Mapped[int]
    y_m: Mapped[int]
    elevation_m: Mapped[float]
    length_m: Mapped[float]
    year_built: Mapped[int]
    depth_below_grade_m: Mapped[float]
    condition: Mapped[str]
    sump_pump_ids: Mapped[list[str]]
    floods_when: Mapped[str | None]
    low_point_elevation_m: Mapped[float]  # computed: terrain - depth_below_grade_m
    description: Mapped[str]


class Dam(Base):
    __tablename__ = "dams"

    id: Mapped[str] = mapped_column(primary_key=True)
    name: Mapped[str]
    kind: Mapped[str]
    river_id: Mapped[str] = mapped_column(ForeignKey("rivers.id"))
    channel_id: Mapped[str | None] = mapped_column(ForeignKey("drainage_channels.id"))
    zone_id: Mapped[str | None] = mapped_column(ForeignKey("zones.id"))
    x_m: Mapped[int]
    y_m: Mapped[int]
    elevation_m: Mapped[float]
    year_built: Mapped[int]
    height_m: Mapped[float]
    storage_mcm: Mapped[float]
    spillway_capacity_m3s: Mapped[float]
    gates: Mapped[int]
    condition: Mapped[str]
    silted_pct: Mapped[float]
    closes_at_river_stage_m: Mapped[float | None]
    downstream_zone_ids: Mapped[list[str]]
    operator: Mapped[str | None]
    description: Mapped[str]
