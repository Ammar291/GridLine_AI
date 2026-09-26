"""Each DEMO control injects world facts and, one simulated hour later, shows the outcome the spec names."""

import asyncio
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import pytest

from gridline.city.model import City
from gridline.events.bus import EventBus, Subscription
from gridline.events.envelope import Event
from gridline.events.types import EventType
from gridline.simulation.engine import SimulationEngine
from gridline.simulation.runner import SimulationRunner
from gridline.simulation.scenarios import ScenarioName
from gridline.simulation.triggers import (
    TRIGGER_ADVANCE_TICKS,
    TRIGGER_SOURCE,
    TRIGGERS,
    TriggerName,
    run_trigger,
)

WALL = datetime(2030, 1, 1, tzinfo=UTC)
BASES = [ScenarioName.NORMAL_CITY, ScenarioName.CASCADING_LANDSLIDE_FLOOD]
HIGH = {"warning", "critical"}


def fresh(city: City, base: ScenarioName) -> SimulationEngine:
    engine = SimulationEngine(city, clock=lambda: WALL)
    engine.reset(base, 42)
    return engine


def last_zone_state(events: list[Event], zone_id: str) -> dict[str, Any]:
    return [e.payload for e in events if e.event_type == EventType.ZONE_STATE and e.location == zone_id][-1]


def untriggered(city: City, base: ScenarioName) -> tuple[list[Event], SimulationEngine]:
    engine = fresh(city, base)
    return engine.advance(TRIGGER_ADVANCE_TICKS), engine


def load_ratio(engine: SimulationEngine, channel_id: str) -> float:
    channel = engine.snapshot().channels[channel_id]
    return channel.flow_m3s / channel.capacity_m3s


@pytest.mark.parametrize("base", BASES)
@pytest.mark.parametrize("name", list(TriggerName))
def test_every_trigger_announces_itself_injects_as_the_operator_and_runs_an_hour(
    city: City, base: ScenarioName, name: TriggerName
) -> None:
    events = run_trigger(fresh(city, base), name)
    announcement = events[0]
    assert announcement.event_type == EventType.SCENARIO_TRIGGER and announcement.source == TRIGGER_SOURCE
    assert announcement.payload["trigger"] == name and announcement.payload["tick"] == 0
    injected = [e for e in events[1:] if e.source == TRIGGER_SOURCE]
    assert [e.event_type for e in injected] == [s.event_type for s in TRIGGERS[name].steps]
    assert sum(e.event_type == EventType.SIM_TICK for e in events) == TRIGGER_ADVANCE_TICKS


@pytest.mark.parametrize("base", BASES)
def test_heavy_rain_raises_rain_saturation_and_drain_load(city: City, base: ScenarioName) -> None:
    engine = fresh(city, base)
    events = run_trigger(engine, TriggerName.HEAVY_RAIN)
    quiet_events, quiet = untriggered(city, base)
    now, before = engine.snapshot(), quiet.snapshot()
    assert all(z.rainfall_intensity_mm_h >= 20 for z in now.zones.values())
    assert now.zones["Z-HV"].saturation > before.zones["Z-HV"].saturation
    assert load_ratio(engine, "D-7") > load_ratio(quiet, "D-7")
    assert (
        last_zone_state(events, "Z-RS")["flood_index"] > last_zone_state(quiet_events, "Z-RS")["flood_index"]
    )


@pytest.mark.parametrize("base", BASES)
def test_landslide_puts_hillview_at_high_landslide_risk(city: City, base: ScenarioName) -> None:
    engine = fresh(city, base)
    hillview = last_zone_state(run_trigger(engine, TriggerName.LANDSLIDE), "Z-HV")
    assert hillview["landslide_index"] >= 0.55 and hillview["band"] in HIGH
    assert engine.snapshot().projects["PR-HT2"].excavation_depth_m == 6.0


@pytest.mark.parametrize("base", BASES)
def test_drainage_block_cuts_d7_and_raises_riverside_flood_risk(city: City, base: ScenarioName) -> None:
    engine = fresh(city, base)
    events = run_trigger(engine, TriggerName.DRAINAGE_BLOCK)
    quiet_events, quiet = untriggered(city, base)
    d7, d7_before = engine.snapshot().channels["D-7"], quiet.snapshot().channels["D-7"]
    assert d7.blocked_fraction == 0.7 and d7.capacity_m3s < d7_before.capacity_m3s
    assert (
        last_zone_state(events, "Z-RS")["flood_index"] > last_zone_state(quiet_events, "Z-RS")["flood_index"]
    )


@pytest.mark.parametrize("base", BASES)
def test_flash_flood_overloads_d7_and_puts_riverside_at_high_flood_risk(
    city: City, base: ScenarioName
) -> None:
    engine = fresh(city, base)
    riverside = last_zone_state(run_trigger(engine, TriggerName.FLASH_FLOOD), "Z-RS")
    assert load_ratio(engine, "D-7") > 1
    assert riverside["band"] in HIGH


@pytest.mark.parametrize("base", BASES)
def test_industrial_fire_exposes_the_neighbouring_population(city: City, base: ScenarioName) -> None:
    engine = fresh(city, base)
    events = run_trigger(engine, TriggerName.INDUSTRIAL_FIRE)
    [fire] = [e for e in events if e.event_type == EventType.EMERGENCY_FIRE]
    assert fire.location == "Z-MI" and fire.payload["exposed_population"] > 0
    assert "Z-MI" in fire.payload["exposed_zone_ids"]
    assert "Z-MI" in engine.snapshot().fires


@pytest.mark.parametrize("base", BASES)
def test_cascading_disaster_runs_landslide_then_blockage_then_flood(city: City, base: ScenarioName) -> None:
    events = run_trigger(fresh(city, base), TriggerName.CASCADING_DISASTER)

    def first(predicate: Callable[[Event], bool]) -> int:
        return next(i for i, e in enumerate(events) if predicate(e))

    failure = first(lambda e: e.event_type == EventType.INFRASTRUCTURE_FAILURE)
    blockage = first(
        lambda e: (
            e.event_type == EventType.INFRASTRUCTURE_DRAINAGE_OBSTRUCTION and e.payload["channel_id"] == "D-7"
        )
    )
    flood = first(
        lambda e: e.event_type == EventType.ZONE_STATE and e.location == "Z-RS" and e.payload["band"] in HIGH
    )
    assert failure < blockage < flood


@pytest.mark.parametrize("base", BASES)
def test_reset_restores_the_original_city(city: City, base: ScenarioName) -> None:
    engine = fresh(city, base)
    for name in TriggerName:
        run_trigger(engine, name)
    engine.reset(base, 42)
    clean = fresh(city, base)
    assert engine.snapshot() == clean.snapshot()
    assert engine.advance(3) == clean.advance(3)  # no rain override, fire or remembered band survives


def test_every_trigger_can_be_pressed_twice_late_in_the_storm(city: City) -> None:
    engine = fresh(city, ScenarioName.CASCADING_LANDSLIDE_FLOOD)
    engine.advance(260)  # SL-HV-1 has already failed and PR-HT2 is halted
    for name in TriggerName:
        run_trigger(engine, name)
        run_trigger(engine, name)
    assert engine.world.tick == 260 + 2 * TRIGGER_ADVANCE_TICKS * len(TriggerName)


def drain(sub: Subscription) -> list[Event]:
    events: list[Event] = []
    while not sub.queue.empty():
        events.append(sub.queue.get_nowait())
    return events


async def test_trigger_while_running_publishes_one_contiguous_batch(city: City) -> None:
    bus = EventBus(maxsize=10_000)
    runner = SimulationRunner(SimulationEngine(city), bus, tick_seconds=0.01)
    await runner.select_scenario("normal_city", seed=1)
    sub = bus.subscribe(maxsize=10_000)
    await runner.start()
    await asyncio.sleep(0.05)
    events = await runner.trigger(TriggerName.HEAVY_RAIN)
    await asyncio.sleep(0.05)
    await runner.shutdown()
    ids = [e.event_id for e in drain(sub)]
    start = ids.index(events[0].event_id)
    assert ids[start : start + len(events)] == [e.event_id for e in events]
