"""The scenario registry."""

from gridline.errors import UnknownScenario
from gridline.simulation.scenarios.base import Scenario, ScenarioName
from gridline.simulation.scenarios.cascading_landslide_flood import CASCADING_LANDSLIDE_FLOOD
from gridline.simulation.scenarios.flash_flood import FLASH_FLOOD
from gridline.simulation.scenarios.hillside_landslide import HILLSIDE_LANDSLIDE
from gridline.simulation.scenarios.normal_city import NORMAL_CITY

SCENARIOS: dict[ScenarioName, Scenario] = {
    s.name: s for s in (NORMAL_CITY, HILLSIDE_LANDSLIDE, FLASH_FLOOD, CASCADING_LANDSLIDE_FLOOD)
}


def get_scenario(name: str) -> Scenario:
    try:
        return SCENARIOS[ScenarioName(name)]
    except ValueError:
        raise UnknownScenario(f"unknown scenario {name!r}; known: {', '.join(SCENARIOS)}") from None


__all__ = ["SCENARIOS", "Scenario", "ScenarioName", "get_scenario"]
