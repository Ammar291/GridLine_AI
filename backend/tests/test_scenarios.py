import pytest
from pydantic import ValidationError

from gridline.city.model import City
from gridline.errors import UnknownScenario
from gridline.events.types import INJECTABLE_TYPES
from gridline.simulation.engine import SimulationEngine
from gridline.simulation.scenarios import SCENARIOS, Scenario, ScenarioName, get_scenario
from gridline.simulation.scenarios.base import Curve, Stage


def test_registry_has_four_names() -> None:
    assert set(SCENARIOS) == {
        "normal_city",
        "hillside_landslide",
        "flash_flood",
        "cascading_landslide_flood",
    }
    assert get_scenario("flash_flood").name == ScenarioName.FLASH_FLOOD
    with pytest.raises(UnknownScenario):
        get_scenario("volcano")


def test_curve_interpolates_and_holds() -> None:
    curve = Curve.of((10, 0.0), (20, 10.0), (30, 4.0))
    assert curve.at(0) == 0.0
    assert curve.at(15) == pytest.approx(5.0)
    assert curve.at(25) == pytest.approx(7.0)
    assert curve.at(30) == 4.0
    assert curve.at(10_000) == 4.0
    with pytest.raises(ValidationError):
        Curve.of((5, 1.0), (5, 2.0))


def test_stages_must_start_at_zero_and_increase() -> None:
    base = SCENARIOS[ScenarioName.NORMAL_CITY]
    with pytest.raises(ValidationError):
        Scenario.model_validate(
            {**base.model_dump(), "stages": [Stage(name="a", start_tick=5, description="d")]}
        )
    with pytest.raises(ValidationError):
        stages = [
            Stage(name="a", start_tick=0, description="d"),
            Stage(name="b", start_tick=0, description="d"),
        ]
        Scenario.model_validate({**base.model_dump(), "stages": stages})
    cascading = SCENARIOS[ScenarioName.CASCADING_LANDSLIDE_FLOOD]
    assert [cascading.stage_index_at(t) for t in (0, 35, 36, 180, 204, 10_000)] == [0, 0, 1, 4, 5, 5]


def test_cascading_shares_the_hillside_storm_until_the_landslide() -> None:
    hillside = SCENARIOS[ScenarioName.HILLSIDE_LANDSLIDE]
    cascading = SCENARIOS[ScenarioName.CASCADING_LANDSLIDE_FLOOD]
    assert cascading.stages[:4] == hillside.stages
    assert all(
        cascading.rain_at(zone, t) == hillside.rain_at(zone, t)
        for zone in ("Z-HV", "Z-RS", "Z-TH", "Z-OT")
        for t in range(0, 217)
    )
    assert [s.name for s in cascading.stages] == [
        "construction_and_rain",
        "intensifying_rain",
        "slope_creep",
        "critical_slope",
        "landslide_and_blockage",
        "downstream_flood",
    ]


@pytest.mark.parametrize("scenario", list(SCENARIOS.values()), ids=lambda s: s.name)
def test_scenario_uses_known_ids_and_injectable_types(city: City, scenario: Scenario) -> None:
    zone_ids = {z.id for z in city.zones}
    assert set(scenario.rainfall) <= zone_ids | {"default"}
    if scenario.excavation is not None:
        city.project(scenario.excavation.project_id)
    for scripted in scenario.scripted:
        assert scripted.event_type in INJECTABLE_TYPES
        if scripted.condition is not None:
            lookup = {
                "saturation": city.zone,
                "water_depth_cm": city.zone,
                "river_level_m": city.river,
                "slope_cumulative_mm": city.slope,
            }[scripted.condition.metric]
            lookup(scripted.condition.target_id)
        engine = SimulationEngine(city)
        engine.reset(scenario.name, seed=1)
        assert engine.inject(scripted.event_type, scripted.payload, source=f"scenario:{scenario.name}")
