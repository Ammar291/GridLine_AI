# GridLine AI — Frontend Dashboard Design

Date: 2026-09-26. Status: design for the React frontend described in ARCHITECTURE.md §13.
Written under autonomous operation: the pasted brief ("Build the interactive frontend…") and
ARCHITECTURE.md were treated as the approved design input. Everything in §2.3 is an assumption
the user can overturn.

The brief calls the product CivicRescue; that was the working name. The product is **GridLine AI**
and the city is **Nandipur** (CLAUDE.md). This document uses those names.

---

## 1. Purpose

A single-screen Emergency Operations Center dashboard for one operator and a projector audience.
It shows the live synthetic city, surfaces threats as the backend detects them, renders the agent's
reasoning and citations as they stream in, lets the operator approve or reject proposed actions,
and shows executed actions changing city state and being verified.

The frontend contains **no AI logic, no simulation and no RAG**. It renders what the backend sends
and posts operator decisions back. Where the backend has produced nothing yet, the UI says so.

Success looks like: a judge watching the primary scenario (Hillview landslide → D-7 blocked →
Riverside flood) can follow detect → reason → predict → recommend → approve → execute → verify
from the screen alone, and can click "Why?" on any recommendation and land on the evidence.

---

## 2. Brief as understood

### 2.1 Stated requirements (from the brief)

| # | Area | Must show / do |
|---|---|---|
| 1 | City overview | city status, active threats, risk zones, preventive actions, active incidents, available emergency resources |
| 2 | Interactive map | layers: zones, roads, rivers, drainage, hills, hospitals, shelters, emergency teams, construction sites, threat areas; pan, zoom, select entities, threat overlays |
| 3 | Live event stream | WebSocket events as they arrive, timestamped, one readable line each |
| 4 | Threat panel | type, severity, confidence, affected zone, estimated population, estimated onset, contributing factors |
| 5 | Reasoning panel | "Why this threat?", "What changed?", "What evidence supports it?", citations from backend |
| 6 | Prevention panel | recommended actions, each with rationale, evidence, expected effect, approval state |
| 7 | Human approval | approve, reject, inspect rationale |
| 8 | Action execution | live state transitions, e.g. `Rescue Team 03  AVAILABLE → DISPATCHED` |
| 9 | Verification | ✓ verified, ⚠ failed, ↻ replanning |
| 10 | Timeline | disaster progression over time |
| 11 | "Why?" interaction | every recommendation opens reasoning summary, retrieved evidence, citations, relevant city state |

### 2.2 Stated constraints

- React + TypeScript + Tailwind. Consumes backend REST + WebSocket only.
- No AI logic, no LangGraph, no RAG, no simulation engine in the frontend.
- Mock API interfaces matching ARCHITECTURE.md where endpoints are not yet available (today: all of them).
- No fake AI reasoning. Explicit loading and empty states.
- Reusable components. Tests for critical components.
- Look: professional EOC, dense but readable, visually impressive, map-centric, clear severity
  hierarchy, not a chatbot.

Plus CLAUDE.md: strict TS, no `any`, no default exports except `App`, generated API types,
TanStack Query for server state, WebSocket store for live state, small presentational components
with data access in hooks, domain naming (zone, channel, project, crew, incident, run, step,
approval, action, claim, citation), TDD, offline-capable, no overengineering.

### 2.3 Assumptions (override any of these)

- F1. **Mock mode is a development scaffold, not a demo.** The mock serves the synthetic city and
  replays a scripted *simulation and detector* event sequence (ticks, readings, zone state, threat
  detected, incident opened). It never emits agent, approval, action or verification events,
  because those would be fabricated AI output. In mock mode the reasoning, prevention, approval
  and verification panels show their empty states, and those panels are exercised by component
  tests with typed fixtures. A persistent banner says `Mock data. Backend not connected.`
- F2. **Interim OpenAPI contract.** No backend exists, so `frontend/openapi.yaml` is hand-written
  from ARCHITECTURE.md §12 (plus the additions in §9 here) and `openapi-typescript` generates
  `src/api/schema.d.ts`. When the backend exists, its `/openapi.json` replaces the YAML as the
  generator input. Domain types are always imported from the generated file, never hand-written.
- F3. **Schematic SVG map, coordinates invented** (ARCHITECTURE A2). Pan and zoom are viewBox
  transforms; no Leaflet or MapLibre. Geometry is served by the backend in `GET /api/city`; the
  mock fixture holds it today and is the source for the backend seed later.
- F4. **One dashboard, one selected incident.** The right column shows the selected incident
  (default: the open incident with the highest band). Selecting a zone or threat changes it.
- F5. **"Timeline" = risk timeline with milestones.** Recharts chart of rain intensity,
  saturation and both indices against sim time, with band threshold lines and markers for
  incident opened, approval decided, action executed, action verified, scenario events.
- F6. **"What changed?" is computed from data the backend already sends** (run trigger, re-plan
  reason, band transitions, reading deltas since the previous run). It is arithmetic over live
  state, not inference.
- F7. **Contract additions** needed by the brief and absent from ARCHITECTURE.md §4 are listed in
  §9 and must be adopted by the backend: zone population, road and channel geometry, static map
  features (river, hill contours), hospitals, and `state_changes` on executed actions.
- F8. Desktop first (≥1280 px), tuned for 1920×1080 projectors. No mobile layout.
- F9. Dark theme only. Severity colours are the primary visual hierarchy.

---

## 3. Approaches considered

**Mock strategy.** (a) MSW intercepting fetch and WebSocket; (b) an `ApiClient` interface with
`HttpApiClient` and `MockApiClient` chosen by `VITE_API_MODE`; (c) a small Node mock server.
Chosen: **(b)**. Zero dependencies, trivially injectable in tests (no network mocking library),
and the mock WebSocket is a plain class that emits the same envelopes the store already handles.
MSW's WebSocket story adds setup for no gain here.

**Type source.** (a) hand-written TS types with a TODO; (b) interim `openapi.yaml` → generated
types. Chosen: **(b)** (assumption F2). It keeps the CLAUDE.md rule intact and produces the
contract the backend must implement.

**Map.** (a) Leaflet/MapLibre with fake tiles; (b) hand-authored SVG with viewBox pan/zoom.
Chosen: **(b)** per ARCHITECTURE A2. Every entity is an SVG element with a click handler, layers
are `<g>` groups, and threat overlays are zone fills keyed to band tokens.

**Right-column organisation.** (a) tabs; (b) three fixed panels each scrolling internally.
Chosen: **(b)**, matching ARCHITECTURE §13. Tabs would hide the approval appearing while the
judge watches reasoning stream in.

---

## 4. Architecture

### 4.1 Stack

Vite 6, React 19, TypeScript 5 (`strict`), Tailwind v4 (`@tailwindcss/vite`), TanStack Query 5,
Zustand 5, Recharts 2, `openapi-typescript` (dev), Vitest + Testing Library + jsdom (dev),
ESLint with `typescript-eslint` strict. No router, no UI kit, no icon library (a handful of
inline SVG icons in `components/ui/icons.tsx`).

### 4.2 Directory layout

```
frontend/
├── openapi.yaml                     interim contract (F2)
├── package.json                     scripts: dev, dev:mock, build, test, typecheck, lint, gen:api
├── vite.config.ts                   proxy /api and /ws → :8000
├── vitest.config.ts / src/test/setup.ts
├── .env.development                 VITE_API_MODE=http (dev:mock overrides to mock)
└── src/
    ├── main.tsx, App.tsx            App is the only default export
    ├── styles/tokens.css            colour, spacing, type tokens (Tailwind @theme)
    ├── api/
    │   ├── schema.d.ts              GENERATED, do not edit
    │   ├── types.ts                 named re-exports of schema components
    │   ├── client.ts                ApiClient interface + createApiClient(mode)
    │   ├── http.ts                  HttpApiClient (fetch)
    │   ├── ApiClientProvider.tsx    React context + useApiClient()
    │   └── queries.ts               TanStack hooks: useCity, useIncident, useApprovals,
    │                                useActions, useChunk, useLlmStatus, useDecideApproval,
    │                                useSimulationControls
    ├── mock/
    │   ├── MockApiClient.ts         in-memory client + mock socket
    │   ├── replay.ts                scripted primary-scenario sim/detector event sequence
    │   └── fixtures/nandipur.city.json
    ├── live/
    │   ├── socket.ts                LiveSocket: connect, backoff, heartbeat, onEvent
    │   ├── applyEvent.ts            pure reducer (LiveState, Event) → LiveState
    │   ├── liveStore.ts             Zustand store: snapshot, events ring, telemetry ring
    │   ├── describeEvent.ts         event → one human-readable line (deterministic)
    │   ├── derive.ts                selectors: cityStatus, riskZones, resources, whatChanged…
    │   └── useLive.ts               hook that wires socket → store once
    ├── ui/uiStore.ts                selectedZoneId, selectedIncidentId, layers, whyTarget,
    │                                sourceChunkId
    ├── components/
    │   ├── ui/                      Panel, Badge, SeverityChip, StatusDot, Button, Drawer,
    │   │                            EmptyState, LoadingState, KeyValue, icons
    │   ├── overview/                OverviewStrip (area 1)
    │   ├── map/                     CityMap, layers/*, MapControls, LayerLegend,
    │   │                            EntityPopover (area 2)
    │   ├── events/                  EventFeed, EventRow (area 3)
    │   ├── incident/                IncidentPanel, ThreatCard (4), ReasoningTrace (5),
    │   │                            ClaimList, CitationChip, SourceDrawer
    │   ├── approvals/               ApprovalsInbox, ProposedActionCard (6), DecisionBar (7)
    │   ├── actions/                 ActionsLog, ActionRow, StateTransition (8),
    │   │                            VerificationBadge (9)
    │   ├── timeline/                RiskTimeline (10)
    │   ├── why/                     WhyDrawer (11)
    │   └── scenario/                ScenarioBar, ProviderBadge, ModeBanner
    └── test/                        fixtures/*.ts, render helpers, FakeSocket
```

Files stay under ~300 lines; the map splits per layer.

### 4.3 Data layer

```ts
interface ApiClient {
  health(): Promise<Health>;
  llmStatus(): Promise<LlmStatus>;
  city(): Promise<City>;
  events(q: { since?: string; type?: string; limit?: number }): Promise<Event[]>;
  incidents(): Promise<IncidentSummary[]>;
  incident(id: string): Promise<Incident>;
  approvals(status?: ApprovalStatus): Promise<Approval[]>;
  decide(id: string, body: ApprovalDecision): Promise<Approval>;
  actions(): Promise<Action[]>;
  action(id: string): Promise<Action>;
  document(docId: string): Promise<Document>;
  chunk(chunkId: string): Promise<Chunk>;
  simulation: {
    start(b: { scenario: string; speed: number; seed?: number }): Promise<SimStatus>;
    pause(): Promise<SimStatus>; resume(): Promise<SimStatus>; reset(): Promise<SimStatus>;
    setSpeed(speed: number): Promise<SimStatus>;
    inject(event: InjectEvent): Promise<SimStatus>;
  };
  openSocket(handlers: SocketHandlers): SocketHandle;   // /ws or mock replay
}
```

- `createApiClient(mode: 'http' | 'mock')` reads `import.meta.env.VITE_API_MODE` (default `http`).
- `HttpApiClient` uses `fetch` against `/api`, throws `ApiError {status, body}` on non-2xx.
- TanStack Query hooks in `api/queries.ts`; keys are `['city']`, `['incident', id]`, etc.
  `useDecideApproval` is a mutation that invalidates `['approvals']` and `['incident', id]`;
  the `approval.decided` event is the source of truth for the final state.
- Live state (everything that changes every tick) lives in the Zustand store, not in Query.
  Query holds static or on-demand data: city model, chunk/document sources, LLM status, deep
  incident fetch on selection.

### 4.4 Live layer

- `LiveSocket` opens `/ws`, expects `state.snapshot` first, then events. Reconnects with
  exponential backoff (1 s → 30 s), surfaces `connection: 'connecting' | 'open' | 'reconnecting'
  | 'closed'`. Heartbeats are answered, never rendered.
- `applyEvent(state, event)` is a pure function with one case per event type (§5.3). Unknown
  types are appended to the feed and otherwise ignored.
- Store shape:

```ts
interface LiveState {
  connection: ConnectionStatus; mode: 'http' | 'mock';
  sim: { simTime: string | null; tick: number; running: boolean; speed: number; scenario: string | null };
  llm: { provider: string; model: string | null } | null;
  zoneState: Record<ZoneId, ZoneState>;
  incidents: Record<IncidentId, Incident>;          // deep: runs → steps, approvals, actions
  approvals: Record<ApprovalId, Approval>;
  actions: Record<ActionId, Action>;
  alerts: Alert[];
  assets: { crews: Record<Id, Crew>; shelters: Record<Id, Shelter>; roads: Record<Id, Road>;
            channels: Record<Id, Channel>; projects: Record<Id, Project>; pumpUnits: PumpUnit[] };
  feed: Event[];                                    // newest last, capped 500
  telemetry: Record<ZoneId, TelemetryPoint[]>;      // per zone, capped 720 points (60 sim-h)
  milestones: Milestone[];                          // for timeline markers
}
```

- `derive.ts` selectors (pure, memoised with `useMemo` at call sites):
  `cityStatus` (max band), `activeThreats` (open incidents by hazard), `riskZones` (band ≥ watch),
  `preventiveActions` (pending / executed / verified counts), `resources` (crews available,
  shelters open + capacity, pump units at depot), `selectedIncidentDefault`,
  `whatChanged(incident, run)` (trigger, replan reason, band transitions, reading deltas).

### 4.5 UI state

`uiStore` (Zustand, not persisted): `selectedZoneId`, `selectedIncidentId`, `activeLayers:
Set<LayerId>`, `whyTarget: { kind: 'action' | 'step'; id } | null`, `sourceChunkId | null`,
`mapView: { x, y, k }`. Selecting a zone selects its open incident if any.

---

## 5. Contract (frontend view)

Full definitions live in `frontend/openapi.yaml`. Names follow ARCHITECTURE.md.

### 5.1 City

`City { zones, roads, channels, projects, sensors, crews, shelters, pump_depot, hospitals,
map_features, view_box, bands, scenarios }` where every spatial entity carries geometry:

| Entity | Key fields |
|---|---|
| `Zone` | id, name, slope_deg, soil_type, population, drains_to_channel_id, svg_path, label_xy, state: ZoneState |
| `ZoneState` | saturation, rain_24h_mm, rain_intensity_mm_h, landslide_index, flood_index, band, updated_sim_time |
| `Road` | id, name, zone_ids, status open/closed, is_evacuation_route, is_bridge, svg_path |
| `Channel` | id, name, design_capacity_m3s, current_capacity_m3s, blocked_fraction, downstream_zone_id, svg_path |
| `Project` | id, name, zone_id, status active/halted, excavation_depth_m, planned_depth_m, permit_doc_id, xy |
| `Sensor` | id, kind rain/soil/channel, zone_id, unit, xy, last_value?, last_sim_time? |
| `Crew` | id, name, status available/dispatched/en_route/on_site/blocked, location_zone_id, target_zone_id?, task?, xy |
| `Shelter` | id, name, status open/closed, capacity, occupancy, zone_id, xy |
| `PumpDepot` | zone_id, xy, units: PumpUnit[] {id, status at_depot/deployed, channel_id?} |
| `Hospital` | id, name, zone_id, beds, xy |
| `MapFeature` | id, kind river/hill_contour/lake/label, svg_path, label? |
| `Bands` | per hazard: watch, warning, critical index thresholds |
| `Scenario` | id, name, injections: {id, label}[] |

### 5.2 Incident and reasoning

| Type | Key fields |
|---|---|
| `Incident` | id, zone_id, hazard landslide/flood, band, status open/closed, opened_at, opened_sim_time, closed_at?, runs: AgentRun[], approvals: Approval[], actions: Action[] |
| `AgentRun` | id, incident_id, thread_id, trigger, replan_reason?, status running/waiting_approval/finished/failed, started_at, finished_at?, steps: AgentStep[] |
| `AgentStep` | id, run_id, node, status running/finished/ungrounded/failed, started_at, finished_at?, duration_ms?, output: StepOutput \| null, citations: Citation[] |
| `StepOutput` | discriminated by `node`: `CitySnapshot` (observe), `RetrievedChunks` (retrieve), `ThreatAssessment` (assess), `RiskPrediction` (predict), `CascadeAnalysis` (cascade), `ActionPlan` (recommend), `ApprovalGateResult`, `ExecuteResult`, `VerificationResult`, `ReplanResult` |
| `ThreatAssessment` | hazard, summary, contributing_factors: {factor, value, citation_ids}[], confidence 0–1, claims |
| `RiskPrediction` | probability_band low/moderate/high/very_high, time_horizon (text), onset_sim_time?, what_would_change_it: string[], claims |
| `CascadeAnalysis` | chain: {cause, effect, affected_asset_ids, citation_ids}[], affected_zone_ids, claims |
| `ActionPlan` | actions: ProposedAction[] |
| `ProposedAction` | action_id, tool, input (object), rationale, expected_effect, citation_ids, requires_approval |
| `Claim` | text, citation_ids |
| `Citation` | id (`dmp-2024#s4.2`, `sensor:RG-02@…`, `state:zone.hillview`, `event:evt_…`), kind chunk/sensor/state/event, label |
| `Chunk` | id, doc_id, doc_title, section, kind, text, metadata |
| `Approval` | id, run_id, incident_id, proposed_actions: ProposedAction[], status pending/approved/rejected/partial, requested_at, decided_at?, decided_by?, note?, approved_action_ids, synthetic (AUTO_APPROVE) |
| `ApprovalDecision` (request) | decision approve/reject/partial, approved_action_ids, note? |
| `Action` | id, run_id, incident_id, tool, input, status pending/executing/executed/failed, executed_at?, state_changes: StateChange[], verification?: ActionVerification |
| `StateChange` | entity_type crew/shelter/road/project/channel/pump_unit/alert, entity_id, entity_name, field, from, to |
| `ActionVerification` | status verified/partially_verified/failed/pending, expected, observed, failures: string[], checked_sim_time |
| `Alert` | id, zone_id, level advisory/warning/evacuate, message, issued_at |

### 5.3 Events (`Event { id, ts, sim_time, type, incident_id?, payload }`)

| type | payload | store effect |
|---|---|---|
| `state.snapshot` | `{ city, sim, llm, incidents, approvals, actions, alerts }` | replace everything |
| `sim.tick` | `{ sim_time, tick, running, speed }` | sim |
| `sensor.reading` | `{ sensor_id, kind, zone_id, value, unit }` | sensor last_value only (telemetry comes from `zone.state`) |
| `zone.state` | `ZoneState & { zone_id, prev_band? }` | zoneState; telemetry point; milestone on band change |
| `threat.detected` / `threat.escalated` | `{ incident_id, zone_id, hazard, band, prev_band?, index }` | milestone |
| `incident.opened` / `incident.closed` | `Incident` | incidents; milestone |
| `agent.run.started` / `agent.run.finished` | `AgentRun` (steps may be empty on start) | incidents[..].runs |
| `agent.node.started` | `{ run_id, incident_id, node, step_id }` | add step with status running |
| `agent.node.finished` | `AgentStep` | replace step |
| `approval.requested` | `Approval` | approvals; incidents[..].approvals; milestone |
| `approval.decided` | `Approval` | same; milestone |
| `action.executed` | `Action` | actions; apply `state_changes` to assets; milestone |
| `action.verified` | `{ action_id, verification }` | actions[..].verification; milestone |
| `replan.triggered` | `{ incident_id, run_id, reason }` | mark run; milestone |
| `alert.issued` | `Alert` | alerts; milestone |
| `scenario.event` | `{ name, description }` | milestone |

Every event also lands in `feed`. `describeEvent` renders one line per type, for example
`sensor.reading` → `Rainfall RG-02 (Hillview) 84 mm/h`, `zone.state` with band change →
`Hillview: landslide index 0.71 · WATCH → WARNING`.

---

## 6. Layout and panels

```
┌ OverviewStrip: city status · threats · risk zones · preventive actions · incidents · resources ┐
├───────────────────────────────────────┬───────────────────────────────────────────────────────┤
│ CityMap (≈58% width, ≈55% height)     │ IncidentPanel: ThreatCard + ReasoningTrace            │
│  LayerLegend · MapControls · Popover  │                                                       │
├───────────────────────────────────────┼───────────────────────────────────────────────────────┤
│ RiskTimeline                          │ ApprovalsInbox: ProposedActionCard × n + DecisionBar  │
├───────────────────────────────────────┼───────────────────────────────────────────────────────┤
│ EventFeed                             │ ActionsLog: ActionRow (StateTransition, Verification) │
├───────────────────────────────────────┴───────────────────────────────────────────────────────┤
│ ScenarioBar: scenario · start/pause/reset · speed · inject · ProviderBadge · connection · mode │
└───────────────────────────────────────────────────────────────────────────────────────────────┘
   WhyDrawer and SourceDrawer slide over the right column.
```

CSS grid, fixed rows, each panel scrolls internally, no page scroll. The `ModeBanner` sits under
the OverviewStrip when `mode === 'mock'` or the socket is not `open`.

Every panel has four states: **loading** (skeleton rows), **empty** (one sentence naming what
would fill it, e.g. "No agent run yet for this incident. Reasoning appears here as each node
finishes."), **populated**, **error** (message + retry). Nothing shows placeholder reasoning.

### 6.1 OverviewStrip (area 1)
Six stat tiles from `derive.ts`. City status tile is the largest and coloured by max band.
Threat tile lists hazards with count. Clicking a tile selects the relevant incident/zone.

### 6.2 CityMap (area 2)
- `viewBox` from `city.view_box`; wheel zoom around cursor, drag pan, buttons zoom ±/fit.
- Layers as `<g data-layer>`: hills (contours), river/lake, zones (fill by band token, 35%
  alpha, stroke on select), drainage (dashed, thickness ∝ capacity, red when blocked_fraction >
  0.3), roads (closed → dashed red with ✕ at midpoint; evacuation routes thicker), construction
  (hatched marker; halted → grey), hospitals (+), shelters (house glyph, filled when open),
  crews (chevron with id, colour by status; en_route animates along its road), sensors (small
  dots with last value on hover), threat overlay (critical zones pulse; evacuate alert → hatched
  exclusion ring; cascade chain drawn as an arrow from source zone to affected zone).
- `LayerLegend` toggles each layer; `EntityPopover` shows the selected entity's fields.
- Selecting a zone sets `selectedZoneId` and its incident.

### 6.3 EventFeed (area 3)
Newest at bottom, auto-scroll unless the user scrolled up ("↓ new events" pill). Each row: wall
time, sim time, severity tint by type, `describeEvent` text, incident tag. Filter chips by type
group (simulation / threat / agent / approval / action / alert).

### 6.4 ThreatCard (area 4)
Header: hazard glyph, zone name, band chip. Grid: confidence (from latest `assess`, else "awaiting
assessment"), affected population (zone.population + cascade zones), estimated onset (`predict`
time_horizon / onset_sim_time, else "awaiting prediction"), contributing factors (chips with value
and citation chip). Selecting another incident swaps the card.

### 6.5 ReasoningTrace (area 5)
Node rail `observe → retrieve → assess → predict → cascade → recommend → approval_gate → execute →
verify [→ replan]` with status dots (running spinner, finished, ungrounded ⚠, failed). Below,
three sections:
- **Why this threat?** `assess.summary` and contributing factors, each claim with CitationChips.
- **What changed?** `whatChanged()` bullets: trigger, band transition, reading deltas, re-plan
  reason. Plus `cascade.chain` as "A → B → C".
- **What evidence supports it?** `retrieve` chunks (title, section, kind, score) and all
  citations in the run. Clicking a chip opens `SourceDrawer` with the chunk (`useChunk`) or the
  reading/state that was cited.
Each run in the incident is an accordion; the latest is open. Each step has a "Why?" button →
`WhyDrawer`.

### 6.6 ApprovalsInbox + ProposedActionCard (areas 6, 7)
Pending approvals first, then decided (collapsed). Each `ProposedActionCard`: tool name mapped to
a verb ("Halt construction", "Close road", "Deploy pumps", "Dispatch crew", "Open shelter", "Issue
alert", "Schedule inspection"), target entity name, rationale, expected effect, evidence chips,
approval state chip (proposed / auto-approved / approved / rejected / executing / executed /
verified / failed), checkbox for partial approval, "Why?" button. `DecisionBar`: Approve all,
Approve selected, Reject, note field. Posts `ApprovalDecision`; disables while pending;
error shown inline. Synthetic (AUTO_APPROVE) decisions are labelled.

### 6.7 ActionsLog (areas 8, 9)
One `ActionRow` per action, newest first: verb + target, executed sim time, `StateTransition`
rows (`Rescue Team 03  AVAILABLE → DISPATCHED` with monospace before/after and an arrow glyph),
`VerificationBadge` (✓ verified / ⚠ failed with failures / ↻ replanning when `replan.triggered`
references the run / ◌ pending with tick countdown). Expected vs observed shown side by side.

### 6.8 RiskTimeline (area 10)
Two Recharts charts stacked and sharing the x axis (sim time), never a dual axis:
- **Rain intensity** (top, ~30% height): single bar series in mm/h, no legend (the title names it).
- **Indices** (bottom): landslide index and flood index as the emphasised 2 px lines, saturation
  as a grey context line with a 10% area wash; all on one 0–1 axis. Legend always shown.
  Hairline `ReferenceLine`s for watch/warning/critical thresholds (from `city.bands`) drawn in
  muted ink with a small band-coloured text label at the right end, so threshold lines never
  impersonate a series. `ReferenceDot` markers for milestones with tooltips.
A crosshair tooltip lists every series at the hovered sim time. Zone switcher above the charts.
Chart colours are the validated `--viz-*` tokens (see plan); band colours are never used for
series.

### 6.9 WhyDrawer (area 11)
Opened for an action or a step. Sections: **Reasoning summary** (the node output's summary or the
action's rationale + expected effect), **Retrieved evidence** (chunks from the run's `retrieve`
step), **Citations** (chips; click → SourceDrawer), **Relevant city state** (the run's `observe`
snapshot for the zone: readings, indices, project, channel, crews, roads). Empty sections say
which node has not finished.

### 6.10 ScenarioBar
Scenario select (`hillside_landslide`, `flash_flood`), start / pause / resume / reset, speed
(0.25×–10×), inject menu (from `city.scenarios[].injections`), `ProviderBadge`
("Anthropic claude-opus-5", "Mock reasoner" or "No backend"), connection dot, sim clock.

---

## 7. Visual direction

Applied with the frontend-design skill during implementation; recorded here so all components
agree.

- Dark, low-glare surface (near-black blue-grey), thin 1 px panel borders, no drop shadows.
- Severity tokens: `--band-normal` (muted teal), `--band-watch` (amber), `--band-warning`
  (orange), `--band-critical` (red), each with a text-safe and a fill-safe variant. These are
  the only saturated colours besides a single accent for interactive elements.
- Type: one variable grotesque (Archivo, self-hosted via fontsource so it works offline) in two
  widths: normal for text, condensed for panel titles and stat values. No monospace face;
  readings, sim times and IDs use `font-variant-numeric: tabular-nums`. Sentence case
  everywhere, including band and status chips. Small sizes (12–13 px body) with generous line
  height.
- Motion: only for meaning — critical zones pulse, new feed rows fade in, crews en route move.
  No decorative animation.
- Every glyph has a text label or `aria-label`. Colour is never the only carrier of state.

---

## 8. Mock mode (assumption F1)

- `MockApiClient` holds `nandipur.city.json` in memory. `city()` returns it with live state.
- `openSocket` emits `state.snapshot`, then replays `replay.ts`: a deterministic list of
  `sim.tick`, `sensor.reading`, `zone.state`, `threat.detected`, `threat.escalated`,
  `incident.opened`, `scenario.event` for the primary scenario over about 6 sim-hours at one tick
  per second (speed adjustable via `simulation.*`). Zone states are produced by the script, not
  computed. This is scripted simulation, which CLAUDE.md permits.
- `incidents()` / `incident(id)` return the opened incident with `runs: []`.
- `approvals()`, `actions()` return `[]`. `decide()` rejects with `ApiError 501 "not available
  in mock mode"`. `chunk()` and `document()` reject the same way.
- `llmStatus()` returns `{ provider: 'none', model: null }` and the badge says `no backend`.
- Result: overview, map, feed and timeline are fully alive; threat card shows detector fields
  and "awaiting assessment / prediction"; reasoning, approvals, actions panels show empty states.

---

## 9. Backend contract obligations

Additions to ARCHITECTURE.md §4/§12 required by this design (to be folded into the backend plan):

1. `zones.population`, `zones.label_xy`; `roads.svg_path`, `roads.is_bridge`;
   `drainage_channels.svg_path`; new static `hospitals` and `map_features` tables or seed entries;
   `xy` on projects, sensors, crews, shelters, pump depot.
2. `GET /api/city` returns `view_box`, `bands` (threshold edges per hazard), and `scenarios`
   (names + available injections).
3. `action.executed` payload includes `state_changes: StateChange[]` computed by each tool from
   the before/after entity state.
4. `agent.node.finished` payload is a full `AgentStep` including `citations` and `status`
   (`ungrounded` when the grounding validator downgraded the step).
5. `state.snapshot` shape as in §5.3; incidents are deep (runs → steps).
6. `Approval.synthetic` flag when `AUTO_APPROVE` recorded the decision.
7. `POST /api/simulation/speed {speed}` in addition to the §12 controls.

The backend's `/openapi.json` must validate against the same component names so `gen:api` can
switch inputs without frontend changes.

---

## 10. Testing

Vitest + Testing Library + jsdom. Tests inject a fake `ApiClient` and a `FakeSocket`; no network
mocking library. Fixtures in `src/test/fixtures/` are typed against the generated schema and use
obviously synthetic text (e.g. `"fixture: assessment summary"`), never plausible reasoning.

Critical tests (each ships with its component, TDD):

| Unit | Test |
|---|---|
| `applyEvent` | snapshot replaces state; `zone.state` updates band and telemetry; `agent.node.started/finished` add and replace a step; `approval.requested/decided` update both maps; `action.executed` applies `state_changes` to the crew/shelter/road; feed capped at 500; unknown type is appended and ignored |
| `LiveSocket` | delivers snapshot then events; reconnects with backoff after close; ignores heartbeats |
| `describeEvent` | one readable line for every event type in the contract |
| `derive` | cityStatus = max band; resources counts; whatChanged lists band transition and reading delta |
| `MockApiClient` | conforms to `ApiClient`; replay emits `state.snapshot` first; `decide` rejects 501 |
| `HttpApiClient` | builds URLs and bodies for each method; throws `ApiError` on 500 |
| `CityMap` | renders one element per zone/road/channel; click selects zone; layer toggle hides group; zone fill class follows band; wheel changes viewBox |
| `EventFeed` | renders rows in order; filter chips; auto-scroll pause pill |
| `ThreatCard` | shows detector fields with "awaiting assessment" when no assess step; shows confidence and factors when present |
| `ReasoningTrace` | node rail statuses; three sections; empty state without runs; citation chip click opens SourceDrawer with the chunk id |
| `ApprovalsInbox` | lists proposed actions; partial selection; approve posts `{decision:'partial', approved_action_ids}`; reject posts reject with note; disabled while pending; error shown; empty state |
| `ActionsLog` | StateTransition renders `from → to`; VerificationBadge for each status; replanning badge when a replan event references the run |
| `RiskTimeline` | renders series and threshold lines for the selected zone; milestone markers; empty state |
| `WhyDrawer` | opens for an action with rationale, evidence, citations, city state; empty sections name the missing node |
| `OverviewStrip` | tiles reflect derived values; click selects incident |
| `App` | renders all panels in mock mode with the mode banner and no page scroll |

`npm test`, `npm run typecheck`, `npm run lint` must all pass; `npm run build` must succeed.

---

## 11. Out of scope

Authentication, mobile layout, light theme, GIS, offline caching of chunks, multi-operator
presence, editing city data, any backend code. The backend plan consumes §9.
