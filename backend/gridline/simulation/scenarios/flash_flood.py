"""Secondary demo: a cloudburst over the eastern hills while D-7 runs through the culvert narrowed in 2025."""

from gridline.events.types import EventType
from gridline.simulation.scenarios.base import (
    Condition,
    Curve,
    ForecastUpdate,
    Scenario,
    ScenarioName,
    ScriptedEvent,
    Stage,
)

CLOUDBURST_POINTS = (
    (0, 5.0),
    (60, 5.0),
    (84, 25.0),
    (96, 55.0),
    (108, 55.0),
    (120, 20.0),
    (138, 6.0),
    (168, 0.0),
)


def _share(factor: float) -> Curve:
    return Curve.of(*((t, round(v * factor, 2)) for t, v in CLOUDBURST_POINTS))


FLASH_FLOOD = Scenario(
    name=ScenarioName.FLASH_FLOOD,
    title="Flash flood",
    description="A cloudburst over Hillview and Riverside while D-7 is limited by the BR-4 culvert.",
    duration_ticks=240,
    antecedent_saturation=0.45,
    rainfall={"Z-HV": _share(1.0), "Z-RS": _share(1.0), "Z-TH": _share(0.5), "default": _share(0.2)},
    temperature=Curve.of((0, 27), (96, 23), (240, 24)),
    wind_speed=Curve.of((0, 10), (96, 35), (240, 15)),
    wind_direction_deg=210,
    river_flow_factor=Curve.of((0, 1.0), (132, 2.5), (240, 2.0)),
    forecasts=(
        ForecastUpdate(
            tick=0,
            horizon_h=24,
            expected_total_mm=40,
            peak_intensity_mm_h=15,
            confidence=0.6,
            summary="Scattered heavy showers, about 40 mm in 24 h",
        ),
        ForecastUpdate(
            tick=40,
            horizon_h=6,
            expected_total_mm=150,
            peak_intensity_mm_h=55,
            confidence=0.9,
            summary="Cloudburst warning for Hillview, Tekri Heights and Riverside: 150 mm in 6 h",
        ),
    ),
    stages=(
        Stage(
            name="culvert_constraint",
            start_tick=0,
            description="D-7 runs through the BR-4 culvert narrowed in 2025",
        ),
        Stage(name="severe_rain", start_tick=48, description="A cloudburst builds over the eastern hills"),
        Stage(
            name="drain_overload",
            start_tick=96,
            description="D-7 carries more than the BR-4 culvert can pass",
        ),
        Stage(name="riverside_flooding", start_tick=132, description="Water ponds across Riverside"),
    ),
    scripted=(
        ScriptedEvent(
            tick=12,
            event_type=EventType.INFRASTRUCTURE_DRAINAGE_OBSTRUCTION,
            payload={
                "channel_id": "D-7",
                "blocked_fraction": 0.25,
                "cause": "monsoon debris caught at the BR-4 culvert",
            },
        ),
        ScriptedEvent(
            tick=132,
            event_type=EventType.INFRASTRUCTURE_ROAD,
            payload={"road_id": "RD-02", "status": "blocked", "reason": "standing water"},
            condition=Condition(target_id="Z-RS", metric="water_depth_cm", min_value=30.0),
        ),
        ScriptedEvent(
            tick=140,
            event_type=EventType.EMERGENCY_HOSPITAL,
            payload={"hospital_id": "H-2", "beds_occupied": 72, "er_status": "busy"},
        ),
        ScriptedEvent(
            tick=144,
            event_type=EventType.EMERGENCY_AMBULANCE,
            payload={"ambulance_id": "AMB-06", "status": "dispatched", "location_zone_id": "Z-RS"},
        ),
        ScriptedEvent(
            tick=150,
            event_type=EventType.EMERGENCY_RESCUE_TEAM,
            payload={
                "crew_id": "C-4",
                "status": "on_site",
                "location_zone_id": "Z-RS",
                "task": "helping residents out of standing water",
            },
        ),
    ),
)
