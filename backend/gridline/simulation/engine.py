"""The synchronous, seed-deterministic simulation engine (spec §7.1).

Given (scenario, seed, ticks) and a fixed clock, two engines produce identical event lists. The engine makes
no decisions: scenarios drive weather and excavation, physics moves the world, sensors report it.
"""

import random
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

from pydantic import AwareDatetime, BaseModel

from gridline.city.model import City
from gridline.errors import NotInjectable
from gridline.events.envelope import Event, new_event
from gridline.events.payloads import (
    PAYLOAD_MODELS,
    ConstructionActivity,
    Payload,
    RunnerState,
    ScenarioStage,
    SimStatus,
    SimTick,
    WeatherForecast,
)
from gridline.events.types import INJECTABLE_TYPES, Band, EventType, Severity
from gridline.simulation import physics as ph
from gridline.simulation.apply import apply_event
from gridline.simulation.dynamics import apply_drivers, step_physics, weather_at
from gridline.simulation.scenarios import Scenario, ScenarioName, get_scenario
from gridline.simulation.schedule import ScriptSchedule
from gridline.simulation.sensors import ENGINE_SOURCE, observe
from gridline.simulation.severity import severity_for
from gridline.simulation.world import WorldSnapshot, WorldState
from gridline.threats.indices import zone_state_events

SIM_START = datetime(2026, 7, 14, 6, 0, tzinfo=UTC)  # every scenario starts here (spec A6)
REPORT_DEPTH_STEP_M = 0.1  # excavation progress reported every 10 cm


def utcnow() -> datetime:
    return datetime.now(UTC)


class EngineStatus(BaseModel):
    scenario: ScenarioName
    seed: int
    tick: int
    sim_time: AwareDatetime
    stage_index: int
    stage_name: str
    stage_description: str
    stage_start_tick: int


class SimulationEngine:
    def __init__(
        self, city: City, *, minutes_per_tick: int = 5, clock: Callable[[], datetime] = utcnow
    ) -> None:
        self.city = city
        self.minutes_per_tick = minutes_per_tick
        self.speed = 1.0  # informational, set by the runner and reported in sim.tick
        self.running = False  # informational, set by the runner and reported in sim.tick
        self._clock = clock
        self._dt_h = minutes_per_tick / 60
        self._scenario: Scenario | None = None
        self._world: WorldState | None = None
        self._seed = 0
        self._rng = random.Random(0)
        self._counter = 0
        self._schedule = ScriptSchedule(())
        self._reported_depth: dict[str, float] = {}
        self._bands: dict[str, Band] = {}  # each zone's band at the last tick

    # ---- lifecycle ----

    def reset(self, scenario: ScenarioName | str, seed: int) -> list[Event]:
        """Rebuild the world from the city at tick 0; emits stage 0 and any tick-0 forecast."""
        chosen = get_scenario(scenario)
        self._scenario, self._seed = chosen, seed
        self._rng = random.Random(seed)
        self._counter = 0
        self._bands = {}
        self._world = WorldState.from_city(
            self.city,
            start=SIM_START,
            weather=weather_at(chosen, 0),
            antecedent_saturation=chosen.antecedent_saturation,
            window_ticks=round(24 * 60 / self.minutes_per_tick),
        )
        if chosen.excavation is not None and chosen.excavation.start_tick == 0:
            self._world.projects[chosen.excavation.project_id].activity = "excavating"
        self._reported_depth = {p.id: p.excavation_depth_m for p in self.city.projects}
        self._schedule = ScriptSchedule(chosen.scripted)
        return [self._stage_event(0), *self._forecasts(0), *self._scripted(0)]

    @property
    def has_reset(self) -> bool:
        return self._world is not None

    @property
    def scenario(self) -> Scenario:
        if self._scenario is None:
            raise RuntimeError("engine has not been reset")
        return self._scenario

    @property
    def world(self) -> WorldState:
        if self._world is None:
            raise RuntimeError("engine has not been reset")
        return self._world

    @property
    def status(self) -> EngineStatus:
        world, scenario = self.world, self.scenario
        stage = scenario.stages[world.stage_index]
        return EngineStatus(
            scenario=scenario.name,
            seed=self._seed,
            tick=world.tick,
            sim_time=world.sim_time,
            stage_index=world.stage_index,
            stage_name=stage.name,
            stage_description=stage.description,
            stage_start_tick=stage.start_tick,
        )

    def snapshot(self) -> WorldSnapshot:
        return self.world.snapshot()

    def replay(self, scenario: ScenarioName | str, seed: int, ticks: int) -> list[Event]:
        return self.reset(scenario, seed) + self.advance(ticks)

    # ---- stepping ----

    def advance(self, ticks: int = 1) -> list[Event]:
        events: list[Event] = []
        for _ in range(ticks):
            events += self._tick()
        return events

    def _tick(self) -> list[Event]:
        world, scenario = self.world, self.scenario
        world.tick += 1
        world.sim_time += timedelta(minutes=self.minutes_per_tick)
        tick = world.tick
        events: list[Event] = []
        for index, stage in enumerate(scenario.stages):
            if stage.start_tick == tick:
                world.stage_index = index
                events.append(self._stage_event(index))
        apply_drivers(world, self.city, scenario, tick, self._dt_h)
        events += self._forecasts(tick)
        events += self._excavate(tick)
        step_physics(world, self.city, scenario, tick, self._dt_h)
        events += self._scripted(tick)
        events += observe(world, self.city, self._rng, self.make_event)
        events += zone_state_events(world, self.city, self._bands, self.make_event)
        stage = scenario.stages[world.stage_index]
        payload = SimTick(
            tick=tick,
            sim_time=world.sim_time,
            scenario=scenario.name,
            stage=stage.name,
            speed=self.speed,
            running=self.running,
        )
        events.append(self.make_event(EventType.SIM_TICK, payload, source=ENGINE_SOURCE, location=None))
        return events

    def _excavate(self, tick: int) -> list[Event]:
        excavation = self.scenario.excavation
        if excavation is None or tick < excavation.start_tick:
            return []
        project = self.city.project(excavation.project_id)
        state = self.world.projects[project.id]
        if state.status != "active":
            return []
        before = state.activity
        state.excavation_depth_m = ph.step_excavation(
            state.excavation_depth_m,
            project.planned_depth_m,
            excavation.rate_m_per_h,
            self._dt_h,
            active=True,
        )
        state.activity = "excavating" if state.excavation_depth_m < project.planned_depth_m else "idle"
        progressed = state.excavation_depth_m - self._reported_depth[project.id] >= REPORT_DEPTH_STEP_M - 1e-9
        if state.activity == before and not progressed:
            return []
        self._reported_depth[project.id] = state.excavation_depth_m
        payload = ConstructionActivity(
            project_id=project.id,
            status=state.status,
            activity=state.activity,
            excavation_depth_m=round(state.excavation_depth_m, 2),
            planned_depth_m=project.planned_depth_m,
        )
        return [
            self.make_event(
                EventType.INFRASTRUCTURE_CONSTRUCTION, payload, source=ENGINE_SOURCE, location=project.zone_id
            )
        ]

    def _forecasts(self, tick: int) -> list[Event]:
        events: list[Event] = []
        for update in self.scenario.forecasts:
            if update.tick == tick:
                forecast = WeatherForecast(
                    issued_sim_time=self.world.sim_time, **update.model_dump(exclude={"tick"})
                )
                events += self._apply(EventType.WEATHER_FORECAST, forecast, source=self._scenario_source())
        return events

    def _scripted(self, tick: int) -> list[Event]:
        events: list[Event] = []
        for scripted in self._schedule.due(tick, self.world):
            model = PAYLOAD_MODELS[scripted.event_type].model_validate(scripted.payload)
            events += self._apply(scripted.event_type, model, source=self._scenario_source())
        return events

    # ---- injection and events ----

    def inject(
        self,
        event_type: EventType | str,
        payload: dict[str, Any],
        *,
        location: str | None = None,
        source: str = "operator:api",
        severity: Severity | None = None,
    ) -> list[Event]:
        """Apply an operator event now; returns it plus derived events. Observations cannot be injected."""
        kind = EventType(event_type)
        if kind not in INJECTABLE_TYPES:
            raise NotInjectable(f"{kind} is derived from state and cannot be injected")
        model = PAYLOAD_MODELS[kind].model_validate(payload)
        return self._apply(kind, model, source=source, location=location, severity=severity)

    def _apply(
        self,
        event_type: EventType,
        payload: Payload,
        *,
        source: str,
        location: str | None = None,
        severity: Severity | None = None,
    ) -> list[Event]:
        events = apply_event(
            self.world,
            self.city,
            event_type,
            payload,
            source=source,
            location=location,
            severity=severity,
            make=self.make_event,
        )
        for event in events:
            if event.event_type == EventType.INFRASTRUCTURE_CONSTRUCTION:
                project_id = str(event.payload["project_id"])
                self._reported_depth[project_id] = self.world.projects[project_id].excavation_depth_m
        return events

    def make_event(
        self,
        event_type: EventType,
        payload: Payload,
        *,
        source: str,
        location: str | None,
        severity: Severity | None = None,
    ) -> Event:
        """Next event id, the wall clock, the sim time, and the sensor band unless a severity is given."""
        self._counter += 1
        return new_event(
            event_type,
            payload,
            event_id=f"evt-{self._counter:06d}",
            timestamp=self._clock(),
            sim_time=self.world.sim_time,
            source=source,
            location=location,
            severity=severity or severity_for(event_type, payload, self.city.thresholds),
        )

    def status_payload(self, state: RunnerState) -> SimStatus:
        status = self.status
        return SimStatus(
            state=state,
            running=state == "running",
            scenario=status.scenario,
            seed=status.seed,
            speed=self.speed,
            tick=status.tick,
            sim_time=status.sim_time,
            stage=status.stage_name,
        )

    def status_event(self, state: RunnerState) -> Event:
        """A ``sim.status`` event numbered by this engine's counter, so transitions replay identically."""
        payload = self.status_payload(state)
        return self.make_event(EventType.SIM_STATUS, payload, source=ENGINE_SOURCE, location=None)

    def now(self) -> datetime:
        """The engine's wall clock (injectable for tests)."""
        return self._clock()

    def _stage_event(self, index: int) -> Event:
        scenario = self.scenario
        stage = scenario.stages[index]
        payload = ScenarioStage(
            scenario=scenario.name,
            stage_index=index,
            stage=stage.name,
            description=stage.description,
            tick=self.world.tick,
        )
        return self.make_event(
            EventType.SCENARIO_STAGE, payload, source=self._scenario_source(), location=None
        )

    def _scenario_source(self) -> str:
        return f"scenario:{self.scenario.name}"
