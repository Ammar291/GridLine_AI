"""Pure-Python consistency of the YAML dataset and corpus (no database)."""

from pathlib import Path

import pytest

from gridline.city.dataset import CityData, load_city_data, validate_references
from gridline.db.seed.corpus import ParsedDocument, load_corpus

DATA = Path(__file__).resolve().parents[1] / "data"


@pytest.fixture
def data() -> CityData:
    return load_city_data(DATA)


@pytest.fixture(scope="module")
def docs() -> list[ParsedDocument]:
    return load_corpus(DATA / "corpus")


def test_dataset_loads_with_expected_counts(data: CityData) -> None:
    assert data.city.id == "nandipur"
    assert len(data.zones) == 10 and len(data.drainage_channels) == 9 and len(data.roads) == 14
    assert (
        len(data.shelters) == 8
        and len(data.zone_yearly_stats) == 90
        and len(data.infrastructure_changes) == 29
    )
    assert len(data.residential_areas) == 22 and len(data.schools) == 16 and len(data.policy_thresholds) == 25


def test_dataset_is_internally_consistent(data: CityData, docs: list[ParsedDocument]) -> None:
    assert validate_references(data, docs) == []


def test_validate_references_reports_bad_id(data: CityData, docs: list[ParsedDocument]) -> None:
    data.shelters[0].school_id = "SC-99"
    problems = validate_references(data, docs)
    assert any("SC-99" in p and data.shelters[0].id in p and "school_id" in p for p in problems)


def test_bad_polymorphic_asset_reported(data: CityData, docs: list[ParsedDocument]) -> None:
    data.critical_infrastructure[0].asset_id = "H-99"
    data.infrastructure_changes[0].asset_kind = "spaceport"
    problems = validate_references(data, docs)
    assert any("H-99" in p for p in problems)
    assert any("spaceport" in p and data.infrastructure_changes[0].id in p for p in problems)


def test_asset_outside_zone_bbox_reported(data: CityData, docs: list[ParsedDocument]) -> None:
    data.hospitals[0].x_m = 11900
    problems = validate_references(data, docs)
    assert any(data.hospitals[0].id in p and "bbox" in p for p in problems)


def test_duplicate_id_reported(data: CityData, docs: list[ParsedDocument]) -> None:
    data.crews[1].id = data.crews[0].id
    assert any("duplicate" in p and data.crews[0].id in p for p in validate_references(data, docs))


def test_river_path_off_centreline_reported(data: CityData, docs: list[ParsedDocument]) -> None:
    r1 = next(r for r in data.rivers if r.id == "R-1")
    r1.path[3] = [r1.path[3][0], r1.path[3][1] + 50]
    assert any("R-1" in p and "river_y" in p for p in validate_references(data, docs))


def test_residential_population_mismatch_reported(data: CityData, docs: list[ParsedDocument]) -> None:
    data.residential_areas[0].population += 20000
    zone = data.residential_areas[0].zone_id
    assert any(zone in p and "population" in p for p in validate_references(data, docs))


def test_missing_yearly_stats_reported(data: CityData, docs: list[ParsedDocument]) -> None:
    removed = data.zone_yearly_stats.pop()
    assert any(removed.zone_id in p and "years" in p for p in validate_references(data, docs))


def test_change_missing_from_change_log_reported(data: CityData, docs: list[ParsedDocument]) -> None:
    data.infrastructure_changes[0].id = "CH-2018-99"
    assert any("CH-2018-99" in p and "change log" in p for p in validate_references(data, docs))


def test_threshold_value_missing_from_section_reported(data: CityData, docs: list[ParsedDocument]) -> None:
    data.policy_thresholds[0].value = 987.6
    assert any(data.policy_thresholds[0].id in p and "987.6" in p for p in validate_references(data, docs))


def test_report_incident_id_mismatch_reported(data: CityData, docs: list[ParsedDocument]) -> None:
    report = next(d for d in docs if d.incident is not None)
    assert report.incident is not None
    bad = report.model_copy(update={"incident": report.incident.model_copy(update={"id": "HI-1999-FL-01"})})
    others = [d for d in docs if d is not report]
    assert any("HI-1999-FL-01" in p for p in validate_references(data, [*others, bad]))
