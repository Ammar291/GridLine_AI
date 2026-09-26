"""Zone population by year, residential areas and schools (spec §5.8)."""

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from gridline.db.base import Base


class ZoneYearlyStats(Base):
    """One row per zone and year 2018..2026; id is ``"<zone>-<year>"`` (e.g. ``Z-NC-2021``)."""

    __tablename__ = "zone_yearly_stats"
    __table_args__ = (UniqueConstraint("zone_id", "year"),)

    id: Mapped[str] = mapped_column(primary_key=True)
    zone_id: Mapped[str] = mapped_column(ForeignKey("zones.id"))
    year: Mapped[int]
    population: Mapped[int]
    households: Mapped[int]
    children_under_5: Mapped[int]
    elderly_over_65: Mapped[int]
    persons_with_disability: Mapped[int]
    informal_settlement_population: Mapped[int]
    low_income_households: Mapped[int]
    impermeable_surface_pct: Mapped[float]
    built_up_pct: Mapped[float]
    green_cover_pct: Mapped[float]
    avg_building_storeys: Mapped[float]
    density_per_km2: Mapped[float]  # computed: population / zone area


class ResidentialArea(Base):
    __tablename__ = "residential_areas"

    id: Mapped[str] = mapped_column(primary_key=True)
    name: Mapped[str]
    zone_id: Mapped[str] = mapped_column(ForeignKey("zones.id"))
    kind: Mapped[str]
    households: Mapped[int]
    population: Mapped[int]
    year_established: Mapped[int | None]
    storeys: Mapped[int | None]
    building_quality: Mapped[str]
    slope_id: Mapped[str | None] = mapped_column(ForeignKey("slopes.id"))
    flood_plain_id: Mapped[str | None] = mapped_column(ForeignKey("flood_plains.id"))
    nearest_channel_id: Mapped[str | None] = mapped_column(ForeignKey("drainage_channels.id"))
    distance_to_channel_m: Mapped[float | None]
    x_m: Mapped[int]
    y_m: Mapped[int]
    elevation_m: Mapped[float]
    description: Mapped[str]


class School(Base):
    __tablename__ = "schools"

    id: Mapped[str] = mapped_column(primary_key=True)
    name: Mapped[str]
    zone_id: Mapped[str] = mapped_column(ForeignKey("zones.id"))
    level: Mapped[str]
    students: Mapped[int]
    staff: Mapped[int]
    floors: Mapped[int]
    # Circular with shelters.school_id: added by ALTER and checked at commit, so insert order is free.
    shelter_id: Mapped[str | None] = mapped_column(
        ForeignKey(
            "shelters.id", use_alter=True, name="fk_schools_shelter", deferrable=True, initially="DEFERRED"
        )
    )
    flood_plain_id: Mapped[str | None] = mapped_column(ForeignKey("flood_plains.id"))
    slope_id: Mapped[str | None] = mapped_column(ForeignKey("slopes.id"))
    x_m: Mapped[int]
    y_m: Mapped[int]
    elevation_m: Mapped[float]
    description: Mapped[str]
