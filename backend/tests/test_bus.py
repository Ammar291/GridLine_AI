from datetime import UTC, datetime

from gridline.events.bus import EventBus, Subscription
from gridline.events.envelope import Event, new_event
from gridline.events.payloads import Heartbeat, SoilObservation, WeatherObservation
from gridline.events.types import EventType, Severity

NOW = datetime(2026, 7, 14, 6, 0, tzinfo=UTC)


def event(event_type: EventType, n: int = 1) -> Event:
    payload = {
        EventType.WEATHER_OBSERVATION: WeatherObservation(station_id="RG-02", rainfall_intensity_mm_h=n),
        EventType.ENVIRONMENT_SOIL: SoilObservation(
            probe_id="SM-01", slope_id="SL-HV-1", soil_moisture_pct=9, saturation=0.2
        ),
        EventType.SIM_HEARTBEAT: Heartbeat(tick=n, sim_time=NOW),
    }[event_type]
    return new_event(
        event_type,
        payload,
        event_id=f"evt-{n:06d}",
        timestamp=NOW,
        sim_time=NOW,
        source="test",
        location=None,
        severity=Severity.INFO,
    )


async def test_prefix_filter_and_fan_out() -> None:
    bus = EventBus()
    weather = bus.subscribe(["weather."])
    everything = bus.subscribe()
    soil_or_weather = bus.subscribe(["environment.soil", "weather.observation"])
    for kind in (EventType.WEATHER_OBSERVATION, EventType.ENVIRONMENT_SOIL, EventType.SIM_HEARTBEAT):
        bus.publish(event(kind))
    assert [e.event_type for e in drain(weather)] == [EventType.WEATHER_OBSERVATION]
    assert len(drain(everything)) == 3
    assert [e.event_type for e in drain(soil_or_weather)] == [
        EventType.WEATHER_OBSERVATION,
        EventType.ENVIRONMENT_SOIL,
    ]


async def test_empty_segments_are_ignored_and_unmatched_prefixes_receive_nothing() -> None:
    bus = EventBus()
    blank = bus.subscribe(["", "  "])
    nope = bus.subscribe(["nope."])
    bus.publish(event(EventType.ENVIRONMENT_SOIL))
    assert blank.prefixes == () and len(drain(blank)) == 1
    assert drain(nope) == []


async def test_full_queue_drops_the_oldest_and_counts() -> None:
    bus = EventBus()
    sub = bus.subscribe(maxsize=2)
    for n in (1, 2, 3):
        bus.publish(event(EventType.SIM_HEARTBEAT, n))
    assert [e.payload["tick"] for e in drain(sub)] == [2, 3]
    assert sub.dropped == 1


async def test_unsubscribe_stops_delivery() -> None:
    bus = EventBus()
    sub = bus.subscribe()
    assert bus.subscriber_count == 1
    bus.unsubscribe(sub)
    bus.unsubscribe(sub)  # idempotent
    bus.publish(event(EventType.SIM_HEARTBEAT))
    assert bus.subscriber_count == 0
    assert drain(sub) == []


def drain(sub: Subscription) -> list[Event]:
    events: list[Event] = []
    while not sub.queue.empty():
        events.append(sub.queue.get_nowait())
    return events
