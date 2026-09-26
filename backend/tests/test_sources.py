import json
from pathlib import Path
from typing import Any

from gridline.city.model import City
from gridline.events.bus import EventBus
from gridline.events.envelope import Event
from gridline.events.types import EventType
from gridline.simulation.engine import SimulationEngine
from gridline.simulation.runner import SimulationRunner
from gridline.sources.demo import DemoDataSource
from gridline.sources.live import LiveDataSource
from gridline.sources.manager import DataSourceManager

FIXTURE = Path(__file__).parent / "fixtures" / "open_meteo" / "kalyan_dombivli.json"


async def fixture_fetch(_url: str) -> dict[str, Any]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


async def offline_fetch(_url: str) -> dict[str, Any]:
    raise OSError("network unreachable")


def drain(bus_sub: Any) -> list[Event]:
    events: list[Event] = []
    while not bus_sub.queue.empty():
        events.append(bus_sub.queue.get_nowait())
    return events


async def test_live_poll_publishes_normalized_weather_events() -> None:
    bus = EventBus()
    sub = bus.subscribe()
    live = LiveDataSource(bus, fetch=fixture_fetch, poll_seconds=60)
    await live.poll_once()
    events = drain(sub)
    types = [e.event_type for e in events]
    assert types == [EventType.WEATHER_OBSERVATION, EventType.WEATHER_FORECAST, EventType.SOURCE_STATUS]
    observation = events[0]
    assert observation.source == "open-meteo:forecast-api"
    assert observation.location == "kalyan-dombivli"
    assert observation.sim_time.isoformat() == "2026-09-26T10:30:00+00:00"
    status = events[2].payload
    assert status["mode"] == "live" and status["last_error"] is None and status["last_updated"] is not None
    assert [e.event_type for e in live.latest()] == types[:2]


async def test_live_poll_failure_reports_error_without_inventing_data() -> None:
    bus = EventBus()
    sub = bus.subscribe()
    live = LiveDataSource(bus, fetch=offline_fetch, poll_seconds=60)
    await live.poll_once()
    events = drain(sub)
    assert [e.event_type for e in events] == [EventType.SOURCE_STATUS]
    assert "network unreachable" in (events[0].payload["last_error"] or "")
    assert live.latest() == []


async def test_manager_switches_modes_and_pauses_the_simulation(city: City) -> None:
    bus = EventBus()
    runner = SimulationRunner(SimulationEngine(city), bus, tick_seconds=0.01)
    await runner.select_scenario("normal_city", 1)
    live = LiveDataSource(bus, fetch=fixture_fetch, poll_seconds=3600)
    manager = DataSourceManager({"demo": DemoDataSource(runner), "live": live}, bus, mode="demo")
    await manager.start()
    await runner.start()
    sub = bus.subscribe(["source."])

    status = await manager.switch("live")
    assert status.mode == "live" and status.label == "LIVE — Kalyan-Dombivli"
    assert runner.state == "paused"
    assert manager.mode == "live"
    await live.wait_first_poll()
    assert drain(sub)[0].payload["mode"] == "live"

    status = await manager.switch("demo")
    assert status.label == "DEMO — Nandipur"
    assert runner.state == "running"  # resumed because the switch paused it
    assert drain(sub)[-1].payload["mode"] == "demo"
    await manager.shutdown()
    await runner.shutdown()


async def test_manager_replay_starts_with_status(city: City) -> None:
    bus = EventBus()
    runner = SimulationRunner(SimulationEngine(city), bus, tick_seconds=0.01)
    await runner.select_scenario("normal_city", 1)
    live = LiveDataSource(bus, fetch=fixture_fetch, poll_seconds=3600)
    manager = DataSourceManager({"demo": DemoDataSource(runner), "live": live}, bus, mode="live")
    await manager.start()
    await live.wait_first_poll()
    replay = manager.replay()
    assert [e.event_type for e in replay] == [
        EventType.SOURCE_STATUS,
        EventType.WEATHER_OBSERVATION,
        EventType.WEATHER_FORECAST,
    ]
    await manager.shutdown()
