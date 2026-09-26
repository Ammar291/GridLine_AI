"""Build ORM rows from validated records, filling every computed column from ``gridline.city.terrain``.

Computed columns (spec §4-§5): ``elevation_m`` of located records, zone ``area_km2`` / elevation range /
``svg_path``, road ``min_elevation_m``, tunnel ``low_point_elevation_m``, hill ``summit_elevation_m``, yearly
``density_per_km2`` and the ``elevation_points`` grid.
"""

from statistics import fmean
from typing import Any

from pydantic import BaseModel

from gridline.city.schema_city import HillRecord, ZoneRecord
from gridline.city.schema_common import Located
from gridline.city.schema_infra import RoadRecord, TunnelRecord
from gridline.city.schema_people import ZoneYearlyStatsRecord
from gridline.city.terrain import elevation_m
from gridline.db.base import Base
from gridline.db.models import (
    Document,
    DocumentSection,
    ElevationPoint,
    Hill,
    HistoricalIncident,
    HistoricalIncidentImpact,
    Road,
    Tunnel,
    Zone,
    ZoneYearlyStats,
)
from gridline.db.seed.corpus import ParsedDocument

Grid = list[tuple[int, int, float]]


def plain[M: Base](model: type[M], record: BaseModel, **extra: Any) -> M:
    """A row whose columns are exactly the record's fields plus ``extra``."""
    return model(**record.model_dump(), **extra)


def located[M: Base](model: type[M], record: Located, **extra: Any) -> M:
    """A row for a located record, with ``elevation_m`` computed from the terrain."""
    return plain(model, record, elevation_m=elevation_m(record.x_m, record.y_m), **extra)


def zone_area_km2(bbox: list[int]) -> float:
    x0, y0, x1, y1 = bbox
    return (x1 - x0) * (y1 - y0) / 1e6


def zone_row(record: ZoneRecord, grid: Grid) -> Zone:
    x0, y0, x1, y1 = record.bbox
    inside = [z for x, y, z in grid if x0 <= x <= x1 and y0 <= y <= y1]
    if not inside:
        raise ValueError(f"zones {record.id}: bbox contains no elevation grid point")
    return plain(
        Zone,
        record,
        area_km2=zone_area_km2(record.bbox),
        elevation_min_m=min(inside),
        elevation_max_m=max(inside),
        elevation_mean_m=round(fmean(inside), 1),
        svg_path=f"M {x0} {y0} H {x1} V {y1} H {x0} Z",
    )


def road_row(record: RoadRecord) -> Road:
    return plain(Road, record, min_elevation_m=min(elevation_m(x, y) for x, y in record.path))


def tunnel_row(record: TunnelRecord) -> Tunnel:
    low_point = round(elevation_m(record.x_m, record.y_m) - record.depth_below_grade_m, 1)
    return located(Tunnel, record, low_point_elevation_m=low_point)


def hill_row(record: HillRecord) -> Hill:
    return plain(Hill, record, summit_elevation_m=elevation_m(record.summit_x_m, record.summit_y_m))


def yearly_stats_row(record: ZoneYearlyStatsRecord, zone_area: float) -> ZoneYearlyStats:
    return plain(ZoneYearlyStats, record, density_per_km2=float(round(record.population / zone_area)))


def elevation_rows(grid: Grid) -> list[ElevationPoint]:
    return [ElevationPoint(x_m=x, y_m=y, elevation_m=z) for x, y, z in grid]


def document_row(doc: ParsedDocument) -> Document:
    meta = doc.meta
    return Document(
        id=meta.document_id,
        title=meta.title,
        kind=meta.kind,
        source=meta.source,
        source_path=doc.source_path,
        date=meta.effective_date,
        version=meta.version,
        effective_date=meta.effective_date,
        supersedes=meta.supersedes,
        summary=meta.summary,
        zone_ids=list(meta.zone_ids),
        hazards=list(meta.hazards),
        content_hash="",  # filled by RAG ingestion
        embedding_model="",
        metadata_={},
    )


def section_rows(doc: ParsedDocument) -> list[DocumentSection]:
    doc_id = doc.meta.document_id
    return [
        DocumentSection(id=f"{doc_id}#{s.section}", document_id=doc_id, **s.model_dump())
        for s in doc.sections
    ]


def incident_row(doc: ParsedDocument) -> HistoricalIncident | None:
    inc = doc.incident
    if inc is None:
        return None
    return located(HistoricalIncident, inc, document_id=doc.meta.document_id)


def impact_rows(doc: ParsedDocument) -> list[HistoricalIncidentImpact]:
    if doc.incident is None:
        return []
    incident_id = doc.incident.id
    return [
        plain(HistoricalIncidentImpact, impact, id=f"{incident_id}-{n}", incident_id=incident_id)
        for n, impact in enumerate(doc.impacts, start=1)
    ]
