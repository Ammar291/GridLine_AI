"""Cross-reference and plausibility checks behind ``gridline.city.dataset.validate_references``.

Each check returns problem strings that name the table, record id and field, so a bad YAML value is found
before the seed writes anything.
"""

from collections import defaultdict
from collections.abc import Iterable, Mapping
from typing import TYPE_CHECKING, Any

from gridline.city.references import ASSET_KINDS, CROSSES_KINDS, IN_ZONE, REFERENCES
from gridline.city.terrain import river_y

if TYPE_CHECKING:
    from gridline.city.dataset import CityData
    from gridline.db.seed.corpus import ParsedDocument

POPULATION_TOLERANCE = 0.10
STATS_YEARS = frozenset(range(2018, 2027))
RIVER_PATH_TOLERANCE_M = 1.0


class ReferenceIndex:
    """Known ids per table: the city YAML tables plus ``documents`` and ``historical_incidents`` (corpus)."""

    def __init__(self, data: "CityData", docs: "list[ParsedDocument]") -> None:
        self.ids: dict[str, set[str]] = {name: {r.id for r in rows} for name, rows in data.tables()}
        self.ids["documents"] = {d.meta.document_id for d in docs}
        self.ids["historical_incidents"] = {d.incident.id for d in docs if d.incident is not None}

    def missing(self, table: str, value: str) -> bool:
        return value not in self.ids.get(table, set())


def _values(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v) for v in value]  # pyright: ignore[reportUnknownVariableType, reportUnknownArgumentType]
    return [str(value)]


def _check_duplicates(data: "CityData") -> list[str]:
    problems: list[str] = []
    for table, rows in data.tables():
        seen: set[str] = set()
        for row in rows:
            if row.id in seen:
                problems.append(f"{table}: duplicate id {row.id!r}")
            seen.add(row.id)
    return problems


def _check_references(data: "CityData", index: ReferenceIndex) -> list[str]:
    tables = dict(data.tables())
    problems: list[str] = []
    for table, field, target in REFERENCES:
        for row in tables[table]:
            for value in _values(getattr(row, field)):
                if index.missing(target, value):
                    problems.append(f"{table} {row.id}: {field} references unknown {target} id {value!r}")
    return problems


def _check_polymorphic(label: str, field: str, kind: str, value: str, kinds: Mapping[str, str],
                       index: ReferenceIndex) -> list[str]:  # fmt: skip
    table = kinds.get(kind)
    if table is None:
        return [f"{label}: unknown {field} kind {kind!r}"]
    if index.missing(table, value):
        return [f"{label}: {field} references unknown {table} id {value!r}"]
    return []


def _check_assets(data: "CityData", docs: "list[ParsedDocument]", index: ReferenceIndex) -> list[str]:
    problems: list[str] = []
    for ci in data.critical_infrastructure:
        label = f"critical_infrastructure {ci.id}"
        problems += _check_polymorphic(label, "asset_kind", ci.asset_kind, ci.asset_id, ASSET_KINDS, index)
    for ch in data.infrastructure_changes:
        label = f"infrastructure_changes {ch.id}"
        problems += _check_polymorphic(label, "asset_kind", ch.asset_kind, ch.asset_id, ASSET_KINDS, index)
    for dc in data.drainage_channels:
        if dc.limiting_structure_kind is not None or dc.limiting_structure_id is not None:
            label = f"drainage_channels {dc.id}"
            kind, value = dc.limiting_structure_kind or "", dc.limiting_structure_id or ""
            problems += _check_polymorphic(label, "limiting_structure", kind, value, ASSET_KINDS, index)
    for br in data.bridges:
        problems += _check_polymorphic(
            f"bridges {br.id}", "crosses_kind", br.crosses_kind, br.crosses_id, CROSSES_KINDS, index
        )
    for doc in docs:
        if doc.incident is None:
            continue
        for n, imp in enumerate(doc.impacts, start=1):
            label = f"{doc.meta.document_id} impact {doc.incident.id}-{n}"
            problems += _check_polymorphic(
                label, "asset_kind", imp.asset_kind, imp.asset_id, ASSET_KINDS, index
            )
    return problems


def _check_documents(data: "CityData", docs: "list[ParsedDocument]", index: ReferenceIndex) -> list[str]:
    problems: list[str] = []
    seen: set[str] = set()
    for doc in docs:
        doc_id = doc.meta.document_id
        if doc_id in seen:
            problems.append(f"documents: duplicate id {doc_id!r}")
        seen.add(doc_id)
        problems += [
            f"documents {doc_id}: zone_ids references unknown zones id {z!r}"
            for z in doc.meta.zone_ids
            if index.missing("zones", z)
        ]
        inc = doc.incident
        if inc is None:
            continue
        expected = "HI-" + doc_id.removeprefix("rep-").upper()
        if not doc_id.startswith("rep-") or inc.id != expected:
            problems.append(
                f"documents {doc_id}: incident id {inc.id!r} does not match report id (want {expected})"
            )
        for field, table, values in (
            ("primary_zone_id", "zones", [inc.primary_zone_id]),
            ("zone_ids", "zones", inc.zone_ids),
            ("slope_id", "slopes", _values(inc.slope_id)),
        ):
            problems += [
                f"historical_incidents {inc.id}: {field} references unknown {table} id {v!r}"
                for v in values
                if index.missing(table, v)
            ]
    return problems


def _inside(bbox: list[int], x: int, y: int) -> bool:
    x0, y0, x1, y1 = bbox
    return x0 <= x <= x1 and y0 <= y <= y1


def _check_geometry(data: "CityData", docs: "list[ParsedDocument]") -> list[str]:
    bboxes = {z.id: z.bbox for z in data.zones}
    tables = dict(data.tables())
    problems: list[str] = []
    for table, field in IN_ZONE:
        for row in tables[table]:
            zone_id = getattr(row, field)
            x, y = int(getattr(row, "x_m")), int(getattr(row, "y_m"))  # noqa: B009 - Record has no x_m
            if zone_id in bboxes and not _inside(bboxes[zone_id], x, y):
                problems.append(f"{table} {row.id}: ({x}, {y}) lies outside the bbox of {field} {zone_id}")
    for hill in data.hills:
        if not any(
            _inside(bboxes[z], hill.summit_x_m, hill.summit_y_m) for z in hill.zone_ids if z in bboxes
        ):
            problems.append(f"hills {hill.id}: summit lies outside the bbox of every zone in zone_ids")
    for doc in docs:
        inc = doc.incident
        if inc is not None and not any(
            _inside(bboxes[z], inc.x_m, inc.y_m) for z in inc.zone_ids if z in bboxes
        ):
            problems.append(
                f"historical_incidents {inc.id}: ({inc.x_m}, {inc.y_m}) outside the bbox of its zones"
            )
    for river in data.rivers:
        if river.id != "R-1":
            continue
        for x, y in river.path:
            if abs(y - river_y(x)) > RIVER_PATH_TOLERANCE_M:
                problems.append(f"rivers R-1: path vertex ({x}, {y}) is off the river_y centreline")
    return problems


def _check_population(data: "CityData") -> list[str]:
    problems: list[str] = []
    years: dict[str, set[int]] = defaultdict(set)
    pop_2026: dict[str, int] = {}
    for stats in data.zone_yearly_stats:
        years[stats.zone_id].add(stats.year)
        if stats.year == 2026:
            pop_2026[stats.zone_id] = stats.population
    residents: dict[str, int] = defaultdict(int)
    for area in data.residential_areas:
        residents[area.zone_id] += area.population
    for zone in data.zones:
        if frozenset(years[zone.id]) != STATS_YEARS:
            problems.append(f"zone_yearly_stats {zone.id}: years {sorted(years[zone.id])} are not 2018..2026")
        target = pop_2026.get(zone.id)
        if target and abs(residents[zone.id] - target) > POPULATION_TOLERANCE * target:
            problems.append(
                f"residential_areas {zone.id}: population {residents[zone.id]} is not within 10 % of "
                f"the zone's 2026 population {target}"
            )
    return problems


def _section_texts(docs: Iterable["ParsedDocument"]) -> dict[tuple[str, str], str]:
    return {(d.meta.document_id, s.section): s.text for d in docs for s in d.sections}


def _check_texts(data: "CityData", docs: "list[ParsedDocument]") -> list[str]:
    texts = _section_texts(docs)
    problems: list[str] = []
    for pt in data.policy_thresholds:
        text = texts.get((pt.document_id, pt.section))
        if text is None:
            problems.append(
                f"policy_thresholds {pt.id}: section {pt.document_id}#{pt.section} does not exist"
            )
        elif f"{pt.value:g}" not in text:
            problems.append(
                f"policy_thresholds {pt.id}: value {pt.value:g} does not appear in "
                f"{pt.document_id}#{pt.section}"
            )
    for ch in data.infrastructure_changes:
        log = " ".join(t for (doc_id, _), t in texts.items() if doc_id == ch.document_id)
        if log and ch.id not in log:
            problems.append(f"infrastructure_changes {ch.id}: not mentioned in change log {ch.document_id}")
    return problems


def check_all(data: "CityData", docs: "list[ParsedDocument]") -> list[str]:
    index = ReferenceIndex(data, docs)
    return [
        *_check_duplicates(data),
        *_check_references(data, index),
        *_check_assets(data, docs, index),
        *_check_documents(data, docs, index),
        *_check_geometry(data, docs),
        *_check_population(data),
        *_check_texts(data, docs),
    ]
