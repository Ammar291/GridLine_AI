# DEMO Controls and Minimal Risk Indices Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Seven DEMO-mode buttons (Heavy Rain, Landslide, Drainage Block, Flash Flood, Industrial Fire, Cascading
Disaster, Reset) inject deterministic world facts into the existing engine → bus → `/ws` → dashboard pipeline, and a
minimal per-zone landslide/flood index (`zone.state`) makes "HIGH risk" a computed, visible signal.

**Architecture:** Two new injectable driver events (`weather.rainfall`, `emergency.fire`) extend `simulation/apply.py`.
A pure `gridline/threats/indices.py` computes indices from `WorldState` after every tick and the engine emits one
`zone.state` per zone. `simulation/triggers.py` holds the button presets as data; `run_trigger` announces the press
(`scenario.trigger`), injects its steps through `engine.inject`, and advances 12 ticks. The frontend moves the detector
contract out of the pending overlay, renders the button row from `GET /api/city` `triggers`, and snaps timeline markers
to the next reading.

**Tech Stack:** Python 3.13, FastAPI, Pydantic v2, pytest (asyncio auto), pyright strict, ruff (uv) · React 19,
TypeScript strict, TanStack Query, zustand, vitest + Testing Library, openapi-typescript (`npm run gen:api`).

**Spec:** `docs/superpowers/specs/2026-09-26-demo-controls-design.md` (read it before starting any task).

## Global Constraints

- Branch `feature/demo-controls`. **Do not commit** — CLAUDE.md: "Commit only when asked." Each task ends at a checkpoint.
- The working tree already holds uncommitted LIVE-mode work (`gridline/sources/`, `api/source.py`, frontend `source/`). Do not revert or reformat unrelated files.
- No scripted conclusions (CLAUDE.md rule 3): triggers inject world facts only; bands come from `gridline/threats/indices.py`.
- "HIGH" = band `warning`; `zone.state` severity maps normal→info, watch→moderate, warning→high, critical→critical.
- Band edges: watch 0.35, warning 0.55, critical 0.75 (both hazards). Trigger advance: `TRIGGER_ADVANCE_TICKS = 12`.
- Trigger source string: `operator:demo`. Detector source string: `threats:indices`.
- Backend: fully typed, `uv run pyright` strict clean, `uv run ruff check .` and `uv run ruff format --check .` clean; files about ≤300 lines; Pydantic v2 for every boundary model; payloads forbid unknown keys.
- Frontend: `strict`, no `any`, no default exports except `App`; payload types only from the generated `schema.d.ts` (`types.ts` re-exports); never hand-write payload types.
- Domain names: zone, channel, project, crew, incident… Do not invent synonyms.
- Backend commands run from `backend/`; frontend commands from `frontend/`. While the backend contract is changing (Tasks 1–4) run the suite with `--deselect tests/test_contract_export.py::test_committed_contract_files_are_current`; Task 5 regenerates the contract and re-enables it.
- Baseline before this plan: backend `520 passed, 1 skipped`; frontend `265 passed`, typecheck clean.

## Review Focus

1. **A button pressed while the simulation is running** — the trigger's 12 ticks and the runner's tick loop must not interleave inside one published batch. Test: Task 4 `test_trigger_while_running_publishes_one_contiguous_batch`.
2. **The same button pressed twice, or late in a storm after SL-HV-1 already failed** — must not raise; the second press re-applies its facts. Test: Task 4 `test_every_trigger_can_be_pressed_twice_late_in_the_storm`.
3. **Reset after several buttons** — rain overrides, fires, obstructions and remembered bands must all be gone (the next ticks equal a fresh run). Test: Task 4 `test_reset_restores_the_original_city`.
4. **A button pressed at tick 0 (fresh reset, idle)** — its timeline marker must still appear although no reading row exists at that sim time. Test: Task 6 `snaps a milestone to the next reading row`.
5. **Rapid clicks in the dashboard** — every demo button is disabled while any control request is pending. Test: Task 6 `disables every demo event while a request is pending`.

---

### Task 1: `weather.rainfall` — operator rain as an injectable driver

**Files:**
- Modify: `backend/gridline/events/types.py` (add `WEATHER_RAINFALL`, make it injectable)
- Modify: `backend/gridline/events/payloads.py` (add `RainfallDriver`, register in `PAYLOAD_MODELS`)
- Modify: `backend/gridline/simulation/world.py` (add `RainOverride`, `WorldState.rain_overrides`)
- Modify: `backend/gridline/simulation/apply.py` (add `_rainfall` handler)
- Modify: `backend/gridline/simulation/dynamics.py` (`apply_drivers` honours overrides)
- Modify: `backend/gridline/simulation/severity.py` (rule for `weather.rainfall`)
- Modify: `backend/gridline/api/event_models.py` (typed `RainfallDriverEvent`)
- Test: `backend/tests/test_rainfall.py` (new), `backend/tests/test_payloads.py`, `backend/tests/test_severity.py`, `backend/tests/test_event_envelope.py`

**Interfaces:**
- Consumes: `SimulationEngine.inject(event_type, payload, *, location=None, source="operator:api", severity=None) -> list[Event]` (existing).
- Produces: `EventType.WEATHER_RAINFALL = "weather.rainfall"`; `payloads.RainfallDriver(zone_ids: list[str] = [], intensity_mm_h: float (0,200], duration_h: float (0,24], description: str = "")`; `world.RainOverride(intensity_mm_h: float, until: AwareDatetime)`; `WorldState.rain_overrides: dict[str, RainOverride]` (internal, not in `WorldSnapshot`).

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_rainfall.py`:

```python
"""weather.rainfall: operator rain raises the scenario's rain in the named zones until it expires."""

import pytest

from gridline.city.model import City
from gridline.errors import UnknownAsset
from gridline.events.types import EventType, Severity
from gridline.simulation.engine import SimulationEngine
from gridline.simulation.scenarios import ScenarioName


@pytest.fixture
def engine(city: City) -> SimulationEngine:
    engine = SimulationEngine(city)
    engine.reset(ScenarioName.NORMAL_CITY, seed=1)
    return engine


def rain(engine: SimulationEngine, zone_id: str) -> float:
    return engine.snapshot().zones[zone_id].rainfall_intensity_mm_h


def test_rainfall_overrides_the_scenario_rain_in_the_named_zones(engine: SimulationEngine) -> None:
    events = engine.inject(
        EventType.WEATHER_RAINFALL, {"zone_ids": ["Z-HV"], "intensity_mm_h": 60, "duration_h": 1}
    )
    assert [e.event_type for e in events] == [EventType.WEATHER_RAINFALL]
    assert events[0].location == "Z-HV" and events[0].severity == Severity.HIGH
    engine.advance(1)
    assert rain(engine, "Z-HV") == 60
    assert rain(engine, "Z-RS") < 5


def test_rainfall_expires_after_its_duration(engine: SimulationEngine) -> None:
    engine.inject(EventType.WEATHER_RAINFALL, {"zone_ids": ["Z-HV"], "intensity_mm_h": 60, "duration_h": 1})
    engine.advance(12)  # 12 ticks of 5 minutes: still inside the hour
    assert rain(engine, "Z-HV") == 60
    engine.advance(1)
    assert rain(engine, "Z-HV") < 5


def test_empty_zone_ids_means_every_zone(engine: SimulationEngine) -> None:
    events = engine.inject(EventType.WEATHER_RAINFALL, {"intensity_mm_h": 20, "duration_h": 1})
    assert events[0].location is None
    engine.advance(1)
    assert all(z.rainfall_intensity_mm_h == 20 for z in engine.snapshot().zones.values())


def test_rainfall_never_lowers_the_scenario_rain(engine: SimulationEngine) -> None:
    engine.advance(120)  # normal_city rain has risen to about 2.7 mm/h by now
    scenario_rain = engine.scenario.rain_at("Z-HV", 121)
    engine.inject(EventType.WEATHER_RAINFALL, {"zone_ids": ["Z-HV"], "intensity_mm_h": 0.5, "duration_h": 1})
    engine.advance(1)
    assert rain(engine, "Z-HV") == pytest.approx(scenario_rain)


def test_unknown_zone_is_rejected(engine: SimulationEngine) -> None:
    with pytest.raises(UnknownAsset):
        engine.inject(EventType.WEATHER_RAINFALL, {"zone_ids": ["Z-XX"], "intensity_mm_h": 20, "duration_h": 1})


def test_reset_clears_the_override(engine: SimulationEngine) -> None:
    engine.inject(EventType.WEATHER_RAINFALL, {"intensity_mm_h": 60, "duration_h": 3})
    engine.reset(ScenarioName.NORMAL_CITY, seed=1)
    engine.advance(1)
    assert rain(engine, "Z-HV") < 5
```

In `backend/tests/test_payloads.py` add to `VALID` (after the `p.WeatherForecast(...)` entry):

```python
    p.RainfallDriver(zone_ids=["Z-HV"], intensity_mm_h=60, duration_h=3, description="cloudburst"),
```

and to `INVALID`:

```python
    (p.RainfallDriver, {"intensity_mm_h": 0, "duration_h": 1}),
    (p.RainfallDriver, {"intensity_mm_h": 20, "duration_h": 25}),
```

In `backend/tests/test_severity.py` add to `CASES` (before the `SIM_HEARTBEAT` case):

```python
    (EventType.WEATHER_RAINFALL, p.RainfallDriver(intensity_mm_h=5, duration_h=1), INF),
    (EventType.WEATHER_RAINFALL, p.RainfallDriver(intensity_mm_h=20, duration_h=1), L),
    (EventType.WEATHER_RAINFALL, p.RainfallDriver(intensity_mm_h=35, duration_h=1), M),
    (EventType.WEATHER_RAINFALL, p.RainfallDriver(intensity_mm_h=60, duration_h=1), H),
```

In `backend/tests/test_event_envelope.py`, `test_injectable_types_are_state_changing_only`, replace the `all(...)` assertion with:

```python
    assert all(
        t.startswith(("infrastructure.", "emergency.")) or t in ("weather.forecast", "weather.rainfall")
        for t in INJECTABLE_TYPES
    )
    assert EventType.WEATHER_RAINFALL in INJECTABLE_TYPES
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_rainfall.py tests/test_payloads.py tests/test_severity.py tests/test_event_envelope.py -q`
Expected: FAIL / collection error — `AttributeError: WEATHER_RAINFALL` and `module 'gridline.events.payloads' has no attribute 'RainfallDriver'`.

- [ ] **Step 3: Implement**

`backend/gridline/events/types.py` — add after `WEATHER_FORECAST = "weather.forecast"`:

```python
    WEATHER_RAINFALL = "weather.rainfall"
```

and add `EventType.WEATHER_RAINFALL,` to `INJECTABLE_TYPES` (after `EventType.WEATHER_FORECAST,`).

`backend/gridline/events/payloads.py` — add after `class WeatherForecast`:

```python
class RainfallDriver(Payload):
    """Operator rain: ``intensity_mm_h`` over ``zone_ids`` (empty means every zone) for ``duration_h`` hours.

    A driver, not a reading: the scenario's own rain resumes when it ends, and it never lowers the scenario's rain.
    """

    zone_ids: list[str] = Field(default_factory=list[str])
    intensity_mm_h: float = Field(gt=0, le=200)
    duration_h: float = Field(gt=0, le=24)
    description: str = ""
```

and in `PAYLOAD_MODELS` after `EventType.WEATHER_FORECAST: WeatherForecast,`:

```python
    EventType.WEATHER_RAINFALL: RainfallDriver,
```

`backend/gridline/simulation/world.py` — add after `class WeatherState`:

```python
class RainOverride(BaseModel):
    """Operator rain on one zone until a sim time (``weather.rainfall``); internal, not in the snapshot."""

    intensity_mm_h: float
    until: AwareDatetime
```

and in `@dataclass class WorldState`, after `forecast: WeatherForecast | None = field(default=None)`:

```python
    rain_overrides: dict[str, RainOverride] = field(default_factory=dict[str, RainOverride])
```

`backend/gridline/simulation/apply.py` — add `from datetime import timedelta` to the imports, add `RainOverride` to the `gridline.simulation.world` import list, add the handler after `_forecast`:

```python
def _rainfall(ctx: _Ctx, r: p.Payload) -> list[Event]:
    assert isinstance(r, p.RainfallDriver)
    zone_ids = [ctx.city.zone(z).id for z in r.zone_ids] or [z.id for z in ctx.city.zones]
    until = ctx.world.sim_time + timedelta(hours=r.duration_h)
    for zone_id in zone_ids:
        ctx.world.rain_overrides[zone_id] = RainOverride(intensity_mm_h=r.intensity_mm_h, until=until)
    location = zone_ids[0] if len(r.zone_ids) == 1 else None
    return [ctx.emit(EventType.WEATHER_RAINFALL, r, location)]
```

and register it in `_HANDLERS` after `EventType.WEATHER_FORECAST: _forecast,`:

```python
    EventType.WEATHER_RAINFALL: _rainfall,
```

`backend/gridline/simulation/dynamics.py` — replace `apply_drivers` with:

```python
def apply_drivers(world: WorldState, city: City, scenario: Scenario, tick: int, dt_h: float) -> None:
    """Scenario rain per zone, raised to any operator rain still in force (and its 24 h window), and weather."""
    for zone in city.zones:
        state = world.zones[zone.id]
        state.rainfall_intensity_mm_h = _rain(world, scenario, zone.id, tick)
        window = world.rain_window[zone.id]
        window.append(state.rainfall_intensity_mm_h * dt_h)
        state.rain_24h_mm = sum(window)
    world.weather = weather_at(scenario, tick)


def _rain(world: WorldState, scenario: Scenario, zone_id: str, tick: int) -> float:
    rain = scenario.rain_at(zone_id, tick)
    override = world.rain_overrides.get(zone_id)
    if override is not None and world.sim_time <= override.until:
        rain = max(rain, override.intensity_mm_h)
    return rain
```

(The engine advances `world.sim_time` before calling `apply_drivers`, so an override issued at T for 1 h covers the 12 ticks up to T + 1 h.)

`backend/gridline/simulation/severity.py` — add after `_forecast`:

```python
def _rainfall(obs: p.RainfallDriver, t: PolicyThresholds) -> Severity:
    rain = [(RAIN_LOW_MM_H, L), (t.rain_1h_watch_mm_h, M), (t.rain_1h_warning_mm_h, H)]
    return banded(obs.intensity_mm_h, rain)
```

and in `RULES` after the `WEATHER_FORECAST` entry:

```python
    EventType.WEATHER_RAINFALL: _band(p.RainfallDriver, _rainfall),
```

`backend/gridline/api/event_models.py` — add after `class WeatherForecastEvent`:

```python
class RainfallDriverEvent(EventBase):
    event_type: Literal[EventType.WEATHER_RAINFALL]
    payload: p.RainfallDriver
```

add `EventType.WEATHER_RAINFALL: RainfallDriverEvent,` to `EVENT_MODELS` after the forecast entry, and `| RainfallDriverEvent` to `AnyEvent` after `| WeatherForecastEvent`.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_rainfall.py tests/test_payloads.py tests/test_severity.py tests/test_event_envelope.py tests/test_event_models.py -q`
Expected: all PASS.

- [ ] **Step 5: Full backend check**

Run: `uv run ruff format . && uv run ruff check . && uv run pyright && uv run pytest -q --deselect tests/test_contract_export.py::test_committed_contract_files_are_current`
Expected: ruff/pyright clean (`0 errors`); pytest all pass.

- [ ] **Step 6: Checkpoint** — do not commit (CLAUDE.md). Report the changed files and test counts.

---

### Task 2: `emergency.fire` — industrial fire with population exposure from city data

**Files:**
- Modify: `backend/gridline/city/model.py` (`Zone.population`, `Zone.bbox`)
- Modify: `backend/gridline/city/nandipur.py` (`_zones` fills them)
- Modify: `backend/gridline/events/types.py`, `backend/gridline/events/payloads.py` (`EMERGENCY_FIRE`, `IndustrialFire`)
- Modify: `backend/gridline/simulation/world.py` (`FireState`, `WorldState.fires`, `WorldSnapshot.fires`)
- Modify: `backend/gridline/simulation/apply.py` (`_fire`, `_bbox_gap_m`, `FIRE_EXPOSURE_M`)
- Modify: `backend/gridline/simulation/severity.py` (`_fire`, `FIRE_CRITICAL_POPULATION`)
- Modify: `backend/gridline/api/event_models.py` (`IndustrialFireEvent`)
- Test: `backend/tests/test_fire.py` (new), `backend/tests/test_payloads.py`, `backend/tests/test_severity.py`

**Interfaces:**
- Consumes: `City.zone(zone_id) -> Zone`, `_Ctx.emit` (existing).
- Produces: `Zone.population: int = 0`, `Zone.bbox: tuple[float, float, float, float] = (0, 0, 0, 0)` (x0, y0, x1, y1 metres); `EventType.EMERGENCY_FIRE = "emergency.fire"` (injectable); `payloads.IndustrialFire(zone_id: str, site: str, description: str = "", exposed_zone_ids: list[str] = [], exposed_population: int = 0)`; `world.FireState(site: str, exposed_zone_ids: list[str], exposed_population: int)`; `WorldSnapshot.fires: dict[str, FireState]` keyed by zone id.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_fire.py`:

```python
"""emergency.fire: a fire in a zone exposes that zone and every zone within 500 m, counted from city data."""

import pytest

from gridline.city.model import City
from gridline.errors import UnknownAsset
from gridline.events.types import EventType, Severity
from gridline.simulation.engine import SimulationEngine
from gridline.simulation.scenarios import ScenarioName

FIRE = {"zone_id": "Z-MI", "site": "Mill Road warehouse", "description": "solvent store alight"}


@pytest.fixture
def engine(city: City) -> SimulationEngine:
    engine = SimulationEngine(city)
    engine.reset(ScenarioName.NORMAL_CITY, seed=1)
    return engine


def test_zone_population_and_bbox_come_from_the_data(city: City) -> None:
    mill_road = city.zone("Z-MI")
    assert mill_road.population == 22000
    assert mill_road.bbox == (8400, 0, 12000, 2700)


def test_fire_exposes_its_zone_and_the_zones_within_500_m(engine: SimulationEngine) -> None:
    [fire] = engine.inject(EventType.EMERGENCY_FIRE, FIRE)
    assert fire.location == "Z-MI" and fire.severity == Severity.CRITICAL
    assert fire.payload["exposed_zone_ids"] == ["Z-NC", "Z-MI"]  # New Colony touches Mill Road; Riverside is 600 m off
    assert fire.payload["exposed_population"] == 80000
    state = engine.snapshot().fires["Z-MI"]
    assert (state.site, state.exposed_population, state.exposed_zone_ids) == (
        "Mill Road warehouse",
        80000,
        ["Z-NC", "Z-MI"],
    )


def test_a_quiet_city_has_no_fires(engine: SimulationEngine) -> None:
    assert engine.snapshot().fires == {}


def test_unknown_zone_is_rejected(engine: SimulationEngine) -> None:
    with pytest.raises(UnknownAsset):
        engine.inject(EventType.EMERGENCY_FIRE, {**FIRE, "zone_id": "Z-XX"})


def test_reset_puts_the_fire_out(engine: SimulationEngine) -> None:
    engine.inject(EventType.EMERGENCY_FIRE, FIRE)
    engine.reset(ScenarioName.NORMAL_CITY, seed=1)
    assert engine.snapshot().fires == {}
```

In `backend/tests/test_payloads.py` add to `VALID` (after `p.ShelterCapacity(...)`):

```python
    p.IndustrialFire(zone_id="Z-MI", site="Mill Road warehouse"),
```

and to `INVALID`:

```python
    (p.IndustrialFire, {"zone_id": "Z-MI", "site": "s", "exposed_population": -1}),
```

In `backend/tests/test_severity.py` add to `CASES`:

```python
    (EventType.EMERGENCY_FIRE, p.IndustrialFire(zone_id="Z-MI", site="s", exposed_population=5000), H),
    (EventType.EMERGENCY_FIRE, p.IndustrialFire(zone_id="Z-MI", site="s", exposed_population=80000), C),
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_fire.py tests/test_payloads.py tests/test_severity.py -q`
Expected: FAIL — `AttributeError: EMERGENCY_FIRE` / `'Zone' object has no attribute 'population'`.

- [ ] **Step 3: Implement**

`backend/gridline/city/model.py`, class `Zone`, add after `drains_to_channel_id`:

```python
    population: int = Field(default=0, ge=0)  # zone_yearly_stats population for the as-of year
    bbox: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)  # x0, y0, x1, y1 in metres
```

`backend/gridline/city/nandipur.py`, `_zones`: add after the `impervious = ...` line

```python
    population = {s.zone_id: s.population for s in data.zone_yearly_stats if s.year == year}
```

and add to the `Zone(...)` call after `drains_to_channel_id=z.drains_to_channel_id,`:

```python
                population=population[z.id],
                bbox=(x0, y0, x1, y1),
```

`backend/gridline/events/types.py`: add `EMERGENCY_FIRE = "emergency.fire"` after `EMERGENCY_SHELTER`, and `EventType.EMERGENCY_FIRE,` to `INJECTABLE_TYPES`.

`backend/gridline/events/payloads.py` — add after `class ShelterCapacity`:

```python
class IndustrialFire(Payload):
    """A fire at a site in a zone; who is exposed is computed from the city by the apply handler."""

    zone_id: str
    site: str
    description: str = ""
    exposed_zone_ids: list[str] = Field(default_factory=list[str])  # filled from the city by the apply handler
    exposed_population: int = Field(default=0, ge=0)  # filled from the city by the apply handler
```

and `EventType.EMERGENCY_FIRE: IndustrialFire,` at the end of `PAYLOAD_MODELS`.

`backend/gridline/simulation/world.py` — add after `class ShelterState`:

```python
class FireState(BaseModel):
    site: str
    exposed_zone_ids: list[str]
    exposed_population: int
```

add `fires: dict[str, FireState]` as the last field of `WorldSnapshot`; in `WorldState` add after `rain_overrides`:

```python
    fires: dict[str, FireState] = field(default_factory=dict[str, FireState])  # keyed by zone id
```

and in `WorldState.snapshot()` add `fires=_copies(self.fires),` after `shelters=...`.

`backend/gridline/simulation/apply.py` — add `import math` to the imports, `FireState` to the world import list, the constant after `LANDSLIDE_REASON`:

```python
FIRE_EXPOSURE_M = 500.0  # zones whose boundary lies within this distance of the burning zone are exposed
```

the handler after `_shelter`:

```python
def _fire(ctx: _Ctx, f: p.Payload) -> list[Event]:
    assert isinstance(f, p.IndustrialFire)
    zone = ctx.city.zone(f.zone_id)
    exposed = [z for z in ctx.city.zones if _bbox_gap_m(zone.bbox, z.bbox) <= FIRE_EXPOSURE_M]
    ids, population = [z.id for z in exposed], sum(z.population for z in exposed)
    ctx.world.fires[zone.id] = FireState(site=f.site, exposed_zone_ids=ids, exposed_population=population)
    filled = f.model_copy(update={"exposed_zone_ids": ids, "exposed_population": population})
    return [ctx.emit(EventType.EMERGENCY_FIRE, filled, zone.id)]


def _bbox_gap_m(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> float:
    """Shortest distance between two axis-aligned boxes; 0 when they touch or overlap."""
    dx = max(0.0, b[0] - a[2], a[0] - b[2])
    dy = max(0.0, b[1] - a[3], a[1] - b[3])
    return math.hypot(dx, dy)
```

and `EventType.EMERGENCY_FIRE: _fire,` at the end of `_HANDLERS`.

`backend/gridline/simulation/severity.py` — add the constant after `OBSTRUCTION_BANDS`:

```python
FIRE_CRITICAL_POPULATION = 20000  # exposed people from which a fire is critical rather than high
```

the rule after `_shelter`:

```python
def _fire(obs: p.IndustrialFire, _: PolicyThresholds) -> Severity:
    return C if obs.exposed_population >= FIRE_CRITICAL_POPULATION else H
```

and `EventType.EMERGENCY_FIRE: _band(p.IndustrialFire, _fire),` at the end of `RULES`.

`backend/gridline/api/event_models.py` — add after `class ShelterCapacityEvent`:

```python
class IndustrialFireEvent(EventBase):
    event_type: Literal[EventType.EMERGENCY_FIRE]
    payload: p.IndustrialFire
```

`EventType.EMERGENCY_FIRE: IndustrialFireEvent,` in `EVENT_MODELS`, `| IndustrialFireEvent` in `AnyEvent`.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_fire.py tests/test_payloads.py tests/test_severity.py tests/test_event_models.py tests/test_city.py tests/test_engine_injection.py -q`
Expected: all PASS.

- [ ] **Step 5: Full backend check**

Run: `uv run ruff format . && uv run ruff check . && uv run pyright && uv run pytest -q --deselect tests/test_contract_export.py::test_committed_contract_files_are_current`
Expected: clean; all pass.

- [ ] **Step 6: Checkpoint** — do not commit.

---

### Task 3: Risk indices, `zone.state`, and `GET /api/detector/bands`

**Files:**
- Create: `backend/gridline/threats/__init__.py`, `backend/gridline/threats/indices.py`
- Create: `backend/gridline/api/detector.py`
- Modify: `backend/gridline/events/types.py` (`Band`, `ZONE_STATE`)
- Modify: `backend/gridline/events/payloads.py` (`ZoneStatePayload`)
- Modify: `backend/gridline/simulation/engine.py` (remember bands, emit `zone.state` each tick)
- Modify: `backend/gridline/simulation/severity.py` (`_zone_state`)
- Modify: `backend/gridline/api/event_models.py` (`ZoneStateEvent`)
- Modify: `backend/gridline/main.py` (include the detector router)
- Test: `backend/tests/test_indices.py` (new), `backend/tests/test_api_detector.py` (new), `backend/tests/test_payloads.py`, `backend/tests/test_severity.py`

**Interfaces:**
- Consumes: `WorldState`, `City`, `slope_cut_m(world, city, slope_id) -> float` (dynamics), `clamp`, `EXC_REF_DEPTH_M`, `SLOPE_REF_DEG` (physics), `MakeEvent` (sensors).
- Produces:
  - `events.types.Band(StrEnum)`: `NORMAL="normal"`, `WATCH="watch"`, `WARNING="warning"`, `CRITICAL="critical"`; `EventType.ZONE_STATE = "zone.state"` (not injectable).
  - `payloads.ZoneStatePayload(zone_id, saturation, rain_24h_mm, rain_intensity_mm_h, landslide_index, flood_index, band: Band, prev_band: Band | None = None, updated_sim_time: AwareDatetime)`.
  - `threats.indices`: `DETECTOR_SOURCE = "threats:indices"`, `LANDSLIDE_WEIGHTS`, `FLOOD_WEIGHTS`, `BandThresholds(watch, warning, critical)`, `Bands(landslide, flood)`, `THRESHOLDS`, `BANDS`, `band_of(index: float) -> Band`, `landslide_index(world, city, zone_id) -> float`, `flood_index(world, city, zone_id) -> float`, `zone_state_events(world, city, bands: dict[str, Band], make: MakeEvent) -> list[Event]`.
  - `GET /api/detector/bands -> Bands`.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_indices.py`:

```python
"""Per-zone landslide and flood indices: factors, bands, and one zone.state per zone after every tick."""

import pytest

from gridline.city.model import City
from gridline.events.envelope import Event
from gridline.events.types import Band, EventType, Severity
from gridline.simulation.engine import SimulationEngine
from gridline.simulation.scenarios import ScenarioName
from gridline.simulation.world import WorldState
from gridline.threats.indices import (
    DETECTOR_SOURCE,
    FLOOD_WEIGHTS,
    LANDSLIDE_WEIGHTS,
    band_of,
    flood_index,
    landslide_index,
)


def quiet_world(city: City) -> WorldState:
    engine = SimulationEngine(city)
    engine.reset(ScenarioName.NORMAL_CITY, seed=1)
    return engine.world


def test_weights_sum_to_one() -> None:
    assert sum(LANDSLIDE_WEIGHTS.values()) == pytest.approx(1)
    assert sum(FLOOD_WEIGHTS.values()) == pytest.approx(1)


@pytest.mark.parametrize(
    ("index", "band"),
    [(0.0, Band.NORMAL), (0.349, Band.NORMAL), (0.35, Band.WATCH), (0.549, Band.WATCH), (0.55, Band.WARNING),
     (0.75, Band.CRITICAL), (1.0, Band.CRITICAL)],
)
def test_band_edges(index: float, band: Band) -> None:
    assert band_of(index) == band


def test_a_quiet_city_is_normal_everywhere(city: City) -> None:
    world = quiet_world(city)
    for zone in city.zones:
        assert band_of(max(landslide_index(world, city, zone.id), flood_index(world, city, zone.id))) == Band.NORMAL


def test_a_zone_without_slopes_has_no_landslide_index(city: City) -> None:
    assert landslide_index(quiet_world(city), city, "Z-RS") == 0.0


@pytest.mark.parametrize("factor", ["saturation", "rain_24h", "cut", "movement"])
def test_each_landslide_factor_raises_the_hillview_index(city: City, factor: str) -> None:
    world = quiet_world(city)
    before = landslide_index(world, city, "Z-HV")
    match factor:
        case "saturation":
            world.slopes["SL-HV-1"].saturation = 0.85
        case "rain_24h":
            world.zones["Z-HV"].rain_24h_mm = 175
        case "cut":
            world.projects["PR-HT2"].excavation_depth_m = 6.0
        case _:
            world.slopes["SL-HV-1"].movement_rate_mm_h = 30
    assert landslide_index(world, city, "Z-HV") > before


def test_a_saturated_moving_cut_slope_is_critical(city: City) -> None:
    world = quiet_world(city)
    world.slopes["SL-HV-1"].saturation = 0.85
    world.slopes["SL-HV-1"].movement_rate_mm_h = 30
    world.zones["Z-HV"].rain_24h_mm = 175
    world.projects["PR-HT2"].excavation_depth_m = 6.0
    index = landslide_index(world, city, "Z-HV")
    assert index == pytest.approx(0.96)  # every factor at 1 except steepness (32 degrees: 0.6)
    assert band_of(index) == Band.CRITICAL


@pytest.mark.parametrize("factor", ["rain", "saturation", "load", "blocked", "water"])
def test_each_flood_factor_raises_the_riverside_index(city: City, factor: str) -> None:
    world = quiet_world(city)
    before = flood_index(world, city, "Z-RS")
    match factor:
        case "rain":
            world.zones["Z-RS"].rainfall_intensity_mm_h = 50
        case "saturation":
            world.zones["Z-RS"].saturation = 1.0
        case "load":
            world.channels["D-7"].flow_m3s = 2 * world.channels["D-7"].capacity_m3s  # D-7 overflows into Riverside
        case "blocked":
            world.channels["D-7"].blocked_fraction = 0.7
        case _:
            world.zones["Z-RS"].water_depth_cm = 50
    assert flood_index(world, city, "Z-RS") > before


def zone_states(events: list[Event]) -> list[Event]:
    return [e for e in events if e.event_type == EventType.ZONE_STATE]


def test_the_engine_emits_one_zone_state_per_zone_each_tick(city: City) -> None:
    engine = SimulationEngine(city)
    engine.reset(ScenarioName.NORMAL_CITY, seed=1)
    events = engine.advance(2)
    states = zone_states(events)
    n = len(city.zones)
    assert len(states) == 2 * n
    assert [s.location for s in states[:n]] == [z.id for z in city.zones]
    assert all(s.payload["prev_band"] is None for s in states[:n])
    assert all(s.payload["prev_band"] == "normal" for s in states[n:])
    assert all(s.source == DETECTOR_SOURCE and s.severity == Severity.INFO for s in states)
    first_tick = events[: events.index(next(e for e in events if e.event_type == EventType.SIM_TICK)) + 1]
    assert first_tick[-2].event_type == EventType.ZONE_STATE  # after the readings, just before sim.tick


def test_reset_forgets_the_previous_bands(city: City) -> None:
    engine = SimulationEngine(city)
    engine.reset(ScenarioName.NORMAL_CITY, seed=1)
    engine.advance(1)
    engine.reset(ScenarioName.NORMAL_CITY, seed=1)
    assert all(s.payload["prev_band"] is None for s in zone_states(engine.advance(1)))
```

Create `backend/tests/test_api_detector.py`:

```python
from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient

from gridline.city.model import City
from gridline.config import Settings
from gridline.main import create_app


@pytest.fixture
async def client(settings: Settings, city: City) -> AsyncIterator[AsyncClient]:
    app = create_app(settings, city=city)
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client,
    ):
        yield client


async def test_bands_are_the_index_thresholds(client: AsyncClient) -> None:
    response = await client.get("/api/detector/bands")
    assert response.status_code == 200
    edges = {"watch": 0.35, "warning": 0.55, "critical": 0.75}
    assert response.json() == {"landslide": edges, "flood": edges}
```

In `backend/tests/test_payloads.py` add `from gridline.events.types import Band` to the imports, to `VALID`:

```python
    p.ZoneStatePayload(
        zone_id="Z-HV",
        saturation=0.5,
        rain_24h_mm=10,
        rain_intensity_mm_h=2,
        landslide_index=0.2,
        flood_index=0.1,
        band=Band.NORMAL,
        updated_sim_time=NOW,
    ),
```

and to `INVALID`:

```python
    (
        p.ZoneStatePayload,
        {
            "zone_id": "Z-HV",
            "saturation": 0.5,
            "rain_24h_mm": 0,
            "rain_intensity_mm_h": 0,
            "landslide_index": 1.5,
            "flood_index": 0,
            "band": "normal",
            "updated_sim_time": NOW,
        },
    ),
```

In `backend/tests/test_severity.py` add `from gridline.events.types import Band` (extend the existing import) and a helper plus cases:

```python
def zone(band: Band) -> p.ZoneStatePayload:
    return p.ZoneStatePayload(
        zone_id="Z-HV", saturation=0.5, rain_24h_mm=0, rain_intensity_mm_h=0, landslide_index=0,
        flood_index=0, band=band, updated_sim_time=NOW,
    )
```

```python
    (EventType.ZONE_STATE, zone(Band.NORMAL), INF),
    (EventType.ZONE_STATE, zone(Band.WATCH), M),
    (EventType.ZONE_STATE, zone(Band.WARNING), H),
    (EventType.ZONE_STATE, zone(Band.CRITICAL), C),
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_indices.py tests/test_api_detector.py tests/test_payloads.py tests/test_severity.py -q`
Expected: FAIL — `ModuleNotFoundError: gridline.threats` / `ImportError: cannot import name 'Band'`.

- [ ] **Step 3: Implement the types and payload**

`backend/gridline/events/types.py` — add after `SEVERITY_ORDER`:

```python
class Band(StrEnum):
    """A zone's risk band from its landslide and flood indices (``gridline.threats.indices``)."""

    NORMAL = "normal"
    WATCH = "watch"
    WARNING = "warning"
    CRITICAL = "critical"
```

and `ZONE_STATE = "zone.state"` in `EventType` after `SCENARIO_STAGE` (not in `INJECTABLE_TYPES`).

`backend/gridline/events/payloads.py` — change the import to `from gridline.events.types import Band, EventType`, and add after `class ScenarioStage`:

```python
class ZoneStatePayload(Payload):
    """One zone's risk indices after a tick (``gridline.threats.indices``): a signal, never a decision."""

    zone_id: str
    saturation: float = Field(ge=0, le=1)
    rain_24h_mm: float = Field(ge=0)
    rain_intensity_mm_h: float = Field(ge=0)
    landslide_index: float = Field(ge=0, le=1)
    flood_index: float = Field(ge=0, le=1)
    band: Band
    prev_band: Band | None = None
    updated_sim_time: AwareDatetime
```

and `EventType.ZONE_STATE: ZoneStatePayload,` in `PAYLOAD_MODELS` after `SCENARIO_STAGE`.

- [ ] **Step 4: Implement the index module**

Create `backend/gridline/threats/__init__.py`:

```python
"""Threat signals derived from the live world (ARCHITECTURE section 5). Only the risk indices exist so far."""
```

Create `backend/gridline/threats/indices.py`:

```python
"""Per-zone landslide and flood indices (ARCHITECTURE section 5), the minimal slice the DEMO controls need.

Each index is a weighted sum of factors clamped to [0, 1], read from the live world and the city's policy
thresholds, so a different world gives a different number. The indices are signals, not decisions. Weights and
band edges are named constants here; hysteresis, incidents and a config file belong to the full detector.
"""

from pydantic import BaseModel

from gridline.city.model import City
from gridline.events.envelope import Event
from gridline.events.payloads import ZoneStatePayload
from gridline.events.types import Band, EventType
from gridline.simulation.dynamics import slope_cut_m
from gridline.simulation.physics import EXC_REF_DEPTH_M, SLOPE_REF_DEG, clamp
from gridline.simulation.sensors import MakeEvent
from gridline.simulation.world import ChannelState, WorldState

DETECTOR_SOURCE = "threats:indices"
SAT_FLOOR = 0.5  # slope saturation below which the saturation factor is 0
CREEP_REF_MM_H = 30.0  # slope movement rate at which the movement factor is 1 (the critical sensor band)
WATER_REF_CM = 50.0  # standing water at which the water factor is 1 (the critical sensor band)
LANDSLIDE_WEIGHTS: dict[str, float] = {
    "saturation": 0.35,
    "rain_24h": 0.15,
    "cut": 0.2,
    "movement": 0.2,
    "steepness": 0.1,
}
FLOOD_WEIGHTS: dict[str, float] = {"rain": 0.15, "saturation": 0.1, "load": 0.35, "blocked": 0.15, "water": 0.25}


class BandThresholds(BaseModel):
    watch: float
    warning: float
    critical: float


class Bands(BaseModel):
    landslide: BandThresholds
    flood: BandThresholds


THRESHOLDS = BandThresholds(watch=0.35, warning=0.55, critical=0.75)
BANDS = Bands(landslide=THRESHOLDS, flood=THRESHOLDS)


def band_of(index: float) -> Band:
    if index >= THRESHOLDS.critical:
        return Band.CRITICAL
    if index >= THRESHOLDS.warning:
        return Band.WARNING
    return Band.WATCH if index >= THRESHOLDS.watch else Band.NORMAL


def landslide_index(world: WorldState, city: City, zone_id: str) -> float:
    """The worst slope of the zone; a zone without slopes has 0."""
    t, zone = city.thresholds, world.zones[zone_id]
    best = 0.0
    for slope in city.slopes:
        if slope.zone_id != zone_id:
            continue
        state = world.slopes[slope.id]
        factors = {
            "saturation": (state.saturation - SAT_FLOOR) / (t.saturation_critical - SAT_FLOOR),
            "rain_24h": zone.rain_24h_mm / t.rain_24h_critical_mm,
            "cut": slope_cut_m(world, city, slope.id) / EXC_REF_DEPTH_M,
            "movement": state.movement_rate_mm_h / CREEP_REF_MM_H,
            "steepness": (slope.mean_angle_deg - SLOPE_REF_DEG) / SLOPE_REF_DEG,
        }
        best = max(best, _weighted(factors, LANDSLIDE_WEIGHTS))
    return best


def flood_index(world: WorldState, city: City, zone_id: str) -> float:
    """Rain, soil and the drains that overflow into the zone (their ``downstream_zone_id``)."""
    t, zone = city.thresholds, world.zones[zone_id]
    channels = [world.channels[c.id] for c in city.channels if c.downstream_zone_id == zone_id]
    factors = {
        "rain": zone.rainfall_intensity_mm_h / t.rain_1h_warning_mm_h,
        "saturation": zone.saturation,
        "load": max((_load(c) for c in channels), default=0.0) / t.channel_ratio_critical,
        "blocked": max((c.blocked_fraction for c in channels), default=0.0),
        "water": zone.water_depth_cm / WATER_REF_CM,
    }
    return _weighted(factors, FLOOD_WEIGHTS)


def zone_state_events(world: WorldState, city: City, bands: dict[str, Band], make: MakeEvent) -> list[Event]:
    """One ``zone.state`` per zone in city order; ``bands`` holds each zone's previous band, updated in place."""
    events: list[Event] = []
    for zone in city.zones:
        state = world.zones[zone.id]
        landslide, flood = landslide_index(world, city, zone.id), flood_index(world, city, zone.id)
        band = band_of(max(landslide, flood))
        payload = ZoneStatePayload(
            zone_id=zone.id,
            saturation=round(state.saturation, 3),
            rain_24h_mm=round(state.rain_24h_mm, 1),
            rain_intensity_mm_h=round(state.rainfall_intensity_mm_h, 2),
            landslide_index=landslide,
            flood_index=flood,
            band=band,
            prev_band=bands.get(zone.id),
            updated_sim_time=world.sim_time,
        )
        bands[zone.id] = band
        events.append(make(EventType.ZONE_STATE, payload, source=DETECTOR_SOURCE, location=zone.id))
    return events


def _load(channel: ChannelState) -> float:
    if channel.capacity_m3s > 0:
        return channel.flow_m3s / channel.capacity_m3s
    return 1.0 if channel.flow_m3s > 0 else 0.0


def _weighted(factors: dict[str, float], weights: dict[str, float]) -> float:
    return round(sum(weights[name] * clamp(value, 0.0, 1.0) for name, value in factors.items()), 3)
```

- [ ] **Step 5: Wire the engine, severity, event model and route**

`backend/gridline/simulation/engine.py`:
- extend the import `from gridline.events.types import INJECTABLE_TYPES, Band, EventType, Severity`;
- add `from gridline.threats.indices import zone_state_events`;
- in `__init__` after `self._reported_depth: dict[str, float] = {}` add `self._bands: dict[str, Band] = {}  # each zone's band at the last tick`;
- in `reset()` after `self._counter = 0` add `self._bands = {}`;
- in `_tick()` replace `events += observe(world, self.city, self._rng, self.make_event)` with:

```python
        events += observe(world, self.city, self._rng, self.make_event)
        events += zone_state_events(world, self.city, self._bands, self.make_event)
```

`backend/gridline/simulation/severity.py` — add `Band` to the `gridline.events.types` import, and after `_fire`:

```python
def _zone_state(obs: p.ZoneStatePayload, _: PolicyThresholds) -> Severity:
    return {Band.NORMAL: INF, Band.WATCH: M, Band.WARNING: H, Band.CRITICAL: C}[obs.band]
```

and `EventType.ZONE_STATE: _band(p.ZoneStatePayload, _zone_state),` in `RULES`.

`backend/gridline/api/event_models.py` — add after `class ScenarioStageEvent`:

```python
class ZoneStateEvent(EventBase):
    event_type: Literal[EventType.ZONE_STATE]
    payload: p.ZoneStatePayload
```

`EventType.ZONE_STATE: ZoneStateEvent,` in `EVENT_MODELS`, `| ZoneStateEvent` in `AnyEvent` after `| ScenarioStageEvent`.

Create `backend/gridline/api/detector.py`:

```python
"""``/api/detector/*``: the thresholds the dashboard draws on the risk timeline."""

from fastapi import APIRouter

from gridline.threats.indices import BANDS, Bands

router = APIRouter(prefix="/detector", tags=["detector"])


@router.get("/bands")
async def get_bands() -> Bands:
    return BANDS
```

`backend/gridline/main.py` — `from gridline.api.detector import router as detector_router` and `app.include_router(detector_router, prefix="/api")` after the simulation router.

- [ ] **Step 6: Run the tests to verify they pass**

Run: `uv run pytest tests/test_indices.py tests/test_api_detector.py tests/test_payloads.py tests/test_severity.py tests/test_event_models.py tests/test_determinism.py -q`
Expected: all PASS.

- [ ] **Step 7: Full backend check and the demo smoke**

Run: `uv run ruff format . && uv run ruff check . && uv run pyright && uv run pytest -q --deselect tests/test_contract_export.py::test_committed_contract_files_are_current && uv run python ../scripts/demo_smoke.py`
Expected: clean; all pass; demo smoke exits 0. If a WebSocket test's `next_of(..., limit=500)` now runs out of frames (ten more events per tick), raise that test's `limit` — do not change the engine.

- [ ] **Step 8: Checkpoint** — do not commit.

---

### Task 4: Triggers — presets, `scenario.trigger`, runner, route, city listing

**Files:**
- Create: `backend/gridline/simulation/triggers.py`
- Modify: `backend/gridline/events/types.py`, `backend/gridline/events/payloads.py` (`SCENARIO_TRIGGER`, `ScenarioTrigger`)
- Modify: `backend/gridline/api/event_models.py` (`ScenarioTriggerEvent`)
- Modify: `backend/gridline/simulation/runner.py` (`trigger`)
- Modify: `backend/gridline/api/simulation_models.py` (`TriggerRequest`), `backend/gridline/api/simulation.py` (route)
- Modify: `backend/gridline/api/city_map.py` (`CityMap.triggers`)
- Test: `backend/tests/test_triggers.py` (new), `backend/tests/test_api_trigger.py` (new), `backend/tests/test_websocket.py`, `backend/tests/test_city_map.py`, `backend/tests/test_payloads.py`

**Interfaces:**
- Consumes: `SimulationEngine.inject`, `.advance`, `.make_event`, `.world`; `SimulationRunner._publish`; `DemoRunnerDep`; `typed_event`.
- Produces:
  - `EventType.SCENARIO_TRIGGER = "scenario.trigger"`; `payloads.ScenarioTrigger(trigger: str, label: str, description: str, tick: int)`.
  - `simulation.triggers`: `TRIGGER_SOURCE = "operator:demo"`, `TRIGGER_ADVANCE_TICKS = 12`, `TriggerName(StrEnum)` with values `heavy_rain, landslide, drainage_block, flash_flood, industrial_fire, cascading_disaster` (in that order), `TriggerStep(event_type, payload)`, `Trigger(name, label, description, steps)`, `TriggerInfo(id: TriggerName, label, description)`, `TRIGGERS: dict[TriggerName, Trigger]`, `trigger_infos() -> list[TriggerInfo]`, `run_trigger(engine, name) -> list[Event]`.
  - `SimulationRunner.trigger(name: TriggerName) -> list[Event]` (async, publishes).
  - `POST /api/simulation/trigger` body `TriggerRequest{trigger: TriggerName}` → `list[Event]`; `CityMap.triggers: list[TriggerInfo]`.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_triggers.py`:

```python
"""Each DEMO control injects world facts and, one simulated hour later, the computed outcome the spec names."""

import asyncio
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
    assert last_zone_state(events, "Z-RS")["flood_index"] > last_zone_state(quiet_events, "Z-RS")["flood_index"]


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
    assert last_zone_state(events, "Z-RS")["flood_index"] > last_zone_state(quiet_events, "Z-RS")["flood_index"]


@pytest.mark.parametrize("base", BASES)
def test_flash_flood_overloads_d7_and_puts_riverside_at_high_flood_risk(city: City, base: ScenarioName) -> None:
    engine = fresh(city, base)
    riverside = last_zone_state(run_trigger(engine, TriggerName.FLASH_FLOOD), "Z-RS")
    assert load_ratio(engine, "D-7") > 1
    assert riverside["band"] in HIGH


@pytest.mark.parametrize("base", BASES)
def test_industrial_fire_exposes_the_neighbouring_population(city: City, base: ScenarioName) -> None:
    engine = fresh(city, base)
    [fire] = [e for e in run_trigger(engine, TriggerName.INDUSTRIAL_FIRE) if e.event_type == EventType.EMERGENCY_FIRE]
    assert fire.location == "Z-MI" and fire.payload["exposed_population"] > 0
    assert "Z-MI" in fire.payload["exposed_zone_ids"]
    assert "Z-MI" in engine.snapshot().fires


@pytest.mark.parametrize("base", BASES)
def test_cascading_disaster_runs_landslide_then_blockage_then_flood(city: City, base: ScenarioName) -> None:
    events = run_trigger(fresh(city, base), TriggerName.CASCADING_DISASTER)

    def first(predicate: Any) -> int:
        return next(i for i, e in enumerate(events) if predicate(e))

    failure = first(lambda e: e.event_type == EventType.INFRASTRUCTURE_FAILURE)
    blockage = first(
        lambda e: e.event_type == EventType.INFRASTRUCTURE_DRAINAGE_OBSTRUCTION and e.payload["channel_id"] == "D-7"
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
```

Create `backend/tests/test_api_trigger.py`:

```python
from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient

from gridline.city.model import City
from gridline.config import Settings
from gridline.main import create_app


@pytest.fixture
async def client(settings: Settings, city: City) -> AsyncIterator[AsyncClient]:
    settings.live_forecast_base_url = "http://127.0.0.1:9/v1/forecast"  # LIVE mode must never touch the network
    app = create_app(settings, city=city)
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client,
    ):
        yield client


async def test_trigger_returns_its_events_and_advances_one_hour(client: AsyncClient) -> None:
    response = await client.post("/api/simulation/trigger", json={"trigger": "flash_flood"})
    assert response.status_code == 200, response.text
    events = response.json()
    assert events[0]["event_type"] == "scenario.trigger" and events[0]["payload"]["label"] == "Flash Flood"
    status = (await client.get("/api/simulation/status")).json()
    assert (status["tick"], status["state"]) == (12, "idle")


async def test_unknown_trigger_is_rejected(client: AsyncClient) -> None:
    response = await client.post("/api/simulation/trigger", json={"trigger": "meteor"})
    assert response.status_code == 422


async def test_trigger_is_refused_in_live_mode(client: AsyncClient) -> None:
    await client.post("/api/source", json={"mode": "live"})
    response = await client.post("/api/simulation/trigger", json={"trigger": "heavy_rain"})
    assert response.status_code == 409 and "DEMO" in response.json()["detail"]


async def test_the_city_lists_the_triggers_in_button_order(client: AsyncClient) -> None:
    city = (await client.get("/api/city")).json()
    assert [(t["id"], t["label"]) for t in city["triggers"]] == [
        ("heavy_rain", "Heavy Rain"),
        ("landslide", "Landslide"),
        ("drainage_block", "Drainage Block"),
        ("flash_flood", "Flash Flood"),
        ("industrial_fire", "Industrial Fire"),
        ("cascading_disaster", "Cascading Disaster"),
    ]
```

In `backend/tests/test_websocket.py` add:

```python
def test_trigger_events_arrive_on_the_socket_in_order(client: TestClient) -> None:
    with client.websocket_connect("/ws") as ws:
        ws.receive_json()
        response = client.post("/api/simulation/trigger", json={"trigger": "cascading_disaster"})
        ids = [e["event_id"] for e in response.json()]
        received: list[str] = []
        while len(received) < len(ids):
            frame = ws.receive_json()
            if frame["event_id"] in ids:
                received.append(frame["event_id"])
    assert received == ids
```

In `backend/tests/test_city_map.py`, `test_scenarios_and_injection_presets_are_listed`, append:

```python
    assert [t.id for t in city_map.triggers] == [
        "heavy_rain",
        "landslide",
        "drainage_block",
        "flash_flood",
        "industrial_fire",
        "cascading_disaster",
    ]
```

In `backend/tests/test_payloads.py` add to `VALID`:

```python
    p.ScenarioTrigger(trigger="heavy_rain", label="Heavy Rain", description="d", tick=0),
```

and to `INVALID`: `(p.ScenarioTrigger, {"trigger": "heavy_rain", "label": "l", "description": "d", "tick": -1}),`

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_triggers.py tests/test_api_trigger.py tests/test_websocket.py tests/test_city_map.py tests/test_payloads.py -q`
Expected: FAIL — `ModuleNotFoundError: gridline.simulation.triggers`.

- [ ] **Step 3: Implement the announcement event**

`backend/gridline/events/types.py`: `SCENARIO_TRIGGER = "scenario.trigger"` after `SCENARIO_STAGE` (not injectable).

`backend/gridline/events/payloads.py` — after `class ScenarioStage`:

```python
class ScenarioTrigger(Payload):
    """An operator pressed a DEMO control; its injected events and one simulated hour follow on the bus."""

    trigger: str
    label: str
    description: str
    tick: int = Field(ge=0)
```

and `EventType.SCENARIO_TRIGGER: ScenarioTrigger,` in `PAYLOAD_MODELS`. (Severity: no rule, so `info`.)

`backend/gridline/api/event_models.py`:

```python
class ScenarioTriggerEvent(EventBase):
    event_type: Literal[EventType.SCENARIO_TRIGGER]
    payload: p.ScenarioTrigger
```

plus `EVENT_MODELS` and `AnyEvent` entries after the stage ones.

- [ ] **Step 4: Implement the presets**

Create `backend/gridline/simulation/triggers.py`:

```python
"""DEMO controls (docs/superpowers/specs/2026-09-26-demo-controls-design.md).

Each trigger is an ordered list of operator events — world facts such as rain, a cut, a blocked drain or a fire —
applied through the normal injection path; one simulated hour then lets physics and sensors show the consequences.
A trigger never states a conclusion: the risk bands come from ``gridline.threats.indices``.
"""

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict

from gridline.events.envelope import Event
from gridline.events.payloads import ScenarioTrigger
from gridline.events.types import EventType
from gridline.simulation.engine import SimulationEngine

TRIGGER_SOURCE = "operator:demo"
TRIGGER_ADVANCE_TICKS = 12  # one simulated hour at five minutes per tick


class TriggerName(StrEnum):
    HEAVY_RAIN = "heavy_rain"
    LANDSLIDE = "landslide"
    DRAINAGE_BLOCK = "drainage_block"
    FLASH_FLOOD = "flash_flood"
    INDUSTRIAL_FIRE = "industrial_fire"
    CASCADING_DISASTER = "cascading_disaster"


class TriggerStep(BaseModel):
    model_config = ConfigDict(frozen=True)

    event_type: EventType
    payload: dict[str, Any]


class Trigger(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: TriggerName
    label: str
    description: str
    steps: tuple[TriggerStep, ...]


class TriggerInfo(BaseModel):
    """A DEMO button as the dashboard lists it (``GET /api/city``)."""

    id: TriggerName
    label: str
    description: str


def _rain(zone_ids: tuple[str, ...], mm_h: float, hours: float, why: str) -> TriggerStep:
    payload = {"zone_ids": list(zone_ids), "intensity_mm_h": mm_h, "duration_h": hours, "description": why}
    return TriggerStep(event_type=EventType.WEATHER_RAINFALL, payload=payload)


_ALL = (
    Trigger(
        name=TriggerName.HEAVY_RAIN,
        label="Heavy Rain",
        description="A monsoon cell brings 20 mm/h over the whole city for three hours",
        steps=(_rain((), 20, 3, "monsoon cell over Nandipur"),),
    ),
    Trigger(
        name=TriggerName.LANDSLIDE,
        label="Landslide",
        description="PR-HT2 cuts SL-HV-1 to its planned 6 m while 60 mm/h of rain falls on Hillview",
        steps=(
            TriggerStep(
                event_type=EventType.INFRASTRUCTURE_CONSTRUCTION,
                payload={
                    "project_id": "PR-HT2",
                    "status": "active",
                    "activity": "excavating",
                    "excavation_depth_m": 6.0,
                },
            ),
            _rain(("Z-HV",), 60, 3, "cloudburst over Hillview"),
        ),
    ),
    Trigger(
        name=TriggerName.DRAINAGE_BLOCK,
        label="Drainage Block",
        description="Debris blocks 70 % of the Kalinadi drain D-7 above Riverside",
        steps=(
            TriggerStep(
                event_type=EventType.INFRASTRUCTURE_DRAINAGE_OBSTRUCTION,
                payload={"channel_id": "D-7", "blocked_fraction": 0.7, "cause": "debris jammed at the BR-4 culvert"},
            ),
        ),
    ),
    Trigger(
        name=TriggerName.FLASH_FLOOD,
        label="Flash Flood",
        description="A 70 mm/h cloudburst over Hillview and Riverside for two hours",
        steps=(_rain(("Z-HV", "Z-RS"), 70, 2, "cloudburst over Hillview and Riverside"),),
    ),
    Trigger(
        name=TriggerName.INDUSTRIAL_FIRE,
        label="Industrial Fire",
        description="A solvent warehouse catches fire in Mill Road Industrial",
        steps=(
            TriggerStep(
                event_type=EventType.EMERGENCY_FIRE,
                payload={
                    "zone_id": "Z-MI",
                    "site": "Mill Road solvent warehouse",
                    "description": "Warehouse fire on Mill Road (RD-08)",
                },
            ),
        ),
    ),
    Trigger(
        name=TriggerName.CASCADING_DISASTER,
        label="Cascading Disaster",
        description="SL-HV-1 fails, its debris blocks D-7, then 40 mm/h of rain floods Riverside",
        steps=(
            TriggerStep(
                event_type=EventType.INFRASTRUCTURE_FAILURE,
                payload={
                    "asset_id": "SL-HV-1",
                    "asset_kind": "slope",
                    "failure_kind": "landslide",
                    "description": "Hillview Terrace slope SL-HV-1 fails above D-7",
                },
            ),
            _rain(("Z-HV", "Z-RS"), 40, 3, "storm over the blocked drain"),
        ),
    ),
)
TRIGGERS: dict[TriggerName, Trigger] = {t.name: t for t in _ALL}


def trigger_infos() -> list[TriggerInfo]:
    return [TriggerInfo(id=t.name, label=t.label, description=t.description) for t in _ALL]


def run_trigger(engine: SimulationEngine, name: TriggerName) -> list[Event]:
    """Announce the press, inject its steps as the operator, then advance one simulated hour."""
    chosen = TRIGGERS[name]
    announcement = ScenarioTrigger(
        trigger=chosen.name, label=chosen.label, description=chosen.description, tick=engine.world.tick
    )
    events = [engine.make_event(EventType.SCENARIO_TRIGGER, announcement, source=TRIGGER_SOURCE, location=None)]
    for step in chosen.steps:
        events += engine.inject(step.event_type, step.payload, source=TRIGGER_SOURCE)
    return events + engine.advance(TRIGGER_ADVANCE_TICKS)
```

- [ ] **Step 5: Implement the runner method, route and city listing**

`backend/gridline/simulation/runner.py` — add `from gridline.simulation.triggers import TriggerName, run_trigger` and after `inject`:

```python
    async def trigger(self, name: TriggerName) -> list[Event]:
        """A DEMO control, in any runner state. No await inside, so the tick loop cannot interleave the batch."""
        events = run_trigger(self.engine, name)
        self._publish(events)
        return events
```

`backend/gridline/api/simulation_models.py` — add `from gridline.simulation.triggers import TriggerName` and:

```python
class TriggerRequest(BaseModel):
    trigger: TriggerName
```

`backend/gridline/api/simulation.py` — add `TriggerRequest` to the `simulation_models` import and:

```python
@router.post("/trigger")
async def trigger(body: TriggerRequest, runner: DemoRunnerDep) -> list[Event]:
    """Press a DEMO control: its announcement, injected events and one simulated hour, all published on the bus."""
    return [typed_event(e) for e in await runner.trigger(body.trigger)]
```

`backend/gridline/api/city_map.py` — add `from gridline.simulation.triggers import TriggerInfo, trigger_infos`, the field `triggers: list[TriggerInfo]` after `injections: list[InjectionPreset]` in `CityMap`, and `triggers=trigger_infos(),` after `injections=list(INJECTION_PRESETS),` in `build_city_map`.

- [ ] **Step 6: Run the tests to verify they pass**

Run: `uv run pytest tests/test_triggers.py tests/test_api_trigger.py tests/test_websocket.py tests/test_city_map.py tests/test_payloads.py tests/test_event_models.py -q`
Expected: all PASS.

- [ ] **Step 7: Full backend check and the demo smoke**

Run: `uv run ruff format . && uv run ruff check . && uv run pyright && uv run pytest -q --deselect tests/test_contract_export.py::test_committed_contract_files_are_current && uv run python ../scripts/demo_smoke.py`
Expected: clean; all pass; demo smoke exits 0.

- [ ] **Step 8: Checkpoint** — do not commit.

---

### Task 5: Frontend contract and event handling

**Files:**
- Regenerate: `frontend/openapi.json`, `frontend/src/mock/fixtures/nandipur.city.json`, `frontend/src/mock/fixtures/nandipur.world.json`, `frontend/src/api/schema.d.ts`
- Modify: `frontend/openapi.pending.yaml` (delete the detector entries except `Hazard`)
- Modify: `frontend/src/api/types.ts`, `client.ts`, `http.ts`, `queries.ts`; `frontend/src/mock/MockApiClient.ts`; `frontend/src/test/fakeClient.ts`
- Modify: `frontend/src/test/fixtures/events.ts`, `frontend/src/test/fixtures/city.ts`
- Modify: `frontend/src/live/describeEvent.ts`, `applyEvent.ts`, `applyWorld.ts`
- Test: `frontend/src/api/types.test.ts`, `frontend/src/api/http.test.ts`, `frontend/src/live/describeEvent.test.ts`, `frontend/src/live/applyEvent.test.ts`

**Interfaces:**
- Consumes (generated): `S['TriggerInfo']`, `S['TriggerName']`, `S['TriggerRequest']`, `S['FireState']`, `S['Band']`, `S['Bands']`, `S['BandThresholds']`, `S['ZoneStatePayload']`; events `weather.rainfall`, `emergency.fire`, `scenario.trigger`, `zone.state` in the backend union.
- Produces: `ApiClient.simulation.trigger(body: TriggerRequest): Promise<Event[]>`; `SimulationControls.trigger: UseMutationResult<Event[], ApiError, TriggerRequest>`; `types.ts` exports `TriggerInfo`, `TriggerName`, `TriggerRequest`, `FireState`, and `ZoneState = Omit<S['ZoneStatePayload'], 'zone_id' | 'prev_band'>`; `cityFixture.triggers` (six real ids); `eventsFixture` entries for the three new types.

- [ ] **Step 1: Regenerate the contract**

In `frontend/openapi.pending.yaml` delete: the `/api/detector/bands` path; the schemas `Band`, `BandThresholds`, `Bands`, `ZoneState`, `ZoneStatePayload`, `ZoneStateEvent`; the `- ZoneStateEvent` line under `x-pending-events`. Keep `Hazard`. In the header comment change the threat-detector line to:

```yaml
#   threat detector (ARCHITECTURE section 5)   threat.detected, threat.escalated; Hazard
```

Run: `npm run gen:api`
Expected: `wrote frontend/openapi.json`, both mock fixtures, and `wrote src/api/schema.d.ts` — no `gen:api: ... is now defined by the backend` error.

Then (backend): `cd ../backend && uv run pytest tests/test_contract_export.py -q` → PASS.

- [ ] **Step 2: Write the failing tests**

`frontend/src/api/types.test.ts` — in `fixtures carry every event type of the contract`, replace the backend and pending lists with:

```ts
      // backend (openapi.json)
      'emergency.ambulance', 'emergency.fire', 'emergency.hospital', 'emergency.rescue_team', 'emergency.shelter', 'environment.drainage',
      'environment.river', 'environment.slope', 'environment.soil', 'environment.water_accumulation', 'infrastructure.bridge',
      'infrastructure.construction', 'infrastructure.drainage_obstruction', 'infrastructure.failure', 'infrastructure.road',
      'scenario.stage', 'scenario.trigger', 'sim.heartbeat', 'sim.snapshot', 'sim.status', 'sim.tick', 'source.status', 'weather.forecast',
      'weather.observation', 'weather.rainfall', 'zone.state',
      // pending (openapi.pending.yaml)
      'action.executed', 'action.verified', 'agent.node.finished', 'agent.node.started', 'agent.run.finished', 'agent.run.started',
      'alert.issued', 'approval.decided', 'approval.requested', 'incident.closed', 'incident.opened', 'replan.triggered',
      'threat.detected', 'threat.escalated',
```

`frontend/src/api/http.test.ts` — in `PENDING routes answer 501…` remove `() => c.bands(), ` from the list, and add a test (reuse the file's `client`/`fakeFetch` helpers):

```ts
  it('bands() and simulation.trigger() call the backend', async () => {
    const f = fakeFetch(200, []);
    const c = client(f);
    await c.bands();
    expect(f.mock.calls[0]?.[0]).toBe('/api/detector/bands');
    await c.simulation.trigger({ trigger: 'flash_flood' });
    expect(f.mock.calls[1]?.[0]).toBe('/api/simulation/trigger');
    expect(JSON.parse(f.mock.calls[1]?.[1]?.body as string)).toEqual({ trigger: 'flash_flood' });
  });
```

`frontend/src/live/describeEvent.test.ts` — add:

```ts
  it('DEMO controls: the announcement, operator rain and a fire', () => {
    expect(d(ev['scenario.trigger'])).toBe('Demo event: Flash Flood');
    expect(d(ev['weather.rainfall'])).toBe('Rain 70 mm/h for 2 h over Hillview, Riverside: fixture: cloudburst');
    expect(d({ ...ev['weather.rainfall'], payload: { ...ev['weather.rainfall'].payload, zone_ids: [] } }))
      .toBe('Rain 70 mm/h for 2 h over the whole city: fixture: cloudburst');
    expect(d(ev['emergency.fire'])).toBe('Fire at fixture warehouse in Riverside: 80,000 people exposed in 2 zones');
    expect(eventGroup('weather.rainfall')).toBe('city');
    expect(eventGroup('emergency.fire')).toBe('city');
    expect(eventGroup('scenario.trigger')).toBe('simulation');
  });
```

`frontend/src/live/applyEvent.test.ts` — add:

```ts
describe('applyEvent: DEMO controls', () => {
  it('a scenario.trigger is a city-wide timeline marker', () => {
    const s = applyEvent(base(), ev['scenario.trigger']);
    expect(s.milestones.at(-1)).toMatchObject({ kind: 'scenario', label: 'Flash Flood', simTime: ev['scenario.trigger'].sim_time });
    expect(s.milestones.at(-1)?.zoneId).toBeUndefined();
  });

  it('an emergency.fire records the fire in the world and marks its zone', () => {
    const s = applyEvent(base(), ev['emergency.fire']);
    expect(s.world?.fires.riverside).toEqual({ site: 'fixture warehouse', exposed_zone_ids: ['riverside', 'old_town'], exposed_population: 80000 });
    expect(s.milestones.at(-1)).toMatchObject({ kind: 'infrastructure', label: 'Fire: fixture warehouse', zoneId: 'riverside' });
  });

  it('weather.rainfall lands in the feed only', () => {
    const before = base();
    const s = applyEvent(before, ev['weather.rainfall']);
    expect(s.feed.at(-1)).toBe(ev['weather.rainfall']);
    expect(s.milestones).toEqual(before.milestones);
    expect(s.world).toEqual(before.world);
  });

  it('a zone.state without a band change is routine: a full feed drops it first', () => {
    const quiet = { ...ev['zone.state'], event_id: 'quiet', payload: { ...ev['zone.state'].payload, prev_band: 'warning' as const } };
    let s = applyEvent(applyEvent(base(), quiet), ev['zone.state']);
    for (let i = 0; s.feed.length < FEED_CAP; i++) s = applyEvent(s, { ...ev['infrastructure.road'], event_id: `r${String(i)}` });
    s = applyEvent(s, ev['infrastructure.bridge']);
    expect(s.feed.some((e) => e.event_id === 'quiet')).toBe(false);
    expect(s.feed.some((e) => e.event_id === ev['zone.state'].event_id)).toBe(true);
  });
});
```

- [ ] **Step 3: Add the fixtures and type exports so the tests compile**

`frontend/src/test/fixtures/events.ts` — add to `eventsFixture` (backend section, next to the other backend events):

```ts
  'scenario.trigger': {
    ...base('scenario.trigger', { source: 'operator:demo' }),
    payload: { trigger: 'flash_flood', label: 'Flash Flood', description: 'fixture: cloudburst', tick: 13 },
  },
  'weather.rainfall': {
    ...base('weather.rainfall', { source: 'operator:demo', severity: 'high' }),
    payload: { zone_ids: ['hillview', 'riverside'], intensity_mm_h: 70, duration_h: 2, description: 'fixture: cloudburst' },
  },
  'emergency.fire': {
    ...base('emergency.fire', { location: 'riverside', source: 'operator:demo', severity: 'critical' }),
    payload: {
      zone_id: 'riverside', site: 'fixture warehouse', description: 'fixture: fire', exposed_zone_ids: ['riverside', 'old_town'],
      exposed_population: 80000,
    },
  },
```

`frontend/src/test/fixtures/city.ts` — add to `cityFixture` after `injections: [...]`:

```ts
  triggers: [
    { id: 'heavy_rain', label: 'Heavy Rain', description: 'fixture: rain over the city' },
    { id: 'landslide', label: 'Landslide', description: 'fixture: cut slope in the rain' },
    { id: 'drainage_block', label: 'Drainage Block', description: 'fixture: debris in D-7' },
    { id: 'flash_flood', label: 'Flash Flood', description: 'fixture: cloudburst' },
    { id: 'industrial_fire', label: 'Industrial Fire', description: 'fixture: warehouse fire' },
    { id: 'cascading_disaster', label: 'Cascading Disaster', description: 'fixture: landslide, blockage, flood' },
  ],
```

and `fires: {},` to `worldFixture` (the generated `WorldSnapshot` requires it).

`frontend/src/api/types.ts`:
- in the city section add `export type TriggerInfo = S['TriggerInfo'];` and `export type TriggerName = S['TriggerName'];`
- in the live world section add `export type FireState = S['FireState'];`
- in the simulation control section add `export type TriggerRequest = S['TriggerRequest'];`
- move `Band`, `Bands`, `BandThresholds` out of the PENDING block into a new block, and replace `ZoneState`:

```ts
// ---- risk indices: zone.state and GET /api/detector/bands ----
export type Band = S['Band'];
export type Bands = S['Bands'];
export type BandThresholds = S['BandThresholds'];
/** A zone's indices as the dashboard keeps them: the zone.state payload without its key and previous band. */
export type ZoneState = Omit<S['ZoneStatePayload'], 'zone_id' | 'prev_band'>;
```

(`Hazard` stays in the PENDING block.)

Run: `npm test -- src/api src/live` → FAIL on the new describeEvent / applyEvent / http assertions (not on compile errors).

- [ ] **Step 4: Implement the client plumbing**

`frontend/src/api/client.ts`: import `TriggerRequest`; add `trigger(body: TriggerRequest): Promise<Event[]>;` to `simulation` after `inject`; move `bands(): Promise<Bands>;` above the `// PENDING` comment.

`frontend/src/api/http.ts`: add `trigger: (body: TriggerRequest): Promise<Event[]> => this.post('/simulation/trigger', body),` after `inject`; replace the pending `bands()` with `bands(): Promise<Bands> { return this.get('/detector/bands'); }` placed after `setSource` (import `TriggerRequest`).

`frontend/src/api/queries.ts`: import `TriggerRequest`; add `trigger: UseMutationResult<Event[], ApiError, TriggerRequest>;` to `SimulationControls` and `trigger: useMutation<Event[], ApiError, TriggerRequest>({ mutationFn: (b) => client.simulation.trigger(b) }),` to `useSimulationControls`; update the `useBands` doc comment to `/** Index band thresholds for the timeline's threshold lines (GET /api/detector/bands). */`.

`frontend/src/mock/MockApiClient.ts`: add `trigger: (_body: TriggerRequest): Promise<Event[]> => notInMock(),` after `inject` (import the type).

`frontend/src/test/fakeClient.ts`: add `trigger: rejectMock` to `simulation`.

- [ ] **Step 5: Implement the event handling**

`frontend/src/live/describeEvent.ts`:
- in `eventGroup`, change the city line to `if (type.startsWith('infrastructure.') || type.startsWith('emergency.') || type === 'weather.forecast' || type === 'weather.rainfall') return 'city';`
- add cases in `describeEvent` (backend section, after `scenario.stage` / `weather.forecast` / `emergency.shelter` respectively):

```ts
    case 'scenario.trigger':
      return `Demo event: ${e.payload.label}`;
```

```ts
    case 'weather.rainfall': {
      const p = e.payload;
      const where = p.zone_ids.length === 0 ? 'the whole city' : p.zone_ids.map((id) => zoneName(city, id)).join(', ');
      return `Rain ${num(p.intensity_mm_h)} mm/h for ${num(p.duration_h)} h over ${where}${reason(p.description)}`;
    }
```

```ts
    case 'emergency.fire': {
      const p = e.payload;
      const people = p.exposed_population.toLocaleString('en-US');
      return `Fire at ${p.site} in ${zoneName(city, p.zone_id)}: ${people} people exposed in ${String(p.exposed_zone_ids.length)} zones`;
    }
```

`frontend/src/live/applyWorld.ts`: add `| 'weather.rainfall' | 'emergency.fire'` to `WorldEvent`, and cases:

```ts
    case 'weather.rainfall':
      return state; // operator rain drives the simulation; its readings arrive as weather.observation
    case 'emergency.fire': {
      const p = e.payload;
      const fire = { site: p.site, exposed_zone_ids: p.exposed_zone_ids, exposed_population: p.exposed_population };
      const next = withWorld(state, (w) => ({ ...w, fires: { ...w.fires, [p.zone_id]: fire } }));
      return addMilestone(next, e, { kind: 'infrastructure', label: `Fire: ${p.site}`, zoneId: p.zone_id });
    }
```

`frontend/src/live/applyEvent.ts`:
- replace `isRoutine` with:

```ts
/** Ticks, readings and a zone.state that keeps its band are routine: a full feed drops them first. */
const isRoutine = (e: Event) =>
  e.event_type === 'sim.tick' || eventGroup(e.event_type) === 'reading' ||
  (e.event_type === 'zone.state' && (e.payload.prev_band == null || e.payload.prev_band === e.payload.band));
```

- add a case after `scenario.stage`:

```ts
    case 'scenario.trigger':
      return addMilestone(s, event, { kind: 'scenario', label: event.payload.label });
```

- add `case 'weather.rainfall':` and `case 'emergency.fire':` to the list that returns `applyWorldEvent(s, event)`.

- [ ] **Step 6: Run the tests to verify they pass**

Run: `npm test && npm run typecheck && npm run lint`
Expected: all tests pass (265 + the new ones), typecheck and lint clean. If a component test that renders the city map or timeline now sees `zone.state` typed from the backend, fix only fixtures (never loosen types).

- [ ] **Step 7: Backend contract test**

Run (backend): `uv run pytest -q`
Expected: all pass, including `test_committed_contract_files_are_current`.

- [ ] **Step 8: Checkpoint** — do not commit.

---

### Task 6: Demo events row, dashboard row height, marker snapping

**Files:**
- Modify: `frontend/src/components/scenario/ScenarioBar.tsx`
- Modify: `frontend/src/components/layout/Dashboard.tsx` (last grid row `44px` → `auto`)
- Modify: `frontend/src/components/timeline/timelineData.ts` (`milestoneMarkers` snapping)
- Test: `frontend/src/components/scenario/ScenarioBar.test.tsx`, `frontend/src/components/timeline/timelineData.test.ts`

**Interfaces:**
- Consumes: `useCity().data.triggers: TriggerInfo[]`, `useSimulationControls().trigger`, `.reset` (Task 5).
- Produces: a `role="group"` named "Demo events" containing one button per trigger (label text, `title` = description) and the single Reset button.

- [ ] **Step 1: Write the failing tests**

`frontend/src/components/scenario/ScenarioBar.test.tsx` — add `within` to the Testing Library import, `import type { SourceStatus } from '@/api/types';`, and inside `describe('ScenarioBar', …)`:

```tsx
  it('lists one demo event per backend trigger, then Reset, in a Demo events group', async () => {
    renderWithProviders(<ScenarioBar />);
    const group = await screen.findByRole('group', { name: 'Demo events' });
    await within(group).findByRole('button', { name: 'Heavy Rain' });
    expect(within(group).getAllByRole('button').map((b) => b.textContent)).toEqual([
      'Heavy Rain', 'Landslide', 'Drainage Block', 'Flash Flood', 'Industrial Fire', 'Cascading Disaster', 'Reset',
    ]);
    expect(within(group).getByRole('button', { name: 'Flash Flood' })).toHaveAttribute('title', 'fixture: cloudburst');
  });

  it('disables the demo events in mock mode but keeps Reset', async () => {
    renderWithProviders(<ScenarioBar />);
    const group = await screen.findByRole('group', { name: 'Demo events' });
    expect(await within(group).findByRole('button', { name: 'Heavy Rain' })).toBeDisabled();
    expect(within(group).getByRole('button', { name: 'Reset' })).toBeEnabled();
  });

  it('in http mode each demo event posts its trigger', async () => {
    useLiveStore.getState().setMode('http');
    const trigger = vi.fn(() => Promise.resolve([]));
    const client = fakeClient();
    renderWithProviders(<ScenarioBar />, { ...client, mode: 'http', simulation: { ...client.simulation, trigger } });
    for (const t of cityFixture.triggers) {
      const button = await screen.findByRole('button', { name: t.label });
      await waitFor(() => { expect(button).toBeEnabled(); });
      fireEvent.click(button);
      await waitFor(() => { expect(trigger).toHaveBeenLastCalledWith({ trigger: t.id }); });
    }
    expect(trigger).toHaveBeenCalledTimes(6);
  });

  it('disables every demo event while a request is pending', async () => {
    useLiveStore.getState().setMode('http');
    const trigger = vi.fn(() => new Promise<never>(() => undefined));
    const client = fakeClient();
    renderWithProviders(<ScenarioBar />, { ...client, mode: 'http', simulation: { ...client.simulation, trigger } });
    fireEvent.click(await screen.findByRole('button', { name: 'Landslide' }));
    await waitFor(() => { expect(screen.getByRole('button', { name: 'Flash Flood' })).toBeDisabled(); });
    fireEvent.click(screen.getByRole('button', { name: 'Flash Flood' }));
    expect(trigger).toHaveBeenCalledTimes(1);
  });

  it('a failed demo event shows an inline error', async () => {
    useLiveStore.getState().setMode('http');
    const trigger = vi.fn(() => Promise.reject(new ApiError(409, null, 'live')));
    const client = fakeClient();
    renderWithProviders(<ScenarioBar />, { ...client, mode: 'http', simulation: { ...client.simulation, trigger } });
    fireEvent.click(await screen.findByRole('button', { name: 'Heavy Rain' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Demo event failed (409)');
  });

  it('shows no demo events in LIVE mode', () => {
    const live: SourceStatus = {
      mode: 'live', label: 'LIVE — Kalyan-Dombivli', city: 'Kalyan-Dombivli', provider: 'Open-Meteo', latitude: 19.235,
      longitude: 73.13, poll_seconds: 300, last_updated: null, last_error: null,
    };
    useLiveStore.setState({ source: live });
    renderWithProviders(<ScenarioBar />);
    expect(screen.queryByRole('group', { name: 'Demo events' })).toBeNull();
  });
```

`frontend/src/components/timeline/timelineData.test.ts` — inside `describe('milestoneMarkers', …)` add:

```ts
  it('snaps a milestone to the next reading row, and waits when there is none yet', () => {
    const ms = [
      milestone('t1', '2026-07-14T09:55:00', { kind: 'scenario' }),
      milestone('t2', '2026-07-14T10:02:00', { kind: 'scenario' }),
      milestone('t3', '2026-07-14T10:07:00', { kind: 'scenario' }),
    ];
    expect(milestoneMarkers(ms, 'hillview', rows).map((m) => [m.id, m.simTime])).toEqual([
      ['t1', '2026-07-14T10:00:00'],
      ['t2', '2026-07-14T10:05:00'],
    ]);
  });
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `npm test -- src/components/scenario src/components/timeline`
Expected: FAIL — no "Demo events" group; t1/t2 markers missing.

- [ ] **Step 3: Implement the marker snapping**

`frontend/src/components/timeline/timelineData.ts` — replace `milestoneMarkers` (keep its doc comment's second sentence about zones) with:

```ts
/**
 * Milestones for this zone, each placed on the first row at or after its sim time: the x axis is categorical, so a
 * marker can only sit on an existing reading (one after the last reading waits for the next). A milestone that names
 * a zone matches on that zone; one without a zone (approval, action, re-plan) matches through its incident's zone
 * when `incidents` is given; one with neither is city-wide.
 */
export function milestoneMarkers(
  milestones: Milestone[], zoneId: string, rows: TimelineRow[], incidents: Record<string, Incident> = {},
): TimelineMarker[] {
  const inZone = (m: Milestone) => {
    if (m.zoneId !== undefined) return m.zoneId === zoneId;
    if (m.incidentId !== undefined) return incidents[m.incidentId]?.zone_id === zoneId;
    return true; // city-wide (a scenario stage or a demo event): marked on every zone's chart
  };
  return milestones.flatMap((m) => {
    const at = m.simTime;
    if (at === null || !inZone(m)) return [];
    const row = rows.find((r) => r.simTime >= at);
    return row ? [{ id: m.id, simTime: row.simTime, label: m.label, kind: m.kind }] : [];
  });
}
```

- [ ] **Step 4: Implement the demo row**

`frontend/src/components/layout/Dashboard.tsx` — change `grid-rows-[64px_auto_50fr_30fr_20fr_44px]` to `grid-rows-[64px_auto_50fr_30fr_20fr_auto]`.

`frontend/src/components/scenario/ScenarioBar.tsx`:
- add `const triggers = city.data?.triggers ?? [];` after `const injections = …`;
- add `['Demo event', controls.trigger]` to `labelled`;
- in the LIVE branch change the outer `className` from `h-full` to `h-11` (the grid row is now `auto`);
- replace the DEMO `return (...)` with:

```tsx
  return (
    <div className="flex flex-col bg-panel border-t border-line text-[12px]">
      <div className="flex items-center gap-3 h-11 px-4">
        <label className="flex items-center gap-2">
          <span className="text-ink-2">Scenario</span>
          <select aria-label="Scenario" className={selectClass} value={scenarioId} disabled={sim.state !== 'idle' || scenarios.length === 0}
            onChange={(e) => { setPicked(e.target.value); }}>
            {scenarios.length === 0 && <option value={scenarioId}>Loading scenarios</option>}
            {scenarios.map((s) => <option key={s.name} value={s.name} title={s.description}>{s.title}</option>)}
          </select>
        </label>
        <Button variant="primary" size="sm" onClick={onPrimary} disabled={busy || scenarios.length === 0} className="w-20 justify-center">
          {sim.state === 'running' ? <IconPause /> : <IconPlay />}
          {sim.state === 'running' ? 'Pause' : sim.state === 'paused' ? 'Resume' : 'Start'}
        </Button>
        <label className="flex items-center gap-2">
          <span className="text-ink-2">Speed</span>
          <select aria-label="Speed" className={selectClass} value={sim.speed}
            onChange={(e) => { controls.setSpeed.mutate(Number(e.target.value)); }}>
            {SPEEDS.map((s) => <option key={s} value={s}>{`${String(s)}×`}</option>)}
          </select>
        </label>
        <label className="flex items-center gap-2">
          <span className="text-ink-2">Inject</span>
          <select aria-label="Inject" className={selectClass} value="" disabled={mode === 'mock' || injections.length === 0}
            onChange={(e) => {
              const preset = injections.find((i) => i.id === e.target.value);
              if (preset) controls.inject.mutate(preset.request);
            }}>
            <option value="">Choose an event</option>
            {injections.map((i) => <option key={i.id} value={i.id} title={i.description}>{i.label}</option>)}
          </select>
        </label>
        {failed && <span role="alert" className="text-band-critical-text">{errorText(failed[0], failed[1].error)}</span>}
        <div className="ml-auto flex items-center gap-4">
          {sim.stage && <span className="text-ink-2" title="Scenario stage">{statusLabel(sim.stage)}</span>}
          <span className="tnum text-ink" title="Simulation time">
            <span className="text-ink-2 mr-1.5">Sim time</span>
            {fmtSimTimeSec(sim.simTime)}
          </span>
          {status}
        </div>
      </div>
      <div role="group" aria-label="Demo events" className="flex items-center gap-2 h-9 px-4 border-t border-line">
        <span className="text-ink-2 mr-1">Demo events</span>
        {triggers.map((t) => (
          <Button key={t.id} size="sm" title={t.description} disabled={busy || mode === 'mock'}
            onClick={() => { controls.trigger.mutate({ trigger: t.id }); }}>
            {t.label}
          </Button>
        ))}
        <Button size="sm" onClick={() => { controls.reset.mutate(); }} disabled={busy}>
          <IconReset />
          Reset
        </Button>
      </div>
    </div>
  );
```

(The Reset button moved from the first line into the group; nothing else on the first line changed.)

- [ ] **Step 5: Run the tests to verify they pass**

Run: `npm test && npm run typecheck && npm run lint`
Expected: all pass (including the existing `shows an inline error when a control fails`, which clicks the one Reset), typecheck and lint clean.

- [ ] **Step 6: Checkpoint** — do not commit.

---

### Task 7: Verification in the running app

**Files:** none committed. Scratch files go in the session scratchpad.

- [ ] **Step 1: Every suite, types, lint and the demo smoke**

Run (backend): `uv run ruff format --check . && uv run ruff check . && uv run pyright && uv run pytest -q`
Run (repo root): `uv run python scripts/demo_smoke.py`
Run (frontend): `npm test && npm run typecheck && npm run lint && npm run build`
Expected: every command exits 0; record the pass counts.

- [ ] **Step 2: Press every button against a real server over HTTP and `/ws`**

Start the backend: `cd backend && uv run uvicorn gridline.main:app --port 8000` (background). Save as `<scratchpad>/press_buttons.py` and run it with `cd backend && uv run python <scratchpad>/press_buttons.py`:

```python
"""Press every DEMO button on a running backend; each response's events must arrive on /ws in order."""

import asyncio
import json

import httpx
import websockets

BASE, WS = "http://127.0.0.1:8000", "ws://127.0.0.1:8000/ws"
BUTTONS = ["heavy_rain", "landslide", "drainage_block", "flash_flood", "industrial_fire", "cascading_disaster"]


async def main() -> None:
    async with websockets.connect(WS, max_size=None) as ws, httpx.AsyncClient(base_url=BASE, timeout=30) as http:
        await ws.recv()  # the snapshot
        for button in BUTTONS:
            response = await http.post("/api/simulation/trigger", json={"trigger": button})
            response.raise_for_status()
            events = response.json()
            ids = [e["event_id"] for e in events]
            got: list[str] = []
            while len(got) < len(ids):
                frame = json.loads(await asyncio.wait_for(ws.recv(), 10))
                if frame["event_id"] in ids:
                    got.append(frame["event_id"])
            assert got == ids, button
            bands = {e["location"]: e["payload"]["band"] for e in events if e["event_type"] == "zone.state"}
            print(f"{button:20} {len(ids):4} events on /ws in order; bands above normal: "
                  f"{ {z: b for z, b in bands.items() if b != 'normal'} }")
        status = (await http.post("/api/simulation/reset")).json()
        print("reset ->", status["state"], "tick", status["tick"])


asyncio.run(main())
```

Expected: six lines with event counts, Landslide showing `Z-HV` warning/critical, Flash Flood and Cascading Disaster showing `Z-RS` warning/critical; `reset -> idle tick 0`.

- [ ] **Step 3: See it in the dashboard**

Start the frontend: `cd frontend && npm run dev` (background, port 5173, proxies to :8000). Take a headless screenshot while a button fires (Edge is at `C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe`):

```powershell
Start-Job { Start-Sleep 6; Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/simulation/trigger -ContentType 'application/json' -Body '{"trigger":"cascading_disaster"}' } | Out-Null
& "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" --headless=new --disable-gpu --window-size=1600,1000 --virtual-time-budget=15000 --screenshot="<scratchpad>\demo-controls.png" http://localhost:5173
```

Read the PNG and confirm: the "Demo events" row with seven buttons, the Live events feed showing "Demo event: Cascading Disaster" and the landslide/obstruction events, Riverside coloured by its band on the map, and the marker on the Risk timeline. If the screenshot races the connection, re-run with a longer `Start-Sleep`. Stop both servers afterwards.

- [ ] **Step 4: Report** — list every command with its real result, the button outcomes printed in Step 2, and what the screenshot showed. Do not commit; ask the user whether to commit.
