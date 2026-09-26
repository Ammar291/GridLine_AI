"""Fixed-threshold sensor bands (spec §3.3). A severity labels one reading; it is never a threat assessment.

Policy bands map to severities as watch -> moderate, warning -> high, critical -> critical. The policy numbers
come from ``City.thresholds`` (policy_thresholds.yaml); the sub-watch ``low`` bands below are local constants.
"""

from collections.abc import Callable, Sequence

from pydantic import BaseModel

from gridline.city.model import PolicyThresholds
from gridline.events import payloads as p
from gridline.events.types import SEVERITY_ORDER, Band, EventType, Severity

RAIN_LOW_MM_H = 10.0  # below this rainfall intensity a reading is info
WIND_LOW_KMH = 40.0  # below this sustained wind a reading is info
SATURATION_LOW = 0.5  # soil saturation bands below the policy warning (0.70)
SATURATION_MODERATE = 0.6
CHANNEL_LOW = 0.6  # channel load ratio below the policy watch (0.8)
RIVER_LOW_SHARE = 0.8  # share of flood stage from which a river reading is low
SLOPE_BANDS_MM_H = (0.5, 2.0, 10.0, 30.0)  # low, moderate, high, critical lower bounds
WATER_LOW_CM = 1.0
WATER_MODERATE_CM = 10.0
WATER_CRITICAL_CM = 50.0
OBSTRUCTION_BANDS = (0.1, 0.25, 0.5, 0.8)  # blocked fraction: low, moderate, high, critical lower bounds
FIRE_CRITICAL_POPULATION = 20000  # exposed people from which a fire is critical rather than high

INF, L, M, H, C = Severity.INFO, Severity.LOW, Severity.MODERATE, Severity.HIGH, Severity.CRITICAL


def banded(value: float, bounds: Sequence[tuple[float, Severity]]) -> Severity:
    """The severity of the highest lower bound that ``value`` reaches, info if none."""
    result = INF
    for bound, severity in bounds:
        if value >= bound:
            result = severity
    return result


def highest(*severities: Severity) -> Severity:
    return max(severities, key=SEVERITY_ORDER.index)


def _weather(obs: p.WeatherObservation, t: PolicyThresholds) -> Severity:
    found = [INF]
    if obs.rainfall_intensity_mm_h is not None:
        rain = [(RAIN_LOW_MM_H, L), (t.rain_1h_watch_mm_h, M), (t.rain_1h_warning_mm_h, H)]
        found.append(banded(obs.rainfall_intensity_mm_h, rain))
    if obs.cumulative_rainfall_24h_mm is not None and obs.station_id in t.landslide_rain_gauge_ids:
        day = [(t.rain_24h_watch_mm, M), (t.rain_24h_warning_mm, H), (t.rain_24h_critical_mm, C)]
        found.append(banded(obs.cumulative_rainfall_24h_mm, day))
    if obs.wind_speed_kmh is not None:
        wind = [(WIND_LOW_KMH, L), (t.wind_watch_kmh, M), (t.wind_warning_kmh, H), (t.wind_critical_kmh, C)]
        found.append(banded(obs.wind_speed_kmh, wind))
    return highest(*found)


def _soil(obs: p.SoilObservation, t: PolicyThresholds) -> Severity:
    bands = [
        (SATURATION_LOW, L),
        (SATURATION_MODERATE, M),
        (t.saturation_warning, H),
        (t.saturation_critical, C),
    ]
    return banded(obs.saturation, bands)


def _drainage(obs: p.DrainageObservation, t: PolicyThresholds) -> Severity:
    return banded(
        obs.load_ratio, [(CHANNEL_LOW, L), (t.channel_ratio_watch, M), (t.channel_ratio_critical, C)]
    )


def _river(obs: p.RiverObservation, _: PolicyThresholds) -> Severity:
    bands = [
        (RIVER_LOW_SHARE * obs.flood_stage_m, L),
        (obs.flood_stage_m, M),
        (obs.warning_level_m, H),
        (obs.danger_level_m, C),
    ]
    return banded(obs.level_m, bands)


def _slope(obs: p.SlopeObservation, _: PolicyThresholds) -> Severity:
    return banded(obs.movement_rate_mm_h, list(zip(SLOPE_BANDS_MM_H, (L, M, H, C), strict=True)))


def _water(obs: p.WaterAccumulation, t: PolicyThresholds) -> Severity:
    bands = [(WATER_LOW_CM, L), (WATER_MODERATE_CM, M), (t.road_closure_depth_cm, H), (WATER_CRITICAL_CM, C)]
    return banded(obs.depth_cm, bands)


def _road(obs: p.RoadStatus, _: PolicyThresholds) -> Severity:
    if obs.status == "open":
        return INF
    return H if obs.is_evacuation_route else M


def _bridge(obs: p.BridgeStatus, _: PolicyThresholds) -> Severity:
    return {"open": INF, "restricted": M, "closed": H}[obs.status]


def _obstruction(obs: p.DrainageObstruction, _: PolicyThresholds) -> Severity:
    return banded(obs.blocked_fraction, list(zip(OBSTRUCTION_BANDS, (L, M, H, C), strict=True)))


def _construction(obs: p.ConstructionActivity, _: PolicyThresholds) -> Severity:
    return L if obs.activity == "excavating" else INF


def _failure(_obs: p.InfrastructureFailure, _: PolicyThresholds) -> Severity:
    return C


def _crew(obs: p.RescueTeamStatus, _: PolicyThresholds) -> Severity:
    return {"blocked": H, "en_route": L, "dispatched": L}.get(obs.status, INF)


def _ambulance(obs: p.AmbulanceStatus, _: PolicyThresholds) -> Severity:
    return INF if obs.available_count >= 2 else (M if obs.available_count == 1 else H)


def _hospital(obs: p.HospitalCapacity, _: PolicyThresholds) -> Severity:
    return {"normal": INF, "busy": M, "overwhelmed": C}[obs.er_status]


def _shelter(obs: p.ShelterCapacity, _: PolicyThresholds) -> Severity:
    return H if obs.status == "full" else INF


def _forecast(obs: p.WeatherForecast, t: PolicyThresholds) -> Severity:
    return banded(obs.peak_intensity_mm_h, [(t.rain_1h_watch_mm_h, M), (t.rain_1h_warning_mm_h, H)])


def _rainfall(obs: p.RainfallDriver, t: PolicyThresholds) -> Severity:
    rain = [(RAIN_LOW_MM_H, L), (t.rain_1h_watch_mm_h, M), (t.rain_1h_warning_mm_h, H)]
    return banded(obs.intensity_mm_h, rain)


def _fire(obs: p.IndustrialFire, _: PolicyThresholds) -> Severity:
    return C if obs.exposed_population >= FIRE_CRITICAL_POPULATION else H


def _zone_state(obs: p.ZoneStatePayload, _: PolicyThresholds) -> Severity:
    return {Band.NORMAL: INF, Band.WATCH: M, Band.WARNING: H, Band.CRITICAL: C}[obs.band]


Rule = Callable[[BaseModel, PolicyThresholds], Severity]


def _band[P: BaseModel](kind: type[P], rule: Callable[[P, PolicyThresholds], Severity]) -> Rule:
    def apply(payload: BaseModel, thresholds: PolicyThresholds) -> Severity:
        if not isinstance(payload, kind):
            raise TypeError(f"expected {kind.__name__}, got {type(payload).__name__}")
        return rule(payload, thresholds)

    return apply


RULES: dict[EventType, Rule] = {
    EventType.WEATHER_OBSERVATION: _band(p.WeatherObservation, _weather),
    EventType.WEATHER_FORECAST: _band(p.WeatherForecast, _forecast),
    EventType.WEATHER_RAINFALL: _band(p.RainfallDriver, _rainfall),
    EventType.ZONE_STATE: _band(p.ZoneStatePayload, _zone_state),
    EventType.ENVIRONMENT_SOIL: _band(p.SoilObservation, _soil),
    EventType.ENVIRONMENT_RIVER: _band(p.RiverObservation, _river),
    EventType.ENVIRONMENT_DRAINAGE: _band(p.DrainageObservation, _drainage),
    EventType.ENVIRONMENT_SLOPE: _band(p.SlopeObservation, _slope),
    EventType.ENVIRONMENT_WATER_ACCUMULATION: _band(p.WaterAccumulation, _water),
    EventType.INFRASTRUCTURE_ROAD: _band(p.RoadStatus, _road),
    EventType.INFRASTRUCTURE_BRIDGE: _band(p.BridgeStatus, _bridge),
    EventType.INFRASTRUCTURE_DRAINAGE_OBSTRUCTION: _band(p.DrainageObstruction, _obstruction),
    EventType.INFRASTRUCTURE_CONSTRUCTION: _band(p.ConstructionActivity, _construction),
    EventType.INFRASTRUCTURE_FAILURE: _band(p.InfrastructureFailure, _failure),
    EventType.EMERGENCY_RESCUE_TEAM: _band(p.RescueTeamStatus, _crew),
    EventType.EMERGENCY_AMBULANCE: _band(p.AmbulanceStatus, _ambulance),
    EventType.EMERGENCY_HOSPITAL: _band(p.HospitalCapacity, _hospital),
    EventType.EMERGENCY_SHELTER: _band(p.ShelterCapacity, _shelter),
    EventType.EMERGENCY_FIRE: _band(p.IndustrialFire, _fire),
}


def severity_for(event_type: EventType, payload: BaseModel, thresholds: PolicyThresholds) -> Severity:
    """The fixed sensor band for one payload; sim.* and scenario.* events are always info."""
    rule = RULES.get(event_type)
    return INF if rule is None else rule(payload, thresholds)
