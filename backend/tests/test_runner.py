import asyncio
from collections.abc import AsyncIterator, Callable

import pytest

from gridline.city.model import City
from gridline.errors import InvalidTransition, UnknownScenario
from gridline.events.bus import EventBus, Subscription
from gridline.events.envelope import Event
from gridline.events.types import EventType
from gridline.simulation.engine import SimulationEngine
from gridline.simulation.runner import SimulationRunner

TICK_SECONDS = 0.01


@pytest.fixture
async def runner(city: City) -> AsyncIterator[SimulationRunner]:
    runner = SimulationRunner(SimulationEngine(city), EventBus(), tick_seconds=TICK_SECONDS)
    await runner.select_scenario("normal_city", seed=1)
    yield runner
    await runner.shutdown()


def drain(sub: Subscription) -> list[Event]:
    events: list[Event] = []
    while not sub.queue.empty():
        events.append(sub.queue.get_nowait())
    return events


async def wait_for(predicate: Callable[[], bool], timeout: float = 2.0) -> None:
    async with asyncio.timeout(timeout):
        while not predicate():
            await asyncio.sleep(TICK_SECONDS)


async def test_start_pause_resume_reset_and_status_events(runner: SimulationRunner) -> None:
    statuses = runner.bus.subscribe(["sim.status"])
    assert runner.status().state == "idle" and runner.status().tick == 0
    started = await runner.start()
    assert started.state == "running" and started.running
    await wait_for(lambda: runner.status().tick >= 3)
    paused = await runner.pause()
    frozen = paused.tick
    await asyncio.sleep(TICK_SECONDS * 5)
    assert runner.status().tick == frozen and runner.status().state == "paused"
    await runner.resume()
    await wait_for(lambda: runner.status().tick > frozen)
    reset = await runner.reset()
    assert (reset.state, reset.tick, reset.scenario, reset.seed) == ("idle", 0, "normal_city", 1)
    states = [e.payload["state"] for e in drain(statuses)]
    assert states == ["running", "paused", "running", "idle"]


async def test_illegal_transitions_raise(runner: SimulationRunner) -> None:
    with pytest.raises(InvalidTransition):
        await runner.pause()
    with pytest.raises(InvalidTransition):
        await runner.resume()
    await runner.start()
    with pytest.raises(InvalidTransition):
        await runner.start()
    with pytest.raises(InvalidTransition):
        await runner.advance(1)
    await runner.pause()
    with pytest.raises(InvalidTransition):
        await runner.start()  # use resume
    with pytest.raises(InvalidTransition):
        await runner.pause()


async def test_advance_is_allowed_when_idle_or_paused(runner: SimulationRunner) -> None:
    events = await runner.advance(2)
    assert runner.status().tick == 2
    assert [e for e in events if e.event_type == EventType.SIM_TICK][-1].payload["running"] is False
    await runner.start()
    await runner.pause()
    before = runner.status().tick
    await runner.advance(3)
    assert runner.status().tick == before + 3


@pytest.mark.parametrize("action", ["reset", "select"])
async def test_reset_or_select_while_ticking_cancels_the_tick_task(
    runner: SimulationRunner, action: str
) -> None:
    ticks = runner.bus.subscribe(["sim.tick"])
    await runner.start()
    await wait_for(lambda: runner.status().tick >= 2)
    if action == "reset":
        status = await runner.reset()
    else:
        status = await runner.select_scenario("flash_flood", seed=9)
        assert (status.scenario, status.seed) == ("flash_flood", 9)
    assert (status.state, status.tick) == ("idle", 0)
    drain(ticks)
    await asyncio.sleep(TICK_SECONDS * 8)
    assert drain(ticks) == []
    assert runner.status().tick == 0


async def test_start_can_select_and_set_speed(runner: SimulationRunner) -> None:
    status = await runner.start(scenario="hillside_landslide", seed=3, speed=4.0)
    assert (status.scenario, status.seed, status.speed, status.state) == (
        "hillside_landslide",
        3,
        4.0,
        "running",
    )
    with pytest.raises(UnknownScenario):
        await runner.select_scenario("volcano")
    assert runner.status().state == "running"  # a bad name changes nothing


async def test_speed_bounds_and_status(runner: SimulationRunner) -> None:
    statuses = runner.bus.subscribe(["sim.status"])
    for bad in (0.1, 10.5):
        with pytest.raises(ValueError):
            await runner.set_speed(bad)
    status = await runner.set_speed(2.5)
    assert status.speed == 2.5 and runner.engine.speed == 2.5
    assert [e.payload["speed"] for e in drain(statuses)] == [2.5]


async def test_inject_publishes_while_running(runner: SimulationRunner) -> None:
    roads = runner.bus.subscribe(["infrastructure.road"])
    await runner.start()
    events = await runner.inject(EventType.INFRASTRUCTURE_ROAD, {"road_id": "RD-05", "status": "closed"})
    assert [e.event_id for e in drain(roads)] == [events[0].event_id]


async def test_tick_loop_survives_an_engine_error(
    runner: SimulationRunner, monkeypatch: pytest.MonkeyPatch
) -> None:
    real_advance = runner.engine.advance
    calls = {"n": 0}

    def flaky(ticks: int = 1) -> list[Event]:
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("boom")
        return real_advance(ticks)

    monkeypatch.setattr(runner.engine, "advance", flaky)
    await runner.start()
    await wait_for(lambda: runner.status().tick >= 2)
    assert runner.status().state == "running"
