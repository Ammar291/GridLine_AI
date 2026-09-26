# Simulation Engine and Event Infrastructure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A deterministic synthetic Nandipur simulation that streams typed city observations over a WebSocket and is controlled through a REST API, with four scenarios including a six-stage cascading landslide-to-flood.

**Architecture:** A synchronous, seed-deterministic `SimulationEngine` steps a `WorldState` built from a typed `City` seed using small physics functions and a data-only `Scenario` script, emitting validated `Event` envelopes. An asyncio `SimulationRunner` paces the engine in real time and publishes to an in-process `EventBus`; FastAPI exposes `/api/simulation/*` and `/ws`. No database, LangGraph, RAG or frontend in this plan.

**Tech Stack:** Python 3.13, uv, FastAPI, Pydantic v2, pydantic-settings, uvicorn, pytest, pytest-asyncio, httpx (Starlette TestClient), pyright strict, ruff.

**Spec:** `docs/superpowers/specs/2026-09-26-simulation-and-events-design.md` — read it first; every task below cites its sections.

## Global Constraints

- Synthetic data only. Every id, name, number and document is invented (CLAUDE.md non-negotiable 1).
- One process. No database, Redis, Celery, message broker or second runtime in this plan (spec §1 A1).
- The simulation makes no AI decisions. Severity is a fixed-threshold sensor band (spec §1 A4, §3.3).
- Python 3.13, `uv`; project root for backend commands is `backend/`. Run tests with `cd backend && uv run pytest`.
- `pyright` strict on `gridline/`; `ruff check .` and `ruff format --check .` clean. Fully typed, Pydantic v2 for every boundary model, no module-level mutable state, files under about 300 lines.
- Async on the request path; the engine itself is synchronous (spec §2, §7.1).
- Domain names only: zone, channel, road, bridge, project, crew, sensor, scenario, stage, event (CLAUDE.md).
- **Do not commit.** CLAUDE.md says commit only when asked. Tasks therefore have no commit steps; leave changes in the working tree on branch `feature/simulation-events`.
- Windows host. Use forward slashes in paths; shell commands below are written for bash (Git Bash) and also run in PowerShell unless noted.
- Timestamps are always timezone-aware UTC (`datetime.now(UTC)`, `datetime(..., tzinfo=UTC)`).
- Every event type has a typed payload model and a test (CLAUDE.md "Both").

## Review Focus

1. **`?types=` filter with empty or unmatched prefixes** (`?types=`, `?types=,,`, `?types=nope.`): empty segments are ignored, an unmatched prefix yields only the snapshot and heartbeats, never an error. Test in Task 13.
2. **Injection with a `location` that contradicts the asset's zone**: the asset's zone wins and the emitted event carries it. Test in Task 7.
3. **Advancing past `duration_ticks`**: curves hold their last value, the last stage persists, no exception. Test in Task 8.
4. **Illegal runner transitions** (`start` twice, `resume` when idle, `advance` while running): typed `InvalidTransition`, mapped to HTTP 409. Tests in Task 11 and Task 12.
5. **Selecting a scenario or resetting while the runner is ticking**: the tick task is cancelled, state becomes `idle` at tick 0, and no further tick events are published. Tests in Task 11 and Task 12.

---

### Task 1: Backend skeleton (uv project, settings, app factory, health route)

**Files:**
- Create: `backend/pyproject.toml`
- Create: `backend/.env.example`
- Create: `backend/gridline/__init__.py`, `backend/gridline/py.typed`
- Create: `backend/gridline/config.py`
- Create: `backend/gridline/main.py`
- Create: `backend/gridline/api/__init__.py`, `backend/gridline/api/health.py`
- Create: `backend/gridline/errors.py`
- Create: `backend/tests/__init__.py`, `backend/tests/conftest.py`
- Test: `backend/tests/test_config.py`, `backend/tests/test_health.py`

**Interfaces:**
- Produces: `Settings` (fields below), `create_app(settings: Settings | None = None) -> FastAPI`, `app` module attribute, `gridline.errors.{SimulationError, InvalidTransition, NotInjectable, UnknownAsset, UnknownScenario}`.

- [ ] **Step 1: Create the uv project**

`backend/pyproject.toml`:

```toml
[project]
name = "gridline"
version = "0.1.0"
description = "GridLine AI backend: city disaster intelligence brain for the fictional city of Nandipur"
requires-python = ">=3.13"
dependencies = [
  "fastapi>=0.115",
  "uvicorn[standard]>=0.30",
  "pydantic>=2.9",
  "pydantic-settings>=2.5",
]

[dependency-groups]
dev = [
  "pytest>=8",
  "pytest-asyncio>=0.24",
  "httpx>=0.27",
  "pyright>=1.1.390",
  "ruff>=0.7",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["gridline"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]

[tool.pyright]
include = ["gridline"]
typeCheckingMode = "strict"
pythonVersion = "3.13"
venvPath = "."
venv = ".venv"

[tool.ruff]
line-length = 110
target-version = "py313"

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B", "SIM", "N", "W"]
```

`backend/.env.example`:

```
SIM_TICK_SECONDS=1.0
SIM_MINUTES_PER_TICK=5
SIM_DEFAULT_SCENARIO=cascading_landslide_flood
SIM_DEFAULT_SEED=42
SIM_AUTOSTART=false
WS_HEARTBEAT_SECONDS=15
EVENT_QUEUE_SIZE=1000
```

`backend/gridline/__init__.py`: `"""GridLine AI backend."""` and an empty `backend/gridline/py.typed`.

Run: `cd backend && uv sync` — Expected: `.venv` created, `gridline` installed editable, dev group installed.

- [ ] **Step 2: Write the failing settings test**

`backend/tests/__init__.py` (empty) and `backend/tests/test_config.py`:

```python
import pytest

from gridline.config import Settings


def test_defaults() -> None:
    s = Settings(_env_file=None)
    assert s.sim_tick_seconds == 1.0
    assert s.sim_minutes_per_tick == 5
    assert s.sim_default_scenario == "cascading_landslide_flood"
    assert s.sim_default_seed == 42
    assert s.sim_autostart is False
    assert s.ws_heartbeat_seconds == 15.0
    assert s.event_queue_size == 1000


def test_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SIM_TICK_SECONDS", "0.25")
    monkeypatch.setenv("SIM_AUTOSTART", "true")
    s = Settings(_env_file=None)
    assert s.sim_tick_seconds == 0.25
    assert s.sim_autostart is True


def test_rejects_non_positive_tick() -> None:
    with pytest.raises(ValueError):
        Settings(_env_file=None, sim_tick_seconds=0)
```

Run: `cd backend && uv run pytest tests/test_config.py -v` — Expected: FAIL, `ModuleNotFoundError: gridline.config`.

- [ ] **Step 3: Implement settings and errors**

`backend/gridline/config.py`:

```python
"""Application settings, loaded from backend/.env by pydantic-settings."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    sim_tick_seconds: float = Field(default=1.0, gt=0, description="Real seconds per tick at speed 1.0")
    sim_minutes_per_tick: int = Field(default=5, ge=1, description="Simulated minutes advanced per tick")
    sim_default_scenario: str = "cascading_landslide_flood"
    sim_default_seed: int = 42
    sim_autostart: bool = False
    ws_heartbeat_seconds: float = Field(default=15.0, gt=0)
    event_queue_size: int = Field(default=1000, ge=1)
```

`backend/gridline/errors.py`:

```python
"""Typed exceptions raised by the simulation and mapped to HTTP codes by the API."""


class SimulationError(Exception):
    """Base class for simulation errors."""


class InvalidTransition(SimulationError):
    """The runner cannot perform this transition from its current state (HTTP 409)."""


class NotInjectable(SimulationError):
    """The event type is an observation or system event and cannot be injected (HTTP 422)."""


class UnknownAsset(SimulationError):
    """An id in a payload does not exist in the city (HTTP 422)."""


class UnknownScenario(SimulationError):
    """No scenario is registered under this name (HTTP 422)."""
```

Run: `cd backend && uv run pytest tests/test_config.py -v` — Expected: 3 passed.

- [ ] **Step 4: Write the failing health test**

`backend/tests/conftest.py`:

```python
import pytest

from gridline.config import Settings


@pytest.fixture
def settings() -> Settings:
    """Fast settings for tests: no .env file, 10 ms ticks, 50 ms heartbeat."""
    return Settings(_env_file=None, sim_tick_seconds=0.01, ws_heartbeat_seconds=0.05)
```

`backend/tests/test_health.py`:

```python
from fastapi.testclient import TestClient

from gridline.config import Settings
from gridline.main import create_app


def test_health(settings: Settings) -> None:
    with TestClient(create_app(settings)) as client:
        response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": "0.1.0"}
```

Run: `cd backend && uv run pytest tests/test_health.py -v` — Expected: FAIL, `ModuleNotFoundError: gridline.main`.

- [ ] **Step 5: Implement the app factory and health route**

`backend/gridline/api/__init__.py`: empty. `backend/gridline/api/health.py`:

```python
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class HealthResponse(BaseModel):
    status: str
    version: str


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(status="ok", version="0.1.0")
```

`backend/gridline/main.py` (Task 12 replaces the lifespan body; keep this shape):

```python
"""FastAPI app factory. Shared services hang off app.state and are injected via dependencies."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from gridline.api.health import router as health_router
from gridline.config import Settings

APP_VERSION = "0.1.0"


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.settings = resolved
        yield

    app = FastAPI(title="GridLine AI", version=APP_VERSION, lifespan=lifespan)
    app.include_router(health_router, prefix="/api")
    return app


app = create_app()
```

Run: `cd backend && uv run pytest -v` — Expected: 4 passed.

- [ ] **Step 6: Lint and type-check**

Run: `cd backend && uv run ruff format . && uv run ruff check . && uv run pyright` — Expected: no errors.

---

### Task 2: Event types, payload models and envelope

**Files:**
- Create: `backend/gridline/events/__init__.py`, `backend/gridline/events/types.py`, `backend/gridline/events/payloads.py`, `backend/gridline/events/envelope.py`
- Test: `backend/tests/test_event_envelope.py`, `backend/tests/test_payloads.py`

**Interfaces:**
- Produces: `Severity`, `EventType`, `INJECTABLE_TYPES`, every payload model in spec §3.2, `PAYLOAD_MODELS: dict[EventType, type[BaseModel]]`, `Event`, `new_event(...)`, `Trend`.

- [ ] **Step 1: Write the failing envelope tests**

`backend/tests/test_event_envelope.py`:

```python
from datetime import UTC, datetime

import pytest
from pydantic import BaseModel, ValidationError

from gridline.events.envelope import Event, new_event
from gridline.events.payloads import PAYLOAD_MODELS, SimTick, WeatherObservation
from gridline.events.types import INJECTABLE_TYPES, EventType, Severity

NOW = datetime(2026, 7, 14, 6, 0, tzinfo=UTC)


def test_registry_is_total() -> None:
    assert set(PAYLOAD_MODELS) == set(EventType)
    for model in PAYLOAD_MODELS.values():
        assert issubclass(model, BaseModel)


def test_new_event_builds_envelope_with_all_fields() -> None:
    payload = WeatherObservation(
        station_id="RG-01", rainfall_intensity_mm_h=12.0, cumulative_rainfall_24h_mm=30.0,
        temperature_c=24.5, wind_speed_kmh=10.0, wind_direction_deg=210.0,
    )
    event = new_event(
        EventType.WEATHER_OBSERVATION, payload, event_id="evt-000001", timestamp=NOW, sim_time=NOW,
        source="sensor:RG-01", location="hillview", severity=Severity.LOW,
    )
    assert event.event_id == "evt-000001"
    assert event.event_type == EventType.WEATHER_OBSERVATION
    assert event.source == "sensor:RG-01"
    assert event.location == "hillview"
    assert event.severity == Severity.LOW
    assert event.payload["station_id"] == "RG-01"
    assert event.incident_id is None


def test_json_round_trip() -> None:
    payload = SimTick(tick=3, sim_time=NOW, scenario="normal_city", stage="steady_state", speed=1.0)
    event = new_event(
        EventType.SIM_TICK, payload, event_id="evt-000003", timestamp=NOW, sim_time=NOW,
        source="simulation:engine", location=None, severity=Severity.INFO,
    )
    data = event.model_dump_json()
    assert Event.model_validate_json(data) == event
    assert set(event.model_dump()) == {
        "event_id", "timestamp", "sim_time", "event_type", "source", "location", "severity", "payload", "incident_id",
    }


def test_payload_is_validated_against_registry() -> None:
    with pytest.raises(ValidationError):
        Event(
            event_id="evt-1", timestamp=NOW, sim_time=NOW, event_type=EventType.ENVIRONMENT_SOIL,
            source="sensor:SM-01", location="hillview", severity=Severity.INFO,
            payload={"probe_id": "SM-01", "depth_cm": 50, "soil_moisture_pct": 150, "saturation": 0.5},
        )


def test_naive_timestamp_rejected() -> None:
    with pytest.raises(ValidationError):
        Event(
            event_id="evt-1", timestamp=datetime(2026, 7, 14), sim_time=NOW, event_type=EventType.SIM_HEARTBEAT,
            source="simulation:engine", location=None, severity=Severity.INFO,
            payload={"tick": 0, "sim_time": NOW.isoformat()},
        )


def test_new_event_rejects_wrong_payload_class() -> None:
    with pytest.raises(TypeError):
        new_event(
            EventType.SIM_TICK, WeatherObservation(
                station_id="RG-01", rainfall_intensity_mm_h=0, cumulative_rainfall_24h_mm=0,
                temperature_c=20, wind_speed_kmh=0, wind_direction_deg=0,
            ),
            event_id="evt-1", timestamp=NOW, sim_time=NOW, source="x", location=None, severity=Severity.INFO,
        )


def test_injectable_types_are_state_changing_only() -> None:
    assert EventType.INFRASTRUCTURE_ROAD in INJECTABLE_TYPES
    assert EventType.WEATHER_FORECAST in INJECTABLE_TYPES
    assert EventType.WEATHER_OBSERVATION not in INJECTABLE_TYPES
    assert EventType.SIM_TICK not in INJECTABLE_TYPES
    assert all(t.startswith(("infrastructure.", "emergency.")) or t == "weather.forecast" for t in INJECTABLE_TYPES)
```

`backend/tests/test_payloads.py` — one valid construction and one bound violation per model:

```python
from datetime import UTC, datetime

import pytest
from pydantic import BaseModel, ValidationError

from gridline.events import payloads as p

NOW = datetime(2026, 7, 14, 6, 0, tzinfo=UTC)

VALID: list[BaseModel] = [
    p.SimTick(tick=1, sim_time=NOW, scenario="normal_city", stage="steady_state", speed=1.0),
    p.SimStatus(state="idle", scenario="normal_city", seed=1, speed=1.0, tick=0, sim_time=NOW, stage="steady_state"),
    p.SimSnapshot(status=p.SimStatus(state="idle", scenario="normal_city", seed=1, speed=1.0, tick=0, sim_time=NOW, stage="s"), world={}),
    p.Heartbeat(tick=0, sim_time=NOW),
    p.ScenarioStage(scenario="normal_city", stage_index=0, stage="steady_state", description="d", tick=0),
    p.WeatherObservation(station_id="RG-01", rainfall_intensity_mm_h=0, cumulative_rainfall_24h_mm=0, temperature_c=25, wind_speed_kmh=3, wind_direction_deg=0),
    p.WeatherForecast(issued_sim_time=NOW, horizon_h=24, expected_total_mm=12, peak_intensity_mm_h=3, confidence=0.8, summary="light showers"),
    p.SoilObservation(probe_id="SM-01", depth_cm=50, soil_moisture_pct=20, saturation=0.4),
    p.RiverObservation(gauge_id="RL-01", river_id="kalinadi", level_m=1.2, warning_level_m=2.5, danger_level_m=3.2, trend="steady"),
    p.DrainageObservation(gauge_id="CL-D7", channel_id="D-7", flow_m3s=1, capacity_m3s=12, load_ratio=0.08, blocked_fraction=0, overflow_m3s=0),
    p.SlopeObservation(monitor_id="SL-01", movement_rate_mm_h=0, cumulative_movement_mm=0, saturation=0.1),
    p.WaterAccumulation(sensor_id="FD-01", depth_cm=0, trend="steady"),
    p.RoadStatus(road_id="hill_road", status="open", reason=""),
    p.BridgeStatus(bridge_id="kalinadi_bridge", status="open", reason=""),
    p.DrainageObstruction(channel_id="D-7", blocked_fraction=0.25, cause="debris"),
    p.ConstructionActivity(project_id="ht_phase2", status="active", activity="excavating", excavation_depth_m=1.5, planned_depth_m=6),
    p.InfrastructureFailure(asset_id="SL-01", asset_kind="slope", failure_kind="landslide", description="slope failed"),
    p.RescueTeamStatus(crew_id="C-1", status="available", location_zone_id="station_road", task="standby"),
    p.AmbulanceStatus(ambulance_id="A-1", status="available", location_zone_id="old_town"),
    p.HospitalCapacity(hospital_id="ngh", beds_occupied=84, er_status="normal"),
    p.ShelterCapacity(shelter_id="S-1", status="closed", occupancy=0),
]


@pytest.mark.parametrize("model", VALID, ids=lambda m: type(m).__name__)
def test_valid_payloads_round_trip(model: BaseModel) -> None:
    assert type(model).model_validate(model.model_dump(mode="json")) == model


INVALID: list[tuple[type[BaseModel], dict[str, object]]] = [
    (p.SimTick, {"tick": -1, "sim_time": NOW, "scenario": "x", "stage": "y", "speed": 1.0}),
    (p.SimStatus, {"state": "flying", "scenario": "x", "seed": 1, "speed": 1.0, "tick": 0, "sim_time": NOW, "stage": "s"}),
    (p.Heartbeat, {"tick": 0}),
    (p.ScenarioStage, {"scenario": "x", "stage_index": -1, "stage": "s", "description": "d", "tick": 0}),
    (p.WeatherObservation, {"station_id": "RG-01", "rainfall_intensity_mm_h": -1, "cumulative_rainfall_24h_mm": 0, "temperature_c": 25, "wind_speed_kmh": 3, "wind_direction_deg": 0}),
    (p.WeatherObservation, {"station_id": "RG-01", "rainfall_intensity_mm_h": 0, "cumulative_rainfall_24h_mm": 0, "temperature_c": 25, "wind_speed_kmh": 3, "wind_direction_deg": 360}),
    (p.WeatherForecast, {"issued_sim_time": NOW, "horizon_h": 0, "expected_total_mm": 1, "peak_intensity_mm_h": 1, "confidence": 0.5, "summary": "s"}),
    (p.WeatherForecast, {"issued_sim_time": NOW, "horizon_h": 1, "expected_total_mm": 1, "peak_intensity_mm_h": 1, "confidence": 1.5, "summary": "s"}),
    (p.SoilObservation, {"probe_id": "SM-01", "depth_cm": 50, "soil_moisture_pct": 20, "saturation": 1.2}),
    (p.RiverObservation, {"gauge_id": "RL-01", "river_id": "k", "level_m": -0.1, "warning_level_m": 2.5, "danger_level_m": 3.2, "trend": "steady"}),
    (p.DrainageObservation, {"gauge_id": "CL-D7", "channel_id": "D-7", "flow_m3s": 1, "capacity_m3s": 12, "load_ratio": 0.1, "blocked_fraction": 1.5, "overflow_m3s": 0}),
    (p.SlopeObservation, {"monitor_id": "SL-01", "movement_rate_mm_h": -1, "cumulative_movement_mm": 0, "saturation": 0.1}),
    (p.WaterAccumulation, {"sensor_id": "FD-01", "depth_cm": 1, "trend": "sideways"}),
    (p.RoadStatus, {"road_id": "r", "status": "flooded", "reason": ""}),
    (p.BridgeStatus, {"bridge_id": "b", "status": "gone", "reason": ""}),
    (p.DrainageObstruction, {"channel_id": "D-7", "blocked_fraction": -0.1, "cause": "x"}),
    (p.ConstructionActivity, {"project_id": "p", "status": "active", "activity": "digging", "excavation_depth_m": 1, "planned_depth_m": 6}),
    (p.InfrastructureFailure, {"asset_id": "a", "asset_kind": "slope", "failure_kind": "meteor", "description": "d"}),
    (p.RescueTeamStatus, {"crew_id": "C-1", "status": "sleeping", "location_zone_id": "z", "task": ""}),
    (p.AmbulanceStatus, {"ambulance_id": "A-1", "status": "available", "location_zone_id": "z", "available_count": -1}),
    (p.HospitalCapacity, {"hospital_id": "h", "beds_occupied": -1, "er_status": "normal"}),
    (p.ShelterCapacity, {"shelter_id": "s", "status": "open", "occupancy": -1}),
]


@pytest.mark.parametrize(("model", "data"), INVALID, ids=lambda x: getattr(x, "__name__", ""))
def test_invalid_payloads_rejected(model: type[BaseModel], data: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        model.model_validate(data)
```

Run: `cd backend && uv run pytest tests/test_event_envelope.py tests/test_payloads.py -v` — Expected: FAIL, `ModuleNotFoundError: gridline.events`.

- [ ] **Step 2: Implement types**

`backend/gridline/events/__init__.py`: empty. `backend/gridline/events/types.py`:

```python
"""Event type and severity enums. Severity is a sensor-band label, never a threat assessment."""

from enum import StrEnum


class Severity(StrEnum):
    INFO = "info"
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"


class EventType(StrEnum):
    SIM_TICK = "sim.tick"
    SIM_STATUS = "sim.status"
    SIM_SNAPSHOT = "sim.snapshot"
    SIM_HEARTBEAT = "sim.heartbeat"
    SCENARIO_STAGE = "scenario.stage"
    WEATHER_OBSERVATION = "weather.observation"
    WEATHER_FORECAST = "weather.forecast"
    ENVIRONMENT_SOIL = "environment.soil"
    ENVIRONMENT_RIVER = "environment.river"
    ENVIRONMENT_DRAINAGE = "environment.drainage"
    ENVIRONMENT_SLOPE = "environment.slope"
    ENVIRONMENT_WATER_ACCUMULATION = "environment.water_accumulation"
    INFRASTRUCTURE_ROAD = "infrastructure.road"
    INFRASTRUCTURE_BRIDGE = "infrastructure.bridge"
    INFRASTRUCTURE_DRAINAGE_OBSTRUCTION = "infrastructure.drainage_obstruction"
    INFRASTRUCTURE_CONSTRUCTION = "infrastructure.construction"
    INFRASTRUCTURE_FAILURE = "infrastructure.failure"
    EMERGENCY_RESCUE_TEAM = "emergency.rescue_team"
    EMERGENCY_AMBULANCE = "emergency.ambulance"
    EMERGENCY_HOSPITAL = "emergency.hospital"
    EMERGENCY_SHELTER = "emergency.shelter"


INJECTABLE_TYPES: frozenset[EventType] = frozenset(
    {
        EventType.WEATHER_FORECAST,
        EventType.INFRASTRUCTURE_ROAD,
        EventType.INFRASTRUCTURE_BRIDGE,
        EventType.INFRASTRUCTURE_DRAINAGE_OBSTRUCTION,
        EventType.INFRASTRUCTURE_CONSTRUCTION,
        EventType.INFRASTRUCTURE_FAILURE,
        EventType.EMERGENCY_RESCUE_TEAM,
        EventType.EMERGENCY_AMBULANCE,
        EventType.EMERGENCY_HOSPITAL,
        EventType.EMERGENCY_SHELTER,
    }
)
```

- [ ] **Step 3: Implement payload models**

`backend/gridline/events/payloads.py` (exactly these fields; derived fields have defaults so injections may omit them and the apply handlers fill them in):

```python
"""One Pydantic model per event type (spec §3.2). PAYLOAD_MODELS maps every EventType to its model."""

from typing import Any, Literal

from pydantic import AwareDatetime, BaseModel, Field

from gridline.events.types import EventType

Trend = Literal["rising", "steady", "falling"]
RunnerState = Literal["idle", "running", "paused"]


class SimTick(BaseModel):
    tick: int = Field(ge=0)
    sim_time: AwareDatetime
    scenario: str
    stage: str
    speed: float = Field(gt=0)


class SimStatus(BaseModel):
    state: RunnerState
    scenario: str
    seed: int
    speed: float = Field(gt=0)
    tick: int = Field(ge=0)
    sim_time: AwareDatetime
    stage: str


class SimSnapshot(BaseModel):
    status: SimStatus
    world: dict[str, Any]


class Heartbeat(BaseModel):
    tick: int = Field(ge=0)
    sim_time: AwareDatetime


class ScenarioStage(BaseModel):
    scenario: str
    stage_index: int = Field(ge=0)
    stage: str
    description: str
    tick: int = Field(ge=0)


class WeatherObservation(BaseModel):
    station_id: str
    rainfall_intensity_mm_h: float = Field(ge=0)
    cumulative_rainfall_24h_mm: float = Field(ge=0)
    temperature_c: float
    wind_speed_kmh: float = Field(ge=0)
    wind_direction_deg: float = Field(ge=0, lt=360)


class WeatherForecast(BaseModel):
    issued_sim_time: AwareDatetime
    horizon_h: float = Field(gt=0)
    expected_total_mm: float = Field(ge=0)
    peak_intensity_mm_h: float = Field(ge=0)
    confidence: float = Field(ge=0, le=1)
    summary: str


class SoilObservation(BaseModel):
    probe_id: str
    depth_cm: int = Field(ge=0)
    soil_moisture_pct: float = Field(ge=0, le=100)
    saturation: float = Field(ge=0, le=1)


class RiverObservation(BaseModel):
    gauge_id: str
    river_id: str
    level_m: float = Field(ge=0)
    warning_level_m: float
    danger_level_m: float
    trend: Trend


class DrainageObservation(BaseModel):
    gauge_id: str
    channel_id: str
    flow_m3s: float = Field(ge=0)
    capacity_m3s: float = Field(ge=0)
    load_ratio: float = Field(ge=0)
    blocked_fraction: float = Field(ge=0, le=1)
    overflow_m3s: float = Field(ge=0)


class SlopeObservation(BaseModel):
    monitor_id: str
    movement_rate_mm_h: float = Field(ge=0)
    cumulative_movement_mm: float = Field(ge=0)
    saturation: float = Field(ge=0, le=1)


class WaterAccumulation(BaseModel):
    sensor_id: str
    depth_cm: float = Field(ge=0)
    trend: Trend


class RoadStatus(BaseModel):
    road_id: str
    status: Literal["open", "blocked", "closed"]
    reason: str = ""
    is_evacuation_route: bool = False  # filled from the city by the apply handler


class BridgeStatus(BaseModel):
    bridge_id: str
    status: Literal["open", "restricted", "closed"]
    reason: str = ""


class DrainageObstruction(BaseModel):
    channel_id: str
    blocked_fraction: float = Field(ge=0, le=1)
    cause: str = ""


class ConstructionActivity(BaseModel):
    project_id: str
    status: Literal["active", "halted"]
    activity: Literal["excavating", "idle", "halted"]
    excavation_depth_m: float = Field(ge=0)
    planned_depth_m: float = Field(default=0, ge=0)  # filled from the city by the apply handler


class InfrastructureFailure(BaseModel):
    asset_id: str
    asset_kind: Literal["slope", "channel", "bridge", "road", "power"]
    failure_kind: Literal["landslide", "culvert_collapse", "embankment_breach", "power_outage"]
    description: str


class RescueTeamStatus(BaseModel):
    crew_id: str
    status: Literal["available", "en_route", "on_site", "blocked", "resting"]
    location_zone_id: str
    task: str = ""


class AmbulanceStatus(BaseModel):
    ambulance_id: str
    status: Literal["available", "dispatched", "out_of_service"]
    location_zone_id: str
    available_count: int = Field(default=0, ge=0)  # recomputed by the apply handler
    total_count: int = Field(default=0, ge=0)  # recomputed by the apply handler


class HospitalCapacity(BaseModel):
    hospital_id: str
    beds_total: int = Field(default=0, ge=0)  # filled from the city by the apply handler
    beds_occupied: int = Field(ge=0)
    beds_available: int = Field(default=0, ge=0)  # recomputed by the apply handler
    er_status: Literal["normal", "busy", "overwhelmed"]


class ShelterCapacity(BaseModel):
    shelter_id: str
    status: Literal["closed", "open", "full"]
    capacity: int = Field(default=0, ge=0)  # filled from the city by the apply handler
    occupancy: int = Field(ge=0)


PAYLOAD_MODELS: dict[EventType, type[BaseModel]] = {
    EventType.SIM_TICK: SimTick,
    EventType.SIM_STATUS: SimStatus,
    EventType.SIM_SNAPSHOT: SimSnapshot,
    EventType.SIM_HEARTBEAT: Heartbeat,
    EventType.SCENARIO_STAGE: ScenarioStage,
    EventType.WEATHER_OBSERVATION: WeatherObservation,
    EventType.WEATHER_FORECAST: WeatherForecast,
    EventType.ENVIRONMENT_SOIL: SoilObservation,
    EventType.ENVIRONMENT_RIVER: RiverObservation,
    EventType.ENVIRONMENT_DRAINAGE: DrainageObservation,
    EventType.ENVIRONMENT_SLOPE: SlopeObservation,
    EventType.ENVIRONMENT_WATER_ACCUMULATION: WaterAccumulation,
    EventType.INFRASTRUCTURE_ROAD: RoadStatus,
    EventType.INFRASTRUCTURE_BRIDGE: BridgeStatus,
    EventType.INFRASTRUCTURE_DRAINAGE_OBSTRUCTION: DrainageObstruction,
    EventType.INFRASTRUCTURE_CONSTRUCTION: ConstructionActivity,
    EventType.INFRASTRUCTURE_FAILURE: InfrastructureFailure,
    EventType.EMERGENCY_RESCUE_TEAM: RescueTeamStatus,
    EventType.EMERGENCY_AMBULANCE: AmbulanceStatus,
    EventType.EMERGENCY_HOSPITAL: HospitalCapacity,
    EventType.EMERGENCY_SHELTER: ShelterCapacity,
}
```

- [ ] **Step 4: Implement the envelope**

`backend/gridline/events/envelope.py`:

```python
"""The Event envelope (spec §3.1). Payloads are validated against PAYLOAD_MODELS on construction."""

from typing import Any

from pydantic import AwareDatetime, BaseModel, ConfigDict, model_validator

from gridline.events.payloads import PAYLOAD_MODELS
from gridline.events.types import EventType, Severity


class Event(BaseModel):
    model_config = ConfigDict(frozen=True)

    event_id: str
    timestamp: AwareDatetime
    sim_time: AwareDatetime
    event_type: EventType
    source: str
    location: str | None = None
    severity: Severity
    payload: dict[str, Any]
    incident_id: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _validate_payload(cls, data: Any) -> Any:
        if isinstance(data, dict) and "event_type" in data and "payload" in data:
            typed: dict[str, Any] = dict(data)  # pyright: ignore[reportUnknownArgumentType]
            model = PAYLOAD_MODELS[EventType(typed["event_type"])]
            typed["payload"] = model.model_validate(typed["payload"]).model_dump(mode="json")
            return typed
        return data


def new_event(
    event_type: EventType,
    payload: BaseModel,
    *,
    event_id: str,
    timestamp: AwareDatetime,
    sim_time: AwareDatetime,
    source: str,
    location: str | None,
    severity: Severity,
    incident_id: str | None = None,
) -> Event:
    """Typed constructor: refuses a payload whose class is not the one registered for event_type."""
    expected = PAYLOAD_MODELS[event_type]
    if type(payload) is not expected:
        raise TypeError(f"{event_type} expects {expected.__name__}, got {type(payload).__name__}")
    return Event(
        event_id=event_id,
        timestamp=timestamp,
        sim_time=sim_time,
        event_type=event_type,
        source=source,
        location=location,
        severity=severity,
        payload=payload.model_dump(mode="json"),
        incident_id=incident_id,
    )
```

Run: `cd backend && uv run pytest tests/test_event_envelope.py tests/test_payloads.py -v` — Expected: all passed.

- [ ] **Step 5: Lint and type-check**

Run: `cd backend && uv run ruff format . && uv run ruff check . && uv run pyright` — Expected: clean. If pyright complains about the `dict(data)` line, narrow with `cast(dict[str, Any], data)` instead of the ignore comment.

---

### Task 3: City model and Nandipur seed

**Files:**
- Create: `backend/gridline/city/__init__.py`, `backend/gridline/city/model.py`, `backend/gridline/city/nandipur.py`
- Test: `backend/tests/test_city.py`

**Interfaces:**
- Consumes: `gridline.errors.UnknownAsset`.
- Produces: `ZoneKind, SoilType, SensorKind, CrewKind` literals; frozen models `Zone, DrainageChannel, River, Road, Bridge, Project, Sensor, Crew, Ambulance, Hospital, Shelter, City`; `City.zone(id)`, `.channel(id)`, `.river(id)`, `.road(id)`, `.bridge(id)`, `.project(id)`, `.sensor(id)`, `.crew(id)`, `.ambulance(id)`, `.hospital(id)`, `.shelter(id)` (each raises `UnknownAsset`); `City.zones_draining_to(channel_id) -> list[Zone]`, `City.roads_in(zone_id)`, `City.bridges_in(zone_id)`, `City.projects_in(zone_id)`; `build_nandipur() -> City`.

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_city.py`:

```python
import pytest
from pydantic import ValidationError

from gridline.city.model import City, DrainageChannel, Zone
from gridline.city.nandipur import build_nandipur
from gridline.errors import UnknownAsset


def test_seed_counts() -> None:
    city = build_nandipur()
    assert city.name == "Nandipur"
    assert len(city.zones) == 6
    assert len(city.channels) == 3
    assert len(city.rivers) == 1
    assert len(city.roads) == 8
    assert len(city.bridges) == 2
    assert len(city.projects) == 1
    assert len(city.sensors) == 14
    assert len(city.crews) == 3
    assert len(city.ambulances) == 4
    assert len(city.hospitals) == 1
    assert len(city.shelters) == 2
    assert city.pump_units_available == 4


def test_lookups_and_relations() -> None:
    city = build_nandipur()
    hillview = city.zone("hillview")
    assert hillview.kind == "hillside" and hillview.slope_deg == 32 and hillview.soil_type == "laterite"
    assert hillview.drains_to_channel_id == "D-7"
    d7 = city.channel("D-7")
    assert d7.design_capacity_m3s == 18 and d7.current_capacity_m3s == 12 and d7.downstream_zone_id == "riverside"
    assert city.zone("riverside").river_id == "kalinadi"
    assert city.road("hill_road").is_sole_access and city.road("hill_road").is_evacuation_route
    assert city.project("ht_phase2").permit_id == "HT-2026-014"
    assert {z.id for z in city.zones_draining_to("D-3")} == {"old_town", "market_ward", "station_road"}
    assert {r.id for r in city.roads_in("hillview")} == {"hill_road", "temple_road"}
    assert [b.id for b in city.bridges_in("hillview")] == ["hill_culvert_bridge"]
    assert [p.id for p in city.projects_in("hillview")] == ["ht_phase2"]
    assert city.sensor("SL-01").kind == "slope_monitor" and city.sensor("SL-01").zone_id == "hillview"
    assert city.sensor("CL-D7").target_id == "D-7"


def test_unknown_ids_raise() -> None:
    city = build_nandipur()
    with pytest.raises(UnknownAsset):
        city.zone("atlantis")
    with pytest.raises(UnknownAsset):
        city.sensor("RG-99")


def test_dangling_reference_rejected() -> None:
    with pytest.raises(ValidationError):
        City(
            name="Broken",
            zones=[Zone(id="a", name="A", kind="urban", slope_deg=1, soil_type="urban_fill", catchment_area_km2=1, drains_to_channel_id="missing")],
            channels=[DrainageChannel(id="D-1", name="D", from_zone_id="a", to_zone_id="a", design_capacity_m3s=1, current_capacity_m3s=1, downstream_zone_id="a")],
            rivers=[], roads=[], bridges=[], projects=[], sensors=[], crews=[], ambulances=[], hospitals=[], shelters=[],
            pump_units_available=0,
        )
```

Run: `cd backend && uv run pytest tests/test_city.py -v` — Expected: FAIL, `ModuleNotFoundError: gridline.city`.

- [ ] **Step 2: Implement the model**

`backend/gridline/city/__init__.py`: empty. `backend/gridline/city/model.py`:

```python
"""Typed description of a city (spec §4). Everything is frozen; live state lives in simulation.world."""

from collections.abc import Iterable
from typing import Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field, model_validator

from gridline.errors import UnknownAsset

ZoneKind = Literal["hillside", "floodplain", "urban", "lakeshore"]
SoilType = Literal["laterite", "alluvium", "urban_fill"]
SensorKind = Literal["weather_station", "soil_probe", "channel_gauge", "river_gauge", "slope_monitor", "flood_depth"]
CrewKind = Literal["rescue", "drainage"]


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True)
    id: str


class Zone(_Frozen):
    name: str
    kind: ZoneKind
    slope_deg: float = Field(ge=0, le=90)
    soil_type: SoilType
    catchment_area_km2: float = Field(gt=0)
    drains_to_channel_id: str
    river_id: str | None = None


class DrainageChannel(_Frozen):
    name: str
    from_zone_id: str
    to_zone_id: str
    design_capacity_m3s: float = Field(gt=0)
    current_capacity_m3s: float = Field(gt=0)
    downstream_zone_id: str
    note: str = ""


class River(_Frozen):
    name: str
    gauge_zone_id: str
    base_level_m: float = Field(ge=0)
    warning_level_m: float = Field(gt=0)
    danger_level_m: float = Field(gt=0)


class Road(_Frozen):
    name: str
    zone_id: str
    is_evacuation_route: bool = False
    is_sole_access: bool = False


class Bridge(_Frozen):
    name: str
    zone_id: str
    carries_road_id: str
    spans_id: str  # a channel id or a river id


class Project(_Frozen):
    name: str
    zone_id: str
    permit_id: str
    planned_depth_m: float = Field(gt=0)
    initial_depth_m: float = Field(ge=0)


class Sensor(_Frozen):
    kind: SensorKind
    zone_id: str
    target_id: str  # zone id, channel id or river id depending on kind
    depth_cm: int | None = None


class Crew(_Frozen):
    name: str
    kind: CrewKind
    home_zone_id: str


class Ambulance(_Frozen):
    home_zone_id: str


class Hospital(_Frozen):
    name: str
    zone_id: str
    beds_total: int = Field(gt=0)
    beds_occupied_baseline: int = Field(ge=0)


class Shelter(_Frozen):
    name: str
    zone_id: str
    capacity: int = Field(gt=0)


T = TypeVar("T", bound=_Frozen)


def _find(items: Iterable[T], item_id: str, kind: str) -> T:
    for item in items:
        if item.id == item_id:
            return item
    raise UnknownAsset(f"unknown {kind} id {item_id!r}")


class City(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    zones: list[Zone]
    channels: list[DrainageChannel]
    rivers: list[River]
    roads: list[Road]
    bridges: list[Bridge]
    projects: list[Project]
    sensors: list[Sensor]
    crews: list[Crew]
    ambulances: list[Ambulance]
    hospitals: list[Hospital]
    shelters: list[Shelter]
    pump_units_available: int = Field(ge=0)

    def zone(self, zone_id: str) -> Zone:
        return _find(self.zones, zone_id, "zone")

    def channel(self, channel_id: str) -> DrainageChannel:
        return _find(self.channels, channel_id, "channel")

    def river(self, river_id: str) -> River:
        return _find(self.rivers, river_id, "river")

    def road(self, road_id: str) -> Road:
        return _find(self.roads, road_id, "road")

    def bridge(self, bridge_id: str) -> Bridge:
        return _find(self.bridges, bridge_id, "bridge")

    def project(self, project_id: str) -> Project:
        return _find(self.projects, project_id, "project")

    def sensor(self, sensor_id: str) -> Sensor:
        return _find(self.sensors, sensor_id, "sensor")

    def crew(self, crew_id: str) -> Crew:
        return _find(self.crews, crew_id, "crew")

    def ambulance(self, ambulance_id: str) -> Ambulance:
        return _find(self.ambulances, ambulance_id, "ambulance")

    def hospital(self, hospital_id: str) -> Hospital:
        return _find(self.hospitals, hospital_id, "hospital")

    def shelter(self, shelter_id: str) -> Shelter:
        return _find(self.shelters, shelter_id, "shelter")

    def zones_draining_to(self, channel_id: str) -> list[Zone]:
        return [z for z in self.zones if z.drains_to_channel_id == channel_id]

    def roads_in(self, zone_id: str) -> list[Road]:
        return [r for r in self.roads if r.zone_id == zone_id]

    def bridges_in(self, zone_id: str) -> list[Bridge]:
        return [b for b in self.bridges if b.zone_id == zone_id]

    def projects_in(self, zone_id: str) -> list[Project]:
        return [p for p in self.projects if p.zone_id == zone_id]

    @model_validator(mode="after")
    def _check_references(self) -> "City":
        zone_ids = {z.id for z in self.zones}
        channel_ids = {c.id for c in self.channels}
        river_ids = {r.id for r in self.rivers}
        road_ids = {r.id for r in self.roads}
        problems: list[str] = []

        def need(ok: bool, message: str) -> None:
            if not ok:
                problems.append(message)

        for z in self.zones:
            need(z.drains_to_channel_id in channel_ids, f"zone {z.id}: channel {z.drains_to_channel_id}")
            need(z.river_id is None or z.river_id in river_ids, f"zone {z.id}: river {z.river_id}")
        for c in self.channels:
            for ref in (c.from_zone_id, c.to_zone_id, c.downstream_zone_id):
                need(ref in zone_ids, f"channel {c.id}: zone {ref}")
        for r in self.rivers:
            need(r.gauge_zone_id in zone_ids, f"river {r.id}: zone {r.gauge_zone_id}")
        for road in self.roads:
            need(road.zone_id in zone_ids, f"road {road.id}: zone {road.zone_id}")
        for b in self.bridges:
            need(b.zone_id in zone_ids, f"bridge {b.id}: zone {b.zone_id}")
            need(b.carries_road_id in road_ids, f"bridge {b.id}: road {b.carries_road_id}")
            need(b.spans_id in channel_ids | river_ids, f"bridge {b.id}: spans {b.spans_id}")
        for p in self.projects:
            need(p.zone_id in zone_ids, f"project {p.id}: zone {p.zone_id}")
        for s in self.sensors:
            need(s.zone_id in zone_ids, f"sensor {s.id}: zone {s.zone_id}")
            target_ok = {
                "weather_station": s.target_id in zone_ids,
                "soil_probe": s.target_id in zone_ids,
                "slope_monitor": s.target_id in zone_ids,
                "flood_depth": s.target_id in zone_ids,
                "channel_gauge": s.target_id in channel_ids,
                "river_gauge": s.target_id in river_ids,
            }[s.kind]
            need(target_ok, f"sensor {s.id}: target {s.target_id}")
        for crew in self.crews:
            need(crew.home_zone_id in zone_ids, f"crew {crew.id}: zone {crew.home_zone_id}")
        for a in self.ambulances:
            need(a.home_zone_id in zone_ids, f"ambulance {a.id}: zone {a.home_zone_id}")
        for h in self.hospitals:
            need(h.zone_id in zone_ids, f"hospital {h.id}: zone {h.zone_id}")
            need(h.beds_occupied_baseline <= h.beds_total, f"hospital {h.id}: occupied > total")
        for sh in self.shelters:
            need(sh.zone_id in zone_ids, f"shelter {sh.id}: zone {sh.zone_id}")
        if problems:
            raise ValueError("dangling references: " + "; ".join(problems))
        return self
```

- [ ] **Step 3: Implement the seed**

`backend/gridline/city/nandipur.py`:

```python
"""The synthetic city of Nandipur (spec §4). Every id, name and number is invented."""

from gridline.city.model import (
    Ambulance, Bridge, City, Crew, DrainageChannel, Hospital, Project, River, Road, Sensor, Shelter, Zone,
)


def build_nandipur() -> City:
    return City(
        name="Nandipur",
        zones=[
            Zone(id="hillview", name="Hillview", kind="hillside", slope_deg=32, soil_type="laterite",
                 catchment_area_km2=1.8, drains_to_channel_id="D-7"),
            Zone(id="riverside", name="Riverside", kind="floodplain", slope_deg=2, soil_type="alluvium",
                 catchment_area_km2=2.4, drains_to_channel_id="D-7", river_id="kalinadi"),
            Zone(id="old_town", name="Old Town", kind="urban", slope_deg=4, soil_type="urban_fill",
                 catchment_area_km2=2.0, drains_to_channel_id="D-3"),
            Zone(id="market_ward", name="Market Ward", kind="urban", slope_deg=3, soil_type="urban_fill",
                 catchment_area_km2=1.5, drains_to_channel_id="D-3"),
            Zone(id="station_road", name="Station Road", kind="urban", slope_deg=5, soil_type="urban_fill",
                 catchment_area_km2=1.2, drains_to_channel_id="D-3"),
            Zone(id="lakeside", name="Lakeside", kind="lakeshore", slope_deg=6, soil_type="alluvium",
                 catchment_area_km2=2.2, drains_to_channel_id="D-11"),
        ],
        channels=[
            DrainageChannel(id="D-7", name="Kalinadi Drain", from_zone_id="hillview", to_zone_id="riverside",
                            design_capacity_m3s=18, current_capacity_m3s=12, downstream_zone_id="riverside",
                            note="Culvert under Hill Road narrowed during the 2025 road widening"),
            DrainageChannel(id="D-3", name="Old Town Drain", from_zone_id="old_town", to_zone_id="market_ward",
                            design_capacity_m3s=14, current_capacity_m3s=14, downstream_zone_id="market_ward"),
            DrainageChannel(id="D-11", name="Lakeside Drain", from_zone_id="lakeside", to_zone_id="lakeside",
                            design_capacity_m3s=10, current_capacity_m3s=10, downstream_zone_id="lakeside"),
        ],
        rivers=[River(id="kalinadi", name="Kalinadi River", gauge_zone_id="riverside", base_level_m=1.2,
                      warning_level_m=2.5, danger_level_m=3.2)],
        roads=[
            Road(id="hill_road", name="Hill Road", zone_id="hillview", is_evacuation_route=True, is_sole_access=True),
            Road(id="riverside_bypass", name="Riverside Bypass", zone_id="riverside", is_evacuation_route=True),
            Road(id="station_road_main", name="Station Road", zone_id="station_road"),
            Road(id="market_street", name="Market Street", zone_id="market_ward"),
            Road(id="old_town_high_street", name="Old Town High Street", zone_id="old_town"),
            Road(id="lakeside_drive", name="Lakeside Drive", zone_id="lakeside"),
            Road(id="temple_road", name="Temple Road", zone_id="hillview"),
            Road(id="mill_lane", name="Mill Lane", zone_id="riverside"),
        ],
        bridges=[
            Bridge(id="kalinadi_bridge", name="Kalinadi Bridge", zone_id="riverside",
                   carries_road_id="riverside_bypass", spans_id="kalinadi"),
            Bridge(id="hill_culvert_bridge", name="Hill Road Culvert Bridge", zone_id="hillview",
                   carries_road_id="hill_road", spans_id="D-7"),
        ],
        projects=[Project(id="ht_phase2", name="Hillview Terrace Phase 2", zone_id="hillview",
                          permit_id="HT-2026-014", planned_depth_m=6.0, initial_depth_m=1.5)],
        sensors=[
            Sensor(id="RG-01", kind="weather_station", zone_id="hillview", target_id="hillview"),
            Sensor(id="RG-02", kind="weather_station", zone_id="riverside", target_id="riverside"),
            Sensor(id="RG-03", kind="weather_station", zone_id="old_town", target_id="old_town"),
            Sensor(id="RG-04", kind="weather_station", zone_id="lakeside", target_id="lakeside"),
            Sensor(id="SM-01", kind="soil_probe", zone_id="hillview", target_id="hillview", depth_cm=50),
            Sensor(id="SM-02", kind="soil_probe", zone_id="hillview", target_id="hillview", depth_cm=150),
            Sensor(id="SM-03", kind="soil_probe", zone_id="riverside", target_id="riverside", depth_cm=50),
            Sensor(id="CL-D7", kind="channel_gauge", zone_id="riverside", target_id="D-7"),
            Sensor(id="CL-D3", kind="channel_gauge", zone_id="market_ward", target_id="D-3"),
            Sensor(id="RL-01", kind="river_gauge", zone_id="riverside", target_id="kalinadi"),
            Sensor(id="SL-01", kind="slope_monitor", zone_id="hillview", target_id="hillview"),
            Sensor(id="FD-01", kind="flood_depth", zone_id="riverside", target_id="riverside"),
            Sensor(id="FD-02", kind="flood_depth", zone_id="old_town", target_id="old_town"),
            Sensor(id="FD-03", kind="flood_depth", zone_id="market_ward", target_id="market_ward"),
        ],
        crews=[
            Crew(id="C-1", name="Rescue Team 1", kind="rescue", home_zone_id="station_road"),
            Crew(id="C-2", name="Drainage Crew 2", kind="drainage", home_zone_id="old_town"),
            Crew(id="C-3", name="Rescue Team 3", kind="rescue", home_zone_id="riverside"),
        ],
        ambulances=[Ambulance(id=f"A-{n}", home_zone_id="old_town") for n in (1, 2, 3, 4)],
        hospitals=[Hospital(id="ngh", name="Nandipur General Hospital", zone_id="old_town",
                            beds_total=120, beds_occupied_baseline=84)],
        shelters=[
            Shelter(id="S-1", name="Market Ward Community Hall", zone_id="market_ward", capacity=400),
            Shelter(id="S-2", name="Station Road School", zone_id="station_road", capacity=600),
        ],
        pump_units_available=4,
    )
```

Run: `cd backend && uv run pytest tests/test_city.py -v` — Expected: 4 passed.

- [ ] **Step 4: Lint and type-check**

Run: `cd backend && uv run ruff format . && uv run ruff check . && uv run pyright` — Expected: clean (ruff will reformat the long constructor lines; that is fine).

---

### Task 4: Physics functions

**Files:**
- Create: `backend/gridline/simulation/__init__.py`, `backend/gridline/simulation/physics.py`
- Test: `backend/tests/test_physics.py`

**Interfaces:**
- Consumes: `SoilType` from `gridline.city.model`.
- Produces: constants `K_IN, K_DRAIN, RUNOFF_BASE, MM_H_KM2_TO_M3S, WATER_POOL, RECESSION, K_RIVER, RIVER_SMOOTHING, K_CREEP, SAT_CREEP_THRESHOLD, EXC_REF_DEPTH_M, SLOPE_REF_DEG, EXC_INFILTRATION`; functions `step_saturation, runoff_flow_m3s, channel_capacity_m3s, step_water_depth, step_river_level, slope_rate_mm_h, step_excavation, clamp`.

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_physics.py`:

```python
import pytest

from gridline.simulation import physics as ph


def test_saturation_clamps_and_rises_with_rain() -> None:
    assert ph.step_saturation(0.0, 0.0, k_in=0.35, excavation_depth_m=0, dt_h=1 / 12) == 0.0
    wet = ph.step_saturation(0.3, 5.0, k_in=0.35, excavation_depth_m=0, dt_h=1 / 12)
    assert wet > 0.3
    assert ph.step_saturation(1.0, 500.0, k_in=0.35, excavation_depth_m=0, dt_h=1 / 12) == 1.0
    assert ph.step_saturation(0.5, 0.0, k_in=0.35, excavation_depth_m=0, dt_h=1.0) < 0.5


def test_excavation_raises_infiltration() -> None:
    shallow = ph.step_saturation(0.2, 5.0, k_in=0.35, excavation_depth_m=0, dt_h=1 / 12)
    deep = ph.step_saturation(0.2, 5.0, k_in=0.35, excavation_depth_m=5, dt_h=1 / 12)
    assert deep > shallow


def test_runoff_flow_increases_with_saturation_and_rain() -> None:
    dry = ph.runoff_flow_m3s(30.0, 0.0, 1.8, 0.30)
    wet = ph.runoff_flow_m3s(30.0, 1.0, 1.8, 0.30)
    assert 0 < dry < wet
    assert wet == pytest.approx(30.0 * 1.8 * ph.MM_H_KM2_TO_M3S)
    assert ph.runoff_flow_m3s(0.0, 1.0, 1.8, 0.30) == 0.0


def test_channel_capacity_with_blockage_and_pumps() -> None:
    assert ph.channel_capacity_m3s(12.0, 0.0, 0.0) == 12.0
    assert ph.channel_capacity_m3s(12.0, 0.7, 0.0) == pytest.approx(3.6)
    assert ph.channel_capacity_m3s(12.0, 1.0, 2.0) == 2.0
    assert ph.channel_capacity_m3s(12.0, 1.0, 0.0) == 0.0


def test_water_depth_pools_on_overflow_and_recedes() -> None:
    assert ph.step_water_depth(0.0, 0.0, 1 / 12) == 0.0
    pooled = ph.step_water_depth(0.0, 12.0, 1 / 12)
    assert pooled > 0
    assert ph.step_water_depth(10.0, 0.0, 1.0) == pytest.approx(10.0 - ph.RECESSION)


def test_river_level_approaches_target() -> None:
    level = 1.2
    for _ in range(40):
        level = ph.step_river_level(level, 1.2, 20.0)
    assert level == pytest.approx(1.2 + ph.K_RIVER * 20.0, abs=0.01)
    assert ph.step_river_level(3.0, 1.2, 0.0) < 3.0


def test_slope_rate_needs_saturation_and_a_deep_cut() -> None:
    assert ph.slope_rate_mm_h(0.5, 32, 5.0) == 0.0
    assert ph.slope_rate_mm_h(1.0, 32, 0.0) == 0.0
    assert ph.slope_rate_mm_h(1.0, 10, 5.0) == 0.0
    shallow = ph.slope_rate_mm_h(1.0, 32, 2.75)
    deep = ph.slope_rate_mm_h(1.0, 32, 5.25)
    assert 0 < shallow < deep
    assert deep / shallow == pytest.approx((5.25 / 2.75) ** 2)


def test_excavation_advances_only_while_active_and_caps() -> None:
    assert ph.step_excavation(1.5, 6.0, 0.25, 1 / 12, active=True) == pytest.approx(1.5 + 0.25 / 12)
    assert ph.step_excavation(1.5, 6.0, 0.25, 1 / 12, active=False) == 1.5
    assert ph.step_excavation(5.99, 6.0, 12.0, 1.0, active=True) == 6.0
```

Run: `cd backend && uv run pytest tests/test_physics.py -v` — Expected: FAIL, `ModuleNotFoundError: gridline.simulation`.

- [ ] **Step 2: Implement**

`backend/gridline/simulation/__init__.py`: empty. `backend/gridline/simulation/physics.py`:

```python
"""Physics-lite models (spec §5.2). Pure functions; every constant is named and commented.

These constants are tuned so the scenario progression tests hold with margin. They are starting values,
not measurements of any real place.
"""

from gridline.city.model import SoilType

K_IN: dict[SoilType, float] = {"laterite": 0.35, "alluvium": 0.25, "urban_fill": 0.15}  # saturation per 100 mm
K_DRAIN = 0.02  # fraction of saturation drained per hour
RUNOFF_BASE: dict[SoilType, float] = {"laterite": 0.30, "alluvium": 0.35, "urban_fill": 0.60}  # runoff coeff dry
MM_H_KM2_TO_M3S = 0.2778  # 1 mm/h over 1 km² = 0.2778 m³/s
EXC_INFILTRATION = 0.15  # extra infiltration per metre of open cut
WATER_POOL = 1.0  # cm of ponding per (m³/s · h) of channel overflow into a zone
RECESSION = 3.0  # cm/h drained from ponded water when there is no overflow
K_RIVER = 0.08  # m of river rise per m³/s of inflow above base flow
RIVER_SMOOTHING = 0.2  # fraction of the gap to target closed per tick
K_CREEP = 80.0  # mm/h of slope creep at full saturation, reference cut depth and 40° slope
SAT_CREEP_THRESHOLD = 0.55  # saturation below which the slope does not creep
EXC_REF_DEPTH_M = 3.0  # cut depth at which the excavation factor is 1
SLOPE_REF_DEG = 20.0  # slope angle below which creep is zero


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def step_saturation(
    sat: float, rain_mm: float, *, k_in: float, excavation_depth_m: float, dt_h: float, k_drain: float = K_DRAIN
) -> float:
    """Bucket model: rain infiltrates (more with an open cut), drainage removes a fraction per hour."""
    infiltration = k_in * (1 + EXC_INFILTRATION * excavation_depth_m) * rain_mm / 100
    return clamp(sat + infiltration - k_drain * sat * dt_h, 0.0, 1.0)


def runoff_flow_m3s(intensity_mm_h: float, sat: float, area_km2: float, runoff_base: float) -> float:
    """Runoff coefficient rises linearly from the dry base to 1.0 at full saturation."""
    coefficient = runoff_base + (1 - runoff_base) * sat
    return coefficient * intensity_mm_h * area_km2 * MM_H_KM2_TO_M3S


def channel_capacity_m3s(current_capacity: float, blocked_fraction: float, extra: float) -> float:
    return max(0.0, current_capacity * (1 - blocked_fraction) + extra)


def step_water_depth(depth_cm: float, overflow_m3s: float, dt_h: float) -> float:
    return max(0.0, depth_cm + WATER_POOL * overflow_m3s * dt_h - RECESSION * dt_h)


def step_river_level(level_m: float, base_level_m: float, inflow_m3s: float) -> float:
    target = base_level_m + K_RIVER * inflow_m3s
    return level_m + RIVER_SMOOTHING * (target - level_m)


def slope_rate_mm_h(sat: float, slope_deg: float, excavation_depth_m: float) -> float:
    """Creep needs saturation above the threshold, a slope above the reference angle and a cut."""
    slope_factor = max(0.0, (slope_deg - SLOPE_REF_DEG) / SLOPE_REF_DEG)
    exc_factor = (excavation_depth_m / EXC_REF_DEPTH_M) ** 2
    return K_CREEP * max(0.0, sat - SAT_CREEP_THRESHOLD) ** 2 * exc_factor * slope_factor


def step_excavation(depth_m: float, planned_depth_m: float, rate_m_per_h: float, dt_h: float, *, active: bool) -> float:
    if not active:
        return depth_m
    return min(planned_depth_m, depth_m + rate_m_per_h * dt_h)
```

Run: `cd backend && uv run pytest tests/test_physics.py -v` — Expected: 8 passed.

- [ ] **Step 3: Lint and type-check**

Run: `cd backend && uv run ruff format . && uv run ruff check . && uv run pyright` — Expected: clean.

---
