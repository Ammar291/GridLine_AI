"""emergency.fire: a fire in a zone exposes that zone and every zone within 500 m, counted from city data."""

import pytest

from gridline.city.model import City
from gridline.errors import UnknownAsset
from gridline.events.types import EventType, Severity
from gridline.simulation.engine import SimulationEngine
from gridline.simulation.scenarios import ScenarioName

FIRE = {"zone_id": "Z-MI", "site": "Mill Road warehouse", "description": "solvent store alight"}


@pytest.fixture
def engine(city: City) -> SimulationEngine:
    engine = SimulationEngine(city)
    engine.reset(ScenarioName.NORMAL_CITY, seed=1)
    return engine


def test_zone_population_and_bbox_come_from_the_data(city: City) -> None:
    mill_road = city.zone("Z-MI")
    assert mill_road.population == 22000
    assert mill_road.bbox == (8400, 0, 12000, 2700)


def test_fire_exposes_its_zone_and_the_zones_within_500_m(engine: SimulationEngine) -> None:
    [fire] = engine.inject(EventType.EMERGENCY_FIRE, FIRE)
    assert fire.location == "Z-MI" and fire.severity == Severity.CRITICAL
    assert fire.payload["exposed_zone_ids"] == [
        "Z-NC",
        "Z-MI",
    ]  # New Colony touches Mill Road; Riverside is 600 m off
    assert fire.payload["exposed_population"] == 80000
    state = engine.snapshot().fires["Z-MI"]
    assert (state.site, state.exposed_population, state.exposed_zone_ids) == (
        "Mill Road warehouse",
        80000,
        ["Z-NC", "Z-MI"],
    )


def test_a_quiet_city_has_no_fires(engine: SimulationEngine) -> None:
    assert engine.snapshot().fires == {}


def test_unknown_zone_is_rejected(engine: SimulationEngine) -> None:
    with pytest.raises(UnknownAsset):
        engine.inject(EventType.EMERGENCY_FIRE, {**FIRE, "zone_id": "Z-XX"})


def test_reset_puts_the_fire_out(engine: SimulationEngine) -> None:
    engine.inject(EventType.EMERGENCY_FIRE, FIRE)
    engine.reset(ScenarioName.NORMAL_CITY, seed=1)
    assert engine.snapshot().fires == {}
