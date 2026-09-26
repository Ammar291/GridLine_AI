"""State-changing events (spec §7.2): validate ids against the city, fill city-derived fields, mutate the
world, and return the event plus any derived events (``source="simulation:engine"``).

The emitted location is always the asset's zone; a contradicting requested location is ignored.
"""

from collections.abc import Callable
from dataclasses import dataclass

from gridline.city.model import City
from gridline.errors import InvalidPayload, NotInjectable
from gridline.events import payloads as p
from gridline.events.envelope import Event
from gridline.events.types import EventType, Severity
from gridline.simulation.sensors import ENGINE_SOURCE, MakeEvent
from gridline.simulation.world import (
    AmbulanceState,
    BridgeState,
    CrewState,
    HospitalState,
    RoadState,
    ShelterState,
    WorldState,
)

LANDSLIDE_DISPLACEMENT_MM = 1500.0  # slope movement added by a landslide
LANDSLIDE_RATE_MM_H = 500.0  # movement rate reported in the tick of the failure
LANDSLIDE_BLOCKAGE = 0.7  # minimum blocked fraction of the slope's toe channel after a landslide
LANDSLIDE_REASON = "landslide debris"


@dataclass(frozen=True)
class _Ctx:
    world: WorldState
    city: City
    source: str
    severity: Severity | None
    location: str | None
    make: MakeEvent

    def emit(self, event_type: EventType, payload: p.Payload, location: str | None) -> Event:
        return self.make(event_type, payload, source=self.source, location=location, severity=self.severity)

    def derive(self, event_type: EventType, payload: p.Payload, location: str | None) -> Event:
        return self.make(event_type, payload, source=ENGINE_SOURCE, location=location)


def apply_event(
    world: WorldState,
    city: City,
    event_type: EventType,
    payload: p.Payload,
    *,
    source: str,
    location: str | None,
    severity: Severity | None,
    make: MakeEvent,
) -> list[Event]:
    handler = _HANDLERS.get(event_type)
    if handler is None:
        raise NotInjectable(f"{event_type} is derived from state and cannot be injected")
    return handler(_Ctx(world, city, source, severity, location, make), payload)


def _forecast(ctx: _Ctx, f: p.Payload) -> list[Event]:
    assert isinstance(f, p.WeatherForecast)
    if ctx.location is not None:
        ctx.city.zone(ctx.location)
    ctx.world.forecast = f
    return [ctx.emit(EventType.WEATHER_FORECAST, f, ctx.location)]


def _road(ctx: _Ctx, r: p.Payload) -> list[Event]:
    assert isinstance(r, p.RoadStatus)
    road = ctx.city.road(r.road_id)
    ctx.world.roads[road.id] = RoadState(status=r.status, reason=r.reason)
    filled = r.model_copy(update={"is_evacuation_route": road.is_evacuation_route})
    return [ctx.emit(EventType.INFRASTRUCTURE_ROAD, filled, road.zone_id)]


def _bridge(ctx: _Ctx, b: p.Payload) -> list[Event]:
    assert isinstance(b, p.BridgeStatus)
    bridge = ctx.city.bridge(b.bridge_id)
    ctx.world.bridges[bridge.id] = BridgeState(status=b.status, reason=b.reason)
    return [ctx.emit(EventType.INFRASTRUCTURE_BRIDGE, b, bridge.zone_id)]


def _obstruction(ctx: _Ctx, o: p.Payload) -> list[Event]:
    assert isinstance(o, p.DrainageObstruction)
    channel = ctx.city.channel(o.channel_id)
    ctx.world.channels[channel.id].blocked_fraction = o.blocked_fraction
    return [ctx.emit(EventType.INFRASTRUCTURE_DRAINAGE_OBSTRUCTION, o, channel.zone_id)]


def _construction(ctx: _Ctx, c: p.Payload) -> list[Event]:
    assert isinstance(c, p.ConstructionActivity)
    project = ctx.city.project(c.project_id)
    state = ctx.world.projects[project.id]
    state.status = c.status
    if c.status == "halted":
        state.activity = "halted"  # halting freezes the cut; the depth reached stays
    else:
        state.activity = "idle" if c.activity == "halted" else c.activity
        state.excavation_depth_m = min(c.excavation_depth_m, project.planned_depth_m)
    filled = c.model_copy(
        update={
            "activity": state.activity,
            "excavation_depth_m": round(state.excavation_depth_m, 2),
            "planned_depth_m": project.planned_depth_m,
        }
    )
    return [ctx.emit(EventType.INFRASTRUCTURE_CONSTRUCTION, filled, project.zone_id)]


def _failure(ctx: _Ctx, f: p.Payload) -> list[Event]:
    assert isinstance(f, p.InfrastructureFailure)
    city, world = ctx.city, ctx.world
    zone_of: dict[str, Callable[[str], str]] = {
        "slope": lambda i: city.slope(i).zone_id,
        "channel": lambda i: city.channel(i).zone_id,
        "bridge": lambda i: city.bridge(i).zone_id,
        "road": lambda i: city.road(i).zone_id,
        "power": lambda i: city.substation(i).zone_id,
    }
    zone_id = zone_of[f.asset_kind](f.asset_id)
    events = [ctx.emit(EventType.INFRASTRUCTURE_FAILURE, f, zone_id)]
    if f.failure_kind == "culvert_collapse" and f.asset_kind == "channel":
        world.channels[f.asset_id].blocked_fraction = 1.0
        obstruction = p.DrainageObstruction(
            channel_id=f.asset_id, blocked_fraction=1.0, cause="culvert collapse"
        )
        events.append(ctx.derive(EventType.INFRASTRUCTURE_DRAINAGE_OBSTRUCTION, obstruction, zone_id))
    if f.failure_kind == "landslide" and f.asset_kind == "slope":
        events += _landslide(ctx, f.asset_id)
    return events


def _landslide(ctx: _Ctx, slope_id: str) -> list[Event]:
    city, world = ctx.city, ctx.world
    slope = city.slope(slope_id)
    state = world.slopes[slope_id]
    state.cumulative_movement_mm += LANDSLIDE_DISPLACEMENT_MM
    state.movement_rate_mm_h = LANDSLIDE_RATE_MM_H
    events: list[Event] = []
    if slope.toe_channel_id is not None:
        channel = city.channel(slope.toe_channel_id)
        channel_state = world.channels[channel.id]
        channel_state.blocked_fraction = max(channel_state.blocked_fraction, LANDSLIDE_BLOCKAGE)
        cause = f"{LANDSLIDE_REASON} from {slope_id}"
        obstruction = p.DrainageObstruction(
            channel_id=channel.id, blocked_fraction=channel_state.blocked_fraction, cause=cause
        )
        events.append(ctx.derive(EventType.INFRASTRUCTURE_DRAINAGE_OBSTRUCTION, obstruction, channel.zone_id))
    for road in city.roads_in(slope.zone_id):
        if road.is_only_access:
            world.roads[road.id] = RoadState(status="blocked", reason=LANDSLIDE_REASON)
            status = p.RoadStatus(
                road_id=road.id,
                status="blocked",
                reason=LANDSLIDE_REASON,
                is_evacuation_route=road.is_evacuation_route,
            )
            events.append(ctx.derive(EventType.INFRASTRUCTURE_ROAD, status, road.zone_id))
    for bridge in city.bridges_in(slope.zone_id):
        world.bridges[bridge.id] = BridgeState(status="closed", reason=LANDSLIDE_REASON)
        closed = p.BridgeStatus(bridge_id=bridge.id, status="closed", reason=LANDSLIDE_REASON)
        events.append(ctx.derive(EventType.INFRASTRUCTURE_BRIDGE, closed, bridge.zone_id))
    for project in city.projects_in(slope.zone_id):
        project_state = world.projects[project.id]
        if project_state.status == "active":
            project_state.status, project_state.activity = "halted", "halted"
            halted = p.ConstructionActivity(
                project_id=project.id,
                status="halted",
                activity="halted",
                excavation_depth_m=round(project_state.excavation_depth_m, 2),
                planned_depth_m=project.planned_depth_m,
            )
            events.append(ctx.derive(EventType.INFRASTRUCTURE_CONSTRUCTION, halted, project.zone_id))
    return events


def _rescue_team(ctx: _Ctx, r: p.Payload) -> list[Event]:
    assert isinstance(r, p.RescueTeamStatus)
    crew = ctx.city.crew(r.crew_id)
    zone = ctx.city.zone(r.location_zone_id)
    ctx.world.crews[crew.id] = CrewState(status=r.status, location_zone_id=zone.id, task=r.task)
    return [ctx.emit(EventType.EMERGENCY_RESCUE_TEAM, r, zone.id)]


def _ambulance(ctx: _Ctx, a: p.Payload) -> list[Event]:
    assert isinstance(a, p.AmbulanceStatus)
    ambulance = ctx.city.ambulance(a.ambulance_id)
    zone = ctx.city.zone(a.location_zone_id)
    ctx.world.ambulances[ambulance.id] = AmbulanceState(status=a.status, location_zone_id=zone.id)
    fleet = [x.id for x in ctx.city.ambulances if x.hospital_id == ambulance.hospital_id]
    available = sum(1 for x in fleet if ctx.world.ambulances[x].status == "available")
    filled = a.model_copy(
        update={
            "hospital_id": ambulance.hospital_id,
            "available_count": available,
            "total_count": len(fleet),
        }
    )
    return [ctx.emit(EventType.EMERGENCY_AMBULANCE, filled, zone.id)]


def _hospital(ctx: _Ctx, h: p.Payload) -> list[Event]:
    assert isinstance(h, p.HospitalCapacity)
    hospital = ctx.city.hospital(h.hospital_id)
    if h.beds_occupied > hospital.beds_total:
        raise InvalidPayload(f"hospital {hospital.id} has {hospital.beds_total} beds, not {h.beds_occupied}")
    ctx.world.hospitals[hospital.id] = HospitalState(beds_occupied=h.beds_occupied, er_status=h.er_status)
    filled = h.model_copy(
        update={
            "beds_total": hospital.beds_total,
            "beds_available": hospital.beds_total - h.beds_occupied,
        }
    )
    return [ctx.emit(EventType.EMERGENCY_HOSPITAL, filled, hospital.zone_id)]


def _shelter(ctx: _Ctx, s: p.Payload) -> list[Event]:
    assert isinstance(s, p.ShelterCapacity)
    shelter = ctx.city.shelter(s.shelter_id)
    if s.occupancy > shelter.capacity:
        raise InvalidPayload(f"shelter {shelter.id} holds {shelter.capacity} people, not {s.occupancy}")
    ctx.world.shelters[shelter.id] = ShelterState(status=s.status, occupancy=s.occupancy)
    filled = s.model_copy(update={"capacity": shelter.capacity})
    return [ctx.emit(EventType.EMERGENCY_SHELTER, filled, shelter.zone_id)]


_HANDLERS: dict[EventType, Callable[[_Ctx, p.Payload], list[Event]]] = {
    EventType.WEATHER_FORECAST: _forecast,
    EventType.INFRASTRUCTURE_ROAD: _road,
    EventType.INFRASTRUCTURE_BRIDGE: _bridge,
    EventType.INFRASTRUCTURE_DRAINAGE_OBSTRUCTION: _obstruction,
    EventType.INFRASTRUCTURE_CONSTRUCTION: _construction,
    EventType.INFRASTRUCTURE_FAILURE: _failure,
    EventType.EMERGENCY_RESCUE_TEAM: _rescue_team,
    EventType.EMERGENCY_AMBULANCE: _ambulance,
    EventType.EMERGENCY_HOSPITAL: _hospital,
    EventType.EMERGENCY_SHELTER: _shelter,
}
