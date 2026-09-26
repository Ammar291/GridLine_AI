"""Per-zone landslide and flood indices: factors, bands, and one zone.state per zone after every tick."""

import pytest

from gridline.city.model import City
from gridline.events.envelope import Event
from gridline.events.types import Band, EventType, Severity
from gridline.simulation.engine import SimulationEngine
from gridline.simulation.scenarios import ScenarioName
from gridline.simulation.world import WorldState
from gridline.threats.indices import (
    DETECTOR_SOURCE,
    FLOOD_WEIGHTS,
    LANDSLIDE_WEIGHTS,
    band_of,
    flood_index,
    landslide_index,
)


def quiet_world(city: City) -> WorldState:
    engine = SimulationEngine(city)
    engine.reset(ScenarioName.NORMAL_CITY, seed=1)
    return engine.world


def test_weights_sum_to_one() -> None:
    assert sum(LANDSLIDE_WEIGHTS.values()) == pytest.approx(1)
    assert sum(FLOOD_WEIGHTS.values()) == pytest.approx(1)


@pytest.mark.parametrize(
    ("index", "band"),
    [
        (0.0, Band.NORMAL),
        (0.349, Band.NORMAL),
        (0.35, Band.WATCH),
        (0.549, Band.WATCH),
        (0.55, Band.WARNING),
        (0.75, Band.CRITICAL),
        (1.0, Band.CRITICAL),
    ],
)
def test_band_edges(index: float, band: Band) -> None:
    assert band_of(index) == band


def test_a_quiet_city_is_normal_everywhere(city: City) -> None:
    world = quiet_world(city)
    for zone in city.zones:
        worst = max(landslide_index(world, city, zone.id), flood_index(world, city, zone.id))
        assert band_of(worst) == Band.NORMAL


def test_a_zone_without_slopes_has_no_landslide_index(city: City) -> None:
    assert landslide_index(quiet_world(city), city, "Z-RS") == 0.0


@pytest.mark.parametrize("factor", ["saturation", "rain_24h", "cut", "movement"])
def test_each_landslide_factor_raises_the_hillview_index(city: City, factor: str) -> None:
    world = quiet_world(city)
    before = landslide_index(world, city, "Z-HV")
    match factor:
        case "saturation":
            world.slopes["SL-HV-1"].saturation = 0.85
        case "rain_24h":
            world.zones["Z-HV"].rain_24h_mm = 175
        case "cut":
            world.projects["PR-HT2"].excavation_depth_m = 6.0
        case _:
            world.slopes["SL-HV-1"].movement_rate_mm_h = 30
    assert landslide_index(world, city, "Z-HV") > before


def test_a_saturated_moving_cut_slope_is_critical(city: City) -> None:
    world = quiet_world(city)
    world.slopes["SL-HV-1"].saturation = 0.85
    world.slopes["SL-HV-1"].movement_rate_mm_h = 30
    world.zones["Z-HV"].rain_24h_mm = 175
    world.projects["PR-HT2"].excavation_depth_m = 6.0
    index = landslide_index(world, city, "Z-HV")
    assert index == pytest.approx(0.96)  # every factor at 1 except steepness (32 degrees: 0.6)
    assert band_of(index) == Band.CRITICAL


@pytest.mark.parametrize("factor", ["rain", "saturation", "load", "blocked", "water"])
def test_each_flood_factor_raises_the_riverside_index(city: City, factor: str) -> None:
    world = quiet_world(city)
    before = flood_index(world, city, "Z-RS")
    match factor:
        case "rain":
            world.zones["Z-RS"].rainfall_intensity_mm_h = 50
        case "saturation":
            world.zones["Z-RS"].saturation = 1.0
        case "load":
            world.channels["D-7"].flow_m3s = (
                2 * world.channels["D-7"].capacity_m3s
            )  # D-7 overflows into Riverside
        case "blocked":
            world.channels["D-7"].blocked_fraction = 0.7
        case _:
            world.zones["Z-RS"].water_depth_cm = 50
    assert flood_index(world, city, "Z-RS") > before


def zone_states(events: list[Event]) -> list[Event]:
    return [e for e in events if e.event_type == EventType.ZONE_STATE]


def test_the_engine_emits_one_zone_state_per_zone_each_tick(city: City) -> None:
    engine = SimulationEngine(city)
    engine.reset(ScenarioName.NORMAL_CITY, seed=1)
    events = engine.advance(2)
    states = zone_states(events)
    n = len(city.zones)
    assert len(states) == 2 * n
    assert [s.location for s in states[:n]] == [z.id for z in city.zones]
    assert all(s.payload["prev_band"] is None for s in states[:n])
    assert all(s.payload["prev_band"] == "normal" for s in states[n:])
    assert all(s.source == DETECTOR_SOURCE and s.severity == Severity.INFO for s in states)
    first_tick = events[: events.index(next(e for e in events if e.event_type == EventType.SIM_TICK)) + 1]
    assert first_tick[-2].event_type == EventType.ZONE_STATE  # after the readings, just before sim.tick


def test_reset_forgets_the_previous_bands(city: City) -> None:
    engine = SimulationEngine(city)
    engine.reset(ScenarioName.NORMAL_CITY, seed=1)
    engine.advance(1)
    engine.reset(ScenarioName.NORMAL_CITY, seed=1)
    assert all(s.payload["prev_band"] is None for s in zone_states(engine.advance(1)))
