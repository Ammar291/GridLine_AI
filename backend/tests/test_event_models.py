"""The typed event contract (OpenAPI ``Event``) describes exactly the JSON the bus and the WebSocket carry."""

from datetime import UTC, datetime

from gridline.api.event_models import EVENT_MODELS, Event, SimSnapshotEvent, typed_event
from gridline.city.model import City
from gridline.events.payloads import PAYLOAD_MODELS
from gridline.events.types import EventType
from gridline.simulation.engine import SimulationEngine


def test_there_is_one_typed_model_per_event_type() -> None:
    assert set(EVENT_MODELS) == set(EventType)
    for event_type, model in EVENT_MODELS.items():
        assert model.model_fields["event_type"].annotation is not None
        payload = model.model_fields["payload"].annotation
        if event_type is not EventType.SIM_SNAPSHOT:
            assert payload is PAYLOAD_MODELS[event_type], event_type


def test_openapi_union_is_discriminated_by_event_type() -> None:
    schema = Event.model_json_schema(mode="serialization")
    assert schema["discriminator"]["propertyName"] == "event_type"
    assert set(schema["discriminator"]["mapping"]) == {t.value for t in EventType}
    assert "SimSnapshotEvent" in schema["$defs"]


def test_every_simulated_event_round_trips_through_the_typed_union(city: City) -> None:
    engine = SimulationEngine(city, clock=lambda: datetime(2026, 9, 26, tzinfo=UTC))
    events = engine.replay("cascading_landslide_flood", 42, 220)
    events += engine.inject("infrastructure.road", {"road_id": "RD-02", "status": "closed", "reason": "test"})
    seen: set[str] = set()
    for event in events:
        typed = typed_event(event)
        assert typed.model_dump(mode="json") == event.model_dump(mode="json")
        seen.add(event.event_type.value)
    assert {"sim.tick", "weather.observation", "infrastructure.failure", "infrastructure.road"} <= seen


def test_snapshot_view_types_the_world_and_the_city() -> None:
    fields = SimSnapshotEvent.model_fields["payload"].annotation
    assert fields is not None and set(fields.model_fields) == {"status", "world", "city"}  # type: ignore[union-attr]
