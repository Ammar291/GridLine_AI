"""Real-time pacing of the engine (spec §7.3): one asyncio tick task, a small state machine, and the bus.

idle --start--> running <--pause/resume--> paused; reset and select_scenario cancel the task and return to
idle at tick 0. Every transition publishes one ``sim.status`` numbered by the engine, so replays match.
"""

import asyncio
import contextlib
import logging
from typing import Any

from pydantic import AwareDatetime, BaseModel

from gridline.errors import InvalidTransition
from gridline.events.bus import EventBus
from gridline.events.envelope import Event
from gridline.events.payloads import RunnerState
from gridline.events.types import EventType, Severity
from gridline.simulation.engine import SimulationEngine
from gridline.simulation.scenarios import ScenarioName, get_scenario
from gridline.simulation.triggers import TriggerName, run_trigger

logger = logging.getLogger(__name__)

MIN_SPEED = 0.25
MAX_SPEED = 10.0


class StageInfo(BaseModel):
    index: int
    name: str
    description: str
    start_tick: int


class SimulationStatus(BaseModel):
    state: RunnerState
    running: bool
    scenario: ScenarioName
    seed: int
    speed: float
    tick: int
    sim_time: AwareDatetime
    stage: StageInfo | None
    minutes_per_tick: int
    tick_seconds: float


class SimulationRunner:
    def __init__(self, engine: SimulationEngine, bus: EventBus, *, tick_seconds: float) -> None:
        self.engine = engine
        self.bus = bus
        self.tick_seconds = tick_seconds
        self._state: RunnerState = "idle"
        self._gate = asyncio.Event()  # set while running; the tick task waits on it
        self._task: asyncio.Task[None] | None = None

    @property
    def state(self) -> RunnerState:
        return self._state

    def status(self) -> SimulationStatus:
        engine = self.engine.status
        stage = StageInfo(
            index=engine.stage_index,
            name=engine.stage_name,
            description=engine.stage_description,
            start_tick=engine.stage_start_tick,
        )
        return SimulationStatus(
            state=self._state,
            running=self._state == "running",
            scenario=engine.scenario,
            seed=engine.seed,
            speed=self.engine.speed,
            tick=engine.tick,
            sim_time=engine.sim_time,
            stage=stage,
            minutes_per_tick=self.engine.minutes_per_tick,
            tick_seconds=self.tick_seconds,
        )

    # ---- transitions ----

    async def select_scenario(self, scenario: str, seed: int | None = None) -> SimulationStatus:
        """Stop, load ``scenario`` (keeping the seed unless one is given) and reset to tick 0."""
        chosen = get_scenario(scenario)
        await self._stop()
        next_seed = seed if seed is not None else (self.engine.status.seed if self.engine.has_reset else 0)
        self._publish(self.engine.reset(chosen.name, next_seed))
        return self._transition("idle")

    async def reset(self) -> SimulationStatus:
        """Same scenario and seed, back to tick 0, idle."""
        status = self.engine.status
        await self._stop()
        self._publish(self.engine.reset(status.scenario, status.seed))
        return self._transition("idle")

    async def start(
        self, scenario: str | None = None, seed: int | None = None, speed: float | None = None
    ) -> SimulationStatus:
        if self._state == "running":
            raise InvalidTransition("simulation is already running")
        if self._state == "paused":
            raise InvalidTransition("simulation is paused; use resume")
        if speed is not None:
            _check_speed(speed)
        if scenario is not None or seed is not None or not self.engine.has_reset:
            current = self.engine.status.scenario if self.engine.has_reset else ScenarioName.NORMAL_CITY
            chosen = get_scenario(scenario or current)
            seed_now = seed if seed is not None else (self.engine.status.seed if self.engine.has_reset else 0)
            self._publish(self.engine.reset(chosen.name, seed_now))
        if speed is not None:
            self.engine.speed = speed
        self._task = asyncio.create_task(self._loop(), name="simulation-ticks")
        return self._transition("running")

    async def pause(self) -> SimulationStatus:
        if self._state != "running":
            raise InvalidTransition(f"cannot pause while {self._state}")
        return self._transition("paused")

    async def resume(self) -> SimulationStatus:
        if self._state != "paused":
            raise InvalidTransition(f"cannot resume while {self._state}")
        return self._transition("running")

    async def set_speed(self, speed: float) -> SimulationStatus:
        _check_speed(speed)
        self.engine.speed = speed
        return self._transition(self._state)

    async def advance(self, ticks: int = 1) -> list[Event]:
        if self._state == "running":
            raise InvalidTransition("cannot advance manually while running; pause first")
        events = self.engine.advance(ticks)
        self._publish(events)
        return events

    async def inject(
        self,
        event_type: EventType | str,
        payload: dict[str, Any],
        *,
        location: str | None = None,
        source: str = "operator:api",
        severity: Severity | None = None,
    ) -> list[Event]:
        events = self.engine.inject(event_type, payload, location=location, source=source, severity=severity)
        self._publish(events)
        return events

    async def trigger(self, name: TriggerName) -> list[Event]:
        """A DEMO control, in any runner state. No await inside: the tick loop cannot interleave the batch."""
        events = run_trigger(self.engine, name)
        self._publish(events)
        return events

    async def shutdown(self) -> None:
        await self._stop()

    # ---- internals ----

    def _transition(self, state: RunnerState) -> SimulationStatus:
        self._state = state
        self.engine.running = state == "running"
        if state == "running":
            self._gate.set()
        else:
            self._gate.clear()
        self.bus.publish(self.engine.status_event(state))
        return self.status()

    async def _stop(self) -> None:
        self._gate.clear()
        task, self._task = self._task, None
        if task is not None:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

    def _publish(self, events: list[Event]) -> None:
        for event in events:
            self.bus.publish(event)

    async def _loop(self) -> None:
        while True:
            await self._gate.wait()
            try:
                events = self.engine.advance()
            except Exception:  # an engine bug must not kill the process silently; log and keep ticking
                logger.exception("simulation tick failed")
                events = []
            self._publish(events)
            await asyncio.sleep(self.tick_seconds / self.engine.speed)


def _check_speed(speed: float) -> None:
    if not MIN_SPEED <= speed <= MAX_SPEED:
        raise ValueError(f"speed must be between {MIN_SPEED} and {MAX_SPEED}, got {speed}")
