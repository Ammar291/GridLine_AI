"""One case per band row of the recalibrated severity table (spec §3.3; policy_thresholds.yaml numbers)."""

from datetime import UTC, datetime

import pytest
from pydantic import BaseModel

from gridline.city.model import City
from gridline.events import payloads as p
from gridline.events.types import Band, EventType, Severity
from gridline.simulation.severity import severity_for

NOW = datetime(2026, 7, 14, 6, 0, tzinfo=UTC)
INF, L, M, H, C = Severity.INFO, Severity.LOW, Severity.MODERATE, Severity.HIGH, Severity.CRITICAL


def rain(mm_h: float, day_mm: float = 0, station: str = "RG-03") -> p.WeatherObservation:
    return p.WeatherObservation(
        station_id=station, rainfall_intensity_mm_h=mm_h, cumulative_rainfall_24h_mm=day_mm
    )


def zone(band: Band) -> p.ZoneStatePayload:
    return p.ZoneStatePayload(
        zone_id="Z-HV",
        saturation=0.5,
        rain_24h_mm=0,
        rain_intensity_mm_h=0,
        landslide_index=0,
        flood_index=0,
        band=band,
        updated_sim_time=NOW,
    )


def wind(kmh: float) -> p.WeatherObservation:
    return p.WeatherObservation(
        station_id="WS-01", wind_speed_kmh=kmh, wind_direction_deg=200, temperature_c=25
    )


def soil(sat: float) -> p.SoilObservation:
    return p.SoilObservation(probe_id="SM-01", slope_id="SL-HV-1", soil_moisture_pct=45 * sat, saturation=sat)


def drain(ratio: float) -> p.DrainageObservation:
    return p.DrainageObservation(
        gauge_id="CL-D7",
        channel_id="D-7",
        flow_m3s=27 * ratio,
        capacity_m3s=27,
        load_ratio=ratio,
        blocked_fraction=0,
        overflow_m3s=0,
    )


def river(level: float) -> p.RiverObservation:
    return p.RiverObservation(
        gauge_id="RV-01",
        river_id="R-1",
        level_m=level,
        flood_stage_m=4.2,
        warning_level_m=5.0,
        danger_level_m=5.5,
        trend="steady",
    )


def slope(rate: float) -> p.SlopeObservation:
    return p.SlopeObservation(
        slope_id="SL-HV-1", movement_rate_mm_h=rate, cumulative_movement_mm=0, saturation=0.9
    )


def water(cm: float) -> p.WaterAccumulation:
    return p.WaterAccumulation(zone_id="Z-RS", depth_cm=cm, trend="rising")


def forecast(peak: float) -> p.WeatherForecast:
    return p.WeatherForecast(
        issued_sim_time=NOW,
        horizon_h=6,
        expected_total_mm=100,
        peak_intensity_mm_h=peak,
        confidence=0.9,
        summary="s",
    )


def crew(status: p.CrewStatusValue) -> p.RescueTeamStatus:
    return p.RescueTeamStatus(crew_id="C-4", status=status, location_zone_id="Z-RS")


def ambulance(available: int) -> p.AmbulanceStatus:
    return p.AmbulanceStatus(
        ambulance_id="AMB-06",
        status="dispatched",
        location_zone_id="Z-RS",
        available_count=available,
        total_count=2,
    )


def obstruction(blocked: float) -> p.DrainageObstruction:
    return p.DrainageObstruction(channel_id="D-7", blocked_fraction=blocked)


CASES: list[tuple[EventType, BaseModel, Severity]] = [
    (EventType.WEATHER_OBSERVATION, rain(5), INF),
    (EventType.WEATHER_OBSERVATION, rain(20), L),
    (EventType.WEATHER_OBSERVATION, rain(30), M),  # flash flood watch 30 mm/h
    (EventType.WEATHER_OBSERVATION, rain(55), H),  # flash flood warning 50 mm/h
    (
        EventType.WEATHER_OBSERVATION,
        rain(2, 120, station="RG-03"),
        INF,
    ),  # Old Town gauge serves no steep slope
    (EventType.WEATHER_OBSERVATION, rain(2, 70, station="RG-02"), M),  # landslide watch 65 mm / 24 h
    (EventType.WEATHER_OBSERVATION, rain(2, 120, station="RG-02"), H),  # landslide warning 115 mm
    (EventType.WEATHER_OBSERVATION, rain(2, 180, station="RG-01"), C),  # landslide critical 175 mm
    (EventType.WEATHER_OBSERVATION, wind(20), INF),
    (EventType.WEATHER_OBSERVATION, wind(50), L),
    (EventType.WEATHER_OBSERVATION, wind(62), M),  # cyclone watch
    (EventType.WEATHER_OBSERVATION, wind(90), H),  # cyclone warning
    (EventType.WEATHER_OBSERVATION, wind(120), C),  # cyclone critical
    (EventType.ENVIRONMENT_SOIL, soil(0.4), INF),
    (EventType.ENVIRONMENT_SOIL, soil(0.55), L),
    (EventType.ENVIRONMENT_SOIL, soil(0.65), M),
    (EventType.ENVIRONMENT_SOIL, soil(0.70), H),  # saturation warning 0.70
    (EventType.ENVIRONMENT_SOIL, soil(0.85), C),  # saturation critical 0.85
    (EventType.ENVIRONMENT_DRAINAGE, drain(0.3), INF),
    (EventType.ENVIRONMENT_DRAINAGE, drain(0.7), L),
    (EventType.ENVIRONMENT_DRAINAGE, drain(0.8), M),  # channel flow ratio watch 0.8
    (EventType.ENVIRONMENT_DRAINAGE, drain(1.0), C),  # channel treated as overflowing at 1.0
    (EventType.ENVIRONMENT_RIVER, river(1.6), INF),
    (EventType.ENVIRONMENT_RIVER, river(3.5), L),
    (EventType.ENVIRONMENT_RIVER, river(4.2), M),  # flood stage (watch)
    (EventType.ENVIRONMENT_RIVER, river(5.0), H),  # warning, BR-1 closes
    (EventType.ENVIRONMENT_RIVER, river(5.5), C),  # danger stage
    (EventType.ENVIRONMENT_SLOPE, slope(0.1), INF),
    (EventType.ENVIRONMENT_SLOPE, slope(1), L),
    (EventType.ENVIRONMENT_SLOPE, slope(5), M),
    (EventType.ENVIRONMENT_SLOPE, slope(20), H),
    (EventType.ENVIRONMENT_SLOPE, slope(30), C),
    (EventType.ENVIRONMENT_WATER_ACCUMULATION, water(0), INF),
    (EventType.ENVIRONMENT_WATER_ACCUMULATION, water(5), L),
    (EventType.ENVIRONMENT_WATER_ACCUMULATION, water(15), M),
    (EventType.ENVIRONMENT_WATER_ACCUMULATION, water(30), H),  # road closure depth 0.3 m
    (EventType.ENVIRONMENT_WATER_ACCUMULATION, water(50), C),
    (EventType.INFRASTRUCTURE_ROAD, p.RoadStatus(road_id="RD-05", status="open"), INF),
    (EventType.INFRASTRUCTURE_ROAD, p.RoadStatus(road_id="RD-05", status="closed"), M),
    (
        EventType.INFRASTRUCTURE_ROAD,
        p.RoadStatus(road_id="RD-01", status="blocked", is_evacuation_route=True),
        H,
    ),
    (EventType.INFRASTRUCTURE_BRIDGE, p.BridgeStatus(bridge_id="BR-1", status="open"), INF),
    (EventType.INFRASTRUCTURE_BRIDGE, p.BridgeStatus(bridge_id="BR-1", status="restricted"), M),
    (EventType.INFRASTRUCTURE_BRIDGE, p.BridgeStatus(bridge_id="BR-1", status="closed"), H),
    (EventType.INFRASTRUCTURE_DRAINAGE_OBSTRUCTION, obstruction(0.05), INF),
    (EventType.INFRASTRUCTURE_DRAINAGE_OBSTRUCTION, obstruction(0.1), L),
    (EventType.INFRASTRUCTURE_DRAINAGE_OBSTRUCTION, obstruction(0.25), M),
    (EventType.INFRASTRUCTURE_DRAINAGE_OBSTRUCTION, obstruction(0.5), H),
    (EventType.INFRASTRUCTURE_DRAINAGE_OBSTRUCTION, obstruction(0.8), C),
    (
        EventType.INFRASTRUCTURE_CONSTRUCTION,
        p.ConstructionActivity(project_id="PR-HT2", status="halted", activity="halted", excavation_depth_m=3),
        INF,
    ),
    (
        EventType.INFRASTRUCTURE_CONSTRUCTION,
        p.ConstructionActivity(
            project_id="PR-HT2", status="active", activity="excavating", excavation_depth_m=3
        ),
        L,
    ),
    (
        EventType.INFRASTRUCTURE_FAILURE,
        p.InfrastructureFailure(
            asset_id="SL-HV-1", asset_kind="slope", failure_kind="landslide", description="d"
        ),
        C,
    ),
    (EventType.EMERGENCY_RESCUE_TEAM, crew("available"), INF),
    (EventType.EMERGENCY_RESCUE_TEAM, crew("en_route"), L),
    (EventType.EMERGENCY_RESCUE_TEAM, crew("blocked"), H),
    (EventType.EMERGENCY_AMBULANCE, ambulance(2), INF),
    (EventType.EMERGENCY_AMBULANCE, ambulance(1), M),
    (EventType.EMERGENCY_AMBULANCE, ambulance(0), H),
    (
        EventType.EMERGENCY_HOSPITAL,
        p.HospitalCapacity(hospital_id="H-2", beds_occupied=63, er_status="normal"),
        INF,
    ),
    (
        EventType.EMERGENCY_HOSPITAL,
        p.HospitalCapacity(hospital_id="H-2", beds_occupied=72, er_status="busy"),
        M,
    ),
    (
        EventType.EMERGENCY_HOSPITAL,
        p.HospitalCapacity(hospital_id="H-2", beds_occupied=79, er_status="overwhelmed"),
        C,
    ),
    (EventType.EMERGENCY_SHELTER, p.ShelterCapacity(shelter_id="S-1", status="open", occupancy=10), INF),
    (EventType.EMERGENCY_SHELTER, p.ShelterCapacity(shelter_id="S-1", status="full", occupancy=800), H),
    (EventType.WEATHER_FORECAST, forecast(10), INF),
    (EventType.WEATHER_FORECAST, forecast(35), M),
    (EventType.WEATHER_FORECAST, forecast(55), H),
    (EventType.WEATHER_RAINFALL, p.RainfallDriver(intensity_mm_h=5, duration_h=1), INF),
    (EventType.WEATHER_RAINFALL, p.RainfallDriver(intensity_mm_h=20, duration_h=1), L),
    (EventType.WEATHER_RAINFALL, p.RainfallDriver(intensity_mm_h=35, duration_h=1), M),
    (EventType.WEATHER_RAINFALL, p.RainfallDriver(intensity_mm_h=60, duration_h=1), H),
    (EventType.EMERGENCY_FIRE, p.IndustrialFire(zone_id="Z-MI", site="s", exposed_population=5000), H),
    (EventType.EMERGENCY_FIRE, p.IndustrialFire(zone_id="Z-MI", site="s", exposed_population=80000), C),
    (EventType.ZONE_STATE, zone(Band.NORMAL), INF),
    (EventType.ZONE_STATE, zone(Band.WATCH), M),
    (EventType.ZONE_STATE, zone(Band.WARNING), H),
    (EventType.ZONE_STATE, zone(Band.CRITICAL), C),
    (EventType.SIM_HEARTBEAT, p.Heartbeat(tick=1, sim_time=NOW), INF),
    (
        EventType.SCENARIO_STAGE,
        p.ScenarioStage(scenario="flash_flood", stage_index=1, stage="severe_rain", description="d", tick=48),
        INF,
    ),
]


@pytest.mark.parametrize(("event_type", "payload", "expected"), CASES)
def test_severity_band(city: City, event_type: EventType, payload: BaseModel, expected: Severity) -> None:
    assert severity_for(event_type, payload, city.thresholds) == expected
