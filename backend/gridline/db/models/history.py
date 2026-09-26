"""Disaster history 2012-2026 and infrastructure changes 2018-2026 (spec §5.9-§5.10).

``asset_kind`` + ``asset_id`` on impacts and changes are polymorphic references resolved by tests, not FKs.
"""

import datetime as dt

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from gridline.db.base import Base


class HistoricalIncident(Base):
    """A past disaster; the source of truth is the ``incident:`` front matter of its report document."""

    __tablename__ = "historical_incidents"

    id: Mapped[str] = mapped_column(primary_key=True)
    hazard: Mapped[str]
    title: Mapped[str]
    started_on: Mapped[dt.date]
    ended_on: Mapped[dt.date]
    primary_zone_id: Mapped[str] = mapped_column(ForeignKey("zones.id"))
    zone_ids: Mapped[list[str]]
    slope_id: Mapped[str | None] = mapped_column(ForeignKey("slopes.id"))
    location_description: Mapped[str]
    x_m: Mapped[int]
    y_m: Mapped[int]
    elevation_m: Mapped[float]
    rainfall_24h_mm: Mapped[float | None]
    rainfall_72h_mm: Mapped[float | None]
    peak_intensity_mm_h: Mapped[float | None]
    wind_speed_kmh: Mapped[float | None]
    wind_gust_kmh: Mapped[float | None]
    river_stage_m: Mapped[float | None]
    antecedent_conditions: Mapped[str]
    infrastructure_state: Mapped[str]
    severity: Mapped[int]
    severity_label: Mapped[str]
    affected_population: Mapped[int]
    evacuated: Mapped[int]
    deaths: Mapped[int]
    injured: Mapped[int]
    houses_damaged: Mapped[int]
    houses_destroyed: Mapped[int]
    damage_estimate_million: Mapped[float]
    response_summary: Mapped[str]
    outcome_summary: Mapped[str]
    lessons: Mapped[str]
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"))

    impacts: Mapped[list["HistoricalIncidentImpact"]] = relationship(
        back_populates="incident", lazy="selectin", order_by="HistoricalIncidentImpact.id"
    )


class HistoricalIncidentImpact(Base):
    """One impact of an incident on an asset; id is ``"<incident>-<n>"``."""

    __tablename__ = "historical_incident_impacts"

    id: Mapped[str] = mapped_column(primary_key=True)
    incident_id: Mapped[str] = mapped_column(ForeignKey("historical_incidents.id"))
    asset_kind: Mapped[str]
    asset_id: Mapped[str]
    impact: Mapped[str]
    detail: Mapped[str]
    duration_hours: Mapped[float | None]
    depth_m: Mapped[float | None]

    incident: Mapped[HistoricalIncident] = relationship(back_populates="impacts")


class InfrastructureChange(Base):
    """A dated change to an asset, documented in ``changelog-infra-2018-2026``."""

    __tablename__ = "infrastructure_changes"

    id: Mapped[str] = mapped_column(primary_key=True)
    effective_date: Mapped[dt.date]
    kind: Mapped[str]
    zone_id: Mapped[str] = mapped_column(ForeignKey("zones.id"))
    asset_kind: Mapped[str]
    asset_id: Mapped[str]
    project_id: Mapped[str | None] = mapped_column(ForeignKey("projects.id"))
    description: Mapped[str]
    metric: Mapped[str | None]
    value_before: Mapped[float | None]
    value_after: Mapped[float | None]
    unit: Mapped[str | None]
    hazard_review_done: Mapped[bool]
    approved_by: Mapped[str | None]
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"))
    related_incident_id: Mapped[str | None] = mapped_column(ForeignKey("historical_incidents.id"))
    notes: Mapped[str | None]
