"""``/ws?types=weather.,environment.soil`` (spec §8.1): a snapshot on connect, then bus events as JSON.

Empty ``types`` segments are ignored (no prefixes left means no filter); an unmatched prefix just yields the
snapshot and heartbeats. Snapshot and heartbeat frames are per connection and never touch the engine's ids.
"""

import asyncio
import contextlib

from fastapi import APIRouter, WebSocket

from gridline.api.deps import BusDep, RunnerDep, SettingsDep
from gridline.events.bus import Subscription
from gridline.events.envelope import Event, new_event
from gridline.events.payloads import Heartbeat, SimSnapshot
from gridline.events.types import EventType, Severity
from gridline.simulation.runner import SimulationRunner
from gridline.simulation.sensors import ENGINE_SOURCE

router = APIRouter()


def snapshot_event(runner: SimulationRunner) -> Event:
    engine = runner.engine
    payload = SimSnapshot(
        status=engine.status_payload(runner.state), world=engine.snapshot().model_dump(mode="json")
    )
    return _frame(runner, EventType.SIM_SNAPSHOT, payload, "evt-snapshot")


def heartbeat_event(runner: SimulationRunner) -> Event:
    status = runner.engine.status
    return _frame(
        runner,
        EventType.SIM_HEARTBEAT,
        Heartbeat(tick=status.tick, sim_time=status.sim_time),
        "evt-heartbeat",
    )


def _frame(
    runner: SimulationRunner, event_type: EventType, payload: SimSnapshot | Heartbeat, event_id: str
) -> Event:
    engine = runner.engine
    return new_event(
        event_type,
        payload,
        event_id=event_id,
        timestamp=engine.now(),
        sim_time=engine.status.sim_time,
        source=ENGINE_SOURCE,
        location=None,
        severity=Severity.INFO,
    )


@router.websocket("/ws")
async def event_stream(
    websocket: WebSocket, runner: RunnerDep, bus: BusDep, settings: SettingsDep, types: str | None = None
) -> None:
    await websocket.accept()
    subscription = bus.subscribe(types.split(",") if types else None, maxsize=settings.event_queue_size)
    try:
        await websocket.send_text(snapshot_event(runner).model_dump_json())
        sender = asyncio.create_task(_forward(websocket, subscription, runner, settings.ws_heartbeat_seconds))
        receiver = asyncio.create_task(_until_disconnect(websocket))
        _, pending = await asyncio.wait({sender, receiver}, return_when=asyncio.FIRST_COMPLETED)
        for task in pending:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await task
    finally:
        bus.unsubscribe(subscription)


async def _forward(
    websocket: WebSocket, subscription: Subscription, runner: SimulationRunner, heartbeat_seconds: float
) -> None:
    while True:
        try:
            event = await asyncio.wait_for(subscription.queue.get(), timeout=heartbeat_seconds)
        except TimeoutError:
            event = heartbeat_event(runner)
        await websocket.send_text(event.model_dump_json())


async def _until_disconnect(websocket: WebSocket) -> None:
    """Client messages are read and ignored; reading is what notices a disconnect promptly."""
    while True:
        message = await websocket.receive()
        if message["type"] == "websocket.disconnect":
            return
