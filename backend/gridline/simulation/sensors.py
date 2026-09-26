"""Sensors sample the world with seeded noise (spec §5.3) and become observation events.

Sensors are the data layer's (RG-*, WS-01, SM-*, CL-*, RV-*), iterated in id order so the stream is
deterministic. The data layer has no inclinometers or flood-depth gauges, so slope movement (for slopes
with soil probes) and ponded water (per zone) are reported as model observations from ``simulation:engine``.
"""

import random
from typing import Protocol

from gridline.city.model import City, Sensor
from gridline.events.envelope import Event
from gridline.events.payloads import (
    DrainageObservation,
    Payload,
    RiverObservation,
    SlopeObservation,
    SoilObservation,
    WaterAccumulation,
    WeatherObservation,
)
from gridline.events.types import EventType, Severity
from gridline.simulation.physics import clamp
from gridline.simulation.world import WorldState

ENGINE_SOURCE = "simulation:engine"
SIGMA_RAIN_MM_H = 0.3
SIGMA_TEMPERATURE_C = 0.2
SIGMA_WIND_KMH = 0.8
SIGMA_SOIL_PCT = 0.5
SIGMA_FLOW_SHARE = 0.02  # channel flow noise as a share of the flow
SIGMA_RIVER_M = 0.02
SIGMA_SLOPE_MM_H = 0.1
POROSITY_PCT = 45.0  # volumetric soil moisture at full saturation
MAX_LOAD_RATIO = 10.0  # reported load ratio when a channel has no capacity left


class MakeEvent(Protocol):
    def __call__(
        self,
        event_type: EventType,
        payload: Payload,
        *,
        source: str,
        location: str | None,
        severity: Severity | None = None,
    ) -> Event: ...


def observe(world: WorldState, city: City, rng: random.Random, make: MakeEvent) -> list[Event]:
    events: list[Event] = []
    for sensor in sorted(city.sensors, key=lambda s: s.id):
        event_type, payload = _reading(world, city, sensor, rng)
        events.append(make(event_type, payload, source=f"sensor:{sensor.id}", location=sensor.zone_id))
    monitored = sorted({s.target_id for s in city.sensors if s.kind == "soil_moisture"})
    for slope_id in monitored:
        state = world.slopes[slope_id]
        rate = _noisy(state.movement_rate_mm_h, SIGMA_SLOPE_MM_H, rng)
        payload = SlopeObservation(
            slope_id=slope_id,
            movement_rate_mm_h=round(rate, 2),
            cumulative_movement_mm=round(state.cumulative_movement_mm, 2),
            saturation=round(state.saturation, 3),
        )
        events.append(
            make(
                EventType.ENVIRONMENT_SLOPE,
                payload,
                source=ENGINE_SOURCE,
                location=city.slope(slope_id).zone_id,
            )
        )
    for zone in city.zones:
        state = world.zones[zone.id]
        if state.water_depth_cm > 0 or state.water_trend == "falling":  # falling to 0 is the final reading
            payload = WaterAccumulation(
                zone_id=zone.id, depth_cm=round(state.water_depth_cm, 1), trend=state.water_trend
            )
            events.append(
                make(
                    EventType.ENVIRONMENT_WATER_ACCUMULATION, payload, source=ENGINE_SOURCE, location=zone.id
                )
            )
    return events


def _noisy(value: float, sigma: float, rng: random.Random) -> float:
    """Gaussian noise on a positive reading; a zero reading stays zero (the draw is still taken)."""
    noise = rng.gauss(0.0, sigma)
    return max(0.0, value + noise) if value > 0 else 0.0


def _reading(world: WorldState, city: City, sensor: Sensor, rng: random.Random) -> tuple[EventType, Payload]:
    match sensor.kind:
        case "rain_gauge":
            zone = world.zones[sensor.target_id]
            return EventType.WEATHER_OBSERVATION, WeatherObservation(
                station_id=sensor.id,
                rainfall_intensity_mm_h=round(_noisy(zone.rainfall_intensity_mm_h, SIGMA_RAIN_MM_H, rng), 2),
                cumulative_rainfall_24h_mm=round(zone.rain_24h_mm, 1),
            )
        case "wind":
            weather = world.weather
            return EventType.WEATHER_OBSERVATION, WeatherObservation(
                station_id=sensor.id,
                temperature_c=round(weather.temperature_c + rng.gauss(0.0, SIGMA_TEMPERATURE_C), 1),
                wind_speed_kmh=round(_noisy(weather.wind_speed_kmh, SIGMA_WIND_KMH, rng), 1),
                wind_direction_deg=weather.wind_direction_deg % 360,
            )
        case "soil_moisture":
            slope = world.slopes[sensor.target_id]
            pct = clamp(POROSITY_PCT * slope.saturation + rng.gauss(0.0, SIGMA_SOIL_PCT), 0.0, POROSITY_PCT)
            return EventType.ENVIRONMENT_SOIL, SoilObservation(
                probe_id=sensor.id,
                slope_id=sensor.target_id,
                soil_moisture_pct=round(pct, 2),
                saturation=round(pct / POROSITY_PCT, 3),
            )
        case "channel_level":
            channel = world.channels[sensor.target_id]
            flow = max(0.0, channel.flow_m3s * (1 + rng.gauss(0.0, SIGMA_FLOW_SHARE)))
            capacity = channel.capacity_m3s
            ratio = flow / capacity if capacity > 0 else (0.0 if flow == 0 else MAX_LOAD_RATIO)
            return EventType.ENVIRONMENT_DRAINAGE, DrainageObservation(
                gauge_id=sensor.id,
                channel_id=sensor.target_id,
                flow_m3s=round(flow, 2),
                capacity_m3s=round(capacity, 2),
                load_ratio=round(min(ratio, MAX_LOAD_RATIO), 3),
                blocked_fraction=channel.blocked_fraction,
                overflow_m3s=round(max(0.0, flow - capacity), 2),
            )
        case "river_level":
            river = city.river(sensor.target_id)
            state = world.rivers[river.id]
            return EventType.ENVIRONMENT_RIVER, RiverObservation(
                gauge_id=sensor.id,
                river_id=river.id,
                level_m=round(max(0.0, state.level_m + rng.gauss(0.0, SIGMA_RIVER_M)), 2),
                flood_stage_m=river.flood_stage_m,
                warning_level_m=river.warning_stage_m,
                danger_level_m=river.danger_stage_m,
                trend=state.trend,
            )
