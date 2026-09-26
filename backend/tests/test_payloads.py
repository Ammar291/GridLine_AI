"""One valid construction and one bound violation per payload model (every event type is covered)."""

from datetime import UTC, datetime

import pytest
from pydantic import BaseModel, ValidationError

from gridline.events import payloads as p

NOW = datetime(2026, 7, 14, 6, 0, tzinfo=UTC)
STATUS = p.SimStatus(
    state="idle", running=False, scenario="normal_city", seed=1, speed=1.0, tick=0, sim_time=NOW, stage="s"
)

VALID: list[BaseModel] = [
    p.SimTick(tick=1, sim_time=NOW, scenario="normal_city", stage="steady_state", speed=1.0, running=False),
    STATUS,
    p.SimSnapshot(status=STATUS, world={"tick": 0}),
    p.Heartbeat(tick=0, sim_time=NOW),
    p.ScenarioStage(scenario="normal_city", stage_index=0, stage="steady_state", description="d", tick=0),
    p.WeatherObservation(station_id="RG-02", rainfall_intensity_mm_h=0, cumulative_rainfall_24h_mm=0),
    p.WeatherForecast(
        issued_sim_time=NOW,
        horizon_h=24,
        expected_total_mm=12,
        peak_intensity_mm_h=3,
        confidence=0.8,
        summary="s",
    ),
    p.SoilObservation(probe_id="SM-01", slope_id="SL-HV-1", soil_moisture_pct=20, saturation=0.4),
    p.RiverObservation(
        gauge_id="RV-01",
        river_id="R-1",
        level_m=1.6,
        flood_stage_m=4.2,
        warning_level_m=5.0,
        danger_level_m=5.5,
        trend="steady",
    ),
    p.DrainageObservation(
        gauge_id="CL-D7",
        channel_id="D-7",
        flow_m3s=1,
        capacity_m3s=27,
        load_ratio=0.04,
        blocked_fraction=0,
        overflow_m3s=0,
    ),
    p.SlopeObservation(slope_id="SL-HV-1", movement_rate_mm_h=0, cumulative_movement_mm=0, saturation=0.1),
    p.WaterAccumulation(zone_id="Z-RS", depth_cm=0, trend="steady"),
    p.RoadStatus(road_id="RD-01", status="open"),
    p.BridgeStatus(bridge_id="BR-1", status="open"),
    p.DrainageObstruction(channel_id="D-7", blocked_fraction=0.25, cause="debris"),
    p.ConstructionActivity(
        project_id="PR-HT2", status="active", activity="excavating", excavation_depth_m=2.5
    ),
    p.InfrastructureFailure(
        asset_id="SL-HV-1", asset_kind="slope", failure_kind="landslide", description="d"
    ),
    p.RescueTeamStatus(crew_id="C-4", status="available", location_zone_id="Z-RS"),
    p.AmbulanceStatus(ambulance_id="AMB-06", status="dispatched", location_zone_id="Z-RS"),
    p.HospitalCapacity(hospital_id="H-2", beds_occupied=63, er_status="normal"),
    p.ShelterCapacity(shelter_id="S-5", status="closed", occupancy=0),
]


def test_valid_payloads_cover_every_model() -> None:
    assert {type(m) for m in VALID} == set(p.PAYLOAD_MODELS.values())


@pytest.mark.parametrize("model", VALID, ids=lambda m: type(m).__name__)
def test_valid_payloads_round_trip(model: BaseModel) -> None:
    assert type(model).model_validate(model.model_dump(mode="json")) == model


INVALID: list[tuple[type[BaseModel], dict[str, object]]] = [
    (p.SimTick, {"tick": -1, "sim_time": NOW, "scenario": "x", "stage": "y", "speed": 1.0}),
    (
        p.SimStatus,
        {
            "state": "flying",
            "scenario": "x",
            "seed": 1,
            "speed": 1.0,
            "tick": 0,
            "sim_time": NOW,
            "stage": "s",
        },
    ),
    (p.SimSnapshot, {"status": {}, "world": {}}),
    (p.Heartbeat, {"tick": 0}),
    (p.ScenarioStage, {"scenario": "x", "stage_index": -1, "stage": "s", "description": "d", "tick": 0}),
    (p.WeatherObservation, {"station_id": "RG-02", "rainfall_intensity_mm_h": -1}),
    (p.WeatherObservation, {"station_id": "WS-01", "wind_speed_kmh": 3, "wind_direction_deg": 360}),
    (
        p.WeatherForecast,
        {
            "issued_sim_time": NOW,
            "horizon_h": 0,
            "expected_total_mm": 1,
            "peak_intensity_mm_h": 1,
            "confidence": 0.5,
            "summary": "s",
        },
    ),
    (
        p.WeatherForecast,
        {
            "issued_sim_time": NOW,
            "horizon_h": 1,
            "expected_total_mm": 1,
            "peak_intensity_mm_h": 1,
            "confidence": 1.5,
            "summary": "s",
        },
    ),
    (p.SoilObservation, {"probe_id": "SM-01", "slope_id": None, "soil_moisture_pct": 20, "saturation": 1.2}),
    (
        p.RiverObservation,
        {
            "gauge_id": "RV-01",
            "river_id": "R-1",
            "level_m": -0.1,
            "flood_stage_m": 4.2,
            "warning_level_m": 5.0,
            "danger_level_m": 5.5,
            "trend": "steady",
        },
    ),
    (
        p.DrainageObservation,
        {
            "gauge_id": "CL-D7",
            "channel_id": "D-7",
            "flow_m3s": 1,
            "capacity_m3s": 27,
            "load_ratio": 0.1,
            "blocked_fraction": 1.5,
            "overflow_m3s": 0,
        },
    ),
    (
        p.SlopeObservation,
        {"slope_id": "SL-HV-1", "movement_rate_mm_h": -1, "cumulative_movement_mm": 0, "saturation": 0.1},
    ),
    (p.WaterAccumulation, {"zone_id": "Z-RS", "depth_cm": 1, "trend": "sideways"}),
    (p.RoadStatus, {"road_id": "RD-01", "status": "flooded"}),
    (p.BridgeStatus, {"bridge_id": "BR-1", "status": "gone"}),
    (p.DrainageObstruction, {"channel_id": "D-7", "blocked_fraction": -0.1}),
    (
        p.ConstructionActivity,
        {"project_id": "PR-HT2", "status": "active", "activity": "digging", "excavation_depth_m": 1},
    ),
    (
        p.InfrastructureFailure,
        {"asset_id": "a", "asset_kind": "slope", "failure_kind": "meteor", "description": "d"},
    ),
    (p.RescueTeamStatus, {"crew_id": "C-4", "status": "sleeping", "location_zone_id": "Z-RS"}),
    (
        p.AmbulanceStatus,
        {"ambulance_id": "AMB-01", "status": "available", "location_zone_id": "Z-CL", "available_count": -1},
    ),
    (p.HospitalCapacity, {"hospital_id": "H-2", "beds_occupied": -1, "er_status": "normal"}),
    (p.ShelterCapacity, {"shelter_id": "S-5", "status": "open", "occupancy": -1}),
]


def test_invalid_cases_cover_every_model() -> None:
    assert {model for model, _ in INVALID} == set(p.PAYLOAD_MODELS.values())


@pytest.mark.parametrize(("model", "data"), INVALID, ids=lambda x: getattr(x, "__name__", ""))
def test_invalid_payloads_rejected(model: type[BaseModel], data: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        model.model_validate(data)
