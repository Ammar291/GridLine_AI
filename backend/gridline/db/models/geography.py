"""Rivers, hills, slopes and flood plains (spec §5.3)."""

import datetime as dt

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from gridline.db.base import Base


class River(Base):
    """A river, stream or lake. ``path`` is a list of ``[x_m, y_m]`` vertices."""

    __tablename__ = "rivers"

    id: Mapped[str] = mapped_column(primary_key=True)
    name: Mapped[str]
    kind: Mapped[str]
    description: Mapped[str]
    length_km: Mapped[float | None]
    ordinary_flow_m3s: Mapped[float | None]
    bankfull_flow_m3s: Mapped[float | None]
    # Plain string, no FK: sensors.river_id already points here and a back-reference would form a cycle.
    gauge_sensor_id: Mapped[str | None]
    gauge_zero_m: Mapped[float | None]
    flood_stage_m: Mapped[float | None]
    danger_stage_m: Mapped[float | None]
    record_stage_m: Mapped[float | None]
    record_date: Mapped[dt.date | None]
    surface_level_m: Mapped[float | None]
    path: Mapped[list[list[int]]]


class Hill(Base):
    __tablename__ = "hills"

    id: Mapped[str] = mapped_column(primary_key=True)
    name: Mapped[str]
    summit_x_m: Mapped[int]
    summit_y_m: Mapped[int]
    summit_elevation_m: Mapped[float]  # computed from terrain
    zone_ids: Mapped[list[str]]
    geological_zone_id: Mapped[str] = mapped_column(ForeignKey("geological_zones.id"))
    description: Mapped[str]


class Slope(Base):
    __tablename__ = "slopes"

    id: Mapped[str] = mapped_column(primary_key=True)
    name: Mapped[str]
    zone_id: Mapped[str] = mapped_column(ForeignKey("zones.id"))
    hill_id: Mapped[str] = mapped_column(ForeignKey("hills.id"))
    x_m: Mapped[int]
    y_m: Mapped[int]
    elevation_m: Mapped[float]
    mean_angle_deg: Mapped[float]
    max_angle_deg: Mapped[float]
    aspect: Mapped[str]
    length_m: Mapped[float]
    height_m: Mapped[float]
    soil_depth_m: Mapped[float]
    vegetation_cover_pct: Mapped[float]
    stability_class: Mapped[str]
    retaining_structures: Mapped[str | None]
    toe_channel_id: Mapped[str | None] = mapped_column(ForeignKey("drainage_channels.id"))
    toe_distance_to_channel_m: Mapped[float | None]
    has_active_construction: Mapped[bool]
    description: Mapped[str]


class FloodPlain(Base):
    __tablename__ = "flood_plains"

    id: Mapped[str] = mapped_column(primary_key=True)
    name: Mapped[str]
    river_id: Mapped[str] = mapped_column(ForeignKey("rivers.id"))
    zone_ids: Mapped[list[str]]
    area_km2: Mapped[float]
    return_period_years: Mapped[int]
    typical_depth_m: Mapped[float]
    protection_type: Mapped[str | None]
    protection_crest_m: Mapped[float | None]
    protection_year_built: Mapped[int | None]
    protection_year_raised: Mapped[int | None]
    residents_2018: Mapped[int]
    residents_2026: Mapped[int]
    description: Mapped[str]
