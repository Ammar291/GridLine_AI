from datetime import UTC, datetime
from typing import Any

from gridline.city.model import City
from gridline.events.bus import EventBus, Subscription
from gridline.events.envelope import Event
from gridline.events.types import EventType
from gridline.simulation.engine import SimulationEngine
from gridline.simulation.runner import SimulationRunner
from gridline.simulation.scenarios import ScenarioName

WALL = datetime(2030, 1, 1, tzinfo=UTC)


def replay(city: City, seed: int, ticks: int = 60) -> list[Event]:
    return SimulationEngine(city, clock=lambda: WALL).replay(
        ScenarioName.CASCADING_LANDSLIDE_FLOOD, seed, ticks
    )


def without_wall_clock(events: list[Event]) -> list[dict[str, Any]]:
    return [e.model_dump(exclude={"timestamp"}) for e in events]


def test_same_scenario_and_seed_replay_identically(city: City) -> None:
    first, second = replay(city, 42), replay(city, 42)
    assert first == second
    assert len(first) > 60


def test_different_seeds_differ_only_in_sensor_noise(city: City) -> None:
    a, b = replay(city, 1), replay(city, 2)
    assert [e.event_id for e in a] == [e.event_id for e in b]
    assert [e.event_type for e in a] == [e.event_type for e in b]
    assert a != b
    ticks_a = [e.payload for e in a if e.event_type == EventType.SIM_TICK]
    ticks_b = [e.payload for e in b if e.event_type == EventType.SIM_TICK]
    assert ticks_a == ticks_b


async def test_runner_reset_reproduces_the_stream(city: City) -> None:
    bus = EventBus()
    runner = SimulationRunner(SimulationEngine(city), bus, tick_seconds=0.01)
    await runner.select_scenario("flash_flood", seed=11)
    sub = bus.subscribe()
    await runner.reset()
    await runner.advance(20)
    first = drain(sub)
    await runner.reset()
    await runner.advance(20)
    second = drain(sub)
    assert first[0].event_id == "evt-000001"
    assert first[-1].event_type == EventType.SIM_TICK and first[-1].payload["tick"] == 20
    assert without_wall_clock(first) == without_wall_clock(second)
    await runner.shutdown()


def drain(sub: Subscription) -> list[Event]:
    events: list[Event] = []
    while not sub.queue.empty():
        events.append(sub.queue.get_nowait())
    return events
