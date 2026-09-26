"""Physics-lite models (spec §5.2), recalibrated to the Nandipur data layer. Pure functions only.

Constants are invented and tuned so the scenario progression tests hold with margin. Where the data layer
has a number it is used instead: zone areas, impervious shares, permeability classes, channel capacities,
the R-1 rating (ordinary and bankfull flow and stage) and the permit's 1.5 m bench height.
"""

from gridline.city.model import PermeabilityClass

# saturation gained per 100 mm of rain; poorly drained soils fill faster (perched water, waterlogging)
K_IN: dict[PermeabilityClass, float] = {"very_low": 0.30, "low": 0.26, "moderate": 0.20, "high": 0.12}
K_DRAIN = 0.08  # fraction of saturation drained per hour (colluvium drains within about a day)
EXC_INFILTRATION = 0.8  # extra infiltration per metre of unsupported cut (open face, stripped cover)
BENCH_SAFE_M = 1.5  # a bench up to this height stands unsupported (permit HT-2026-014 s2)
MM_H_KM2_TO_M3S = 0.2778  # 1 mm/h over 1 km2 = 0.2778 m3/s
CATCHMENT_ROUTING = 0.35  # share of rational-method runoff reaching the channel within a tick (storage, lag)
WATER_POOL_CM = 3.0  # cm of ponding at the low point per (m3/s * h) of overflow into a dry zone
POND_SPREAD_CM = 40.0  # depth at which spreading over the flood plain halves the ponding rate
RECESSION_CM_H = 2.0  # cm/h drained from ponded water
RIVER_SMOOTHING = 0.1  # fraction of the gap to the rating-curve stage closed per tick
K_CREEP = 700.0  # mm/h per unit of (saturation excess)^2 at a 3 m unsupported cut on a 40 degree slope
SAT_CREEP_THRESHOLD = 0.65  # saturation below which the slope does not creep (just under the 0.70 warning)
EXC_REF_DEPTH_M = 3.0  # unsupported cut at which the excavation factor is 1
SLOPE_REF_DEG = 20.0  # slope angle below which creep is zero


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def step_saturation(
    sat: float, rain_mm: float, *, k_in: float, cut_m: float, dt_h: float, k_drain: float = K_DRAIN
) -> float:
    """Bucket model: rain infiltrates (more through an unsupported cut), drainage removes a share per hour."""
    infiltration = k_in * (1 + EXC_INFILTRATION * cut_m) * rain_mm / 100
    return clamp(sat + infiltration - k_drain * sat * dt_h, 0.0, 1.0)


def unsupported_cut_m(excavation_depth_m: float, soil_depth_m: float) -> float:
    """Height of cut soil face beyond one self-supporting bench; a cut into rock adds no soil face."""
    return max(0.0, min(excavation_depth_m, soil_depth_m) - BENCH_SAFE_M)


def runoff_flow_m3s(intensity_mm_h: float, sat: float, area_km2: float, impervious: float) -> float:
    """Flow reaching the zone's channel; the runoff coefficient rises from the impervious share to 1."""
    coefficient = impervious + (1 - impervious) * sat
    return coefficient * intensity_mm_h * area_km2 * MM_H_KM2_TO_M3S * CATCHMENT_ROUTING


def channel_capacity_m3s(
    current_capacity: float,
    blocked_fraction: float,
    extra: float,
    *,
    gate_closed: bool = False,
    pumped: float = 0.0,
) -> float:
    """Conveyance; a flap gate closed by high river stage leaves only the channel's fixed pumps."""
    gravity = 0.0 if gate_closed else current_capacity * (1 - blocked_fraction)
    return max(0.0, (pumped if gate_closed else 0.0) + gravity + extra)


def step_water_depth(depth_cm: float, overflow_m3s: float, dt_h: float) -> float:
    """Overflow ponds at the low point; deeper water spreads wider, so each m3 adds less depth."""
    pooled = WATER_POOL_CM * overflow_m3s * dt_h / (1 + depth_cm / POND_SPREAD_CM)
    return max(0.0, depth_cm + pooled - RECESSION_CM_H * dt_h)


def rating_stage_m(
    flow_m3s: float, *, ordinary_flow: float, ordinary_stage: float, bankfull_flow: float, flood_stage: float
) -> float:
    """Linear rating through (ordinary flow, ordinary stage) and (bankfull flow, flood stage)."""
    slope = (flood_stage - ordinary_stage) / (bankfull_flow - ordinary_flow)
    return max(0.0, ordinary_stage + slope * (flow_m3s - ordinary_flow))


def step_river_level(level_m: float, target_m: float) -> float:
    return level_m + RIVER_SMOOTHING * (target_m - level_m)


def slope_rate_mm_h(sat: float, slope_deg: float, cut_m: float) -> float:
    """Creep needs saturation above the threshold, a slope steeper than the reference and an open cut."""
    slope_factor = max(0.0, (slope_deg - SLOPE_REF_DEG) / SLOPE_REF_DEG)
    exc_factor = (cut_m / EXC_REF_DEPTH_M) ** 2
    return K_CREEP * max(0.0, sat - SAT_CREEP_THRESHOLD) ** 2 * exc_factor * slope_factor


def step_excavation(
    depth_m: float, planned_depth_m: float, rate_m_per_h: float, dt_h: float, *, active: bool
) -> float:
    if not active:
        return depth_m
    return min(planned_depth_m, depth_m + rate_m_per_h * dt_h)
