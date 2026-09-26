"""Event type and severity enums. Severity is a sensor-band label, never a threat assessment."""

from enum import StrEnum


class Severity(StrEnum):
    INFO = "info"
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"


SEVERITY_ORDER: tuple[Severity, ...] = tuple(Severity)


class EventType(StrEnum):
    SIM_TICK = "sim.tick"
    SIM_STATUS = "sim.status"
    SIM_SNAPSHOT = "sim.snapshot"
    SIM_HEARTBEAT = "sim.heartbeat"
    SCENARIO_STAGE = "scenario.stage"
    WEATHER_OBSERVATION = "weather.observation"
    WEATHER_FORECAST = "weather.forecast"
    ENVIRONMENT_SOIL = "environment.soil"
    ENVIRONMENT_RIVER = "environment.river"
    ENVIRONMENT_DRAINAGE = "environment.drainage"
    ENVIRONMENT_SLOPE = "environment.slope"
    ENVIRONMENT_WATER_ACCUMULATION = "environment.water_accumulation"
    INFRASTRUCTURE_ROAD = "infrastructure.road"
    INFRASTRUCTURE_BRIDGE = "infrastructure.bridge"
    INFRASTRUCTURE_DRAINAGE_OBSTRUCTION = "infrastructure.drainage_obstruction"
    INFRASTRUCTURE_CONSTRUCTION = "infrastructure.construction"
    INFRASTRUCTURE_FAILURE = "infrastructure.failure"
    EMERGENCY_RESCUE_TEAM = "emergency.rescue_team"
    EMERGENCY_AMBULANCE = "emergency.ambulance"
    EMERGENCY_HOSPITAL = "emergency.hospital"
    EMERGENCY_SHELTER = "emergency.shelter"


INJECTABLE_TYPES: frozenset[EventType] = frozenset(
    {
        EventType.WEATHER_FORECAST,
        EventType.INFRASTRUCTURE_ROAD,
        EventType.INFRASTRUCTURE_BRIDGE,
        EventType.INFRASTRUCTURE_DRAINAGE_OBSTRUCTION,
        EventType.INFRASTRUCTURE_CONSTRUCTION,
        EventType.INFRASTRUCTURE_FAILURE,
        EventType.EMERGENCY_RESCUE_TEAM,
        EventType.EMERGENCY_AMBULANCE,
        EventType.EMERGENCY_HOSPITAL,
        EventType.EMERGENCY_SHELTER,
    }
)
