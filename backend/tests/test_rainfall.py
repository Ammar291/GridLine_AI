"""weather.rainfall: operator rain raises the scenario's rain in the named zones until it expires."""

import pytest

from gridline.city.model import City
from gridline.errors import UnknownAsset
from gridline.events.types import EventType, Severity
from gridline.simulation.engine import SimulationEngine
from gridline.simulation.scenarios import ScenarioName


@pytest.fixture
def engine(city: City) -> SimulationEngine:
    engine = SimulationEngine(city)
    engine.reset(ScenarioName.NORMAL_CITY, seed=1)
    return engine


def rain(engine: SimulationEngine, zone_id: str) -> float:
    return engine.snapshot().zones[zone_id].rainfall_intensity_mm_h


def test_rainfall_overrides_the_scenario_rain_in_the_named_zones(engine: SimulationEngine) -> None:
    events = engine.inject(
        EventType.WEATHER_RAINFALL, {"zone_ids": ["Z-HV"], "intensity_mm_h": 60, "duration_h": 1}
    )
    assert [e.event_type for e in events] == [EventType.WEATHER_RAINFALL]
    assert events[0].location == "Z-HV" and events[0].severity == Severity.HIGH
    engine.advance(1)
    assert rain(engine, "Z-HV") == 60
    assert rain(engine, "Z-RS") < 5


def test_rainfall_expires_after_its_duration(engine: SimulationEngine) -> None:
    engine.inject(EventType.WEATHER_RAINFALL, {"zone_ids": ["Z-HV"], "intensity_mm_h": 60, "duration_h": 1})
    engine.advance(12)  # 12 ticks of 5 minutes: still inside the hour
    assert rain(engine, "Z-HV") == 60
    engine.advance(1)
    assert rain(engine, "Z-HV") < 5


def test_empty_zone_ids_means_every_zone(engine: SimulationEngine) -> None:
    events = engine.inject(EventType.WEATHER_RAINFALL, {"intensity_mm_h": 20, "duration_h": 1})
    assert events[0].location is None
    engine.advance(1)
    assert all(z.rainfall_intensity_mm_h == 20 for z in engine.snapshot().zones.values())


def test_rainfall_never_lowers_the_scenario_rain(engine: SimulationEngine) -> None:
    engine.advance(120)  # normal_city rain has risen to about 2.7 mm/h by now
    scenario_rain = engine.scenario.rain_at("Z-HV", 121)
    engine.inject(EventType.WEATHER_RAINFALL, {"zone_ids": ["Z-HV"], "intensity_mm_h": 0.5, "duration_h": 1})
    engine.advance(1)
    assert rain(engine, "Z-HV") == pytest.approx(scenario_rain)


def test_unknown_zone_is_rejected(engine: SimulationEngine) -> None:
    with pytest.raises(UnknownAsset):
        engine.inject(
            EventType.WEATHER_RAINFALL, {"zone_ids": ["Z-XX"], "intensity_mm_h": 20, "duration_h": 1}
        )


def test_reset_clears_the_override(engine: SimulationEngine) -> None:
    engine.inject(EventType.WEATHER_RAINFALL, {"intensity_mm_h": 60, "duration_h": 3})
    engine.reset(ScenarioName.NORMAL_CITY, seed=1)
    engine.advance(1)
    assert rain(engine, "Z-HV") < 5
