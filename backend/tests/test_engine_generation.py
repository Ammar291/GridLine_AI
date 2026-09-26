from datetime import UTC, datetime, timedelta

import pytest

from gridline.city.model import City
from gridline.events.envelope import Event
from gridline.events.types import EventType, Severity
from gridline.simulation.engine import SIM_START, SimulationEngine
from gridline.simulation.scenarios import ScenarioName

WALL = datetime(2030, 1, 1, tzinfo=UTC)
SENSOR_TYPES = {
    "rain_gauge": EventType.WEATHER_OBSERVATION,
    "wind": EventType.WEATHER_OBSERVATION,
    "soil_moisture": EventType.ENVIRONMENT_SOIL,
    "channel_level": EventType.ENVIRONMENT_DRAINAGE,
    "river_level": EventType.ENVIRONMENT_RIVER,
}


def engine_for(
    city: City, scenario: ScenarioName = ScenarioName.NORMAL_CITY, seed: int = 7
) -> SimulationEngine:
    engine = SimulationEngine(city, clock=lambda: WALL)
    engine.reset(scenario, seed)
    return engine


def test_reset_emits_stage_zero_first(city: City) -> None:
    engine = SimulationEngine(city, clock=lambda: WALL)
    events = engine.reset(ScenarioName.FLASH_FLOOD, seed=3)
    first = events[0]
    assert first.event_type == EventType.SCENARIO_STAGE
    assert first.event_id == "evt-000001"
    assert first.payload["stage_index"] == 0 and first.payload["stage"] == "culvert_constraint"
    assert first.sim_time == SIM_START == datetime(2026, 7, 14, 6, 0, tzinfo=UTC)
    assert [e.event_type for e in events[1:]] == [EventType.WEATHER_FORECAST]  # the t=0 forecast
    assert engine.status.tick == 0 and engine.status.stage_name == "culvert_constraint"


def test_one_tick_emits_one_observation_per_sensor_then_sim_tick(city: City) -> None:
    engine = engine_for(city)
    events = engine.advance()
    assert events[-1].event_type == EventType.SIM_TICK
    assert events[-1].payload["tick"] == 1
    by_source = {e.source: e for e in events}
    for sensor in city.sensors:
        event = by_source[f"sensor:{sensor.id}"]
        assert event.event_type == SENSOR_TYPES[sensor.kind]
        assert event.location == sensor.zone_id
    monitored = {s.target_id for s in city.sensors if s.kind == "soil_moisture"}
    slope_events = [e for e in events if e.event_type == EventType.ENVIRONMENT_SLOPE]
    assert {e.payload["slope_id"] for e in slope_events} == monitored
    assert all(e.source == "simulation:engine" for e in slope_events)
    observed = len(city.sensors) + len(monitored)
    construction = [e for e in events if e.event_type == EventType.INFRASTRUCTURE_CONSTRUCTION]
    zone_states = [e for e in events if e.event_type == EventType.ZONE_STATE]
    assert [e.location for e in zone_states] == [z.id for z in city.zones]  # one risk reading per zone
    assert len(events) == observed + len(construction) + len(zone_states) + 1


def test_sensor_payloads_carry_their_ids_and_units(city: City) -> None:
    events = engine_for(city).advance()
    by_source = {e.source: e for e in events}
    rain = by_source["sensor:RG-02"].payload
    assert rain["station_id"] == "RG-02" and rain["rainfall_intensity_mm_h"] is not None
    assert rain["wind_speed_kmh"] is None
    wind = by_source["sensor:WS-01"].payload
    assert wind["wind_speed_kmh"] is not None and wind["rainfall_intensity_mm_h"] is None
    assert by_source["sensor:SM-01"].payload["slope_id"] == "SL-HV-1"
    drain = by_source["sensor:CL-D7"].payload
    assert drain["channel_id"] == "D-7" and drain["capacity_m3s"] == pytest.approx(27.0)
    river = by_source["sensor:RV-01"].payload
    assert (river["river_id"], river["flood_stage_m"], river["warning_level_m"], river["danger_level_m"]) == (
        "R-1",
        4.2,
        5.0,
        5.5,
    )
    assert river["level_m"] == pytest.approx(1.6, abs=0.1)


def test_events_validate_are_sequential_and_timed(city: City) -> None:
    engine = SimulationEngine(city, clock=lambda: WALL)
    events = engine.reset(ScenarioName.CASCADING_LANDSLIDE_FLOOD, 42) + engine.advance(3)
    assert [e.event_id for e in events] == [f"evt-{n:06d}" for n in range(1, len(events) + 1)]
    for event in events:
        assert Event.model_validate_json(event.model_dump_json()) == event
        assert event.timestamp == WALL
        assert event.severity in Severity
    ticks = [e for e in events if e.event_type == EventType.SIM_TICK]
    assert [e.sim_time for e in ticks] == [SIM_START + timedelta(minutes=5 * n) for n in (1, 2, 3)]


def test_advancing_past_duration_holds_the_last_values(city: City) -> None:
    engine = engine_for(city, ScenarioName.NORMAL_CITY)
    duration = engine.scenario.duration_ticks
    engine.advance(duration)
    at_end = engine.snapshot()
    events = engine.advance(30)
    after = engine.snapshot()
    assert engine.status.tick == duration + 30
    assert engine.status.stage_name == "steady_state"
    assert not [e for e in events if e.event_type == EventType.SCENARIO_STAGE]
    assert after.zones["Z-HV"].rainfall_intensity_mm_h == at_end.zones["Z-HV"].rainfall_intensity_mm_h == 0
    assert after.weather.temperature_c == pytest.approx(at_end.weather.temperature_c)


def test_stage_entries_are_emitted_at_their_ticks(city: City) -> None:
    engine = engine_for(city, ScenarioName.FLASH_FLOOD)
    events = engine.advance(140)
    stages = [
        (e.payload["tick"], e.payload["stage"]) for e in events if e.event_type == EventType.SCENARIO_STAGE
    ]
    assert stages == [(48, "severe_rain"), (96, "drain_overload"), (132, "riverside_flooding")]
    forecasts = [e for e in events if e.event_type == EventType.WEATHER_FORECAST]
    assert len(forecasts) == 1 and forecasts[0].payload["peak_intensity_mm_h"] == 55
    assert engine.snapshot().forecast is not None


def test_engine_requires_reset(city: City) -> None:
    engine = SimulationEngine(city)
    with pytest.raises(RuntimeError):
        engine.advance()
