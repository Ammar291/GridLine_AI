"""Per-zone landslide and flood indices (ARCHITECTURE section 5), the minimal slice the DEMO controls need.

Each index is a weighted sum of factors clamped to [0, 1], read from the live world and the city's policy
thresholds, so a different world gives a different number. The indices are signals, not decisions. Weights and
band edges are named constants here; hysteresis, incidents and a config file belong to the full detector.
"""

from pydantic import BaseModel

from gridline.city.model import City
from gridline.events.envelope import Event
from gridline.events.payloads import ZoneStatePayload
from gridline.events.types import Band, EventType
from gridline.simulation.dynamics import slope_cut_m
from gridline.simulation.physics import EXC_REF_DEPTH_M, SLOPE_REF_DEG, clamp
from gridline.simulation.sensors import MakeEvent
from gridline.simulation.world import ChannelState, WorldState

DETECTOR_SOURCE = "threats:indices"
SAT_FLOOR = 0.5  # slope saturation below which the saturation factor is 0
CREEP_REF_MM_H = 30.0  # slope movement rate at which the movement factor is 1 (the critical sensor band)
WATER_REF_CM = 50.0  # standing water at which the water factor is 1 (the critical sensor band)
LANDSLIDE_WEIGHTS: dict[str, float] = {
    "saturation": 0.35,
    "rain_24h": 0.15,
    "cut": 0.2,
    "movement": 0.2,
    "steepness": 0.1,
}
FLOOD_WEIGHTS: dict[str, float] = {
    "rain": 0.15,
    "saturation": 0.1,
    "load": 0.35,
    "blocked": 0.15,
    "water": 0.25,
}


class BandThresholds(BaseModel):
    watch: float
    warning: float
    critical: float


class Bands(BaseModel):
    landslide: BandThresholds
    flood: BandThresholds


THRESHOLDS = BandThresholds(watch=0.35, warning=0.55, critical=0.75)
BANDS = Bands(landslide=THRESHOLDS, flood=THRESHOLDS)


def band_of(index: float) -> Band:
    if index >= THRESHOLDS.critical:
        return Band.CRITICAL
    if index >= THRESHOLDS.warning:
        return Band.WARNING
    return Band.WATCH if index >= THRESHOLDS.watch else Band.NORMAL


def landslide_index(world: WorldState, city: City, zone_id: str) -> float:
    """The worst slope of the zone; a zone without slopes has 0."""
    t, zone = city.thresholds, world.zones[zone_id]
    best = 0.0
    for slope in city.slopes:
        if slope.zone_id != zone_id:
            continue
        state = world.slopes[slope.id]
        factors = {
            "saturation": (state.saturation - SAT_FLOOR) / (t.saturation_critical - SAT_FLOOR),
            "rain_24h": zone.rain_24h_mm / t.rain_24h_critical_mm,
            "cut": slope_cut_m(world, city, slope.id) / EXC_REF_DEPTH_M,
            "movement": state.movement_rate_mm_h / CREEP_REF_MM_H,
            "steepness": (slope.mean_angle_deg - SLOPE_REF_DEG) / SLOPE_REF_DEG,
        }
        best = max(best, _weighted(factors, LANDSLIDE_WEIGHTS))
    return best


def flood_index(world: WorldState, city: City, zone_id: str) -> float:
    """Rain, soil and the drains that overflow into the zone (their ``downstream_zone_id``)."""
    t, zone = city.thresholds, world.zones[zone_id]
    channels = [world.channels[c.id] for c in city.channels if c.downstream_zone_id == zone_id]
    factors = {
        "rain": zone.rainfall_intensity_mm_h / t.rain_1h_warning_mm_h,
        "saturation": zone.saturation,
        "load": max((_load(c) for c in channels), default=0.0) / t.channel_ratio_critical,
        "blocked": max((c.blocked_fraction for c in channels), default=0.0),
        "water": zone.water_depth_cm / WATER_REF_CM,
    }
    return _weighted(factors, FLOOD_WEIGHTS)


def zone_state_events(world: WorldState, city: City, bands: dict[str, Band], make: MakeEvent) -> list[Event]:
    """One ``zone.state`` per zone in city order; ``bands`` holds each previous band, updated in place."""
    events: list[Event] = []
    for zone in city.zones:
        state = world.zones[zone.id]
        landslide, flood = landslide_index(world, city, zone.id), flood_index(world, city, zone.id)
        band = band_of(max(landslide, flood))
        payload = ZoneStatePayload(
            zone_id=zone.id,
            saturation=round(state.saturation, 3),
            rain_24h_mm=round(state.rain_24h_mm, 1),
            rain_intensity_mm_h=round(state.rainfall_intensity_mm_h, 2),
            landslide_index=landslide,
            flood_index=flood,
            band=band,
            prev_band=bands.get(zone.id),
            updated_sim_time=world.sim_time,
        )
        bands[zone.id] = band
        events.append(make(EventType.ZONE_STATE, payload, source=DETECTOR_SOURCE, location=zone.id))
    return events


def _load(channel: ChannelState) -> float:
    if channel.capacity_m3s > 0:
        return channel.flow_m3s / channel.capacity_m3s
    return 1.0 if channel.flow_m3s > 0 else 0.0


def _weighted(factors: dict[str, float], weights: dict[str, float]) -> float:
    return round(sum(weights[name] * clamp(value, 0.0, 1.0) for name, value in factors.items()), 3)
