from datetime import UTC, datetime

import pytest
from pydantic import BaseModel, ValidationError

from gridline.events.envelope import Event, new_event
from gridline.events.payloads import PAYLOAD_MODELS, SimTick, WeatherObservation
from gridline.events.types import INJECTABLE_TYPES, EventType, Severity

NOW = datetime(2026, 7, 14, 6, 0, tzinfo=UTC)


def rain(station_id: str = "RG-02") -> WeatherObservation:
    return WeatherObservation(
        station_id=station_id, rainfall_intensity_mm_h=12.0, cumulative_rainfall_24h_mm=30.0
    )


def test_registry_is_total() -> None:
    assert set(PAYLOAD_MODELS) == set(EventType)
    for model in PAYLOAD_MODELS.values():
        assert issubclass(model, BaseModel)


def test_new_event_builds_envelope_with_all_fields() -> None:
    event = new_event(
        EventType.WEATHER_OBSERVATION,
        rain(),
        event_id="evt-000001",
        timestamp=NOW,
        sim_time=NOW,
        source="sensor:RG-02",
        location="Z-HV",
        severity=Severity.LOW,
    )
    assert event.event_id == "evt-000001"
    assert event.event_type == EventType.WEATHER_OBSERVATION
    assert event.source == "sensor:RG-02"
    assert event.location == "Z-HV"
    assert event.severity == Severity.LOW
    assert event.payload["station_id"] == "RG-02"
    assert event.payload["wind_speed_kmh"] is None
    assert event.incident_id is None


def test_json_round_trip_and_field_set() -> None:
    payload = SimTick(
        tick=3, sim_time=NOW, scenario="normal_city", stage="steady_state", speed=1.0, running=True
    )
    event = new_event(
        EventType.SIM_TICK,
        payload,
        event_id="evt-000003",
        timestamp=NOW,
        sim_time=NOW,
        source="simulation:engine",
        location=None,
        severity=Severity.INFO,
    )
    assert Event.model_validate_json(event.model_dump_json()) == event
    assert set(event.model_dump()) == {
        "event_id",
        "timestamp",
        "sim_time",
        "event_type",
        "source",
        "location",
        "severity",
        "payload",
        "incident_id",
    }
    assert event.payload["sim_time"] == "2026-07-14T06:00:00Z"


def test_payload_is_validated_against_registry() -> None:
    with pytest.raises(ValidationError):
        Event(
            event_id="evt-1",
            timestamp=NOW,
            sim_time=NOW,
            event_type=EventType.ENVIRONMENT_SOIL,
            source="sensor:SM-01",
            location="Z-HV",
            severity=Severity.INFO,
            payload={"probe_id": "SM-01", "slope_id": "SL-HV-1", "soil_moisture_pct": 150, "saturation": 0.5},
        )


def test_unknown_payload_keys_are_rejected() -> None:
    with pytest.raises(ValidationError):
        Event(
            event_id="evt-1",
            timestamp=NOW,
            sim_time=NOW,
            event_type=EventType.SIM_HEARTBEAT,
            source="simulation:engine",
            location=None,
            severity=Severity.INFO,
            payload={"tick": 0, "sim_time": NOW.isoformat(), "surprise": 1},
        )


def test_naive_timestamp_rejected() -> None:
    with pytest.raises(ValidationError):
        Event(
            event_id="evt-1",
            timestamp=datetime(2026, 7, 14),
            sim_time=NOW,
            event_type=EventType.SIM_HEARTBEAT,
            source="simulation:engine",
            location=None,
            severity=Severity.INFO,
            payload={"tick": 0, "sim_time": NOW.isoformat()},
        )


def test_event_is_frozen() -> None:
    event = new_event(
        EventType.WEATHER_OBSERVATION,
        rain(),
        event_id="evt-1",
        timestamp=NOW,
        sim_time=NOW,
        source="sensor:RG-02",
        location="Z-HV",
        severity=Severity.INFO,
    )
    with pytest.raises(ValidationError):
        event.severity = Severity.HIGH  # type: ignore[misc]


def test_new_event_rejects_wrong_payload_class() -> None:
    with pytest.raises(TypeError):
        new_event(
            EventType.SIM_TICK,
            rain(),
            event_id="evt-1",
            timestamp=NOW,
            sim_time=NOW,
            source="x",
            location=None,
            severity=Severity.INFO,
        )


def test_injectable_types_are_state_changing_only() -> None:
    assert EventType.INFRASTRUCTURE_ROAD in INJECTABLE_TYPES
    assert EventType.WEATHER_FORECAST in INJECTABLE_TYPES
    assert EventType.WEATHER_OBSERVATION not in INJECTABLE_TYPES
    assert EventType.SIM_TICK not in INJECTABLE_TYPES
    assert all(
        t.startswith(("infrastructure.", "emergency.")) or t in ("weather.forecast", "weather.rainfall")
        for t in INJECTABLE_TYPES
    )
    assert EventType.WEATHER_RAINFALL in INJECTABLE_TYPES
    assert {t for t in EventType if t.startswith(("infrastructure.", "emergency."))} <= INJECTABLE_TYPES
