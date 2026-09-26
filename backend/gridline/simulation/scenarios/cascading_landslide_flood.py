"""Primary demo, full cascade: rain -> Hillview saturation -> excavation at PR-HT2 -> creep on SL-HV-1 ->
landslide (only if the slope has actually moved) blocking D-7 -> Riverside flooding while the Kalinadi rises.
"""

from gridline.events.types import EventType
from gridline.simulation.scenarios.base import Condition, Curve, Scenario, ScenarioName, ScriptedEvent, Stage
from gridline.simulation.scenarios.hillside_landslide import (
    HILL_RESCUE_STANDBY,
    STORM_EXCAVATION,
    STORM_FORECASTS,
    STORM_RIVER_RISE,
    STORM_STAGES,
    STORM_TEMPERATURE,
    STORM_WIND,
    storm_rainfall,
)

LANDSLIDE_MOVEMENT_MM = 80.0  # cumulative creep on SL-HV-1 at which the scripted slope failure can occur


def _at(
    tick: int, event_type: EventType, condition: Condition | None = None, **payload: object
) -> ScriptedEvent:
    return ScriptedEvent(tick=tick, event_type=event_type, payload=payload, condition=condition)


CASCADING_LANDSLIDE_FLOOD = Scenario(
    name=ScenarioName.CASCADING_LANDSLIDE_FLOOD,
    title="Cascading landslide and flood",
    description=(
        "Excavation on SL-HV-1 in heavy rain; if the slope fails it blocks D-7 below Hill Road and Riverside "
        "floods while the Kalinadi rises."
    ),
    duration_ticks=300,
    antecedent_saturation=0.5,
    rainfall=storm_rainfall(((228, 15.0), (264, 6.0), (300, 0.0))),
    temperature=STORM_TEMPERATURE,
    wind_speed=STORM_WIND,
    wind_direction_deg=240,
    river_flow_factor=Curve.of(*STORM_RIVER_RISE, (180, 9.0), (228, 17.0), (264, 17.5), (300, 13.0)),
    forecasts=STORM_FORECASTS,
    excavation=STORM_EXCAVATION,
    stages=(
        *STORM_STAGES,
        Stage(
            name="landslide_and_blockage",
            start_tick=180,
            description="The saturated cut slope may fail into D-7 below Hill Road",
        ),
        Stage(
            name="downstream_flood",
            start_tick=204,
            description="D-7 overflows into Riverside while the Kalinadi rises",
        ),
    ),
    scripted=(
        HILL_RESCUE_STANDBY,
        _at(
            180,
            EventType.INFRASTRUCTURE_FAILURE,
            Condition(target_id="SL-HV-1", metric="slope_cumulative_mm", min_value=LANDSLIDE_MOVEMENT_MM),
            asset_id="SL-HV-1",
            asset_kind="slope",
            failure_kind="landslide",
            description="Hillview Terrace slope SL-HV-1 failed above D-7",
        ),
        _at(210, EventType.EMERGENCY_HOSPITAL, hospital_id="H-2", beds_occupied=70, er_status="busy"),
        _at(
            216,
            EventType.EMERGENCY_AMBULANCE,
            ambulance_id="AMB-06",
            status="dispatched",
            location_zone_id="Z-RS",
        ),
        _at(
            228,
            EventType.INFRASTRUCTURE_BRIDGE,
            Condition(target_id="R-1", metric="river_level_m", min_value=5.0),
            bridge_id="BR-1",
            status="closed",
            reason="Kalinadi at the 5.0 m closure stage at RV-01",
        ),
        _at(
            234,
            EventType.INFRASTRUCTURE_ROAD,
            Condition(target_id="Z-RS", metric="water_depth_cm", min_value=30.0),
            road_id="RD-02",
            status="blocked",
            reason="flood water over the carriageway",
        ),
        _at(
            240,
            EventType.EMERGENCY_RESCUE_TEAM,
            crew_id="C-4",
            status="on_site",
            location_zone_id="Z-RS",
            task="evacuation support in Riverside",
        ),
        _at(246, EventType.EMERGENCY_HOSPITAL, hospital_id="H-2", beds_occupied=78, er_status="overwhelmed"),
    ),
)
