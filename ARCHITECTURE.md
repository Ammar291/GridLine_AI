# GridLine AI — Architecture

**AI-powered City Disaster Intelligence Brain** for the fictional city of **Nandipur**.
Hackathon prototype. Status: **v0.1 design, awaiting review — nothing implemented yet.**

All city data is synthetic. Nandipur, its districts, sensors, policies, history and people do not exist.

---

## 1. Purpose and success criteria

The system watches a simulated city and runs one loop, continuously:

```
detect → reason → predict → recommend prevention → request approval → execute → verify → re-plan
```

**Primary demo.** A hillside construction project (Hillview Terrace, Phase 2) keeps excavating while rainfall
rises. The brain combines rainfall, soil saturation, slope, excavation depth, historical landslide events,
recent infrastructure changes and city disaster policy to detect rising landslide risk, then identifies a
cascading flood risk: if the slope fails it blocks drainage channel D-7 and floods Riverside below.

**Secondary demo.** A flash-flood threat from severe rainfall plus reduced drainage capacity (a narrowed culvert
on D-7 after a 2025 road-widening project).

**Judging requirements the design must visibly satisfy**

| Requirement | Where it shows up |
|---|---|
| City / organization brain | Live city state model + continuous monitoring loop (§3, §5) |
| Agentic workflows with LangGraph | One graph per incident, with interrupt-based human approval and re-plan loop (§8) |
| Reasoning with citations | Every LLM output is structured and cites retrieved chunks or live readings; ungrounded citations are rejected (§7) |
| Time / effort savings | The brain does in seconds what a duty officer does in hours: cross-reads policy, history, permits and telemetry, drafts the action plan, executes it and proves it worked |
| RAG | pgvector-backed retrieval over synthetic policies, history, permits, change logs (§7) |
| Differentiators | WebSocket event stream, prediction, prevention, cascading-risk reasoning, approval gate, state-changing tools, verification, interactive dashboard |

**Definition of done for the prototype**

1. One command starts everything locally (Postgres in Docker, backend, frontend).
2. A judge can start the primary scenario and watch it run end to end in about five minutes, with the
   reasoning trace and citations visible as it happens.
3. It runs with no API credentials (mock provider) and runs better with an Anthropic key.
4. Approving an action changes city state, the system proves the change happened, and a forced failure
   makes it re-plan.

**Assumptions made beyond the brief** (override any of these):

- A1. Single operator, no authentication, no multi-tenancy.
- A2. The map is a schematic SVG of Nandipur, not GIS tiles. Coordinates are made up.
- A3. The hosted LLM is Anthropic Claude via the official `anthropic` SDK. The mock provider is a
  deterministic heuristic reasoner that builds its answer from the same retrieved context and state; it is
  not canned text.
- A4. Default model `claude-opus-5` at effort `medium` for demo latency, overridable by environment variable.
- A5. Embeddings run locally (fastembed, ONNX, CPU) so RAG works offline and needs no key.
- A6. Development happens on Windows; startup scripts ship for both PowerShell and bash.

---

## 2. Components

One FastAPI process and one PostgreSQL database. No microservices, no message broker.

```
┌──────────────────────────────── backend (single FastAPI process) ────────────────────────────────┐
│                                                                                                   │
│  Simulation engine ──tick──▶ Threat detector ──open/escalate incident──▶ Agent runner (LangGraph) │
│        │                          │                                            │                  │
│        │ state mutations          │ risk indices                 nodes call    │  interrupt()     │
│        ▼                          ▼                                            ▼                  │
│  City state (DB) ◀──── Tools (execute / verify) ◀──── Approvals ◀──── REST API ◀── frontend       │
│        │                                                                       ▲                  │
│        └──────────────▶ Event bus ──────────────▶ WebSocket /ws ───────────────┘                  │
│                            │                                                                      │
│                            └──▶ events table (append-only)     RAG: fastembed + pgvector          │
└───────────────────────────────────────────────────────────────────────────────────────────────────┘
```

| Component | Responsibility | Package |
|---|---|---|
| City model | Typed description of Nandipur: districts, zones, slopes, roads, drainage channels, construction projects, sensors, crews, shelters | `gridline/city` |
| Simulation engine | Advances a simulated clock, drives weather and construction from a scenario script, updates saturation and drainage, emits sensor readings, reacts to executed actions | `gridline/simulation` |
| Threat detector | Deterministic per-tick risk indices with banded thresholds and hysteresis; opens or escalates incidents; triggers agent runs | `gridline/threats` |
| Event bus + WebSocket | In-process asyncio pub/sub, persisted to DB, streamed to browsers | `gridline/events` |
| RAG | Corpus loading, chunking, embedding, pgvector search, citation IDs, grounding validator | `gridline/rag` |
| LLM provider | `LLMProvider` protocol; Anthropic implementation; mock heuristic implementation; prompt templates | `gridline/llm` |
| Agent | LangGraph state, nodes, edges, checkpointer, runner with one-active-run-per-incident rule | `gridline/agents` |
| Tools | Registry of state-changing actions, each with typed input, approval policy, `execute()` and `verify()` | `gridline/tools` |
| Approvals | Pending approval queue backed by graph interrupts; decision endpoint resumes the graph | `gridline/approvals` |
| REST API | Thin routers over the above | `gridline/api` |
| Frontend | React dashboard: map, risk timeline, event feed, incident reasoning, approvals inbox, actions log, scenario controls | `frontend/` |

---

## 3. Data flow

**Steady state (every tick, no LLM calls):**

1. Simulation advances the clock by one step and applies the scenario script (rainfall curve, excavation schedule).
2. Physics-lite models update soil saturation per zone and flow/capacity per drainage channel.
3. Sensors emit readings (`sensor.reading` events) with small deterministic noise.
4. Threat detector recomputes landslide and flood indices per zone and applies band thresholds.
5. Everything that changed is written to the DB and published on the event bus; the WebSocket fans it out.

**Incident flow (LLM calls happen here):**

1. A zone index crosses into `watch` or a higher band, or jumps by more than a configured delta.
2. Threat detector opens an `Incident` (or attaches to the open one for that zone) and asks the agent
   runner to start a graph run with `thread_id = incident_id`.
3. Graph: `observe → retrieve → assess → predict → cascade → recommend → approval_gate`.
4. `approval_gate` calls `interrupt()`; the checkpoint is persisted; an `approval.requested` event goes out.
5. Operator decides in the dashboard → `POST /api/approvals/{id}/decide` → graph resumes with the decision.
6. `execute` runs approved tools (mutating city state and simulation), `verify` waits for the expected
   effect, and the graph ends or routes to `replan`.
7. Each node start/finish is published as `agent.node.*` events carrying the structured output of that node,
   so the dashboard renders reasoning live.

**Re-plan loop:** `verify` failure, a further band escalation, or a materialized cascade (landslide occurs,
D-7 blocked) starts a new run on the same thread with `replan_reason` and the history of executed actions,
so the model cannot re-recommend what is already done.

---

## 4. Database

PostgreSQL 16 with the pgvector extension, via the `pgvector/pgvector:pg16` Docker image.
SQLAlchemy 2.x async with the psycopg 3 driver; the LangGraph Postgres checkpointer uses the same driver
and database. No Alembic: schema is created at startup, and `POST /api/simulation/reset` truncates
dynamic tables and re-seeds.

| Table | Purpose | Key columns |
|---|---|---|
| `zones` | Districts / hillside zones | id, name, slope_deg, soil_type, catchment_id, drains_to_channel_id, svg_path |
| `roads` | Road segments | id, name, zone_id, status (open / closed), is_evacuation_route |
| `drainage_channels` | Channels and culverts | id, name, design_capacity_m3s, current_capacity_m3s, blocked_fraction, downstream_zone_id |
| `projects` | Construction projects | id, name, zone_id, status (active / halted), excavation_depth_m, planned_depth_m, permit_doc_id |
| `sensors` | Rain gauges, soil moisture probes, channel level gauges | id, kind, zone_id, unit |
| `sensor_readings` | Time series | sensor_id, sim_time, value |
| `crews`, `shelters`, `pump_units` | Response assets | id, status, location_zone_id, capacity |
| `zone_state` | Live derived state per zone | zone_id, saturation, rain_24h_mm, landslide_index, flood_index, band |
| `incidents` | One per hazard episode | id, zone_id, hazard, band, status, opened_at, closed_at |
| `agent_runs` | One per graph invocation | id, incident_id, thread_id, trigger, status, started_at, finished_at |
| `agent_steps` | Node outputs for the trace | run_id, node, started_at, finished_at, output_json, citations_json |
| `approvals` | Pending / decided approval requests | id, run_id, incident_id, proposed_actions_json, status, decided_by, note |
| `actions` | Executed tool calls | id, run_id, tool, input_json, status, executed_at, verification_json |
| `alerts` | Public alerts issued | id, zone_id, level, message, issued_at |
| `documents`, `chunks` | RAG corpus | doc id, title, kind, source_path; chunk id, doc_id, section, text, embedding `vector(384)`, metadata jsonb |
| `events` | Append-only event log | id, ts, sim_time, type, incident_id, payload jsonb |
| `checkpoints*` | LangGraph checkpointer tables | created by `AsyncPostgresSaver.setup()` |

Indexes: `chunks.embedding` (HNSW, cosine), `events (ts)`, `sensor_readings (sensor_id, sim_time)`.

---

## 5. Simulation and threat detection

**Clock.** Simulated time advances in fixed steps (default 5 simulated minutes per tick, one tick per real
second, speed adjustable 0.25x to 10x, pausable). All timestamps in the system carry both wall time and
`sim_time`.

**Scenario scripts** are plain Python data: a rainfall intensity curve over sim time, a construction schedule
(depth per day), optional scripted events (culvert partially blocked at t; landslide occurs at t if the index
stays above threshold for N ticks), and failure injections for demoing re-planning (crew delayed because its
route is closed). Two scenarios ship: `hillside_landslide` (primary) and `flash_flood` (secondary). Scenarios
are deterministic given a seed.

**Physics-lite models** (small, unit-tested, documented in code):

- Soil saturation per zone: bucket model, `sat += k_in * rain - k_drain * sat`, clamped to [0, 1];
  excavation raises `k_in` for the affected zone.
- Drainage channel flow: `flow = catchment_runoff(rain, sat)`, capacity reduced by `blocked_fraction`;
  overflow when `flow > current_capacity`.
- Pumps add capacity to a channel; halting a project freezes excavation depth; a landslide event sets
  `blocked_fraction` on the downstream channel.

**Sensors** sample the model state with seeded noise, giving the brain real telemetry to cite.

**Threat detector** runs after each tick and computes two transparent indices per zone, each a weighted sum
of factors in [0, 1] with weights in a config file (not in prompts):

- `landslide_index` = f(antecedent rainfall, saturation, slope factor, excavation factor, history factor,
  recent infrastructure change factor).
- `flood_index` (downstream zones) = f(rain intensity, saturation, channel capacity ratio, blocked fraction).

Bands: `normal < watch < warning < critical`, with thresholds loaded from the seeded policy document so the
number the detector uses is the number the model can cite. Hysteresis prevents flapping. Band entry or a
sharp rise triggers the agent; a cooldown and a one-active-run-per-incident rule bound LLM spend.

The indices are **signals**, not decisions. The agent reads them together with the retrieved context and
produces the assessment, prediction and recommendation.

---

## 6. City data (synthetic seed)

Kept small enough to hold in one head and cite precisely.

- **Zones:** Hillview (hillside, slope 32°, construction site), Riverside (downstream of D-7, flood-prone),
  Old Town, Market Ward, Station Road, Lakeside.
- **Drainage:** D-7 "Kalinadi drain" (Hillview → Riverside; culvert narrowed in 2025), D-3 (Old Town),
  D-11 (Lakeside).
- **Roads:** Hill Road (only access to Hillview), Riverside Bypass (evacuation route), six others.
- **Project:** Hillview Terrace Phase 2 (permit HT-2026-014; planned excavation 6 m; on a 32° slope).
- **Sensors:** rain gauges RG-01..RG-04, soil probes SM-01..SM-03, channel gauges CL-D7, CL-D3.
- **Assets:** crews C-1..C-3, shelters S-1..S-2, pump depot with four units.
- **Corpus (Markdown with YAML front matter, about 25 documents):** Nandipur Disaster Management Policy
  (thresholds, halt rules for slopes above 25°), landslide event reports (2014, 2019, 2022), flood report
  (2021), infrastructure change log (2025 Hill Road widening; D-7 culvert narrowing), construction permit
  HT-2026-014 with conditions, zone geotechnical profiles, SOPs (road closure, evacuation, crew dispatch,
  pump deployment).

---

## 7. RAG

1. **Load.** `gridline/rag/index.py` reads `backend/data/corpus/*.md`, splits by heading into chunks of
   roughly 200–500 tokens, and stores chunks with metadata (`kind`, `zone_ids`, `hazards`, `date`, `section`).
2. **Embed.** fastembed `BAAI/bge-small-en-v1.5` (384-dim, ONNX, CPU, downloaded once). Stored in
   `chunks.embedding`.
3. **Retrieve.** `retrieve(query, filters, k=8)`: cosine similarity in pgvector with optional metadata
   filters (hazard, zone). The `retrieve` node issues two or three targeted queries per incident (policy
   thresholds; history for this zone and hazard; recent changes affecting the zone) and merges results.
   Stretch: add Postgres full-text search with reciprocal rank fusion if dense-only retrieval misses
   exact identifiers such as permit numbers.
4. **Citation IDs.** Every retrieved chunk is presented to the model as `[doc-slug#section]`
   (e.g. `[dmp-2024#s4.2]`). Live inputs get IDs too: `[sensor:RG-02@sim_time]`, `[state:zone.hillview]`,
   `[event:evt_123]`. The model may cite only IDs present in its input.
5. **Grounding validator.** Structured outputs carry `claims: list[{text, citation_ids}]`. The validator
   rejects unknown IDs and factual claims with no citation, retries once with the error fed back, and on a
   second failure marks the step `ungrounded` and lowers confidence. The dashboard shows the source chunk
   when a citation chip is clicked.

---

## 8. LangGraph agent

**State** (`TypedDict` with Pydantic models inside):

```
incident_id, trigger, replan_reason?, city_snapshot, retrieved: list[Chunk], prior_actions: list[Action],
assessment?, prediction?, cascade?, recommendation?, approval?, executed: list[ActionResult],
verification?: VerificationResult, citations: list[Citation], step_log: list[StepSummary]
```

**Nodes**

| Node | Kind | Input → Output |
|---|---|---|
| `observe` | code | Builds `city_snapshot` for the incident zone and its downstream neighbours: readings (last 24 sim-h), indices, project status, channel status, crews, open roads |
| `retrieve` | code | Runs targeted RAG queries; returns chunks with citation IDs |
| `assess` | LLM | `ThreatAssessment`: what is happening, contributing factors, confidence, claims with citations |
| `predict` | LLM | `RiskPrediction`: probability band and time horizon for the hazard, what would change it; cites indices and history |
| `cascade` | LLM | `CascadeAnalysis`: downstream effects (landslide → D-7 blocked → Riverside flood), affected assets; cites change log and channel data |
| `recommend` | LLM | `ActionPlan`: ordered list of tool calls chosen from the registry schema, each with rationale, expected effect and citations; excludes `prior_actions` |
| `approval_gate` | code | Splits the plan into auto-approved and approval-required actions; if any require approval, `interrupt(ApprovalRequest)` |
| `execute` | code | Runs approved actions through the tool registry; records `ActionResult`s |
| `verify` | code | Waits up to `max_ticks` per action for its declared post-condition; returns `VerificationResult` |
| `replan` | code | Sets `replan_reason` and routes back to `observe` (bounded to 3 re-plans per incident) |

**Edges:** linear through `recommend`; `approval_gate` → `execute` (after resume) or `END` if the plan is
empty or fully rejected; `verify` → `END` on success, → `replan` on failure; `replan` → `observe`.

**Human in the loop.** `approval_gate` uses `langgraph.types.interrupt`. The API resumes with
`Command(resume=ApprovalDecision)`. A partial approval executes only the approved actions. A full rejection
ends the run without executing anything; the operator note stays in thread state and is fed to `recommend`
on the next run for this incident. Nothing auto-executes on timeout; a pending approval stays pending.

**Checkpointing.** `AsyncPostgresSaver` on the app database; `thread_id = incident_id`. The approval pause
survives a backend restart, and the trace comes for free.

**Concurrency.** One active run per incident (guarded in the runner). Runs for different incidents may
overlap. LLM nodes have timeouts and one retry.

**Tracing.** The runner streams graph events and publishes `agent.node.started` / `agent.node.finished`
with the structured output and citations of each node, and writes `agent_steps` rows.

---

## 9. LLM provider layer

```python
class LLMProvider(Protocol):
    name: str
    async def complete_structured(self, *, system: str, user: str, schema: type[T], effort: str) -> T: ...
```

- **`AnthropicProvider`** — official `anthropic` SDK (`AsyncAnthropic`), structured outputs via a Pydantic
  schema, adaptive thinking (default on current models), `output_config.effort` from `LLM_EFFORT`,
  a frozen system prompt with `cache_control` so the tool registry and policy preamble are cached across
  nodes, server-side refusal fallback enabled. Model from `LLM_MODEL` (default `claude-opus-5`).
- **`MockProvider`** — deterministic heuristic reasoner for offline use. It parses the same inputs
  (indices, readings, retrieved chunks) and fills the same schemas by rule: thresholds are read from the
  retrieved policy chunk, history is summarized from retrieved event reports, recommendations are chosen
  by band from the SOP chunks, and every claim cites the chunk or reading it came from. If a needed chunk
  was not retrieved, it says so rather than inventing it. It is clearly labelled `provider=mock` in the UI.
- Provider is chosen at startup: `LLM_PROVIDER=anthropic|mock|auto`; `auto` picks Anthropic when a key is
  present, mock otherwise. `GET /api/llm/status` reports which one is live.

Prompts live in `gridline/llm/prompts/*.md` and are rendered with the same context for both providers.

---

## 10. Action execution

**Tool contract** (`gridline/tools/base.py`):

```python
class Tool(Protocol):
    name: str
    description: str
    Input: type[BaseModel]              # JSON schema is given to the LLM and the frontend
    requires_approval: bool
    max_verify_ticks: int
    async def execute(self, inp: Input, ctx: ToolContext) -> ActionResult: ...
    async def verify(self, inp: Input, ctx: ToolContext) -> VerificationResult: ...
```

| Tool | Effect on state | Approval |
|---|---|---|
| `issue_alert(zone_id, level, message)` | Inserts alert; broadcast | auto for `advisory`, required for `evacuate` |
| `halt_construction(project_id, reason)` | Project status `halted`; simulation stops excavation | required |
| `close_road(road_id, reason)` | Road status `closed`; simulation reroutes crews | required |
| `deploy_pumps(channel_id, units)` | Raises channel capacity; depot units become `deployed` | required |
| `dispatch_crew(crew_id, zone_id, task)` | Crew travels over open roads; arrives after N ticks | required |
| `open_shelter(shelter_id)` | Shelter status `open` | required |
| `schedule_inspection(asset_id, priority)` | Creates inspection task | auto |

Rules: tools are the only way the agent changes state; each action has an idempotency key
(`action_id`); executions publish `action.executed`; failures are recorded, never hidden; the registry
exports JSON schemas so `recommend` can only propose valid calls.

---

## 11. Verification

Verification is deterministic and reads state back from the database and simulation, never from the
output of the model.

- Each tool declares a post-condition: `halt_construction` → project status is `halted` **and** excavation
  depth unchanged over the next two ticks; `close_road` → road closed and no crew routes through it;
  `deploy_pumps` → channel capacity increased by the expected amount; `dispatch_crew` → crew location equals
  target within `max_verify_ticks`; `issue_alert` → alert row exists and was broadcast.
- The `verify` node polls per tick until all post-conditions hold or the tick budget is spent.
- Result: `verified`, `partially_verified` (list of failures), or `failed`. Anything but `verified`
  routes to `replan` with the concrete failure (e.g. "crew C-2 blocked: Hill Road closed"), which the next
  `recommend` must address.
- The dashboard shows expected effect vs observed effect per action.

---

## 12. Event bus, WebSocket and REST

**Event bus** (`gridline/events/bus.py`): asyncio pub/sub; `publish(event)` writes the `events` row
and puts the event on every bounded subscriber queue (drop-oldest for slow consumers). A single
`EventBus` instance lives on `app.state`.

**Envelope:** `{ id, ts, sim_time, type, incident_id?, payload }`.

**Types:** `sim.tick`, `sensor.reading`, `zone.state`, `threat.detected`, `threat.escalated`,
`incident.opened`, `incident.closed`, `agent.run.started`, `agent.node.started`, `agent.node.finished`,
`agent.run.finished`, `approval.requested`, `approval.decided`, `action.executed`, `action.verified`,
`replan.triggered`, `alert.issued`, `scenario.event`.

**WebSocket `/ws`:** on connect sends `state.snapshot` (full city state, open incidents, pending approvals),
then live events. Optional `?types=` filter. Heartbeat every 15 s.

**REST** (all JSON, under `/api`):

| Method / path | Purpose |
|---|---|
| `GET /health`, `GET /llm/status` | Liveness; active provider and model |
| `GET /city` | Static city model plus live state |
| `GET /events?since=&type=&limit=` | Event history |
| `GET /incidents`, `GET /incidents/{id}` | Incidents with runs, steps, citations, actions |
| `GET /approvals?status=`, `POST /approvals/{id}/decide` | Inbox; body `{decision: approve/reject/partial, approved_action_ids, note}` |
| `GET /actions`, `GET /actions/{id}` | Executed actions with verification |
| `GET /documents/{doc}`, `GET /chunks/{chunk_id}` | Citation sources |
| `POST /simulation/start {scenario, speed, seed}`, `/pause`, `/resume`, `/reset`, `/inject {event}` | Demo control |

---

## 13. Frontend

Vite + React 19 + TypeScript + Tailwind v4. TanStack Query for REST, a small Zustand store fed by the
WebSocket for live state. Charts with Recharts. No router: one dashboard.

Layout (desktop first, readable on a projector):

```
┌───────────────────────────────┬──────────────────────────────┐
│ Schematic map of Nandipur     │ Incident panel               │
│ zones coloured by band,       │ reasoning trace per node,    │
│ roads, channels, sensors,     │ citation chips → source      │
│ crews, construction site      │ drawer, confidence           │
├───────────────────────────────┼──────────────────────────────┤
│ Risk timeline                 │ Approvals inbox              │
│ rain, saturation, indices     │ proposed actions, approve /  │
│ with band thresholds          │ reject / partial, note       │
├───────────────────────────────┼──────────────────────────────┤
│ Live event feed               │ Actions log                  │
│                               │ expected vs observed effect  │
└───────────────────────────────┴──────────────────────────────┘
  Scenario bar: scenario, start / pause / reset, speed, inject, provider badge
```

Types for API payloads are generated from the backend OpenAPI schema (`openapi-typescript`) so the
frontend and backend share one contract.

---

## 14. Configuration and local startup

`backend/.env` (example committed as `.env.example`):

```
DATABASE_URL=postgresql+psycopg://gridline:gridline@localhost:5432/gridline
LLM_PROVIDER=auto            # anthropic | mock | auto
ANTHROPIC_API_KEY=           # optional
LLM_MODEL=claude-opus-5
LLM_EFFORT=medium
SIM_TICK_SECONDS=1.0
SIM_MINUTES_PER_TICK=5
AUTO_APPROVE=false           # demo shortcut; still records approvals
```

Startup: `scripts/dev.ps1` or `scripts/dev.sh` runs, in order, `docker compose up -d db`, `uv sync`,
seed if the database is empty, then backend (`uvicorn`) and frontend (`vite`) concurrently.
Backend on `:8000`, frontend on `:5173` proxying `/api` and `/ws`.

---

## 15. Testing strategy

| Layer | What is tested | How |
|---|---|---|
| Unit — simulation | Bucket model, channel overflow, scenario script application, determinism by seed | pytest, pure functions, no DB |
| Unit — threat detector | Index math, band transitions with hysteresis, trigger and cooldown | pytest |
| Unit — tools | `execute` mutates state as declared; `verify` passes on success and fails on injected failure | pytest + test DB (Postgres in Docker) |
| Unit — RAG | Chunking, citation ID stability, retrieval returns the policy chunk for a threshold query on the seed corpus, grounding validator rejects unknown IDs | pytest + test DB |
| Unit — mock provider | Fills every schema, cites only provided IDs, reflects changed inputs | pytest |
| Integration — graph | Full run with `MockProvider`: reaches the `approval_gate` interrupt, resumes on decision, executes, verifies, re-plans on injected crew failure, stops after the re-plan limit | pytest-asyncio + test DB |
| Integration — API | REST endpoints and WebSocket snapshot + event stream | httpx `ASGITransport`, Starlette WS test client |
| Contract — Anthropic | Structured output round-trip against the real API for one node | pytest, skipped without `ANTHROPIC_API_KEY` |
| Frontend | Citation chip opens the right source; approvals inbox posts the decision; store applies snapshot then events | Vitest + Testing Library |
| Demo smoke | `scripts/demo_smoke.py` runs the primary scenario headless with the mock provider at 10x and asserts the final state: project halted, D-7 pumps deployed, alert issued, all actions verified | run before every demo |

Invariants enforced by tests, not by convention: no LLM output enters state without schema validation and
grounding; no state changes outside the tool registry; every event type has a documented payload model.

---

## 16. Repository layout

```
GridLine_AI/
├── ARCHITECTURE.md            this file
├── CLAUDE.md                  project constitution and working rules
├── docker-compose.yml         postgres + pgvector
├── scripts/                   dev.ps1, dev.sh, demo_smoke.py
├── backend/
│   ├── pyproject.toml         uv-managed; fastapi, uvicorn, sqlalchemy, psycopg, pgvector, langgraph,
│   │                          langgraph-checkpoint-postgres, anthropic, fastembed, pydantic-settings
│   ├── data/corpus/           synthetic documents (Markdown + front matter)
│   ├── data/city/             synthetic city seed (YAML)
│   ├── gridline/
│   │   ├── main.py            app factory, lifespan (db, bus, simulation, agent runner)
│   │   ├── config.py
│   │   ├── db/                engine, models, seed, reset
│   │   ├── city/              typed city model
│   │   ├── simulation/        clock, physics, scenarios, sensors
│   │   ├── threats/           indices, bands, detector
│   │   ├── events/            bus, envelope models, websocket
│   │   ├── rag/               corpus loader, embedder, retriever, citations, validator
│   │   ├── llm/               provider protocol, anthropic, mock, prompts/
│   │   ├── agents/            state, nodes/, graph, runner
│   │   ├── tools/             base, registry, one module per tool
│   │   ├── approvals/
│   │   └── api/               routers
│   └── tests/
└── frontend/
    ├── package.json           vite, react, typescript, tailwindcss, @tanstack/react-query, zustand, recharts
    └── src/
        ├── api/               generated types, query hooks
        ├── ws/                socket client, store
        ├── components/        Map, RiskTimeline, EventFeed, IncidentPanel, ApprovalsInbox, ActionsLog, ScenarioBar
        └── App.tsx
```

---

## 17. Non-goals and constraints

- No microservices, Kafka, Kubernetes, Celery, Redis. One process, one database, one frontend.
- No real GIS, weather feeds, or real-city data. No personal data anywhere, including in fake reports.
- No auth, roles, or audit beyond the append-only event log.
- No hardcoded model answers. The deterministic parts are the simulation, the indices and the mock
  heuristic, all of which read live state and retrieved context.
- No autonomous execution of approval-required actions, even in demo mode (`AUTO_APPROVE` records a
  synthetic approval and is shown as such).

---

## 18. Implementation milestones (for the plan; not started)

1. Skeleton: compose file, backend app factory, DB models, seed, event bus, WebSocket, simulation loop,
   `sim.tick` visible in a bare frontend.
2. Threat detector and primary scenario producing band changes and incidents.
3. RAG: corpus, embedding, retrieval, citation IDs, validator.
4. LangGraph with `MockProvider` end to end, including interrupt, tools, verification, re-plan.
5. `AnthropicProvider` with structured outputs and caching; grounding on real outputs.
6. Dashboard panels; demo smoke script.
7. Secondary scenario; polish; README.
