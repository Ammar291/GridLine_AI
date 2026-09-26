# DEMO Controls and Minimal Risk Indices — Design

Date: 2026-09-26. Status: design approved in chat; this spec awaits review.
Branch: `feature/demo-controls`.

## 1. Purpose and scope

An operator giving the Nandipur pitch needs one-click disasters. DEMO mode gets a row of buttons:

`[Heavy Rain] [Landslide] [Drainage Block] [Flash Flood] [Industrial Fire] [Cascading Disaster] [Reset]`

Each button injects events into the **existing** pipeline (engine → bus → `/ws` → dashboard). The state changes
are deterministic, and every event appears in the Live events feed and as a marker on the Risk timeline.
"HIGH landslide risk" and "HIGH flood risk" are **computed** from city state by a minimal risk-index module.
They are never scripted, because scripted conclusions would break CLAUDE.md rule 3.

**In scope:** trigger presets and a route; two new injectable event types (`weather.rainfall`,
`emergency.fire`) plus the `scenario.trigger` announcement; per-zone landslide and flood indices emitted as
`zone.state`; `GET /api/detector/bands`; the button row; tests.

**Out of scope:** the following all stay pending:
- incidents, `threat.*` events, hysteresis, cooldowns, agent runs, and any LLM call
- risk indices in LIVE mode
- a map layer for fires
- Playwright browser automation

MVP only: no redesign of existing panels.

## 2. Decisions

| # | Decision | Why |
|---|---|---|
| D1 | "HIGH" means the **warning** band. `zone.state` severity maps watch → moderate, warning → high, critical → critical, as the sensor bands already do. | Reuses the repo's band-to-severity mapping. |
| D2 | Indices are computed in the engine from `WorldState` after each tick. They are not computed by a bus subscriber. | One pure module; replays stay identical because the engine numbers the events. The full bus-side detector remains a later milestone. |
| D3 | Weights and band thresholds are named constants in `threats/indices.py`. There is no config file. | YAGNI for the MVP. ARCHITECTURE §5's "weights in a config file" is deferred. |
| D4 | Every trigger advances the engine **12 ticks (1 simulated hour)** after injecting, whatever the runner state. | Physics and sensors show consequences at once, even when idle. It also makes each button testable deterministically. |
| D5 | Reset is the existing `POST /api/simulation/reset`: same scenario and seed, back to tick 0. | Rebuilding the world from the city also clears rain overrides and fires. |
| D6 | The existing Reset button moves into the new row, so there is only one Reset. The Inject dropdown stays. | Keeps the change minimal and avoids duplicate controls. |
| D7 | A Risk timeline marker whose sim time has no reading row snaps to the next row. | Otherwise a trigger pressed at tick 0 has no row to sit on and would not appear. |

## 3. Triggers

Triggers are defined in `gridline/simulation/triggers.py` as data, like `api/injections.py`. Each one is:
- a `TriggerName`
- a label and a description
- an ordered tuple of `InjectRequest`s with source `operator:demo`

The events are world facts (drivers), never conclusions.

| Trigger | Injected events, in order | Outcome asserted by tests (after the 12-tick advance) |
|---|---|---|
| `heavy_rain` | `weather.rainfall`: every zone, heavy intensity, 3 h | rain intensity, zone saturation and D-7 load ratio all above the no-trigger baseline |
| `landslide` | `infrastructure.construction`: PR-HT2 active, excavating, at its planned depth. Then `weather.rainfall` on Z-HV, heavy, 3 h | Z-HV `landslide_index` in band ≥ warning |
| `drainage_block` | `infrastructure.drainage_obstruction`: D-7, 0.7 blocked | D-7 capacity below baseline; Z-RS `flood_index` above baseline |
| `flash_flood` | `weather.rainfall` on Z-HV and Z-RS, very intense, 2 h | D-7 load ratio > 1 (overloaded); Z-RS `flood_index` in band ≥ warning |
| `industrial_fire` | `emergency.fire` at Z-MI | the event carries `exposed_zone_ids` containing Z-MI and `exposed_population` > 0; the fire is in `world.fires` |
| `cascading_disaster` | `infrastructure.failure`: SL-HV-1 landslide (the existing handler derives the D-7 obstruction, the Hill Road block and the project halt). Then `weather.rainfall` on Z-HV and Z-RS, heavy, 3 h | order in the emitted list: failure → D-7 obstruction → later a Z-RS `zone.state` with band ≥ warning |

Rain intensities are tuned while testing so each outcome holds with margin. The outcome tests run from a reset
of both the default scenario (`cascading_landslide_flood`) and `normal_city`.

**Route:** `POST /api/simulation/trigger` with body `{trigger: TriggerName}`, returning `list[Event]`.
It uses `DemoRunnerDep`, so LIVE mode rejects it like the other demo controls. `SimulationRunner.trigger(name)`:
1. publishes a `scenario.trigger` announcement;
2. runs each request through `engine.inject`;
3. calls `engine.advance(12)`, even while the runner is running (the engine is synchronous, so this is safe);
4. publishes everything and returns the events.

`CityMap` gains `triggers: list[TriggerInfo]` (id, label, description), served by `GET /api/city` next to
`injections`, so the dashboard renders the buttons from the backend.

## 4. New event types

All three are added to `EventType`, `PAYLOAD_MODELS`, the typed union in `api/event_models.py` and
`severity.RULES`.

- **`weather.rainfall`** (injectable): `RainfallDriver{zone_ids: list[str] (empty = every zone),
  intensity_mm_h, duration_h, description}`. The apply handler validates the zone ids and sets
  `world.rain_overrides[zone] = (intensity, until_tick)`. `apply_drivers` then uses
  `max(scenario rain, override)` while `tick <= until_tick`. Its severity uses the same rain bands as
  `weather.forecast`.
- **`emergency.fire`** (injectable): `IndustrialFire{zone_id, site, description, exposed_zone_ids,
  exposed_population}`. The last two are filled by the apply handler: the fire zone, plus every zone whose
  bbox lies within 500 m of the fire zone's bbox, with populations summed from the zone yearly stats (as-of
  year). It records `world.fires[zone_id] = FireState(...)`. Severity is critical when the exposed
  population is at least 20 000 and high otherwise. The runtime `Zone` gains `population` and `bbox`.
- **`scenario.trigger`** (not injectable): `ScenarioTrigger{trigger, label, description, tick}`, with
  severity info.

`WorldState` and `WorldSnapshot` gain `fires: dict[str, FireState]`. `WorldState` also gains
`rain_overrides`, which stays internal and is not part of the snapshot.

## 5. Risk indices: `gridline/threats/indices.py`

This is a pure function, `zone_risks(world, city) -> dict[zone_id, ZoneRisk]`. Every factor is clamped to
[0, 1].

- **`landslide_index`** is the maximum over the zone's slopes of a weighted sum of:
  - saturation above 0.5, scaled to the policy `saturation_critical`
  - zone 24 h rain as a share of `rain_24h_critical_mm`
  - unsupported cut depth ÷ 3 m
  - slope movement rate ÷ 30 mm/h
  - steepness, (angle − 20°) ÷ 20°

  A zone with no slopes has index 0.
- **`flood_index`** is a weighted sum of:
  - rain intensity ÷ `rain_1h_warning_mm_h`
  - zone saturation
  - the worst load ratio of the channels whose `downstream_zone_id` is this zone, as a share of
    `channel_ratio_critical`
  - the worst blocked fraction of those channels
  - standing water depth ÷ 50 cm
- **Bands:** normal < watch 0.35 ≤ warning 0.55 ≤ critical 0.75, the same for both hazards. The zone's
  band is the band of the higher index.

`GET /api/detector/bands` returns `Bands{landslide, flood}` built from these constants.

**Emission:** at the end of every tick, after the observations and before `sim.tick`, the engine emits one
`zone.state` per zone. The payload is `ZoneStatePayload`, the same shape as in `openapi.pending.yaml`:
- `zone_id`, `saturation`, `rain_24h_mm`, `rain_intensity_mm_h`
- `landslide_index`, `flood_index`, `band`, `prev_band`, `updated_sim_time`

`prev_band` is the band from the previous tick; it is null at tick 1 after a reset.

## 6. Frontend

- **Contract:** remove `zone.state`, `Band`, `Hazard`, `BandThresholds`, `Bands`, `ZoneState`,
  `ZoneStatePayload` and `/api/detector/bands` from `openapi.pending.yaml`. The `threat.*` and `incident.*`
  entries stay pending and keep referencing `Band` and `Hazard`. Run `npm run gen:api`. `http.ts` `bands()`
  becomes a real GET.
- **Client:** `simulation.trigger(body)` in `ApiClient`, `HttpApiClient` and `useSimulationControls`. The
  mock client rejects it (`notInMock`), as it does for inject; so does `fakeClient`.
- **ScenarioBar (DEMO only):** a second line labelled "Demo events" with one button per `city.triggers`
  entry, then Reset (moved from the first line). The buttons are disabled in mock mode, while any control
  is pending, and when no triggers are loaded. A failure reuses the bar's alert, labelled "Demo event".
  The dashboard's last grid row grows to fit the two lines.
- **Events:**
  - `describeEvent` gets a line for each of the 3 new types.
  - `eventGroup` puts `weather.rainfall` in the city group.
  - `applyEvent`: `scenario.trigger` becomes a Risk timeline marker (kind `scenario`); `emergency.fire`
    updates `world.fires` and adds a marker (kind `infrastructure`); `weather.rainfall` goes to the feed only.
  - The feed treats a `zone.state` whose band did not change as routine, so it is dropped first when the feed
    is full.
- **Risk timeline:** `milestoneMarkers` snaps a marker to the first row at or after its sim time (D7).

## 7. Testing

All tests are written first.

- **Backend unit tests:**
  - each index factor and the band edges
  - the `weather.rainfall` override, including expiry
  - the `emergency.fire` exposure computed from city data
  - `zone.state` emitted per zone per tick with the right `prev_band`
  - engine replay still identical
  - payload and event-model tests following the existing files
- **Backend trigger tests:** one outcome test per row of §3, from both base scenarios. Reset restores a
  snapshot equal to a fresh one.
- **Backend API tests:**
  - `POST /api/simulation/trigger` returns 200, returns 422 for an unknown trigger, and is rejected in LIVE mode
  - `GET /api/detector/bands` returns the bands
  - `GET /api/city` includes `triggers`
- **Frontend tests:**
  - ScenarioBar renders the 7 buttons in DEMO and none in LIVE
  - each button calls `simulation.trigger({trigger})`, and Reset calls `reset`
  - `describeEvent` and `applyEvent` handle the new events
  - the marker snapping works
- **End to end:** a script against the running backend opens `/ws`, POSTs each trigger (and Reset), and
  checks that every returned event id arrives on the socket in order. Then `scripts/demo_smoke.py` runs.
- **Done when** these commands pass: `uv run pytest`, `uv run pyright`, `uv run ruff check .`,
  `npm test`, `npm run typecheck`.
