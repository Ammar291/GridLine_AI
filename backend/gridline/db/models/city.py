"""City metadata, zones, catchments, geology, soils and the terrain elevation grid (spec §4, §5.1-§5.3).

Column types come from the annotations: ``str``/``int``/``float``/``bool``/``date`` map to portable SQL types,
``X | None`` makes a column nullable, and list/dict annotations map to JSON (JSONB on Postgres) via ``Base``.
"""

import datetime as dt
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from gridline.db.base import Base

if TYPE_CHECKING:
    from gridline.db.models.infrastructure import DrainageChannel


class City(Base):
    __tablename__ = "city"

    id: Mapped[str] = mapped_column(primary_key=True)
    name: Mapped[str]
    region: Mapped[str]
    country: Mapped[str]
    founded_year: Mapped[int]
    area_km2: Mapped[float]
    population_2026: Mapped[int]
    bbox: Mapped[list[int]]
    crs: Mapped[str]
    river_datum_m: Mapped[float]
    gauge_zero_m: Mapped[float]
    as_of_date: Mapped[dt.date]
    administration: Mapped[str]
    disaster_authority: Mapped[str]
    emergency_number: Mapped[str]
    description: Mapped[str]


class GeologicalZone(Base):
    __tablename__ = "geological_zones"

    id: Mapped[str] = mapped_column(primary_key=True)
    name: Mapped[str]
    lithology: Mapped[str]
    description: Mapped[str]
    permeability_class: Mapped[str]
    bearing_capacity_class: Mapped[str]
    hazard_notes: Mapped[str]


class Catchment(Base):
    __tablename__ = "catchments"

    id: Mapped[str] = mapped_column(primary_key=True)
    name: Mapped[str]
    zone_ids: Mapped[list[str]]
    area_km2: Mapped[float]
    outlet_river_id: Mapped[str] = mapped_column(ForeignKey("rivers.id"))
    outlet_description: Mapped[str]
    impervious_pct_2018: Mapped[float]
    impervious_pct_2026: Mapped[float]


class Zone(Base):
    __tablename__ = "zones"

    id: Mapped[str] = mapped_column(primary_key=True)
    name: Mapped[str]
    kind: Mapped[str]
    bbox: Mapped[list[int]]
    slope_deg: Mapped[float]
    soil_type: Mapped[str]
    geological_zone_id: Mapped[str] = mapped_column(ForeignKey("geological_zones.id"))
    catchment_id: Mapped[str] = mapped_column(ForeignKey("catchments.id"))
    # Circular with drainage_channels.upstream/downstream_zone_id: added by ALTER after both tables exist and
    # checked at commit, so the seed may insert zones and channels in either order within one transaction.
    drains_to_channel_id: Mapped[str | None] = mapped_column(
        ForeignKey(
            "drainage_channels.id",
            use_alter=True,
            name="fk_zones_drains_to_channel",
            deferrable=True,
            initially="DEFERRED",
        )
    )
    description: Mapped[str]
    # Computed at seed time from the bbox and gridline.city.terrain.
    area_km2: Mapped[float]
    elevation_min_m: Mapped[float]
    elevation_max_m: Mapped[float]
    elevation_mean_m: Mapped[float]
    svg_path: Mapped[str]

    channel: Mapped["DrainageChannel | None"] = relationship(foreign_keys=[drains_to_channel_id])


class SoilProfile(Base):
    __tablename__ = "soil_profiles"

    id: Mapped[str] = mapped_column(primary_key=True)
    zone_id: Mapped[str] = mapped_column(ForeignKey("zones.id"))
    soil_type: Mapped[str]
    depth_to_bedrock_m: Mapped[float]
    permeability_class: Mapped[str]
    infiltration_rate_mm_h: Mapped[float]
    field_capacity: Mapped[float]
    plasticity_index: Mapped[float]
    shrink_swell: Mapped[str]
    liquefaction_susceptibility: Mapped[str]
    bearing_capacity_kpa: Mapped[float]
    water_table_depth_m: Mapped[float]
    notes: Mapped[str | None]


class ElevationPoint(Base):
    """Terrain grid sample (spec §4): x = 0..12000 × y = 0..9000 every 500 m."""

    __tablename__ = "elevation_points"

    x_m: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    y_m: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    elevation_m: Mapped[float]
