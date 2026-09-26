"""Infrastructure changes, incident front matter, thresholds and document metadata (spec §5.9-§7)."""

import datetime as dt
from typing import Literal

from pydantic import BaseModel, ConfigDict

from gridline.city.schema_common import Located, Record

DocumentKind = Literal["policy", "sop", "report", "permit", "change_log", "profile"]
# The ten knowledge categories of the RAG brief (RAG spec §4). ``kind`` is the document's form, ``category``
# what it is about: every ``report`` is an ``incident_report``, and only reports are.
DocumentCategory = Literal[
    "policy", "sop", "procedure", "incident_report", "infrastructure_report", "engineering_report",
    "construction_safety", "evacuation", "resource_rules", "change_log",
]  # fmt: skip
Hazard = Literal["flood", "flash_flood", "landslide", "cyclone", "urban_fire"]
Impact = Literal[
    "closed", "blocked", "overflowed", "surcharged", "flooded", "damaged", "destroyed", "outage", "failed",
    "opened", "evacuated", "deployed", "saturated",
]  # fmt: skip


class InfrastructureChangeRecord(Record):
    effective_date: dt.date
    kind: str
    zone_id: str
    asset_kind: str
    asset_id: str
    project_id: str | None
    description: str
    metric: str | None
    value_before: float | None
    value_after: float | None
    unit: str | None
    hazard_review_done: bool
    approved_by: str | None
    document_id: str
    related_incident_id: str | None
    notes: str | None = None


class IncidentRecord(Located):
    """A report's ``incident:`` front-matter block: every historical_incidents column but document_id."""

    hazard: Hazard
    title: str
    started_on: dt.date
    ended_on: dt.date
    primary_zone_id: str
    zone_ids: list[str]
    slope_id: str | None
    location_description: str
    rainfall_24h_mm: float | None
    rainfall_72h_mm: float | None
    peak_intensity_mm_h: float | None
    wind_speed_kmh: float | None
    wind_gust_kmh: float | None
    river_stage_m: float | None
    antecedent_conditions: str
    infrastructure_state: str
    severity: int
    severity_label: str
    affected_population: int
    evacuated: int
    deaths: int
    injured: int
    houses_damaged: int
    houses_destroyed: int
    damage_estimate_million: float
    response_summary: str
    outcome_summary: str
    lessons: str


class ImpactRecord(BaseModel):
    """One entry of a report's ``impacts:`` list; the seed assigns the id ``<incident>-<n>``."""

    model_config = ConfigDict(extra="forbid")

    asset_kind: str
    asset_id: str
    impact: Impact
    detail: str
    duration_hours: float | None = None
    depth_m: float | None = None


class PolicyThresholdRecord(Record):
    document_id: str
    section: str
    hazard: str
    metric: str
    band: str
    applies_to: str
    operator: str
    value: float
    unit: str
    note: str | None = None


class DocumentMeta(BaseModel):
    """Front matter of a corpus document (without the report-only ``incident``/``impacts`` blocks)."""

    model_config = ConfigDict(extra="forbid")

    document_id: str
    title: str
    kind: DocumentKind
    category: DocumentCategory
    source: str
    version: str
    effective_date: dt.date
    hazards: list[Hazard]
    zone_ids: list[str]
    supersedes: str | None = None
    summary: str
