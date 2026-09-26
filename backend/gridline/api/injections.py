"""Operator injection presets for the dashboard's Inject menu.

Each preset is a ready-made ``POST /api/simulation/inject`` body naming data-layer assets, for demoing how the
city (and later the agent) reacts to a disruption. They are scripted operator events, never conclusions.
"""

from pydantic import BaseModel

from gridline.api.simulation_models import InjectRequest
from gridline.events.types import EventType


class InjectionPreset(BaseModel):
    id: str
    label: str
    description: str
    request: InjectRequest


def _preset(
    id: str, label: str, description: str, event_type: EventType, payload: dict[str, object]
) -> InjectionPreset:
    return InjectionPreset(
        id=id,
        label=label,
        description=description,
        request=InjectRequest(event_type=event_type, payload=payload),
    )


INJECTION_PRESETS: tuple[InjectionPreset, ...] = (
    _preset(
        "culvert_blocked",
        "Culvert blocked on D-7",
        "Debris jams the Kalinadi drain D-7 at the Hill Road culvert (BR-4), cutting its capacity.",
        EventType.INFRASTRUCTURE_DRAINAGE_OBSTRUCTION,
        {"channel_id": "D-7", "blocked_fraction": 0.6, "cause": "debris jammed at the BR-4 culvert"},
    ),
    _preset(
        "crew_route_blocked",
        "Hill Road blocked",
        "Rockfall blocks Hill Road (RD-01), the only access to Hillview, so crews cannot reach the slope.",
        EventType.INFRASTRUCTURE_ROAD,
        {"road_id": "RD-01", "status": "blocked", "reason": "rockfall on Hill Road"},
    ),
    _preset(
        "crew_delayed",
        "Rescue team C-4 blocked",
        "The Hill Rescue Team (C-4) is held up on its way to Hillview.",
        EventType.EMERGENCY_RESCUE_TEAM,
        {
            "crew_id": "C-4",
            "status": "blocked",
            "location_zone_id": "Z-RS",
            "task": "route to Hillview blocked",
        },
    ),
    _preset(
        "bridge_closed",
        "Kalinadi Bridge closed",
        "Kalinadi Bridge (BR-1) closes for a scour inspection, cutting Old Town off from the south bank.",
        EventType.INFRASTRUCTURE_BRIDGE,
        {"bridge_id": "BR-1", "status": "closed", "reason": "emergency scour inspection"},
    ),
    _preset(
        "slope_failure",
        "Landslide at Hillview Terrace",
        "Forces the Hillview Terrace slope (SL-HV-1) to fail now: debris blocks D-7 and Hill Road.",
        EventType.INFRASTRUCTURE_FAILURE,
        {
            "asset_id": "SL-HV-1",
            "asset_kind": "slope",
            "failure_kind": "landslide",
            "description": "Operator-injected failure of the Hillview Terrace slope above D-7",
        },
    ),
)
