from collections.abc import Callable
from typing import Any

import pytest
from pydantic import ValidationError

from gridline.city.model import City
from gridline.errors import InvalidPayload, NotInjectable, UnknownAsset
from gridline.events.types import EventType, Severity
from gridline.simulation.engine import SimulationEngine
from gridline.simulation.scenarios import ScenarioName
from gridline.simulation.world import WorldSnapshot


@pytest.fixture
def engine(city: City) -> SimulationEngine:
    engine = SimulationEngine(city)
    engine.reset(ScenarioName.HILLSIDE_LANDSLIDE, seed=5)
    return engine


Check = Callable[[WorldSnapshot], bool]
CASES: list[tuple[EventType, dict[str, Any], str | None, Check]] = [
    (
        EventType.WEATHER_FORECAST,
        {
            "issued_sim_time": "2026-07-14T06:00:00Z",
            "horizon_h": 6,
            "expected_total_mm": 90,
            "peak_intensity_mm_h": 40,
            "confidence": 0.7,
            "summary": "heavy showers",
        },
        None,
        lambda s: s.forecast is not None and s.forecast.expected_total_mm == 90,
    ),
    (
        EventType.INFRASTRUCTURE_ROAD,
        {"road_id": "RD-05", "status": "closed", "reason": "fire"},
        "Z-OT",
        lambda s: s.roads["RD-05"].status == "closed" and s.roads["RD-05"].reason == "fire",
    ),
    (
        EventType.INFRASTRUCTURE_BRIDGE,
        {"bridge_id": "BR-1", "status": "restricted", "reason": "scour check"},
        "Z-OT",
        lambda s: s.bridges["BR-1"].status == "restricted",
    ),
    (
        EventType.INFRASTRUCTURE_DRAINAGE_OBSTRUCTION,
        {"channel_id": "D-3", "blocked_fraction": 0.4, "cause": "silt"},
        "Z-OT",
        lambda s: s.channels["D-3"].blocked_fraction == 0.4,
    ),
    (
        EventType.INFRASTRUCTURE_CONSTRUCTION,
        {"project_id": "PR-HT2", "status": "halted", "activity": "halted", "excavation_depth_m": 0},
        "Z-HV",
        lambda s: s.projects["PR-HT2"].status == "halted" and s.projects["PR-HT2"].excavation_depth_m == 2.5,
    ),
    (
        EventType.INFRASTRUCTURE_FAILURE,
        {
            "asset_id": "D-12",
            "asset_kind": "channel",
            "failure_kind": "culvert_collapse",
            "description": "collapsed",
        },
        "Z-MI",
        lambda s: s.channels["D-12"].blocked_fraction == 1.0,
    ),
    (
        EventType.EMERGENCY_RESCUE_TEAM,
        {"crew_id": "C-7", "status": "en_route", "location_zone_id": "Z-NC"},
        "Z-NC",
        lambda s: s.crews["C-7"].status == "en_route" and s.crews["C-7"].location_zone_id == "Z-NC",
    ),
    (
        EventType.EMERGENCY_AMBULANCE,
        {"ambulance_id": "AMB-07", "status": "dispatched", "location_zone_id": "Z-HV"},
        "Z-HV",
        lambda s: s.ambulances["AMB-07"].status == "dispatched",
    ),
    (
        EventType.EMERGENCY_HOSPITAL,
        {"hospital_id": "H-1", "beds_occupied": 400, "er_status": "busy"},
        "Z-CL",
        lambda s: s.hospitals["H-1"].beds_occupied == 400 and s.hospitals["H-1"].er_status == "busy",
    ),
    (
        EventType.EMERGENCY_SHELTER,
        {"shelter_id": "S-1", "status": "open", "occupancy": 120},
        "Z-CL",
        lambda s: s.shelters["S-1"].status == "open" and s.shelters["S-1"].occupancy == 120,
    ),
]


@pytest.mark.parametrize(("event_type", "payload", "zone", "check"), CASES, ids=[c[0] for c in CASES])
def test_each_injectable_type_mutates_state_and_emits(
    engine: SimulationEngine, event_type: EventType, payload: dict[str, Any], zone: str | None, check: Check
) -> None:
    events = engine.inject(event_type, payload)
    assert events[0].event_type == event_type
    assert events[0].source == "operator:api"
    assert events[0].location == zone
    assert check(engine.snapshot())


def test_filled_fields_come_from_the_city(engine: SimulationEngine) -> None:
    road = engine.inject(EventType.INFRASTRUCTURE_ROAD, {"road_id": "RD-02", "status": "blocked"})[0]
    assert road.payload["is_evacuation_route"] is True and road.severity == Severity.HIGH
    amb = engine.inject(
        EventType.EMERGENCY_AMBULANCE,
        {"ambulance_id": "AMB-06", "status": "dispatched", "location_zone_id": "Z-RS"},
    )[0]
    assert (amb.payload["hospital_id"], amb.payload["available_count"], amb.payload["total_count"]) == (
        "H-2",
        1,
        2,
    )
    assert amb.severity == Severity.MODERATE
    hospital = engine.inject(
        EventType.EMERGENCY_HOSPITAL, {"hospital_id": "H-2", "beds_occupied": 70, "er_status": "busy"}
    )[0]
    assert (hospital.payload["beds_total"], hospital.payload["beds_available"]) == (80, 10)
    shelter = engine.inject(
        EventType.EMERGENCY_SHELTER, {"shelter_id": "S-5", "status": "open", "occupancy": 5}
    )[0]
    assert shelter.payload["capacity"] == 300


def test_asset_zone_wins_over_a_contradicting_location(engine: SimulationEngine) -> None:
    event = engine.inject(
        EventType.INFRASTRUCTURE_ROAD, {"road_id": "RD-01", "status": "closed"}, location="Z-LK"
    )[0]
    assert event.location == "Z-HV"


def test_landslide_cascades_into_four_derived_events(engine: SimulationEngine) -> None:
    events = engine.inject(
        EventType.INFRASTRUCTURE_FAILURE,
        {
            "asset_id": "SL-HV-1",
            "asset_kind": "slope",
            "failure_kind": "landslide",
            "description": "slope failed",
        },
    )
    assert [e.event_type for e in events] == [
        EventType.INFRASTRUCTURE_FAILURE,
        EventType.INFRASTRUCTURE_DRAINAGE_OBSTRUCTION,
        EventType.INFRASTRUCTURE_ROAD,
        EventType.INFRASTRUCTURE_BRIDGE,
        EventType.INFRASTRUCTURE_CONSTRUCTION,
    ]
    assert events[0].severity == Severity.CRITICAL and events[0].location == "Z-HV"
    assert all(e.source == "simulation:engine" for e in events[1:])
    assert events[1].payload["channel_id"] == "D-7" and events[1].payload["blocked_fraction"] >= 0.7
    assert (events[2].payload["road_id"], events[2].payload["status"]) == ("RD-01", "blocked")
    assert (events[3].payload["bridge_id"], events[3].payload["status"]) == ("BR-4", "closed")
    assert (events[4].payload["project_id"], events[4].payload["status"]) == ("PR-HT2", "halted")
    snap = engine.snapshot()
    assert snap.channels["D-7"].blocked_fraction >= 0.7
    assert snap.roads["RD-01"].status == "blocked" and snap.bridges["BR-4"].status == "closed"
    assert snap.projects["PR-HT2"].status == "halted"
    assert snap.slopes["SL-HV-1"].cumulative_movement_mm >= 1500


def test_halted_project_stops_excavating(engine: SimulationEngine) -> None:
    engine.advance(24)
    depth = engine.snapshot().projects["PR-HT2"].excavation_depth_m
    assert depth > 2.5
    engine.inject(
        EventType.INFRASTRUCTURE_CONSTRUCTION,
        {"project_id": "PR-HT2", "status": "halted", "activity": "halted", "excavation_depth_m": depth},
    )
    engine.advance(24)
    project = engine.snapshot().projects["PR-HT2"]
    assert (project.status, project.activity, project.excavation_depth_m) == ("halted", "halted", depth)


def test_severity_override_and_noop_injection(engine: SimulationEngine) -> None:
    events = engine.inject(
        EventType.INFRASTRUCTURE_ROAD,
        {"road_id": "RD-05", "status": "open"},
        severity=Severity.CRITICAL,
        source="operator:test",
    )
    assert events[0].severity == Severity.CRITICAL and events[0].source == "operator:test"


def test_rejections(engine: SimulationEngine) -> None:
    with pytest.raises(NotInjectable):
        engine.inject(EventType.WEATHER_OBSERVATION, {"station_id": "RG-02"})
    with pytest.raises(NotInjectable):
        engine.inject(EventType.SIM_TICK, {})
    with pytest.raises(UnknownAsset):
        engine.inject(EventType.INFRASTRUCTURE_ROAD, {"road_id": "RD-99", "status": "closed"})
    with pytest.raises(UnknownAsset):
        engine.inject(
            EventType.EMERGENCY_RESCUE_TEAM,
            {"crew_id": "C-1", "status": "en_route", "location_zone_id": "Z-XX"},
        )
    with pytest.raises(UnknownAsset):
        engine.inject(
            EventType.INFRASTRUCTURE_FAILURE,
            {"asset_id": "SL-HV-1", "asset_kind": "bridge", "failure_kind": "landslide", "description": "d"},
        )
    with pytest.raises(ValidationError):
        engine.inject(EventType.INFRASTRUCTURE_ROAD, {"road_id": "RD-01", "status": "flooded"})
    with pytest.raises(InvalidPayload):
        engine.inject(
            EventType.EMERGENCY_HOSPITAL,
            {"hospital_id": "H-2", "beds_occupied": 81, "er_status": "overwhelmed"},
        )
