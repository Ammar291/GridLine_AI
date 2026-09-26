"""One physics step over the whole world (spec §5.2 per-tick order), using the pure functions in ``physics``.

Order: drivers -> saturation (zones, then slopes with their cuts) -> channel flow and overflow, tributaries
first -> ponding in each channel's downstream zone -> river level from upstream flow plus channel outfalls.
"""

from gridline.city.model import City, DrainageChannel
from gridline.events.payloads import Trend
from gridline.simulation import physics as ph
from gridline.simulation.scenarios.base import Scenario
from gridline.simulation.world import WeatherState, WorldState

TREND_EPSILON = 0.001  # smallest per-tick change reported as rising or falling


def trend(before: float, after: float) -> Trend:
    if after - before > TREND_EPSILON:
        return "rising"
    return "falling" if before - after > TREND_EPSILON else "steady"


def weather_at(scenario: Scenario, tick: int) -> WeatherState:
    return WeatherState(
        temperature_c=scenario.temperature.at(tick),
        wind_speed_kmh=max(0.0, scenario.wind_speed.at(tick)),
        wind_direction_deg=scenario.wind_direction_deg,
    )


def apply_drivers(world: WorldState, city: City, scenario: Scenario, tick: int, dt_h: float) -> None:
    """Scenario rain per zone (and its 24 h window) and city-wide weather for this tick."""
    for zone in city.zones:
        state = world.zones[zone.id]
        state.rainfall_intensity_mm_h = scenario.rain_at(zone.id, tick)
        window = world.rain_window[zone.id]
        window.append(state.rainfall_intensity_mm_h * dt_h)
        state.rain_24h_mm = sum(window)
    world.weather = weather_at(scenario, tick)


def slope_cut_m(world: WorldState, city: City, slope_id: str) -> float:
    """Deepest unsupported cut of any project on the slope; halting freezes a cut, it does not fill it."""
    slope = city.slope(slope_id)
    cuts = [
        ph.unsupported_cut_m(world.projects[p.id].excavation_depth_m, slope.soil_depth_m)
        for p in city.projects
        if p.slope_id == slope_id
    ]
    return max(cuts, default=0.0)


def step_physics(world: WorldState, city: City, scenario: Scenario, tick: int, dt_h: float) -> None:
    for zone in city.zones:
        state = world.zones[zone.id]
        rain_mm = state.rainfall_intensity_mm_h * dt_h
        state.saturation = ph.step_saturation(
            state.saturation, rain_mm, k_in=ph.K_IN[zone.permeability_class], cut_m=0.0, dt_h=dt_h
        )
    for slope in city.slopes:
        zone = city.zone(slope.zone_id)
        state = world.slopes[slope.id]
        cut = slope_cut_m(world, city, slope.id)
        rain_mm = world.zones[zone.id].rainfall_intensity_mm_h * dt_h
        state.saturation = ph.step_saturation(
            state.saturation, rain_mm, k_in=ph.K_IN[zone.permeability_class], cut_m=cut, dt_h=dt_h
        )
        state.movement_rate_mm_h = ph.slope_rate_mm_h(state.saturation, slope.mean_angle_deg, cut)
        state.cumulative_movement_mm += state.movement_rate_mm_h * dt_h
    conveyed = _route_channels(world, city)
    _pond(world, city, dt_h)
    _step_rivers(world, city, scenario, tick, conveyed)


def _route_channels(world: WorldState, city: City) -> dict[str, float]:
    """Flow, capacity and overflow per channel; returns what each channel passes on downstream."""
    conveyed: dict[str, float] = {}
    for channel in city.channels_upstream_first():
        state = world.channels[channel.id]
        runoff = sum(
            ph.runoff_flow_m3s(
                world.zones[z.id].rainfall_intensity_mm_h,
                world.zones[z.id].saturation,
                z.area_km2,
                z.impervious_fraction,
            )
            for z in city.zones_draining_to(channel.id)
        )
        inflow = runoff + sum(conveyed[t.id] for t in city.channels_outfalling_to(channel.id))
        gate_stage = channel.gate_closes_at_river_stage_m
        state.gate_closed = gate_stage is not None and _outfall_level(world, city, channel) >= gate_stage
        state.capacity_m3s = ph.channel_capacity_m3s(
            channel.current_capacity_m3s,
            state.blocked_fraction,
            state.extra_capacity_m3s,
            gate_closed=state.gate_closed,
            pumped=channel.pumped_capacity_m3s,
        )
        state.flow_m3s = inflow
        state.overflow_m3s = max(0.0, inflow - state.capacity_m3s)
        conveyed[channel.id] = inflow - state.overflow_m3s
    return conveyed


def _outfall_level(world: WorldState, city: City, channel: DrainageChannel) -> float:
    """Stage of the river the channel finally drains to, via outfall channels; 0 if none is modelled."""
    current: DrainageChannel | None = channel
    while current is not None:
        if current.outfall_river_id is not None and current.outfall_river_id in world.rivers:
            return world.rivers[current.outfall_river_id].level_m
        current = city.channel(current.outfall_channel_id) if current.outfall_channel_id else None
    return 0.0


def _pond(world: WorldState, city: City, dt_h: float) -> None:
    overflow: dict[str, float] = {}
    for channel in city.channels:
        zone_id = channel.downstream_zone_id
        overflow[zone_id] = overflow.get(zone_id, 0.0) + world.channels[channel.id].overflow_m3s
    for zone in city.zones:
        state = world.zones[zone.id]
        before = state.water_depth_cm
        state.water_depth_cm = ph.step_water_depth(before, overflow.get(zone.id, 0.0), dt_h)
        state.water_trend = trend(before, state.water_depth_cm)


def _step_rivers(
    world: WorldState, city: City, scenario: Scenario, tick: int, conveyed: dict[str, float]
) -> None:
    factor = max(0.0, scenario.river_flow_factor.at(tick))
    for river in city.rivers:
        state = world.rivers[river.id]
        outfalls = sum(conveyed[c.id] for c in city.channels if c.outfall_river_id == river.id)
        state.inflow_m3s = river.ordinary_flow_m3s * factor + outfalls
        target = ph.rating_stage_m(
            state.inflow_m3s,
            ordinary_flow=river.ordinary_flow_m3s,
            ordinary_stage=river.ordinary_stage_m,
            bankfull_flow=river.bankfull_flow_m3s,
            flood_stage=river.flood_stage_m,
        )
        before = state.level_m
        state.level_m = ph.step_river_level(before, target)
        state.trend = trend(before, state.level_m)
