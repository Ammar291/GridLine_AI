# GridLine AI — Architecture

**AI-powered City Disaster Intelligence Brain** for the fictional city of **Nandipur**.
Hackathon prototype. Status (2026-09-26): **partly built.**

- **Implemented:** the city data layer (§4, §6), the RAG layer (§7), the simulation engine and live event
  stream (§5, §12), the city operations tools (§10, §11), and the dashboard connected to the backend (§13).
- **Not yet built:** the threat detector, the LangGraph agent, the approvals subsystem, the LLM providers and
  event persistence (no `events` table). The sections on these are the design for later milestones and are
  marked **Pending**. §18 tracks the milestones.

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
- A5. Embeddings run locally (fastembed, ONNX, CPU) so RAG works offline and needs no key; with no model
  download available, a deterministic hashed embedder takes over (`EMBEDDING_PROVIDER=auto`).
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

**Built so far:** `city`, `simulation`, `events` (in-memory bus and WebSocket, no DB writer), `rag`, `tools`,
`api` and the frontend. **Pending:** `threats`, `llm`, `agents`, `approvals` and the `events` table. The
simulation runs in memory and needs no database. The tools write only to the database. The two are not
coupled yet.

---

## 3. Data flow

**Steady state (every tick, no LLM calls):**

1. Simulation advances the clock by one step and applies the scenario script (rainfall curve, excavation schedule).
2. Physics-lite models update soil saturation per zone and flow/capacity per drainage channel.
3. Sensors emit typed observation events (`weather.observation`, `environment.soil`, `environment.drainage`,
   `environment.river`, ...) with small deterministic noise.
4. Threat detector recomputes landslide and flood indices per zone and applies band thresholds. **Pending.**
5. Everything that changed is written to the DB and published on the event bus; the WebSocket fans it out.
   Built: the bus and the WebSocket. The DB write is **pending**. Live state stays in the engine's in-memory
   `WorldState`.

**Incident flow (LLM calls happen here). Pending:** it needs the threat detector, the agent and approvals.

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

PostgreSQL 16 with the pgvector extension, via the `pgvector/pgvector:pg16` Docker image (host port 5433).
SQLAlchemy 2.x async with the psycopg 3 driver. The LangGraph Postgres checkpointer (pending) will use the
same driver and database. No Alembic: the seed CLI (`python -m gridline.db.seed [--reset]`) creates the
schema, and the test suite creates its own. The app does not touch the schema. It connects lazily, and today
only `GET /api/chunks/{id}` uses the database. `POST /api/simulation/reset` resets the in-memory engine only.

**Built:** the city data layer's 38 seeded tables (the table below lists those the brain reads; the full
catalogue is in `docs/superpowers/specs/2026-09-26-nandipur-city-data-layer-design.md` §5–§6), `chunks`, and
the seven operations tables. **Pending:** `sensor_readings`, `zone_state`, `agent_runs`, `agent_steps`,
`approvals`, `events` and the checkpointer tables. With no `events` table, event history
(`GET /api/events`) is pending too, and events exist only on the in-memory bus.

| Table | Purpose | Key columns |
|---|---|---|
| `zones` | Districts / hillside zones | id, name, slope_deg, soil_type, catchment_id, drains_to_channel_id, svg_path |
| `roads` | Road segments | id, name, zone_id, from_zone_id, to_zone_id, status (open / blocked / closed), is_evacuation_route, is_only_access; live: closure_reason, closed_at, incident_id |
| `drainage_channels` | Channels and culverts | id, name, design_capacity_m3s, current_capacity_m3s, blocked_fraction, downstream_zone_id |
| `projects` | Construction projects | id, name, zone_id, status (active / halted / planned / completed), excavation_depth_m, planned_depth_m, permit_doc_id; live: depth_limit_m |
| `sensors` | Rain gauges, soil moisture probes, channel level gauges | id, kind, zone_id, unit |
| `sensor_readings` | **Pending.** Time series | sensor_id, sim_time, value |
| `crews` | Response crews (rescue, hill_rescue, boat, drainage, road, medical, electrical, volunteer) | id, kind, members, status, capabilities, location_zone_id; live: target_zone_id, task, incident_id, dispatched_at |
| `ambulances` | Ambulances by base hospital | id, hospital_id, kind (ALS / BLS), status, location_zone_id; live: target_zone_id, destination_hospital_id, incident_id, dispatched_at |
| `shelters`, `pump_units` | Shelters and pumps | id, status, zone / location, capacity_persons, current_occupancy, access_road_id; shelters live: opened_at, incident_id |
| `hospitals`, `hospital_beds` | Hospitals and bed pools per type | hospital: id, zone_id, status, access_road_id; beds: id `<hospital>-<type>`, bed_type, total, available; live: reserved |
| `zone_state` | **Pending.** Live derived state per zone | zone_id, saturation, rain_24h_mm, landslide_index, flood_index, band |
| `incidents` | One per hazard episode (at most one open per zone and hazard) | id, zone_id, hazard, band, status, title, summary, opened_at, updated_at, closed_at |
| `agent_runs` | **Pending.** One per graph invocation | id, incident_id, thread_id, trigger, status, started_at, finished_at |
| `agent_steps` | **Pending.** Node outputs for the trace | run_id, node, started_at, finished_at, output_json, citations_json |
| `approvals` | **Pending.** Pending / decided approval requests | id, run_id, incident_id, proposed_actions_json, status, decided_by, note |
| `actions` | Audit trail: every attempted tool call, rejected and failed ones included | id, tool, status (executed / unchanged / rejected / failed), idempotency_key (unique, executed/unchanged only), actor, approval_id, run_id, incident_id (no FK), input_json, before_json, after_json, affected_entities_json, message, sim_time, executed_at, verification_json |
| `alerts` | Public alerts issued | id, zone_id, level (advisory / warning / evacuate), message, incident_id, issued_at |
| `evacuation_orders` | At most one active order per zone | id, zone_id, level (voluntary / mandatory), reason, shelter_id, incident_id, status (active / lifted), issued_at, updated_at |
| `construction_restrictions` | Halts and depth limits on projects | id, project_id, kind (halt / depth_limit), max_depth_m, reason, incident_id, status, issued_at |
| `tasks` | Inspection, monitoring, evacuation and emergency work | id, kind, title, description, priority, status, zone_id, target_kind, target_id, metric, interval_minutes, assigned_crew_id, incident_id, evacuation_order_id, created_by, created_at, completed_at |
| `bed_reservations` | Beds held for an incident | id, hospital_id, hospital_bed_id, bed_type, incident_id, beds, status, created_at |
| `documents`, `document_sections`, `chunks` | Corpus (seeded) and RAG index | documents: id, title, kind, source, zone_ids / hazards text[], content_hash, embedding_model; sections: id `<doc>#<section>`; chunks: id = citation id `<doc>#s4.2`, document_id, section_id, text, embedding `vector(384)`, kind, zone_ids, hazards (filter columns), metadata jsonb (incl. `category`, the knowledge-category filter) |
| `events` | **Pending.** Append-only event log | the envelope (§12): event_id, timestamp, sim_time, event_type, source, location, severity, incident_id, payload jsonb |
| `checkpoints*` | **Pending.** LangGraph checkpointer tables | created by `AsyncPostgresSaver.setup()` |

Indexes: `chunks.embedding` (HNSW, cosine), `actions.idempotency_key` (unique), and partial unique indexes
for one open incident per (zone, hazard) and one active evacuation order per zone. Pending with their tables:
`events (timestamp)`, `sensor_readings (sensor_id, sim_time)`.

"Live" columns on seeded tables and the operations tables (`incidents`, `alerts`, `evacuation_orders`,
`construction_restrictions`, `tasks`, `bed_reservations`, `actions`) are written only by the tool layer
(§10); the seed leaves them empty. The operations tables are listed in
`gridline.db.models.OPERATIONS_TABLES`.

---

## 5. Simulation and threat detection

The simulation is built (`gridline/simulation`; design and implementation deviations in
`docs/superpowers/specs/2026-09-26-simulation-and-events-design.md`). The threat detector is **pending**.

**Clock.** Simulated time advances in fixed steps (default 5 simulated minutes per tick, one tick per real
second, speed adjustable 0.25x to 10x, pausable). All timestamps in the system carry both wall time and
`sim_time`.

**Scenario scripts** are plain Python data: a rainfall intensity curve over sim time, a construction schedule
(excavation rate), named stages, and scripted events, some conditional on the world (the SL-HV-1 landslide
fires only once the slope has actually moved 80 mm). Four scenarios ship: `normal_city`, `hillside_landslide`,
`flash_flood` (secondary) and `cascading_landslide_flood` (primary, the default `SIM_DEFAULT_SCENARIO`).
Operators inject disruptions through `POST /api/simulation/inject`. `GET /api/city` lists ready-made presets
for re-planning demos (`gridline/api/injections.py`): D-7 culvert blocked, Hill Road blocked, rescue team C-4
delayed, Kalinadi Bridge closed, forced SL-HV-1 slope failure. Scenarios are deterministic given a seed.

**Physics-lite models** (small, unit-tested, documented in code):

- Soil saturation per zone: bucket model, `sat += k_in * rain - k_drain * sat`, clamped to [0, 1];
  excavation raises `k_in` for the affected zone.
- Drainage channel flow: `flow = catchment_runoff(rain, sat)`, capacity reduced by `blocked_fraction`;
  overflow when `flow > current_capacity`.
- Pumps add capacity to a channel; halting a project freezes excavation depth; a landslide event sets
  `blocked_fraction` on the downstream channel.
- As built, the models are recalibrated to the data layer: per-slope saturation and creep driven by the
  unsupported cut, ponding in downstream zones, a river rating curve and flap gates. Constants are named in
  `simulation/physics.py`. Fixed pumps count toward channel capacity. Deploying mobile pumps is pending
  (`deploy_pumps`, §10).

**Sensors** sample the model state with seeded noise, giving the brain real telemetry to cite. Each
observation carries a `severity`. This is a fixed-threshold sensor band taken from the policy numbers
(`simulation/severity.py`), never a threat assessment.

**Threat detector (pending)** runs after each tick and computes two transparent indices per zone, each a
weighted sum of factors in [0, 1] with weights in a config file (not in prompts):

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

Built as the city data layer: `backend/data/city/*.yaml` plus the corpus, validated and cross-checked before
`python -m gridline.db.seed` writes anything. Design:
`docs/superpowers/specs/2026-09-26-nandipur-city-data-layer-design.md`; usage: `backend/README.md`. The
simulation builds its `City` from the same YAML (`gridline/city/nandipur.py`) without the database. The data
is richer than first planned, but the demos turn on a few assets.

- **Zones (10):** Hillview `Z-HV` (hillside, slope 32°, construction site), Riverside `Z-RS` (downstream of
  D-7, flood-prone), Tekri Heights, Old Town, Market Ward, Station Road, Civil Lines, Lakeside, New Colony,
  Mill Road Industrial.
- **Water:** nine drainage channels, among them D-7 "Kalinadi drain" (Hillview → Riverside; its BR-4
  culvert was narrowed in 2025), D-3 and the pumped D-11. Rivers: R-1 Kalinadi, R-2 Tekri Nala and
  R-3 Nandi Lake.
- **Roads:** 14 roads and 5 bridges. Hill Road `RD-01` is the only access to Hillview. Riverside Bypass
  `RD-02` is an evacuation route. BR-1 is Kalinadi Bridge.
- **Projects (9):** Hillview Terrace Phase 2 `PR-HT2` (permit HT-2026-014; planned excavation 6 m, 2.5 m at
  the start; on slope SL-HV-1 at 32°).
- **Sensors (16):** rain gauges RG-01..RG-05, soil probes SM-01..SM-04, channel gauges CL-D7, CL-D3 and
  CL-D11, river gauges RV-01 and RV-02, weather station WS-01, and lake level LL-01.
- **Assets:** crews C-1..C-8, 14 ambulances, hospitals H-1..H-5 with bed pools, shelters S-1..S-8, and nine
  pump units (four mobile units at the depot).
- **History:** 29 infrastructure changes (2018–2026), 17 historical incidents and 25 policy thresholds.
- **Corpus (37 Markdown documents with YAML front matter):** the Disaster Management Policy (thresholds, halt
  rules for slopes above 25°) and seven other policies, four SOPs, 17 post-incident reports, construction
  permit HT-2026-014 with conditions, the 2018–2026 infrastructure change log, zone geotechnical and city
  profiles, a D-7 condition survey, a BR-1 inspection, and the SL-HV-1 slope-stability and D-7
  hydraulic-capacity studies.

---

## 7. RAG

1. **Load.** `gridline/rag/ingest.py` (`uv run gridline-ingest`) parses `backend/data/corpus/*.md` with the
   seed's corpus parser and makes one chunk per numbered section, so chunk ids equal `document_sections` ids
   (a section over 350 words is split at paragraphs into extra `-p2`, `-p3` parts). Chunks carry `kind`,
   `zone_ids`, `hazards` and metadata (including the document's `category`). Documents must be seeded
   first; files whose hash and embedder are unchanged are skipped, so ids stay stable. Only `chunks` and the
   documents' fingerprint are written.
2. **Embed.** fastembed `BAAI/bge-small-en-v1.5` (384-dim, ONNX, CPU, downloaded once), or the offline
   `hashed` embedder (`EMBEDDING_PROVIDER=auto|fastembed|hashed`; `auto` falls back to `hashed`). Stored in
   `chunks.embedding`; retrieval refuses to run when the live embedder differs from the indexed one.
3. **Retrieve.** `Retriever.retrieve(query, filters, top_k=8)`: cosine similarity in pgvector with optional
   any-of filters `kinds, categories, hazards, zone_ids, document_ids`. Different fields intersect. A chunk
   with empty `zone_ids`/`hazards` is city-wide / all-hazard and matches every zone / hazard filter. `kinds`
   is a document's form (`policy, sop, report, permit, change_log, profile`). `categories` is what it is
   about: every corpus document declares one of the brief's ten knowledge categories in its required
   `category:` front matter (`policy, sop, procedure, incident_report, infrastructure_report,
   engineering_report, construction_safety, evacuation, resource_rules, change_log`; reports, and only
   reports, are `incident_report`). The category is stored in `chunks.metadata` and filtered on
   `metadata->>'category'`. **Pending:** the `retrieve` node issues two or three targeted queries per
   incident (policy thresholds; history for this zone and hazard; recent changes affecting the zone) and
   merges results. Stretch: add Postgres full-text search with reciprocal rank fusion if dense-only
   retrieval misses exact identifiers such as permit numbers. Usage and the category mapping: `docs/rag.md`.
4. **Citation IDs.** Every retrieved chunk is presented to the model as `[doc-slug#section]`
   (e.g. `[dmp-2024#s4.2]`). Live inputs get IDs too: `[sensor:RG-02@sim_time]`, `[state:zone.hillview]`,
   `[event:evt_123]`. The model may cite only IDs present in its input. Built: a chunk's id is its citation
   id, and `GET /api/chunks/{chunk_id}` resolves it. Live-input ids are pending with the agent.
5. **Grounding validator (pending).** Structured outputs carry `claims: list[{text, citation_ids}]`. The
   validator rejects unknown IDs and factual claims with no citation, retries once with the error fed back,
   and on a second failure marks the step `ungrounded` and lowers confidence. Built so far: its core check,
   `validate_citation_ids(cited, allowed)` in `rag/citations.py`, and the dashboard's source drawer, which
   shows the chunk behind a clicked citation chip.

---

## 8. LangGraph agent

**Pending** (no `gridline/agents` yet; LangGraph is not a dependency yet). The tools it will call are built
(§10).

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

**Pending** (no `gridline/llm` yet; the `anthropic` SDK is not a dependency yet). The dashboard's provider badge
reads "No reasoner yet" until `GET /api/llm/status` exists.

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

Implemented in `gridline/tools` (design: `docs/superpowers/specs/2026-09-26-city-operations-tools-design.md`).
Tools are the only way the agent, and later the operator, changes the city. They change the **database**; the
simulation will read those changes when it is coupled to the tools (crew travel, excavation freeze).

**Contract** (`gridline/tools/base.py`):

```python
class ActionTool[I: ActionInput, P]:      # I: Pydantic input, extra="forbid", has idempotency_key
    name: str; description: str; approval_required: bool; Input: type[I]
    def requires_approval(self, inp: I) -> bool                 # overridden only by issue_preventive_alert
    async def check(self, inp: I, ctx: ToolContext) -> Plan[P]  # load rows (FOR UPDATE), validate city state,
                                                                # raise ToolRejected(reason)
    async def apply(self, inp: I, ctx: ToolContext, plan: Plan[P]) -> Applied   # mutate, never commit
    async def verify(self, inp: I, ctx: ToolContext, result: ActionResult) -> VerificationResult

class ReadTool[I: ReadInput, O]:          # typed views, never audited
    async def run(self, inp: I, ctx: ToolContext) -> O
```

`ToolContext` carries the session, `actor` (agent / operator / system), `approval_id`, `run_id` and `sim_time`.
Every action returns an `ActionResult`: `action_id, action_type, status (executed / unchanged / rejected /
failed), before, after` (row snapshots keyed `"kind:id"`), `timestamp, sim_time, affected_entities, message,
actor, approval_id, idempotency_key, incident_id, replayed`.

**Executor** (`execute_action(tool, raw, ctx)` in `gridline/tools/executor.py`): validate input → replay an
earlier request with the same `idempotency_key` (a key reused for another tool or input is rejected) → reject
approval-required calls without `ctx.approval_id` → `check` → before snapshot → `apply` + flush → after
snapshot → insert the `actions` row → commit. `ToolRejected` and validation errors give `rejected`, any other
exception gives `failed`; both roll back first and are audited, and neither blocks a retry with the same key.
"Unchanged" means the city was already in the requested state (for example closing a closed road). The
executor expires the session first so it never decides on a stale identity map. `build_registry()` returns the
21 tools; `describe()` exports each input's JSON schema for `recommend`.

| Group | Tool | Effect on state | Approval |
|---|---|---|---|
| Resources | `get_available_rescue_teams(zone_id?)` | read: available crews of kind rescue, hill_rescue, boat | — |
| | `dispatch_rescue_team(crew_id, zone_id, task, incident_id?)` | crew `dispatched` with target zone, task, incident; zone must have an open access road | required |
| | `get_available_ambulances(zone_id?)` | read: available ambulances | — |
| | `dispatch_ambulance(ambulance_id, zone_id, incident_id?, destination_hospital_id?)` | ambulance `dispatched`; zone and destination hospital reachable over open roads | required |
| Shelters | `get_shelter_capacity(shelter_id?, zone_id?)` | read: status, capacity, occupancy, free places | — |
| | `open_shelter(shelter_id, incident_id?)` | shelter `open`; its access road must be open | required |
| | `close_shelter(shelter_id, reason)` | shelter `closed`; must be empty and not an active evacuation destination | required |
| Hospitals | `get_hospital_capacity(hospital_id?, zone_id?)` | read: beds per type (total, available, reserved, occupied) | — |
| | `reserve_hospital_beds(hospital_id, incident_id, beds, bed_type="general")` | `bed_reservations` row; beds move from `available` to `reserved` | required |
| Roads | `get_road_status(road_id?, zone_id?)` | read: status, closure reason, route flags | — |
| | `close_road(road_id, reason, incident_id?)` | road `closed` | required |
| | `reopen_road(road_id, reason)` | road `open`; a `blocked` road must be cleared first | required |
| Prevention | `create_inspection_order(target_kind, target_id, priority, reason, incident_id?)` | inspection task on a zone, road, bridge, channel, slope, project, shelter or hospital | auto |
| | `create_monitoring_task(target_kind, target_id, metric, interval_minutes, reason, ...)` | monitoring task | auto |
| | `create_construction_restriction(project_id, kind, max_depth_m?, reason, incident_id?)` | `halt` → project `halted`; `depth_limit` → tightest `depth_limit_m` | required |
| | `issue_preventive_alert(zone_id, level, message, incident_id?)` | inserts alert | auto for `advisory`, required for `warning` / `evacuate` |
| Evacuation | `create_evacuation_order(zone_id, level, reason, shelter_id?, incident_id?)` | active order; a higher level escalates it in place; shelter must be open and outside the zone | required |
| | `create_evacuation_task(zone_id, description, priority, assigned_crew_id?)` | task on the zone's active order | auto |
| Incidents | `create_incident(zone_id, hazard, band, title, summary)` | open incident (unchanged if one is open for the zone and hazard) | auto |
| | `update_incident(incident_id, band?, status?, summary?)` | band, summary, or close | auto |
| | `create_emergency_task(incident_id, title, description, priority, zone_id?, assigned_crew_id?)` | emergency task | auto |

`halt_construction` is `create_construction_restriction(kind="halt")`; `dispatch_crew`, `issue_alert` and
`schedule_inspection` became `dispatch_rescue_team`, `issue_preventive_alert` and `create_inspection_order`.
**Pending:** `deploy_pumps(channel_id, units)`, publishing `action.executed` on the event bus, and any caller.
No API route or agent invokes the tools yet, and the registry is not on `app.state`.

---

## 11. Verification

Verification is deterministic and reads state back from the database (and, once coupled, the simulation),
never from the output of the model. `execute_action` does not verify: the caller runs
`tool.verify(inp, ctx, result)`, which re-reads rows with `populate_existing`, and stores the outcome on the
audit row with `record_verification(session, action_id, result)` (`actions.verification_json`). Created or
existing ids come from `result.after`, our own audit data.

- Post-conditions: `dispatch_rescue_team` / `dispatch_ambulance` → status `dispatched` and target zone equals
  the requested zone; `open_shelter` → `open`; `close_shelter` → `closed`; `close_road` → `closed`;
  `reopen_road` → `open`; `reserve_hospital_beds` → reservation `active` with the requested beds and the bed
  pool's `reserved` at least that many; `create_construction_restriction` → restriction `active` and project
  `halted` (halt) or `depth_limit_m <= max_depth_m` (depth limit); `issue_preventive_alert` → alert row exists
  with the level; `create_evacuation_order` → an `active` order at the requested level or higher; the task
  tools → task `open` (monitoring also checks metric and interval); `create_incident` → incident `open` for
  the zone and hazard; `update_incident` → every requested field has the requested value.
- Once the simulation is coupled: `halt` also checks excavation depth unchanged over the next two ticks,
  `close_road` that no crew routes through it, dispatch that the crew reaches the target within
  `max_verify_ticks`, `deploy_pumps` that channel capacity rose by the expected amount.
- A tool returns `verified` or `failed` with one `VerificationCheck(name, passed, expected, observed)` per
  condition. The `verify` node (pending, §8) polls per tick until all post-conditions hold or the tick
  budget is spent and reports `verified`, `partially_verified` (list of failures) or `failed` for the plan.
  Anything but `verified` routes to `replan` with the concrete failure (e.g. "crew C-4 target zone:
  expected Z-HV, observed Z-RS"), which the next `recommend` must address.
- The dashboard's actions log shows expected effect vs observed effect per action. It is built, but it
  stays empty until `/api/actions` and the `action.*` events exist.

---

## 12. Event bus, WebSocket and REST

**Event bus** (`gridline/events/bus.py`): asyncio pub/sub. `publish(event)` puts the event on every bounded
subscriber queue whose event-type prefixes match (drop-oldest for slow consumers, `EVENT_QUEUE_SIZE`). A single
`EventBus` instance lives on `app.state.bus`. **Pending:** a DB-writer subscriber that appends each event to
the `events` table.

**Envelope** (`gridline/events/envelope.py`): `{ event_id, timestamp, sim_time, event_type, source,
location?, severity, payload, incident_id? }`. `event_id` is engine-numbered (`evt-000123`). `timestamp` is
wall time, and `sim_time` is simulated time. `severity` is one of `info / low / moderate / high / critical`,
a sensor band and not a threat assessment. `payload` is validated against the payload model registered for
`event_type` (`events/payloads.py`). For clients, `Event` in `gridline/api/event_models.py` is a Pydantic
discriminated union on `event_type` with one typed envelope per type. It is exported in `/openapi.json`, and
the WebSocket sends exactly these shapes.

**Types** (`gridline/events/types.py`). Built: `sim.tick`, `sim.status`, `sim.snapshot`, `sim.heartbeat`,
`scenario.stage`, `weather.observation`, `weather.forecast`, `environment.soil`, `environment.river`,
`environment.drainage`, `environment.slope`, `environment.water_accumulation`, `infrastructure.road`,
`infrastructure.bridge`, `infrastructure.drainage_obstruction`, `infrastructure.construction`,
`infrastructure.failure`, `emergency.rescue_team`, `emergency.ambulance`, `emergency.hospital`,
`emergency.shelter`. Operators may inject `weather.forecast` and the `infrastructure.*` and `emergency.*`
types. **Pending** (their contract is in `frontend/openapi.pending.yaml`): `zone.state`, `threat.detected`,
`threat.escalated`, `incident.opened`, `incident.closed`, `agent.run.started`, `agent.node.started`,
`agent.node.finished`, `agent.run.finished`, `approval.requested`, `approval.decided`, `action.executed`,
`action.verified`, `replan.triggered`, `alert.issued`. The typed observation events replace the design's
`sensor.reading`, and `scenario.stage` replaces `scenario.event`.

**WebSocket `/ws`** (`gridline/events/websocket.py`): the first frame is `sim.snapshot` with payload
`{status, world, city}`: the runner status, the whole `WorldSnapshot` and the static `CityMap` (the same body as
`GET /api/city`). Live events follow. A `sim.heartbeat` `{tick, sim_time}` is sent whenever no event arrives
for `WS_HEARTBEAT_SECONDS` (15 s). `?types=weather.,environment.soil` subscribes by comma-separated
event-type prefix. Empty segments are ignored, and snapshot and heartbeats are always sent. Client messages
are ignored. **Pending:** open incidents and pending approvals in the snapshot.

**REST** (all JSON, under `/api`). Every body is a Pydantic model. Invalid runner transitions return 409.
Unknown scenarios or assets, non-injectable types and invalid payloads return 422.

| Method / path | Purpose |
|---|---|
| `GET /health` | Liveness and version |
| `GET /city` | Static city map: zones (SVG paths), roads, bridges, channels, slopes, projects, sensors, crews, shelters, hospitals, pump depot, map features, scenarios, inject presets. Live state is in `WorldSnapshot`, not here |
| `GET /chunks/{chunk_id}` | Citation source: the stored chunk (404 when unknown, 503 when the database is unreachable) |
| `GET /simulation/status`, `/scenarios`, `/snapshot` | Runner status; the four scenarios with their stages; the current `WorldSnapshot` |
| `POST /simulation/scenario {scenario, seed?}` | Select a scenario (back to idle at tick 0) |
| `POST /simulation/start {scenario?, seed?, speed?}`, `/pause`, `/resume`, `/reset` | Runner control (`reset` resets the engine only) |
| `POST /simulation/advance {ticks}` | Step 1–1000 ticks while not running; returns `events_emitted` and status |
| `POST /simulation/speed {speed}` | 0.25x–10x |
| `POST /simulation/inject {event_type, payload, location?, source?, severity?}` | Apply an operator event now; returns it plus derived events (all published on the bus) |

**Pending routes** (design; the frontend already codes against `openapi.pending.yaml`):

| Method / path | Purpose |
|---|---|
| `GET /llm/status` | Active provider and model |
| `GET /detector/bands` | Detector band thresholds for the risk timeline |
| `GET /events?since=&type=&limit=` | Event history (needs the `events` table) |
| `GET /incidents`, `GET /incidents/{id}` | Incidents with runs, steps, citations, actions |
| `GET /approvals?status=`, `POST /approvals/{id}/decide` | Inbox; body `{decision: approve/reject/partial, approved_action_ids, note}` |
| `GET /actions`, `GET /actions/{id}` | Executed actions with verification |
| `GET /documents/{doc_id}` | Whole citation source document |

---

## 13. Frontend

Built and connected to the backend. Vite + React 19 + TypeScript + Tailwind v4. TanStack Query handles REST.
A small Zustand store in `src/live` holds live state and is fed by the WebSocket: pure reducers apply the
`sim.snapshot` and then each event, the socket reconnects with backoff, and an engine reset triggers a resync.
Charts use Recharts. There is no router: one dashboard.

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

As built, an overview strip and a mode/connection banner sit above the grid, and a "Why" drawer and a
citation source drawer open over it. Against the live backend, the panels fed by pending subsystems (incident
reasoning, approvals, actions) show empty states. The risk timeline plots the observations but has no
detector indices or band lines yet.

**Contract.** Payload types are generated, never hand-written. `npm run gen:api` runs two steps:
`gen:contract` runs `backend/scripts/export_contract.py` (`gridline/api/contract.py`), which writes
`frontend/openapi.json` and the mock fixtures `src/mock/fixtures/nandipur.{city,world}.json`, all built by the
backend with no database or network. `gen:types` then runs `scripts/gen-api.mjs`, which merges `openapi.json`
with the hand-written `openapi.pending.yaml` overlay for pending routes and events and generates
`src/api/schema.d.ts` with `openapi-typescript`. `src/api/types.ts` re-exports the names. The overlay may only
add: the merge fails if the backend already defines one of its paths, schemas or event types, so each entry
is deleted when its backend lands. Drift test: `backend/tests/test_contract_export.py` fails when the
committed `openapi.json` or fixtures differ from what the backend renders now.

**Modes** (`VITE_API_MODE`; see `src/api/client.ts`):

- `http` (the default, `npm run dev`). `HttpApiClient` calls `/api` and `/ws` through the Vite dev proxy
  (`GRIDLINE_BACKEND_URL`, default `http://localhost:8000`). Pending routes are answered with a local 501 and
  no request is sent.
- `mock` (`npm run dev:mock`). `MockApiClient` serves the backend-generated fixtures and replays
  `hillside_landslide` observations, plus scripted detector events for the pending detector panels. It
  never fabricates agent, approval, action or verification output.

---

## 14. Configuration and local startup

`backend/.env` is optional (the example is committed as `backend/.env.example`). `gridline/config.py` reads it
with `pydantic-settings`, and the defaults match the Docker database on host port **5433**:

```
DATABASE_URL=postgresql+psycopg://gridline:gridline@localhost:5433/gridline
TEST_DATABASE_URL=postgresql+psycopg://gridline:gridline@localhost:5433/gridline_test
EMBEDDING_PROVIDER=auto       # auto | fastembed | hashed
EMBEDDING_MODEL=BAAI/bge-small-en-v1.5
CORPUS_DIR=data/corpus        # relative to backend/
RAG_TOP_K=8                   # reserved for the retrieve node
DATA_DIR=data                 # holds city/ and corpus/
SIM_TICK_SECONDS=1.0          # real seconds per tick at speed 1.0
SIM_MINUTES_PER_TICK=5
SIM_DEFAULT_SCENARIO=cascading_landslide_flood
SIM_DEFAULT_SEED=42
SIM_AUTOSTART=false
WS_HEARTBEAT_SECONDS=15
EVENT_QUEUE_SIZE=1000         # per-subscriber bus queue (drop-oldest)
```

**Pending** with the LLM, agent and approvals layers: `LLM_PROVIDER=auto` (anthropic | mock | auto),
`ANTHROPIC_API_KEY` (optional), `LLM_MODEL=claude-opus-5`, `LLM_EFFORT=medium`, and `AUTO_APPROVE=false`
(a demo shortcut that still records approvals).

Other knobs: `GRIDLINE_DB_PORT` (docker-compose host port, default 5433). On the frontend,
`GRIDLINE_BACKEND_URL` sets the Vite dev proxy target for `/api` and `/ws` (default
`http://localhost:8000`), and `VITE_API_MODE=http|mock` picks the API client
(`frontend/.env.development`, `frontend/.env.mock`).

Startup (design): `scripts/dev.ps1` or `scripts/dev.sh` runs, in order, `docker compose up -d db`, `uv sync`,
seed if the database is empty, then backend (`uvicorn`) and frontend (`vite`) concurrently. **Pending: the
dev scripts do not exist yet.** Until they do, start the pieces by hand:

```
docker compose up -d db                                   # repo root; also creates gridline_test
cd backend && uv sync && uv run python -m gridline.db.seed && uv run gridline-ingest
cd backend && uv run uvicorn gridline.main:app            # :8000 (the simulation needs no database)
cd frontend && npm install && npm run dev                 # :5173, proxies /api and /ws to the backend
```

---

## 15. Testing strategy

| Layer | What is tested | How |
|---|---|---|
| Unit — simulation | Bucket model, channel overflow, scenario script application, determinism by seed | pytest, pure functions, no DB |
| Unit — threat detector (pending) | Index math, band transitions with hysteresis, trigger and cooldown | pytest |
| Unit — tools | `execute_action` mutates state as declared, audits every outcome, replays idempotency keys, refuses approval-required calls without an approval; `verify` passes on success and fails on injected failure | pytest + test DB (Postgres in Docker), `tests/tools/` |
| Unit — RAG | Chunking, citation ID stability, embedder fallback, retrieval returns the policy chunk for a threshold query on the seed corpus, kind/category/hazard/zone filters, `validate_citation_ids` rejects unknown IDs (full grounding validator pending) | pytest + test DB |
| Unit — mock provider (pending) | Fills every schema, cites only provided IDs, reflects changed inputs | pytest |
| Integration — graph (pending) | Full run with `MockProvider`: reaches the `approval_gate` interrupt, resumes on decision, executes, verifies, re-plans on injected crew failure, stops after the re-plan limit | pytest-asyncio + test DB |
| Integration — API | REST endpoints and WebSocket snapshot + event stream | httpx `ASGITransport`, Starlette WS test client |
| Contract — Anthropic (pending) | Structured output round-trip against the real API for one node | pytest, skipped without `ANTHROPIC_API_KEY` |
| Contract — frontend | Committed `frontend/openapi.json` and mock fixtures equal what the backend renders | `tests/test_contract_export.py` |
| Frontend | Citation chip opens the right source; approvals inbox posts the decision; store applies snapshot then events; generated event union covers every backend and pending type | Vitest + Testing Library |
| Demo smoke | Built (simulation only, no DB or network): `scripts/demo_smoke.py` replays `cascading_landslide_flood` (seed 42, 300 ticks) and asserts the stages in order, the SL-HV-1 landslide, D-7 blocked, Riverside flooded, the Kalinadi above warning, Hill Road and Riverside Bypass blocked, and that halting PR-HT2 at t=60 prevents the landslide. Pending, once the agent exists: run it with the mock provider and assert project halted, D-7 pumps deployed, alert issued, all actions verified | run before every demo |

Invariants enforced by tests, not by convention: no LLM output enters state without schema validation and
grounding (from the agent milestone on); no state changes outside the tool registry; every event type has a
documented payload model.

---

## 16. Repository layout

```
GridLine_AI/
├── ARCHITECTURE.md            this file
├── CLAUDE.md                  project constitution and working rules
├── docker-compose.yml         postgres + pgvector on localhost:5433 (GRIDLINE_DB_PORT)
├── docs/                      rag.md (RAG usage); superpowers/specs and plans per subsystem; screenshots/
├── scripts/                   demo_smoke.py; db/init.sql (creates gridline_test, enables vector);
│                              dev.ps1, dev.sh (pending)
├── backend/
│   ├── pyproject.toml         uv-managed; fastapi, uvicorn, sqlalchemy, psycopg, pgvector, fastembed,
│   │                          pydantic-settings, pyyaml, numpy (langgraph, langgraph-checkpoint-postgres,
│   │                          anthropic: pending)
│   ├── README.md              data layer, seed, ingest, simulation, tools, tests
│   ├── data/city/             synthetic city seed (YAML, one file per area)
│   ├── data/corpus/           37 synthetic documents (Markdown + front matter)
│   ├── scripts/               export_contract.py: openapi.json + mock fixtures for the frontend
│   ├── gridline/
│   │   ├── main.py            app factory, lifespan (city, engine, bus, runner, city map, chunk store)
│   │   ├── config.py          Settings from backend/.env
│   │   ├── errors.py          typed errors mapped to 409 / 422
│   │   ├── city/              data-layer record schemas, loader, consistency and reference checks, terrain;
│   │   │                      the simulation's typed City (model.py) built by nandipur.py
│   │   ├── db/                base, engine, models/ (one module per area, incl. knowledge, operations),
│   │   │                      schema, seed/ (corpus parser, rows, CLI)
│   │   ├── simulation/        engine, world, physics, dynamics, apply, sensors, severity, schedule, runner,
│   │   │                      scenarios/
│   │   ├── events/            types, payloads, envelope, bus, websocket (/ws)
│   │   ├── rag/               chunker, embedder, models, store, retriever, citations, ingest
│   │   ├── tools/             base, executor, registry, snapshot, views, vocab, common, one module per group
│   │   ├── api/               routers: health, city, chunks, simulation; models and helpers: city_map,
│   │   │                      map_geometry, map_labels, simulation_models, injections, event_models,
│   │   │                      contract, deps, errors
│   │   ├── threats/           pending: indices, bands, detector
│   │   ├── llm/               pending: provider protocol, anthropic, mock, prompts/
│   │   ├── agents/            pending: state, nodes/, graph, runner
│   │   └── approvals/         pending
│   └── tests/                 pytest; tools/ for the tool layer; fixtures/corpus for RAG
└── frontend/
    ├── package.json           vite, react, typescript, tailwindcss, @tanstack/react-query, zustand, recharts,
    │                          openapi-typescript
    ├── openapi.json           backend contract (generated, do not edit)
    ├── openapi.pending.yaml   hand-written contract of pending routes and events
    ├── scripts/gen-api.mjs    merges both into src/api/schema.d.ts
    └── src/
        ├── api/               ApiClient, HttpApiClient, generated schema.d.ts, types.ts, query hooks
        ├── live/              WebSocket client, Zustand live store, pure event reducers, selectors
        ├── mock/              MockApiClient, MockSocket, scripted replay, backend-generated fixtures
        ├── components/        map, timeline, events, incident, approvals, actions, scenario, overview, why,
        │                      layout, ui
        ├── ui/                UI state (selection, layers, drawers)
        ├── hooks/, styles/, test/
        └── App.tsx
```

---

## 17. Non-goals and constraints

- No microservices, Kafka, Kubernetes, Celery, Redis. One process, one database, one frontend.
- No real GIS, weather feeds, or real-city data. No personal data anywhere, including in fake reports.
- No auth, roles, or audit beyond the append-only event log (pending) and the `actions` audit trail.
- No hardcoded model answers. The deterministic parts are the simulation, the indices and the mock
  heuristic, all of which read live state and retrieved context.
- No autonomous execution of approval-required actions, even in demo mode (`AUTO_APPROVE` records a
  synthetic approval and is shown as such).

---

## 18. Implementation milestones (status 2026-09-26)

1. Skeleton: compose file, backend app factory, DB models, seed, event bus, WebSocket, simulation loop,
   `sim.tick` visible in a bare frontend. **Done**, except that the bus is not persisted (no `events`
   table) and the `dev.ps1` / `dev.sh` start scripts are missing.
2. Threat detector and primary scenario producing band changes and incidents. **Scenarios done** (all four).
   **Detector pending.**
3. RAG: corpus, embedding, retrieval, citation IDs, validator. **Done**, with the ten-category filter. The
   grounding validator is pending beyond `validate_citation_ids`.
4. LangGraph with `MockProvider` end to end, including interrupt, tools, verification, re-plan. **Tools and
   per-tool verification done** (§10, §11). **Graph, mock provider and approvals pending.**
5. `AnthropicProvider` with structured outputs and caching; grounding on real outputs. **Pending.**
6. Dashboard panels; demo smoke script. **Done**: the dashboard is connected to the backend over generated
   types, and the smoke script covers the simulation. Agent-driven panels wait on 4–5.
7. Secondary scenario; polish; README. **Secondary scenario (`flash_flood`) and `backend/README.md` done.**
