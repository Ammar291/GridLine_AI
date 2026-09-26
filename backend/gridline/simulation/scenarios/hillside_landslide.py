"""Primary demo, first half: PR-HT2 keeps excavating SL-HV-1 while monsoon rain saturates Hillview.

The storm, excavation, forecasts and stages 0-3 are shared with ``cascading_landslide_flood``. No landslide is
scripted here: the scenario ends with the slope creeping at the critical stage.
"""

from gridline.events.types import EventType
from gridline.simulation.scenarios.base import (
    Curve,
    Excavation,
    ForecastUpdate,
    Scenario,
    ScenarioName,
    ScriptedEvent,
    Stage,
)

# mm/h over Hillview (RG-02); other zones get a share of it (the storm cell sits over the eastern hills)
STORM_RAIN = ((0, 3.0), (36, 3.0), (72, 8.25), (96, 12.0), (144, 15.0), (216, 15.0))
RIVERSIDE_SHARE = 0.8
TEKRI_SHARE = 0.8
ELSEWHERE_SHARE = 0.5


def storm_rainfall(tail: tuple[tuple[int, float], ...]) -> dict[str, Curve]:
    points = STORM_RAIN + tail

    def share(factor: float) -> Curve:
        return Curve.of(*((t, round(v * factor, 2)) for t, v in points))

    return {
        "Z-HV": share(1.0),
        "Z-RS": share(RIVERSIDE_SHARE),
        "Z-TH": share(TEKRI_SHARE),
        "default": share(ELSEWHERE_SHARE),
    }


STORM_TEMPERATURE = Curve.of((0, 26), (96, 22), (216, 21), (300, 24))
STORM_WIND = Curve.of((0, 8), (120, 28), (300, 12))
STORM_EXCAVATION = Excavation(project_id="PR-HT2", start_tick=0, rate_m_per_h=0.15)
STORM_FORECASTS = (
    ForecastUpdate(
        tick=0,
        horizon_h=24,
        expected_total_mm=60,
        peak_intensity_mm_h=12,
        confidence=0.7,
        summary="Moderate monsoon rain over the eastern hills, about 60 mm in 24 h",
    ),
    ForecastUpdate(
        tick=30,
        horizon_h=24,
        expected_total_mm=180,
        peak_intensity_mm_h=25,
        confidence=0.85,
        summary="Heavy rain warning for Hillview and Tekri Heights: 150-200 mm in 24 h",
    ),
)
STORM_STAGES = (
    Stage(
        name="construction_and_rain",
        start_tick=0,
        description="Excavation continues at PR-HT2 on SL-HV-1 as monsoon rain begins",
    ),
    Stage(
        name="intensifying_rain", start_tick=36, description="Rain intensifies and Hillview soils saturate"
    ),
    Stage(name="slope_creep", start_tick=96, description="The cut slope SL-HV-1 begins to creep"),
    Stage(name="critical_slope", start_tick=144, description="Saturation and creep on SL-HV-1 keep rising"),
)
HILL_RESCUE_STANDBY = ScriptedEvent(
    tick=150,
    event_type=EventType.EMERGENCY_RESCUE_TEAM,
    payload={
        "crew_id": "C-4",
        "status": "available",
        "location_zone_id": "Z-RS",
        "task": "monsoon standby at the Riverside base",
    },
)
STORM_RIVER_RISE = ((0, 1.0), (96, 2.0), (144, 3.5))

HILLSIDE_LANDSLIDE = Scenario(
    name=ScenarioName.HILLSIDE_LANDSLIDE,
    title="Hillside landslide risk",
    description="Hillview Terrace Phase 2 keeps excavating the 32 degree slope SL-HV-1 as rain rises.",
    duration_ticks=288,
    antecedent_saturation=0.5,
    rainfall=storm_rainfall(((252, 4.0), (288, 0.0))),
    temperature=STORM_TEMPERATURE,
    wind_speed=STORM_WIND,
    wind_direction_deg=240,
    river_flow_factor=Curve.of(*STORM_RIVER_RISE, (216, 4.0), (288, 3.0)),
    forecasts=STORM_FORECASTS,
    excavation=STORM_EXCAVATION,
    stages=STORM_STAGES,
    scripted=(HILL_RESCUE_STANDBY,),
)
