# Simulation engine and event infrastructure — design

Date: 2026-09-26. Status: approved for planning under the assumptions in §1.
Scope: ARCHITECTURE.md milestone 1 minus the database. Nothing here makes an AI decision.

## 1. Intent, scope and assumptions

**Intent.** Give GridLine AI a continuously changing synthetic city. The engine turns a scenario script plus
small physics models into a stream of typed observation events (weather, environment, infrastructure,
emergency) that the threat detector, agent and dashboard will consume later. Operators control it through
REST and watch it through a WebSocket.

**In scope.** Event schema and payload models, city model and Nandipur seed, physics-lite models, four
scenarios, simulation engine (reset / advance / inject / replay), asyncio runner (start / pause / resume /
speed), in-process event bus, `/ws` endpoint, `/api/simulation/*` endpoints, backend skeleton (uv project,
config, app factory), tests, and a headless smoke script.

**Out of scope.** Threat indices and bands, incidents, LangGraph, RAG, tools, approvals, PostgreSQL
persistence, frontend. The event bus exposes `subscribe()`; the DB writer will be one more subscriber.

**Assumptions (override any):**

- A1. No database yet. The bus is in-memory. `POST /api/simulation/reset` resets the engine only.
- A2. The event envelope is the seven fields from the request plus `sim_time` and an optional `incident_id`
  (ARCHITECTURE §12 requires wall time and sim time on every timestamped thing; incidents come next).
- A3. City seed is typed Python (`gridline/city/nandipur.py`), not YAML. No new dependency; pyright covers it.
- A4. Severity on observation events is a fixed-threshold sensor band (like a gauge alarm level). It is
  not a threat assessment. Thresholds live in one module, not in prompts.
- A5. Stage boundaries are scheduled by tick. Observations inside a stage come from physics driven by the
  scripted rainfall and excavation curves, so they respond to state changes (a halted project lowers
  infiltration; a blocked channel raises downstream load). The stage-5 landslide is conditional on the
  hillside actually being saturated.
- A6. Synthetic time starts at 2026-07-14 06:00 UTC for every scenario. One tick is 5 simulated minutes.
- A7. Feature branch `feature/simulation-events`; no commits until asked.

## 2. Package layout

```
backend/
  pyproject.toml                 uv project "gridline", hatchling build, editable install
  .env.example
  gridline/
    __init__.py, py.typed
    config.py                    Settings (pydantic-settings)
    main.py                      create_app(settings) with lifespan; app = create_app()
    city/
      model.py                   City and asset models
      nandipur.py                build_nandipur() -> City
    events/
      types.py                   EventType, Severity
      payloads.py                one Pydantic model per event type + PAYLOAD_MODELS registry
      envelope.py                Event model, new_event() factory
      bus.py                     EventBus, Subscription
      websocket.py               /ws route
    simulation/
      world.py                   WorldState + WorldSnapshot
      physics.py                 pure numeric step functions
      severity.py                severity_for(event_type, payload) thresholds
      scenarios/
        base.py                  Scenario, Stage, Curve, ForecastUpdate, ScriptedEvent, Condition
        normal_city.py, hillside_landslide.py, flash_flood.py, cascading_landslide_flood.py
        __init__.py              SCENARIOS registry, get_scenario()
      apply.py                   apply_event(world, event) -> list[Event]   (state mutation handlers)
      engine.py                  SimulationEngine
      runner.py                  SimulationRunner (asyncio, real-time pacing)
    api/
      deps.py                    get_runner, get_bus
      health.py                  GET /api/health
      simulation.py              /api/simulation/* router + request/response models
  tests/                         see §11
scripts/demo_smoke.py            headless cascading scenario, asserts final state
docs/superpowers/specs/…         this file
```

Files stay under about 300 lines. Everything on the request path is async; the engine itself is
synchronous and pure with respect to its own state and seed.

## 3. Event schema

### 3.1 Envelope (`gridline/events/envelope.py`)

```python
class Event(BaseModel):
    model_config = ConfigDict(frozen=True)
    event_id: str            # "evt-000001" — sequential per engine reset, so replays match
    timestamp: datetime      # wall clock, tz-aware UTC, from an injectable clock
    sim_time: datetime       # simulated clock, tz-aware UTC
    event_type: EventType
    source: str              # "sensor:RG-01" | "scenario:<name>" | "operator:api" | "simulation:engine"
    location: str | None     # zone id, or None for city-wide events
    severity: Severity       # info | low | moderate | high | critical
    payload: dict[str, Any]  # validated against PAYLOAD_MODELS[event_type]
    incident_id: str | None = None
```

A `model_validator(mode="after")` validates `payload` with the registered model for `event_type`
and stores the model's `model_dump(mode="json")`, so an `Event` is always JSON-safe and its payload
always conforms. Unknown or malformed payloads raise `ValidationError`.

`new_event(event_type, payload: BaseModel, *, source, location, severity, event_id, timestamp, sim_time)`
is the typed constructor. It asserts `type(payload) is PAYLOAD_MODELS[event_type]`.

### 3.2 Enums (`gridline/events/types.py`)

`Severity(StrEnum)`: `info, low, moderate, high, critical`.

`EventType(StrEnum)` and payload models (`gridline/events/payloads.py`). Every field is typed and
bounded (`Field(ge=…)`) where a bound exists. `location` for every zone-scoped type is the zone id.

| Event type | Emitted | Payload model and fields |
|---|---|---|
| `sim.tick` | every tick | `SimTick`: tick:int, sim_time:datetime, scenario:str, stage:str, speed:float |
| `sim.status` | on start/pause/resume/reset/select/speed | `SimStatus`: state:`idle\|running\|paused`, scenario, seed:int, speed, tick, sim_time, stage |
| `sim.snapshot` | WebSocket connect only | `SimSnapshot`: status:SimStatus, world:WorldSnapshot |
| `sim.heartbeat` | WebSocket idle only | `Heartbeat`: tick, sim_time |
| `scenario.stage` | on stage entry (including stage 0 at tick 0) | `ScenarioStage`: scenario, stage_index:int, stage:str, description:str, tick |
| `weather.observation` | per weather station per tick | `WeatherObservation`: station_id, rainfall_intensity_mm_h≥0, cumulative_rainfall_24h_mm≥0, temperature_c, wind_speed_kmh≥0, wind_direction_deg∈[0,360) |
| `weather.forecast` | scripted or injected | `WeatherForecast`: issued_sim_time, horizon_h>0, expected_total_mm≥0, peak_intensity_mm_h≥0, confidence∈[0,1], summary:str |
| `environment.soil` | per soil probe per tick | `SoilObservation`: probe_id, depth_cm, soil_moisture_pct∈[0,100], saturation∈[0,1] |
| `environment.river` | per river gauge per tick | `RiverObservation`: gauge_id, river_id, level_m≥0, warning_level_m, danger_level_m, trend:`rising\|steady\|falling` |
| `environment.drainage` | per channel gauge per tick | `DrainageObservation`: gauge_id, channel_id, flow_m3s≥0, capacity_m3s≥0, load_ratio≥0, blocked_fraction∈[0,1], overflow_m3s≥0 |
| `environment.slope` | per slope monitor per tick | `SlopeObservation`: monitor_id, movement_rate_mm_h≥0, cumulative_movement_mm≥0, saturation |
| `environment.water_accumulation` | per flood-depth sensor per tick while depth>0, plus one final reading when it returns to 0 | `WaterAccumulation`: sensor_id, depth_cm≥0, trend |
| `infrastructure.road` | on change | `RoadStatus`: road_id, status:`open\|blocked\|closed`, reason:str, is_evacuation_route:bool |
| `infrastructure.bridge` | on change | `BridgeStatus`: bridge_id, status:`open\|restricted\|closed`, reason |
| `infrastructure.drainage_obstruction` | on change | `DrainageObstruction`: channel_id, blocked_fraction∈[0,1], cause:str |
| `infrastructure.construction` | on status change, or when depth advanced ≥ 0.1 m since last report (source `simulation:engine`) | `ConstructionActivity`: project_id, status:`active\|halted`, activity:`excavating\|idle\|halted`, excavation_depth_m≥0, planned_depth_m |
| `infrastructure.failure` | scripted or injected | `InfrastructureFailure`: asset_id, asset_kind:`slope\|channel\|bridge\|road\|power`, failure_kind:`landslide\|culvert_collapse\|embankment_breach\|power_outage`, description |
| `emergency.rescue_team` | on change | `RescueTeamStatus`: crew_id, status:`available\|en_route\|on_site\|blocked\|resting`, location_zone_id, task:str |
| `emergency.ambulance` | on change | `AmbulanceStatus`: ambulance_id, status:`available\|dispatched\|out_of_service`, location_zone_id, available_count≥0, total_count≥0 |
| `emergency.hospital` | on change | `HospitalCapacity`: hospital_id, beds_total, beds_occupied, beds_available, er_status:`normal\|busy\|overwhelmed` |
| `emergency.shelter` | on change | `ShelterCapacity`: shelter_id, status:`closed\|open\|full`, capacity, occupancy |

`PAYLOAD_MODELS: dict[EventType, type[BaseModel]]` maps every member; a test asserts the map is total.

**Injectable types** (have an `apply` handler, §7): `weather.forecast`, `infrastructure.*`, `emergency.*`.
Observation types (`weather.observation`, `environment.*`) and `sim.*`/`scenario.*` are derived from
state and cannot be injected (HTTP 422).

### 3.3 Severity (`gridline/simulation/severity.py`)

`severity_for(event_type, payload) -> Severity` with these fixed bands. Injection may override.

| Type | info | low | moderate | high | critical |
|---|---|---|---|---|---|
| weather.observation (mm/h) | <10 | <25 | <40 | <60 | ≥60 |
| environment.soil (saturation) | <0.5 | <0.7 | <0.85 | <0.95 | ≥0.95 |
| environment.drainage (load_ratio) | <0.6 | <0.85 | <1.0 | <1.5 | ≥1.5 |
| environment.river (level) | <0.8·warning | — | <warning | <danger | ≥danger |
| environment.slope (mm/h) | 0 | <2 | <10 | <30 | ≥30 |
| environment.water_accumulation (cm) | 0 | <10 | <25 | <50 | ≥50 |
| infrastructure.road | open | — | blocked/closed | blocked/closed and evacuation route | — |
| infrastructure.bridge | open | — | restricted | closed | — |
| infrastructure.drainage_obstruction (blocked_fraction) | <0.1 | <0.25 | <0.5 | <0.8 | ≥0.8 |
| infrastructure.construction | halted / idle | excavating | — | — | — |
| infrastructure.failure | — | — | — | — | always |
| emergency.rescue_team | available/resting/on_site | en_route | — | blocked | — |
| emergency.ambulance (available_count) | ≥2 | — | 1 | 0 | — |
| emergency.hospital | normal | — | busy | — | overwhelmed |
| emergency.shelter | closed/open | — | — | full | — |
| sim.*, scenario.stage, weather.forecast | info (forecast: peak ≥40 → high) | | | | |

## 4. City model and Nandipur seed

`gridline/city/model.py` — frozen Pydantic models, ids are stable snake_case / dashed strings:

- `Zone(id, name, kind: hillside|floodplain|urban|lakeshore, slope_deg, soil_type: laterite|alluvium|urban_fill, catchment_area_km2, drains_to_channel_id, river_id|None)`
- `DrainageChannel(id, name, from_zone_id, to_zone_id, design_capacity_m3s, current_capacity_m3s, downstream_zone_id, note)`
- `River(id, name, gauge_zone_id, base_level_m, warning_level_m, danger_level_m)`
- `Road(id, name, zone_id, is_evacuation_route, is_sole_access)`
- `Bridge(id, name, zone_id, carries_road_id, spans: channel id or river id)`
- `Project(id, name, zone_id, permit_id, planned_depth_m, initial_depth_m)`
- `Sensor(id, kind: weather_station|soil_probe|channel_gauge|river_gauge|slope_monitor|flood_depth, zone_id, target_id, depth_cm|None)`
- `Crew(id, name, kind: rescue|drainage, home_zone_id)`, `Ambulance(id, home_zone_id)`,
  `Hospital(id, name, zone_id, beds_total, beds_occupied_baseline)`, `Shelter(id, name, zone_id, capacity)`
- `City(name, zones, channels, rivers, roads, bridges, projects, sensors, crews, ambulances, hospitals, shelters, pump_units_available)` with `zone(id)`-style lookups and a validator that every cross-reference resolves.

`build_nandipur()` seed (all invented):

| Kind | Entries |
|---|---|
| Zones | `hillview` (hillside, 32°, laterite, 1.8 km², →D-7), `riverside` (floodplain, 2°, alluvium, 2.4, →D-7 lower, on `kalinadi`), `old_town` (urban, 4°, urban_fill, 2.0, →D-3), `market_ward` (urban, 3°, urban_fill, 1.5, →D-3), `station_road` (urban, 5°, urban_fill, 1.2, →D-3), `lakeside` (lakeshore, 6°, alluvium, 2.2, →D-11) |
| Channels | `D-7` Kalinadi Drain hillview→riverside, design 18, current 12 (culvert narrowed 2025); `D-3` Old Town Drain, 14/14, downstream market_ward; `D-11` Lakeside Drain, 10/10, downstream lakeside |
| River | `kalinadi`, gauge in riverside, base 1.2 m, warning 2.5, danger 3.2 |
| Roads | `hill_road` (hillview, sole access, evacuation), `riverside_bypass` (riverside, evacuation), `station_road_main`, `market_street`, `old_town_high_street`, `lakeside_drive`, `temple_road` (hillview), `mill_lane` (riverside) |
| Bridges | `kalinadi_bridge` (riverside, carries riverside_bypass, spans kalinadi), `hill_culvert_bridge` (hillview, carries hill_road, spans D-7) |
| Project | `ht_phase2` Hillview Terrace Phase 2, hillview, permit `HT-2026-014`, planned 6.0 m, initial 1.5 m |
| Sensors | weather stations RG-01 hillview, RG-02 riverside, RG-03 old_town, RG-04 lakeside; soil probes SM-01 hillview 50 cm, SM-02 hillview 150 cm, SM-03 riverside 50 cm; channel gauges CL-D7, CL-D3; river gauge RL-01; slope monitor SL-01 hillview; flood depth FD-01 riverside, FD-02 old_town, FD-03 market_ward |
| Crews | C-1 rescue (station_road), C-2 drainage (old_town), C-3 rescue (riverside) |
| Ambulances | A-1..A-4, home old_town |
| Hospital | `ngh` Nandipur General Hospital, old_town, 120 beds, 84 occupied baseline |
| Shelters | S-1 Market Ward Community Hall (400), S-2 Station Road School (600) |
| Pumps | 4 units at the station_road depot |

## 5. World state and physics

### 5.1 WorldState (`gridline/simulation/world.py`)

Mutable dataclass built from `City` at reset. Per zone: `saturation`, `rain_24h: deque[float]` (288
per-tick amounts), `rainfall_intensity_mm_h`, `temperature_c`, `wind_speed_kmh`, `wind_direction_deg`,
`water_depth_cm`, `slope_rate_mm_h`, `slope_cumulative_mm`. Per channel: `blocked_fraction`,
`extra_capacity_m3s` (pumps later), `flow_m3s`, `overflow_m3s`. River: `level_m`. Roads and bridges:
status and reason. Project: `status`, `excavation_depth_m`, `activity`. Crews, ambulances, hospital,
shelters: current fields from §3.2. `forecast: WeatherForecast | None`. `tick`, `sim_time`, `stage_index`.

`WorldSnapshot` is the frozen Pydantic export of all of the above (used by `sim.snapshot` and
`GET /api/simulation/snapshot`).

### 5.2 Physics (`gridline/simulation/physics.py`, pure functions, `dt_h = minutes_per_tick / 60`)

Constants per soil type: `K_IN = {laterite: 0.35, alluvium: 0.25, urban_fill: 0.15}` (saturation per
100 mm), `K_DRAIN = 0.02` per hour, `RUNOFF_BASE = {laterite: 0.30, alluvium: 0.35, urban_fill: 0.60}`.

- `step_saturation(sat, rain_mm, k_in, k_drain, excavation_depth_m, dt_h)`:
  `sat + k_in * (1 + 0.15 * excavation_depth_m) * rain_mm / 100 - k_drain * sat * dt_h`, clamped [0, 1].
- `runoff_flow_m3s(intensity_mm_h, sat, area_km2, runoff_base)`:
  `c = runoff_base + (1 - runoff_base) * sat`; `flow = c * intensity_mm_h * area_km2 * 0.2778`.
- `channel_capacity_m3s(current_capacity, blocked_fraction, extra)`: `current * (1 - blocked) + extra`.
- `step_water_depth(depth_cm, overflow_m3s, dt_h)`: `depth + WATER_POOL * overflow * dt_h - RECESSION * dt_h`,
  clamped ≥ 0, with `WATER_POOL = 1.0` cm per (m³/s·h) and `RECESSION = 3.0` cm/h.
- `step_river_level(level, base, inflow_m3s)`: `target = base + K_RIVER * inflow` (`K_RIVER = 0.08`);
  `level + 0.2 * (target - level)`.
- `slope_rate_mm_h(sat, slope_deg, excavation_depth_m)`:
  `slope_factor = max(0, (slope_deg - 20) / 20)`; `exc_factor = (excavation_depth_m / 3.0) ** 2`;
  `K_CREEP * max(0, sat - 0.55) ** 2 * exc_factor * slope_factor` with `K_CREEP = 80`. The squared
  excavation term is what makes halting construction early prevent the landslide (§6.2, §11).
- `step_excavation(depth, planned, rate_m_per_h, dt_h, status)`: advances only while `active`, capped at planned.

These constants are starting values chosen by back-of-envelope estimates. The implementer may tune them so
that every assertion in §11 holds with margin, and must keep the final values as named module constants
with a one-line comment each. Behavioural intent is fixed: rain saturates soil within hours during the storm
scenarios; a narrowed or blocked channel overloads under storm runoff; slope creep needs both saturation and
a deep cut; halting the cut at t=60 keeps cumulative movement well under the landslide condition.

Per-tick order inside the engine: apply scenario drivers → excavation → saturation per zone → channel
flow and overflow (flow into a channel = runoff of every zone draining to it) → water depth of the
channel's downstream zone → river level (inflow = D-7 flow + riverside runoff) → slope rate for hillside
zones → sensors sample with noise.

### 5.3 Sensor noise

Seeded `random.Random(seed)` per reset. Gaussian sigma: rain 0.3 mm/h (clamped ≥ 0), temperature 0.2,
wind 0.8, soil moisture 0.5 pct, channel flow 2 % of value, river level 0.02 m, slope 0.1 mm/h.
`soil_moisture_pct = 45 * saturation` before noise. Iteration order is sorted by sensor id so the event
sequence is deterministic.

## 6. Scenarios

### 6.1 Models (`gridline/simulation/scenarios/base.py`)

```python
class Keyframe(BaseModel): tick: int; value: float
class Curve(BaseModel):  keyframes: list[Keyframe]     # piecewise-linear; holds last value after the end
    def at(self, tick: int) -> float
class Stage(BaseModel): name: str; start_tick: int; description: str
class ForecastUpdate(BaseModel): tick: int; forecast: WeatherForecast
class Condition(BaseModel): zone_id: str; metric: Literal["saturation","water_depth_cm","river_level_m","slope_cumulative_mm"]; min_value: float
class ScriptedEvent(BaseModel):
    tick: int; event_type: EventType; location: str | None; payload: dict[str, Any]
    condition: Condition | None = None; deadline_ticks: int = 36   # re-check each tick until tick+deadline, then drop
class Excavation(BaseModel): project_id: str; start_tick: int; rate_m_per_h: float
class Scenario(BaseModel):
    name: ScenarioName; title: str; description: str; duration_ticks: int
    rainfall: dict[str, Curve]          # per zone id; missing zones use "default"
    temperature: Curve; wind_speed: Curve; wind_direction_deg: float
    forecasts: list[ForecastUpdate]; excavation: Excavation | None
    stages: list[Stage]; scripted: list[ScriptedEvent]
```

`ScenarioName(StrEnum)`: `normal_city`, `hillside_landslide`, `flash_flood`, `cascading_landslide_flood`.
`SCENARIOS` registry, `get_scenario(name)`. Stages must start at 0 and be strictly increasing (validator).

### 6.2 Definitions (tick = 5 min, 12 ticks/hour; rain in mm/h)

**normal_city** (288 ticks). Rain default: 0 → 2 at t=96 → 3 at t=132 → 0 at t=168 → 0. Temperature
24 → 31 (t=108) → 25. Wind 6 → 14 → 8. One stage `steady_state`. One forecast at t=0 ("light showers,
12 mm over 24 h", peak 3, confidence 0.8). No scripted events, excavation `ht_phase2` at 0.05 m/h from
t=0 (routine). Nothing exceeds `low` severity.

**hillside_landslide** (288 ticks). Excavation `ht_phase2` from t=0 at 0.25 m/h. Rain (hillview and
default): 4 → 4 (t=36) → 22 (t=72) → 30 (t=96) → 35 (t=144) → 35 (t=216) → 5 (t=252) → 0 (t=288).
Riverside rain curve identical minus 20 %. Temperature 26 → 22 (t=96) → 21 → 24. Wind 8 → 28 (t=120) → 12.
Forecasts: t=0 moderate (60 mm/24 h, peak 20, 0.7); t=30 heavy-rain warning (180 mm/24 h, peak 40, 0.85).
Stages: 0 `construction_and_rain` t=0; 1 `intensifying_rain` t=36; 2 `slope_creep` t=96;
3 `critical_slope` t=144. Scripted: t=150 `emergency.rescue_team` C-1 `available` task "standby hillside"
(source scenario). No landslide occurs.

**flash_flood** (240 ticks). No excavation. Rain: 6 → 6 (t=48) → 45 (t=84) → 45 (t=132) → 20 (t=168)
→ 0 (t=204). Temperature 27 → 23 → 24. Wind 10 → 35 (t=96) → 15. Forecasts: t=0 (40 mm, peak 15, 0.6);
t=40 cloudburst warning (150 mm/6 h, peak 50, 0.9). Stages: 0 `culvert_constraint` t=0;
1 `severe_rain` t=48; 2 `drain_overload` t=96; 3 `riverside_flooding` t=132. Scripted:
t=12 `infrastructure.drainage_obstruction` D-7 blocked 0.25 "monsoon debris at the narrowed culvert";
t=132 `infrastructure.road` riverside_bypass `blocked` "standing water" if riverside water_depth_cm ≥ 20;
t=140 `emergency.hospital` ngh occupied 104 `busy`; t=144 `emergency.ambulance` A-2 `dispatched`
riverside (available 3/4); t=150 `emergency.rescue_team` C-3 `on_site` riverside "pump and evacuate".

**cascading_landslide_flood** (300 ticks). Stages 0–3 identical to hillside_landslide (same curves
through t=216, rain then 35 → 35 (t=240) → 8 (t=276) → 0 (t=300)). Additional stages:
4 `landslide_and_blockage` t=180; 5 `downstream_flood` t=204. Scripted:
t=150 rescue-team standby as above;
t=180 `infrastructure.failure` asset SL-01 slope `landslide` "Hillview Terrace slope failed above D-7"
**if hillview slope_cumulative_mm ≥ 80** (deadline 36 ticks) — the apply handler (§7) then blocks D-7 at 0.7,
blocks hill_road, closes hill_culvert_bridge, halts ht_phase2;
t=210 `emergency.hospital` ngh 100 occupied `busy`;
t=216 `emergency.ambulance` A-1 `dispatched` hillview (3/4);
t=228 `infrastructure.bridge` kalinadi_bridge `closed` "river at danger level" if riverside river_level_m ≥ 3.0;
t=234 `infrastructure.road` riverside_bypass `blocked` "flood water" if riverside water_depth_cm ≥ 25;
t=240 `emergency.rescue_team` C-3 `on_site` riverside "evacuation support";
t=246 `emergency.hospital` ngh 112 occupied `overwhelmed`.

The six stages requested map as: stage 1 construction + rainfall → `construction_and_rain`; stage 2 rain
and saturation rising → `intensifying_rain`; stage 3 landslide probability rising → `slope_creep`
(slope monitor reports creep); stage 4 critical → `critical_slope`; stage 5 drainage blockage →
`landslide_and_blockage`; stage 6 downstream flood → `downstream_flood`.

## 7. Engine, apply handlers, runner

### 7.1 `SimulationEngine` (`gridline/simulation/engine.py`, synchronous, deterministic)

```python
class SimulationEngine:
    def __init__(self, city: City, *, minutes_per_tick: int = 5, clock: Callable[[], datetime] = utcnow)
    def reset(self, scenario: ScenarioName, seed: int) -> list[Event]       # world from city; rng; tick 0; emits scenario.stage 0
    def advance(self, ticks: int = 1) -> list[Event]                        # one physics step per tick; returns events in order
    def inject(self, event_type, payload: dict, *, location, source="operator:api", severity=None) -> list[Event]
    def replay(self, scenario, seed, ticks) -> list[Event]                  # reset + advance, convenience for tests/smoke
    def snapshot(self) -> WorldSnapshot
    @property status -> EngineStatus(scenario, seed, tick, sim_time, stage_index, stage_name)
    @property speed  -> float    # informational; set by runner, included in sim.tick
```

`advance` per tick: tick += 1; sim_time += minutes_per_tick; enter stage if `start_tick == tick` (emit
`scenario.stage`); apply scenario drivers (rain per zone, temperature, wind, forecast updates → emit
`weather.forecast` when a new forecast is issued); excavation; physics (§5.2); scripted events whose tick
has arrived or whose condition is pending (evaluate condition; on pass → `apply_event`; past deadline →
drop silently); sensors → observation events; `sim.tick` last. Event ids come from a counter reset at
`reset()`. All emitted events pass through `severity_for` unless a severity is given.

### 7.2 `apply_event` (`gridline/simulation/apply.py`)

`apply_event(world, city, event) -> list[Event]` mutates state and returns the event itself plus derived
events (`source="simulation:engine"`). Handlers:

- `weather.forecast` → `world.forecast`.
- `infrastructure.road` / `.bridge` → set status and reason.
- `infrastructure.drainage_obstruction` → `blocked_fraction`.
- `infrastructure.construction` → status/activity/depth (halting sets activity `halted`; depth stays).
- `infrastructure.failure` with `landslide` on a hillside asset → `slope_cumulative_mm += 1500`,
  `slope_rate` spike, D-7 `blocked_fraction = max(current, 0.7)`, roads in that zone with
  `is_sole_access` → `blocked`, bridges in that zone → `closed`, projects in that zone → `halted`; each
  derived change emits its own event. `culvert_collapse` → channel blocked 1.0. Others: no derived state.
- `emergency.*` → set the corresponding fields.

Injecting a non-injectable type raises `NotInjectable` (→ 422). Unknown ids raise `UnknownAsset` (→ 422).
No-op injections (state already equal) still emit the event.

### 7.3 `SimulationRunner` (`gridline/simulation/runner.py`, asyncio)

Owns the engine, the bus and a single ticking task. State machine: `idle` (scenario loaded, tick 0 or
stopped) → `start()` → `running` ⇄ `pause()`/`resume()` → `paused`; `reset()` and
`select_scenario()` cancel the task and return to `idle`; `advance(n)` is allowed in `idle` or `paused`
and raises `InvalidTransition` when `running`; `set_speed(s)` (0.25 ≤ s ≤ 10) at any time;
`inject(...)` at any time (events are published). `start()` while `paused` raises `InvalidTransition` (use
`resume()`). Tick loop: `events = engine.advance(); publish each; await sleep(tick_seconds / speed)`;
pause blocks on an `asyncio.Event`. Every transition publishes one `sim.status` event whose id comes from
the engine's counter (`engine.status_event(...)`), so a reset followed by the same operations replays
identically. `status()` returns
`SimulationStatus(state, scenario, seed, speed, tick, sim_time, stage: StageInfo|None, minutes_per_tick,
tick_seconds)`. `start(scenario=None, seed=None, speed=None)` selects and resets first if a scenario or seed
is given, or if the engine has never been reset. `shutdown()` cancels the task.

### 7.4 `EventBus` (`gridline/events/bus.py`)

`subscribe(type_prefixes: Sequence[str] | None = None, *, maxsize=1000) -> Subscription` with
`queue: asyncio.Queue[Event]`, `dropped: int`, `matches(event)`. `publish(event)` is synchronous:
for each subscription whose filter matches, `put_nowait`; when full, drop the oldest and increment
`dropped`. `unsubscribe(sub)`. `subscriber_count`. One instance on `app.state.bus`.

## 8. API

### 8.1 WebSocket `/ws?types=weather.,environment.soil`

On accept: subscribe with the optional comma-separated prefix filter, send one `sim.snapshot` event
(status + world snapshot, `source="simulation:engine"`), then forward bus events as `event.model_dump_json()`.
If nothing is sent for `WS_HEARTBEAT_SECONDS`, send a `sim.heartbeat` event. Snapshot and heartbeat frames are
per-connection and never touch the bus or the engine's id counter; their ids are `evt-snapshot` and
`evt-heartbeat`. Disconnect (either side) unsubscribes. Messages from the client are read and ignored (this
keeps disconnects prompt).

### 8.2 REST (`/api`, JSON; every request and response body is a Pydantic model)

| Method and path | Body → Response | Errors |
|---|---|---|
| `GET /health` | → `{status:"ok", version}` | |
| `GET /simulation/status` | → `SimulationStatus` | |
| `GET /simulation/scenarios` | → `list[ScenarioInfo{name,title,description,duration_ticks,stages[]}]` | |
| `GET /simulation/snapshot` | → `WorldSnapshot` | |
| `POST /simulation/scenario` | `{scenario, seed?}` → `SimulationStatus` (stops and resets to tick 0) | 422 unknown scenario |
| `POST /simulation/start` | `{scenario?, seed?, speed?}` → `SimulationStatus` | 409 already running |
| `POST /simulation/pause` | → `SimulationStatus` | 409 not running |
| `POST /simulation/resume` | → `SimulationStatus` | 409 not paused |
| `POST /simulation/reset` | → `SimulationStatus` (same scenario and seed, tick 0, idle) | |
| `POST /simulation/advance` | `{ticks: int = 1 (1..1000)}` → `{events_emitted, status}` | 409 running |
| `POST /simulation/speed` | `{speed}` → `SimulationStatus` | 422 out of range |
| `POST /simulation/inject` | `{event_type, location?, payload, source?, severity?}` → `list[Event]` (event plus derived) | 422 not injectable / invalid payload / unknown asset |

`InvalidTransition` → 409 with `{detail}`; `NotInjectable`, `UnknownAsset`, payload `ValidationError` → 422.

### 8.3 Config (`gridline/config.py`, `backend/.env.example`)

```
SIM_TICK_SECONDS=1.0
SIM_MINUTES_PER_TICK=5
SIM_DEFAULT_SCENARIO=cascading_landslide_flood
SIM_DEFAULT_SEED=42
SIM_AUTOSTART=false
WS_HEARTBEAT_SECONDS=15
EVENT_QUEUE_SIZE=1000
```

`create_app(settings: Settings | None = None)`; lifespan builds city → engine → bus → runner, resets to
the default scenario and seed, optionally autostarts, stores on `app.state`, and shuts the runner down on
exit. Dependencies in `api/deps.py`. `gridline.main:app` is the uvicorn target.

## 9. Determinism and replay

Given `(scenario, seed, ticks)` two engines with the same injected clock produce identical event lists
(ids, sim times, payloads, severities). Sources of nondeterminism are limited to `timestamp` (wall
clock, injectable) and operator injections. Replay = `reset` + `advance`; the runner's `reset()`
reproduces the same stream when nothing is injected.

## 10. Error handling

Engine and runner raise typed exceptions (`InvalidTransition`, `NotInjectable`, `UnknownAsset`,
`UnknownScenario`); the API maps them to 409 / 422. Payload validation errors are FastAPI 422s. A slow
WebSocket consumer loses oldest events (counted, never blocking the engine). The tick loop catches and
logs exceptions per tick and keeps running; an engine bug never kills the process silently.

## 11. Testing

All backend tests run with `cd backend && uv run pytest`, no Docker, under about ten seconds.

| File | Covers |
|---|---|
| `test_event_envelope.py` | envelope fields, JSON round trip, payload validation against the registry, registry is total over `EventType`, `new_event` rejects wrong payload class |
| `test_payloads.py` | one construction and one bound violation per payload model |
| `test_severity.py` | one case per band row in §3.3 |
| `test_city.py` | seed loads, every cross-reference resolves, counts match §4 |
| `test_physics.py` | saturation clamps and monotonicity, excavation raises infiltration, capacity with blockage, overflow only above capacity, water depth recedes, river approaches target, slope rate zero below threshold and rises with saturation and excavation |
| `test_scenarios.py` | registry has four names, curve interpolation and hold, stages validated, each scenario's scripted events use known ids and injectable types |
| `test_engine_generation.py` | reset emits stage 0; one tick emits `sim.tick` plus one event per weather station, soil probe, channel gauge, river gauge and slope monitor; sources and locations match the sensor table; all events validate; event ids sequential |
| `test_engine_injection.py` | each injectable type mutates snapshot and emits; landslide failure cascades into four derived events; non-injectable → `NotInjectable`; unknown id → `UnknownAsset` |
| `test_scenario_progression.py` | cascading: stages entered in order at their ticks; hillview saturation rises during stage 1 and is ≥0.75 by t=180; slope rate >0 by end of stage 2; cumulative slope movement ≥80 mm by t=216; landslide fires during stage 4 (t=180..204) and D-7 blocked ≥0.7, hill_road blocked, hill_culvert_bridge closed, ht_phase2 halted; riverside water depth ≥25 cm and river level >warning during stage 5; bypass blocked. hillside_landslide: no `infrastructure.failure`. flash_flood: D-7 load ratio >1 in stage 2, riverside max water depth >20 cm during stage 3 and bypass blocked. normal_city: no event above `low` over 288 ticks. cascading with `ht_phase2` halted by injection at t=60: no `infrastructure.failure` through t=300 and cumulative movement <80 mm |
| `test_determinism.py` | same scenario+seed → identical event lists with fixed clock; different seeds differ; runner reset reproduces the first N events |
| `test_bus.py` | prefix filter, fan-out, drop-oldest with `dropped` count, unsubscribe |
| `test_runner.py` | (tick_seconds=0.01) start → running and ticks grow; pause freezes tick; resume continues; reset → idle tick 0 and `sim.status` published for each transition; advance while running → `InvalidTransition`; select_scenario cancels the task; speed bounds |
| `test_api_simulation.py` | every route in §8.2 including 409/422 paths, via httpx `ASGITransport` |
| `test_websocket.py` | first frame is `sim.snapshot` with all envelope fields; after `advance`, frames carry `event_id, timestamp, sim_time, event_type, source, location, severity, payload`; `?types=` filter; heartbeat arrives with a short heartbeat setting; disconnect unsubscribes |

`scripts/demo_smoke.py`: replays `cascading_landslide_flood` seed 42 for 300 ticks headless, asserts
the stage sequence, the landslide failure, D-7 blocked ≥0.7, riverside water depth >0 and river level
>warning, and prints a compact per-stage summary. Exit code 1 on any failed assertion.

## 12. Quality gates

`uv run pytest`, `uv run pyright` (strict on `gridline/`), `uv run ruff check .` and `uv run ruff format --check .`
all clean; the app boots with `uv run uvicorn gridline.main:app` and a WebSocket client sees `sim.snapshot`
followed by `sim.tick` frames after `POST /api/simulation/start`.

## 13. Deviations (implementation, 2026-09-26)

Decided with the orchestrator during implementation; everything else follows §1–§12.

1. **One Nandipur (overrides A3 and §4).** `build_nandipur(data_dir)` converts the validated data layer
   (`load_city_data`, `backend/data/city/*.yaml`) into the frozen `City`; no second hand-typed dataset and no DB
   access. Ids are the data layer's (Z-HV, Z-RS, D-7, D-8, R-1, RD-01, RD-02, BR-1, BR-4, PR-HT2, SL-HV-1, RG-02,
   WS-01, SM-01, CL-D7, RV-01, C-4, AMB-06, H-2, S-5 …). Model changes: `Zone` gets `permeability_class`,
   `impervious_fraction` (2026 zone stats) and `area_km2` (bbox), loses `river_id` and the soil enum; new `Slope`
   and `Substation`; `DrainageChannel` gets initial `blocked_fraction`, outfall channel/river, flap-gate stage and
   fixed-pump capacity; `River` gets flows and stages (ordinary stage = surface level − gauge zero, warning stage
   from policy PT-15); `is_sole_access` → `is_only_access`; `Project` has `slope_id`, `permit_number` and the
   data's starting depth (PR-HT2 2.5 m); sensor kinds are the data's; hospital beds are summed from
   `hospital_beds`; `City.thresholds` holds the policy numbers from `policy_thresholds.yaml`. Only gauged rivers
   (R-1), active excavation projects (PR-HT2, PR-TQ, PR-MWM) and observable sensor kinds (not LL-01) are modelled.
   `create_app(settings, *, city=None)` accepts a prebuilt city so tests load the YAML once.
2. **Physics recalibrated (§5.2).** Infiltration by permeability class; runoff base = impervious share; a
   `CATCHMENT_ROUTING` factor on rational runoff; tributaries routed first (D-2→D-4→D-3, D-8→D-7); flap gates close
   at the data's river stage (D-8 4.0 m, D-11 2.5 m, leaving only fixed pumps); ponding spreads with depth
   (`POND_SPREAD_CM`); the river follows a linear rating through (85 m³/s, 1.6 m) and (1100 m³/s, 4.2 m), driven by
   a scenario upstream-flow factor plus channel outfalls. Slopes have their own saturation; the cut adds
   infiltration and creep uses the unsupported cut `min(depth, soil depth) − 1.5 m` (permit bench height). Final
   constants are named in `physics.py`. Halting PR-HT2 at t=60 leaves SL-HV-1 at 48 mm by t=300 (failure needs 80).
3. **Severity (§3.3)** uses the policy bands (watch → moderate, warning → high, critical → critical): rain 30/50
   mm/h; 24 h rain 65/115/175 mm at the gauges serving slopes over 25° (RG-01, RG-02); wind 62/89/118 km/h;
   saturation 0.70/0.85; channel ratio 0.8 → moderate, ≥ 1.0 → critical (policy has no warning band); river
   3.36/4.2/5.0/5.5 m; water 1/10/30 (road closure)/50 cm; forecast peak ≥ 30 moderate, ≥ 50 high.
4. **Payloads (§3.2).** `WeatherObservation` fields are optional (rain gauges report rain, WS-01 wind and
   temperature); `SoilObservation.depth_cm` → `slope_id`; `RiverObservation` adds `flood_stage_m`;
   `SlopeObservation.monitor_id` → `slope_id` and `WaterAccumulation.sensor_id` → `zone_id`, both from
   `simulation:engine` because the data layer has no inclinometers or flood-depth gauges (slopes with soil probes;
   zones with water); crew statuses add `dispatched`, `busy`, `off_duty` (data and tool vocabulary) and drop
   `resting`; ambulance `out_of_service` → `maintenance`, plus `hospital_id`, counts per hospital fleet; `SimTick`
   and `SimStatus` add `running`; payloads forbid unknown keys; new `InvalidPayload` (422) for beds or occupancy
   beyond capacity.
5. **Scenarios (§6.2)** keep their narratives with data ids and policy numbers: storm peak 15 mm/h over Hillview,
   24 h rain crossing 65/115/175 mm in stages 2/3/5, excavation 0.15 m/h from 2.5 m, rain easing after t=216
   (hillside) or t=228 (cascading); the Kalinadi rises to about 5.2 m in the cascade; landslide condition 80 mm
   on SL-HV-1 (fires at t=190); BR-1 closes at R-1 ≥ 5.0 m; RD-02 blocks at Z-RS ≥ 30 cm; H-2, AMB-06 and C-4
   replace ngh, A-1/A-2 and C-1/C-3. The flash flood is a 2.5 h cloudburst (55 mm/h over Hillview and Riverside)
   instead of 7 h at 45 mm/h. `Condition` names a `target_id` (zone, river or slope).
6. **Structure.** Physics application in `simulation/dynamics.py`, sensors in `simulation/sensors.py`, scripted
   timing in `simulation/schedule.py`, HTTP error mapping in `api/errors.py`. The world's zone model is
   `ZoneConditions` (the frontend's `ZoneState` is the detector's). Start and speed bodies are named
   `SimulationStart` / `SimulationSpeed` (frontend component names); `POST /start` and `/advance` bodies are
   optional; `select_scenario` keeps the current seed when none is given.
7. **Smoke script** also asserts the prevention counterfactual (halt at t=60 → no landslide) and re-runs itself
   inside `backend/` when started elsewhere, so `uv run python scripts/demo_smoke.py` works from the repo root.
