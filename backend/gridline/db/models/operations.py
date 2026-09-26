"""Operations tables written only by the city operations tools (``gridline/tools``), never by the seed.

``actions`` is the append-only audit trail: one row per attempted action, rejected and failed ones included.
Its ``incident_id`` is a plain string (no FK) so an attempt naming an unknown incident is recorded too, and
``idempotency_key`` is only filled for executed/unchanged rows so a failed attempt never blocks a retry.
Status and kind columns hold the Literal values of ``gridline.tools.vocab``.
"""

import datetime as dt
from typing import Any

from sqlalchemy import ForeignKey, Index, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from gridline.db.base import Base, JSONType


class Incident(Base):
    """A live hazard episode in one zone (``historical_incidents`` holds past ones); one open per hazard."""

    __tablename__ = "incidents"
    __table_args__ = (
        Index(
            "uq_incidents_open_zone_hazard",
            "zone_id",
            "hazard",
            unique=True,
            postgresql_where=text("status = 'open'"),
        ),
    )

    id: Mapped[str] = mapped_column(primary_key=True)
    zone_id: Mapped[str] = mapped_column(ForeignKey("zones.id"))
    hazard: Mapped[str]
    band: Mapped[str]
    status: Mapped[str]
    title: Mapped[str]
    summary: Mapped[str] = mapped_column(Text)
    opened_at: Mapped[dt.datetime]
    updated_at: Mapped[dt.datetime]
    closed_at: Mapped[dt.datetime | None]


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[str] = mapped_column(primary_key=True)
    zone_id: Mapped[str] = mapped_column(ForeignKey("zones.id"))
    level: Mapped[str]
    message: Mapped[str] = mapped_column(Text)
    incident_id: Mapped[str | None] = mapped_column(ForeignKey("incidents.id"))
    issued_at: Mapped[dt.datetime]


class EvacuationOrder(Base):
    """At most one ``active`` order per zone; escalation updates it in place."""

    __tablename__ = "evacuation_orders"
    __table_args__ = (
        Index(
            "uq_evacuation_orders_active_zone",
            "zone_id",
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
    )

    id: Mapped[str] = mapped_column(primary_key=True)
    zone_id: Mapped[str] = mapped_column(ForeignKey("zones.id"))
    level: Mapped[str]
    reason: Mapped[str] = mapped_column(Text)
    shelter_id: Mapped[str | None] = mapped_column(ForeignKey("shelters.id"))
    incident_id: Mapped[str | None] = mapped_column(ForeignKey("incidents.id"))
    status: Mapped[str]
    issued_at: Mapped[dt.datetime]
    updated_at: Mapped[dt.datetime]


class ConstructionRestriction(Base):
    __tablename__ = "construction_restrictions"

    id: Mapped[str] = mapped_column(primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"))
    kind: Mapped[str]
    max_depth_m: Mapped[float | None]
    reason: Mapped[str] = mapped_column(Text)
    incident_id: Mapped[str | None] = mapped_column(ForeignKey("incidents.id"))
    status: Mapped[str]
    issued_at: Mapped[dt.datetime]


class Task(Base):
    """Inspection, monitoring, evacuation and emergency work; ``target_kind`` + ``target_id`` has no FK."""

    __tablename__ = "tasks"

    id: Mapped[str] = mapped_column(primary_key=True)
    kind: Mapped[str]
    title: Mapped[str]
    description: Mapped[str] = mapped_column(Text)
    priority: Mapped[str]
    status: Mapped[str]
    zone_id: Mapped[str | None] = mapped_column(ForeignKey("zones.id"))
    target_kind: Mapped[str | None]
    target_id: Mapped[str | None]
    metric: Mapped[str | None]
    interval_minutes: Mapped[int | None]
    assigned_crew_id: Mapped[str | None] = mapped_column(ForeignKey("crews.id"))
    incident_id: Mapped[str | None] = mapped_column(ForeignKey("incidents.id"))
    evacuation_order_id: Mapped[str | None] = mapped_column(ForeignKey("evacuation_orders.id"))
    created_by: Mapped[str]
    created_at: Mapped[dt.datetime]
    completed_at: Mapped[dt.datetime | None]


class BedReservation(Base):
    """Beds of one type held for an incident; ``hospital_beds.reserved`` changes in the same transaction."""

    __tablename__ = "bed_reservations"

    id: Mapped[str] = mapped_column(primary_key=True)
    hospital_id: Mapped[str] = mapped_column(ForeignKey("hospitals.id"))
    hospital_bed_id: Mapped[str] = mapped_column(ForeignKey("hospital_beds.id"))
    bed_type: Mapped[str]
    incident_id: Mapped[str] = mapped_column(ForeignKey("incidents.id"))
    beds: Mapped[int]
    status: Mapped[str]
    created_at: Mapped[dt.datetime]


class Action(Base):
    """Audit row of one tool call: input, before/after snapshots, affected entities and verification."""

    __tablename__ = "actions"

    id: Mapped[str] = mapped_column(primary_key=True)
    tool: Mapped[str]
    status: Mapped[str]
    idempotency_key: Mapped[str | None] = mapped_column(unique=True)
    actor: Mapped[str]
    approval_id: Mapped[str | None]
    run_id: Mapped[str | None]
    incident_id: Mapped[str | None] = mapped_column(index=True)
    input_json: Mapped[dict[str, Any]]
    before_json: Mapped[dict[str, Any]]
    after_json: Mapped[dict[str, Any]]
    affected_entities_json: Mapped[list[dict[str, str]]] = mapped_column(JSONType)
    message: Mapped[str] = mapped_column(Text)
    sim_time: Mapped[dt.datetime | None]
    executed_at: Mapped[dt.datetime]
    verification_json: Mapped[dict[str, Any] | None]
