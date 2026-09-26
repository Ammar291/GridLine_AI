"""A quiet monsoon day in Nandipur: light showers and routine excavation. Nothing should exceed ``low``."""

from gridline.simulation.scenarios.base import (
    Curve,
    Excavation,
    ForecastUpdate,
    Scenario,
    ScenarioName,
    Stage,
)

NORMAL_CITY = Scenario(
    name=ScenarioName.NORMAL_CITY,
    title="Normal city",
    description="A quiet monsoon day: light showers and routine excavation at Hillview Terrace Phase 2.",
    duration_ticks=288,
    antecedent_saturation=0.35,
    rainfall={"default": Curve.of((0, 0), (96, 2), (132, 3), (168, 0))},
    temperature=Curve.of((0, 24), (108, 31), (288, 25)),
    wind_speed=Curve.of((0, 6), (144, 14), (288, 8)),
    wind_direction_deg=225,
    river_flow_factor=Curve.of((0, 1.0)),
    forecasts=(
        ForecastUpdate(
            tick=0,
            horizon_h=24,
            expected_total_mm=12,
            peak_intensity_mm_h=3,
            confidence=0.8,
            summary="Light afternoon showers, about 12 mm over 24 h",
        ),
    ),
    excavation=Excavation(project_id="PR-HT2", start_tick=0, rate_m_per_h=0.05),
    stages=(
        Stage(
            name="steady_state",
            start_tick=0,
            description="Routine city operations under light monsoon showers",
        ),
    ),
)
