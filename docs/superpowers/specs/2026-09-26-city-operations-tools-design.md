# City Operations Action Tool Layer — Design

Date: 2026-09-26. Status: approved for planning (autonomous session; assumptions flagged in §2).
Implements ARCHITECTURE.md §10 (Action execution) and §11 (Verification) for the tool set requested
in the "City Operations Action Tool layer" brief, plus the minimal backend skeleton those tools need.

## 1. Purpose and scope

The tool layer is the **only** way the GridLine agent (and later the operator UI) changes the state of
the synthetic city of Nandipur. Each tool validates its input, validates the current city state, mutates
PostgreSQL inside one transaction, writes an audit row, and returns a structured `ActionResult` with
before/after state. Read tools return typed views of current state and do not write.

**In scope**

- Backend skeleton required by the tools: `uv` project, settings, async SQLAlchemy engine, ORM models,
  schema creation and reset, synthetic city seed (YAML + loader), `docker-compose.yml` for Postgres.
- Tool contract, executor (validation, idempotency, approval enforcement, snapshots, audit), registry.
- The 21 tools listed in §9, in seven groups (4 + 3 + 2 + 3 + 4 + 2 + 3).
- Tests against a real Postgres that read state back through a *separate* session to prove mutation.
- A targeted update of ARCHITECTURE.md §4, §10 and §11 so the design document matches the code.

**Out of scope** (later milestones): LangGraph agent, RAG, frontend, FastAPI routes, event bus,
simulation engine, threat detector, approvals subsystem, `deploy_pumps`.

## 2. Decisions and assumptions to review

These were decided without a live user; each is easy to reverse.

| # | Decision | Why |
|---|---|---|
| D1 | Tool names follow the brief verbatim (`dispatch_rescue_team`, not `dispatch_crew`). Rescue teams are rows in `crews` with `kind = "rescue"`. | Brief is the newest instruction; CLAUDE.md vocabulary is kept for entities. |
| D2 | `halt_construction` from ARCHITECTURE §10 is realised as `create_construction_restriction(kind="halt")`. `deploy_pumps` is not built. | Not in the brief; adding it is a 40-line follow-up once the framework exists. |
| D3 | The audit trail **is** the `actions` table from ARCHITECTURE §4, extended with before/after JSON, affected entities, actor, approval id and idempotency key. Rejected and failed attempts are recorded too. No second audit table. | One table, one concept ("action"), append-only. |
| D4 | Approval-required tools are rejected when `ToolContext.approval_id` is `None`. The id is recorded but not validated against an `approvals` table (that table arrives with the approvals subsystem). | Enforces non-negotiable #5 at the layer that mutates state. |
| D5 | Read tools are not audited and return view models, not `ActionResult`. | Before/after state is meaningless for a read. |
| D6 | Tools mutate the database only. Simulation coupling (crew travel, excavation freeze) is deferred to the simulation milestone; verification therefore checks DB post-conditions only. | Simulation does not exist yet. |
| D7 | Work happens on `feature/city-operations-tools`, created from the unborn `main`. `main` stays empty until the user merges. Per-task commits follow the subagent-driven workflow CLAUDE.md mandates. | Reconciles "commit only when asked" with the mandated process. |
| D8 | Postgres is exposed on host port **5433** (5432 is taken by another project on this machine). | Environment fact. |
| D9 | `hospitals.reserved_beds` is a denormalised counter updated in the same transaction as the `bed_reservations` row. | Makes before/after on the hospital row legible in the audit trail. |
| D10 | Escalating an evacuation order (voluntary → mandatory) updates the existing active order in place via `create_evacuation_order`. | Brief has no `update_evacuation_order`; one active order per zone is the simplest invariant. |
| D11 | `execute_action` does **not** call `verify()`. Verification is a separate step the caller runs (tests now; the LangGraph `verify` node later, which polls per tick). `record_verification(session, action_id, result)` stores the outcome in `actions.verification_json` so the audit trail carries it. | ARCHITECTURE §11 verifies after ticks elapse; coupling it to execution would make the executor wait on a simulation that does not exist. |
| D12 | `crews.kind` is `rescue` or `engineering` only (pumps are `pump_units` in ARCHITECTURE §4, not crews). The engineering crew `C-3` is seeded so read-tool filtering is testable; no tool acts on it in this milestone (a generic `dispatch_crew` is a later follow-up). | Keeps the seed honest without inventing tools the brief did not ask for. |

## 3. Package layout

```
docker-compose.yml                       postgres (pgvector/pgvector:pg16), host port 5433, volume pgdata
backend/
  pyproject.toml                         uv; python 3.13; deps in §12
  .env.example                           DATABASE_URL, TEST_DATABASE_URL
  data/city/nandipur.yaml                synthetic seed
  gridline/
    __init__.py
    config.py                            Settings (pydantic-settings): database_url, test_database_url
    city/
      __init__.py
      enums.py                           StrEnums: statuses, kinds, levels, bands, priorities
      seed_models.py                     Pydantic models for the YAML seed (CitySeed and per-entity)
    db/
      __init__.py
      engine.py                          make_engine, make_session_factory, create_schema, truncate_all
      models.py                          DeclarativeBase + city and operations tables (§4)
      seed.py                            load_city_seed(path) -> CitySeed; seed_city(session, seed)
    tools/
      __init__.py
      base.py                            ToolContext, EntityRef, ActionStatus, ActionResult,
                                         VerificationCheck, VerificationResult, ToolRejected,
                                         Plan, Applied, ActionTool, ReadTool
      snapshot.py                        ENTITY_MODELS, row_to_dict, snapshot(session, refs)
      executor.py                        execute_action(tool, raw_input, ctx) -> ActionResult,
                                         record_verification(session, action_id, result) -> None
      registry.py                        ToolRegistry, ToolSpec, build_registry()
      common.py                          shared lookups: require_zone, require_open_incident,
                                         require_crew, zone_has_open_road, create_task, new_id
      views.py                           CrewView, AmbulanceView, ShelterView, HospitalView, RoadView
      roads.py                           get_road_status, close_road, reopen_road
      resources.py                       get_available_rescue_teams, dispatch_rescue_team,
                                         get_available_ambulances, dispatch_ambulance
      shelters.py                        get_shelter_capacity, open_shelter, close_shelter
      hospitals.py                       get_hospital_capacity, reserve_hospital_beds
      incidents.py                       create_incident, update_incident, create_emergency_task
      prevention.py                      create_inspection_order, create_monitoring_task,
                                         create_construction_restriction, issue_preventive_alert
      evacuation.py                      create_evacuation_order, create_evacuation_task
  tests/
    conftest.py                          Windows selector loop policy, DB fixtures, seeded session
    test_config.py, test_schema.py, test_seed.py
    test_executor.py, test_snapshot.py, test_registry.py
    tools/test_roads.py, test_resources.py, test_shelters.py, test_hospitals.py,
          test_incidents.py, test_prevention.py, test_evacuation.py
```

Every module stays under about 300 lines. Fully typed; `pyright` strict over `gridline/`; `ruff` clean.

## 4. Database schema

All tables live in one PostgreSQL database. IDs are strings. Seeded entities use readable ids
(`hillview`, `hill-road`, `C-1`); created rows get `<prefix>_<12 hex>` ids (`inc_`, `task_`, `alert_`,
`evac_`, `restr_`, `resv_`, `act_`). Timestamps are `DateTime(timezone=True)` in UTC. Status and kind
columns are `String` columns holding `StrEnum` values (no native Postgres enum types). JSON columns are
`JSONB`. Schema is created with `Base.metadata.create_all` at startup; no migrations (ARCHITECTURE §4).

| Table | Columns (PK first; FK → table) |
|---|---|
| `zones` | id, name, slope_deg float, soil_type |
| `roads` | id, name, zone_id→zones, status (`open`/`closed`), is_evacuation_route bool, closure_reason nullable, closed_at nullable, incident_id nullable→incidents |
| `projects` | id, name, zone_id→zones, status (`active`/`halted`), excavation_depth_m float, planned_depth_m float, depth_limit_m float nullable, permit_id |
| `crews` | id, name, kind (`rescue`/`engineering`), status (`available`/`dispatched`/`unavailable`), members int, location_zone_id→zones, target_zone_id nullable→zones, task nullable, incident_id nullable→incidents, dispatched_at nullable |
| `ambulances` | id, callsign, status (`available`/`dispatched`), base_hospital_id→hospitals, location_zone_id→zones, target_zone_id nullable→zones, destination_hospital_id nullable→hospitals, incident_id nullable→incidents, dispatched_at nullable |
| `shelters` | id, name, zone_id→zones, status (`closed`/`open`), capacity int, occupancy int default 0, opened_at nullable, incident_id nullable→incidents |
| `hospitals` | id, name, zone_id→zones, total_beds int, occupied_beds int, reserved_beds int default 0 |
| `bed_reservations` | id, hospital_id→hospitals, incident_id→incidents, beds int, status (`active`/`released`), created_at |
| `incidents` | id, zone_id→zones, hazard (`landslide`/`flood`/`fire`/`storm`/`other`), band (`normal`/`watch`/`warning`/`critical`), status (`open`/`closed`), title, summary, opened_at, updated_at, closed_at nullable |
| `alerts` | id, zone_id→zones, level (`advisory`/`warning`/`evacuate`), message, incident_id nullable→incidents, issued_at |
| `evacuation_orders` | id, zone_id→zones, level (`voluntary`/`mandatory`), reason, shelter_id nullable→shelters, incident_id nullable→incidents, status (`active`/`lifted`), issued_at, updated_at |
| `construction_restrictions` | id, project_id→projects, kind (`halt`/`depth_limit`), max_depth_m float nullable, reason, incident_id nullable→incidents, status (`active`/`lifted`), issued_at |
| `tasks` | id, kind (`inspection`/`monitoring`/`evacuation`/`emergency`), title, description, priority (`low`/`medium`/`high`/`critical`), status (`open`/`in_progress`/`done`/`cancelled`), zone_id nullable→zones, target_kind nullable, target_id nullable, metric nullable, interval_minutes int nullable, assigned_crew_id nullable→crews, incident_id nullable→incidents, evacuation_order_id nullable→evacuation_orders, created_by, created_at, completed_at nullable |
| `actions` | id, tool, status (`executed`/`unchanged`/`rejected`/`failed`), idempotency_key nullable **unique**, actor, approval_id nullable, run_id nullable, incident_id nullable (plain string, no FK), input_json JSONB, before_json JSONB, after_json JSONB, affected_entities_json JSONB, message, sim_time nullable, executed_at, verification_json JSONB nullable |

Foreign keys on `incident_id` columns other than `actions` point at `incidents.id`. `actions.incident_id`
is a plain string so a rejected attempt that named a nonexistent incident id can still be recorded.
The executor fills it from, in order of precedence: `Applied.incident_id` (set by tools that create or
derive the incident, e.g. `create_incident`, `create_evacuation_task`), `Plan.incident_id`, then the
validated input's `incident_id` field when the tool's `Input` has one; otherwise `NULL`.

`truncate_all(session)` truncates every table (`TRUNCATE ... CASCADE`) so tests and the future
`POST /api/simulation/reset` can re-seed.

## 5. Synthetic seed (`backend/data/city/nandipur.yaml`)

Everything is invented. Loaded through Pydantic (`CitySeed`) so a malformed file fails fast.

- **zones** (6): `hillview` (Hillview, 32°, colluvium), `riverside` (Riverside, 3°, alluvium),
  `old-town` (Old Town, 8°, clay), `market-ward` (Market Ward, 5°, silt), `station-road`
  (Station Road, 4°, gravel), `lakeside` (Lakeside, 6°, sandy loam).
- **roads** (8): `hill-road` (Hill Road, hillview, only access), `riverside-bypass` (Riverside Bypass,
  riverside, evacuation route), `kalinadi-bridge-road` (riverside), `old-town-high-street` (old-town),
  `temple-lane` (old-town), `market-ring-road` (market-ward), `station-road` (station-road, evacuation
  route), `lakeside-drive` (lakeside). All `open`.
- **projects** (1): `ht-phase-2` Hillview Terrace Phase 2, hillview, active, excavation 3.5 m of
  planned 6.0 m, permit `HT-2026-014`.
- **crews** (3): `C-1` Alpha Rescue (rescue, 6 members, old-town), `C-2` Bravo Rescue (rescue, 6,
  station-road), `C-3` Charlie Engineering (engineering, 4, market-ward). All `available`.
- **hospitals** (2): `H-1` Nandipur General (old-town, 120 beds, 84 occupied),
  `H-2` Riverside Clinic (riverside, 40 beds, 30 occupied).
- **ambulances** (3): `A-1`, `A-2` based at H-1 (old-town); `A-3` based at H-2 (riverside). All `available`.
- **shelters** (2): `S-1` Old Town Community Hall (old-town, capacity 300), `S-2` Station Road School
  (station-road, capacity 500). Both `closed`, occupancy 0.

Seeding order respects foreign keys: zones, hospitals, roads, projects, crews, ambulances, shelters.

## 6. Tool contract

```python
class ToolContext:                      # plain dataclass, built per call by the caller
    session: AsyncSession               # executor owns commit/rollback on this session
    actor: str = "agent"                # agent | operator | system
    approval_id: str | None = None
    run_id: str | None = None
    sim_time: datetime | None = None

class EntityRef(BaseModel):  kind: str; id: str          # key form "kind:id"
ActionStatus = Literal["executed", "unchanged", "rejected", "failed"]

class ActionResult(BaseModel):
    action_id: str                       # actions.id, server generated
    action_type: str                     # tool name
    status: ActionStatus
    before: dict[str, dict[str, Any]]    # "kind:id" -> row dict, entities in the plan
    after: dict[str, dict[str, Any]]     # same keys plus created entities
    timestamp: datetime                  # wall clock, UTC
    sim_time: datetime | None
    affected_entities: list[EntityRef]   # changed or created rows ([] when rejected/failed)
    message: str
    actor: str
    approval_id: str | None
    idempotency_key: str | None
    replayed: bool = False               # True when served from an earlier identical request

class VerificationCheck(BaseModel): name: str; passed: bool; expected: Any; observed: Any
class VerificationResult(BaseModel): status: Literal["verified", "failed"]; checks: list[VerificationCheck]

class ToolRejected(Exception): reason: str      # raised by check() or apply() for state/precondition failures

class Plan:      refs: list[EntityRef]; data: dict[str, Any]; incident_id: str | None = None
                 # what to snapshot, rows loaded by check(), and the incident this action concerns if known
class Applied:   changed: bool; message: str; created: list[EntityRef] = []; incident_id: str | None = None

class ReadTool[I: BaseModel, O: BaseModel]:
    name: ClassVar[str]; description: ClassVar[str]; Input: ClassVar[type[BaseModel]]; Output: ...
    async def run(self, inp: I, ctx: ToolContext) -> O

class ActionTool[I: BaseModel]:
    name, description, Input as above; approval_required: ClassVar[bool]
    def requires_approval(self, inp: I) -> bool          # default: self.approval_required
    async def check(self, inp: I, ctx: ToolContext) -> Plan   # loads rows, validates state, raises ToolRejected
    async def apply(self, inp: I, ctx: ToolContext, plan: Plan) -> Applied   # mutates via session, no commit
    async def verify(self, inp: I, ctx: ToolContext) -> VerificationResult   # re-reads DB; never reads model output
```

Every action `Input` model includes `idempotency_key: str | None = None`; pydantic `extra="forbid"`.

## 7. Executor algorithm (`execute_action`)

1. **Validate input.** `tool.Input.model_validate(raw)`. On `ValidationError` → result `rejected`,
   message is the flattened error list, audit row written, no state read.
2. **Idempotency replay.** If `idempotency_key` is set and an `actions` row exists with that key and
   status `executed` or `unchanged`: return that row as an `ActionResult` with `replayed=True`. No new
   row. Rows with status `rejected`/`failed` never block a retry: the `actions.idempotency_key` column
   is only populated for rows written with status executed/unchanged; rejected/failed rows keep the key
   inside `input_json` and leave the column `NULL`, so the unique index never fires for them.
3. **Approval.** If `tool.requires_approval(inp)` and `ctx.approval_id is None` → `rejected`,
   message `"approval required for <tool>"`.
4. **Check.** `plan = await tool.check(inp, ctx)`; `ToolRejected` → `rejected` (after rollback).
5. **Before snapshot.** `before = await snapshot(session, plan.refs)`.
6. **Apply.** `applied = await tool.apply(inp, ctx, plan)`; `await session.flush()`.
   `ToolRejected` → `rejected`. Any other exception → `failed` with `"<ExcType>: <msg>"`, logged with
   traceback, after rollback.
7. **After snapshot.** `after = await snapshot(session, plan.refs + applied.created)`.
8. **Audit + commit.** Insert the `actions` row (status `executed` if `applied.changed` else
   `unchanged`; affected = refs whose before/after differ, plus created), commit, return the result.

Rejected and failed paths: `await session.rollback()`, then insert the audit row in a fresh transaction
and commit; `before`/`after` are `{}` and `affected_entities` is `[]`.

The executor never raises for tool-level problems; it returns a status. It re-raises only if the audit
insert itself fails (that is an infrastructure fault).

`execute_action` never calls `verify()` (D11). `record_verification(session, action_id, result)` writes
`result.model_dump()` into `actions.verification_json` for that row and commits; it raises `KeyError` if
the action id is unknown. The caller (tests now, the graph's `verify` node later) runs
`tool.verify(inp, ctx)` and then `record_verification`.

## 8. Idempotency

Two layers, both audited:

- **Request idempotency** (executor, §7 step 2): the caller supplies `idempotency_key` (the agent will
  use its planned action id). A replay returns the stored result; nothing runs twice.
- **State idempotency** (tool `check`/`apply`): if the world is already in the requested end state the
  tool returns `Applied(changed=False)` and the result status is `unchanged`, with `before == after`.
  §9 lists the "unchanged" rule per tool.

## 9. Tool catalogue

Common validations used by many tools (in `tools/common.py`): `require_zone(id)`, `require_road`,
`require_project`, `require_crew`, `require_ambulance`, `require_shelter`, `require_hospital`,
`require_open_incident(id)` (exists and `status == "open"`), `zone_has_open_road(zone_id)` (at least one
road with that `zone_id` and `status == "open"`). Each raises `ToolRejected` with a specific message
naming the entity id (e.g. `"road 'sky-road' not found"`, `"incident 'inc_x' is closed"`).

Approval column: **auto** = executes without approval; **required** = rejected without `approval_id`.

### Resources (`tools/resources.py`)

| Tool | Input | Validation | Effect | Unchanged when | Verify | Approval |
|---|---|---|---|---|---|---|
| `get_available_rescue_teams` | `zone_id?` | zone exists if given | read: crews with `kind=rescue`, `status=available`, optionally at `location_zone_id=zone_id` → `RescueTeamsResult(items: list[CrewView])` | — | — | — |
| `dispatch_rescue_team` | `crew_id, zone_id, task: str(1..200), incident_id?` | crew exists and `kind=rescue`; zone exists; incident open if given; `zone_has_open_road(zone_id)` else reject `"zone 'hillview' has no open access road"`; crew `status` must be `available` unless already dispatched to the same zone with the same incident_id (→ unchanged); any other status → reject | crew: `status=dispatched, target_zone_id, task, incident_id, dispatched_at=now` | already dispatched to same zone + incident | `crew.status == dispatched` and `target_zone_id == zone_id` | required |
| `get_available_ambulances` | `zone_id?` | as above | read: ambulances `status=available` (optional location filter) → `AmbulancesResult(items: list[AmbulanceView])` | — | — | — |
| `dispatch_ambulance` | `ambulance_id, zone_id, incident_id?, destination_hospital_id?` | ambulance exists; zone exists; hospital exists if given; incident open if given; `zone_has_open_road`; status `available` unless same zone + incident (→ unchanged) | ambulance: `status=dispatched, target_zone_id, destination_hospital_id, incident_id, dispatched_at` | same target + incident | `status == dispatched` and target matches | required |

### Shelters (`tools/shelters.py`)

| Tool | Input | Validation | Effect | Unchanged when | Verify | Approval |
|---|---|---|---|---|---|---|
| `get_shelter_capacity` | `shelter_id?, zone_id?` | ids exist if given | read → `SheltersResult(items: list[ShelterView])`; `ShelterView.available = capacity - occupancy` | — | — | — |
| `open_shelter` | `shelter_id, incident_id?` | shelter exists; incident open if given | `status=open, opened_at=now, incident_id` | already open | `status == open` | required |
| `close_shelter` | `shelter_id, reason: str` | shelter exists; `occupancy == 0` else reject `"shelter 'S-1' has 12 occupants"` | `status=closed, opened_at=None, incident_id=None` | already closed | `status == closed` | required |

### Hospitals (`tools/hospitals.py`)

| Tool | Input | Validation | Effect | Unchanged when | Verify | Approval |
|---|---|---|---|---|---|---|
| `get_hospital_capacity` | `hospital_id?, zone_id?` | ids exist if given | read → `HospitalsResult(items: list[HospitalView])`; `available = total - occupied - reserved` | — | — | — |
| `reserve_hospital_beds` | `hospital_id, beds: int ≥ 1, incident_id` | hospital exists; incident open; `available >= beds` else reject `"hospital 'H-2' has 10 beds available, 12 requested"` | insert `bed_reservations` (active); `hospital.reserved_beds += beds` | never (request idempotency only) | reservation row active with `beds`; `hospital.reserved_beds >= beds` | required |

### Infrastructure (`tools/roads.py`)

| Tool | Input | Validation | Effect | Unchanged when | Verify | Approval |
|---|---|---|---|---|---|---|
| `get_road_status` | `road_id?, zone_id?` | ids exist if given | read → `RoadsResult(items: list[RoadView])` | — | — | — |
| `close_road` | `road_id, reason: str, incident_id?` | road exists; incident open if given | `status=closed, closure_reason, closed_at=now, incident_id` | already closed | `status == closed` | required |
| `reopen_road` | `road_id, reason: str` | road exists | `status=open, closure_reason=None, closed_at=None, incident_id=None` | already open | `status == open` | required |

### Prevention (`tools/prevention.py`)

| Tool | Input | Validation | Effect | Unchanged when | Verify | Approval |
|---|---|---|---|---|---|---|
| `create_inspection_order` | `target_kind: zone/road/project/shelter/hospital, target_id, priority, reason, incident_id?` | target exists (per kind); incident open if given | insert `tasks` kind `inspection` with `target_kind`, `target_id`, title `"Inspect <kind> <id>"`, description=reason, zone_id = the target's zone (or the zone itself) | an `open` inspection task exists for the same `(target_kind, target_id)` | task row open | auto |
| `create_monitoring_task` | `target_kind: zone/project/road, target_id, metric: str(1..64), interval_minutes: int 5..1440, reason, incident_id?` | as above | insert `tasks` kind `monitoring` with `target_kind`, `target_id`, `metric`, `interval_minutes`, title `"Monitor <metric> on <kind> <id>"` | an open monitoring task exists for same `(target_kind, target_id, metric)` | task row open with the interval | auto |
| `create_construction_restriction` | `project_id, kind: halt/depth_limit, max_depth_m?: float > 0, reason, incident_id?` | project exists; `kind == depth_limit` without `max_depth_m` → reject `"max_depth_m is required for kind 'depth_limit'"`; `kind == halt` with `max_depth_m` → reject `"max_depth_m only applies to kind 'depth_limit'"`; `max_depth_m > planned_depth_m` → reject; incident open if given | insert `construction_restrictions` (active); `halt` → `project.status = halted`; `depth_limit` → `project.depth_limit_m = min(existing or inf, max_depth_m)` | an active restriction with identical `(project_id, kind, max_depth_m)` exists | restriction active; project status/limit as expected | required |
| `issue_preventive_alert` | `zone_id, level: advisory/warning/evacuate, message: str(1..500), incident_id?` | zone exists; incident open if given | insert `alerts` | an alert with identical `(zone_id, level, message)` exists | alert row exists | **auto for `advisory`, required for `warning` and `evacuate`** (overrides `requires_approval`) |

### Evacuation (`tools/evacuation.py`)

| Tool | Input | Validation | Effect | Unchanged when | Verify | Approval |
|---|---|---|---|---|---|---|
| `create_evacuation_order` | `zone_id, level: voluntary/mandatory, reason, shelter_id?, incident_id?` | zone exists; shelter exists **and is open** if given (reject `"shelter 'S-1' is not open; open it first"`); incident open if given | no active order for zone → insert (active); active order with lower level → update `level`, `reason`, `updated_at` in place (D10) | active order exists with same or higher level | active order for zone with level ≥ requested | required |
| `create_evacuation_task` | `zone_id, description: str(1..500), priority, assigned_crew_id?` | an active evacuation order exists for the zone else reject `"no active evacuation order for zone 'riverside'"`; crew exists if given (no crew status change) | insert `tasks` kind `evacuation` linked to that order (`evacuation_order_id`, `incident_id` from the order) | an open evacuation task with the same description exists for that order | task row open | auto |

### Incidents (`tools/incidents.py`)

| Tool | Input | Validation | Effect | Unchanged when | Verify | Approval |
|---|---|---|---|---|---|---|
| `create_incident` | `zone_id, hazard, band: watch/warning/critical, title: str(1..120), summary: str(1..1000)` | zone exists | insert `incidents` (open, opened_at=updated_at=now) | an open incident exists for `(zone_id, hazard)` (result's `after` shows that incident) | incident row open | auto |
| `update_incident` | `incident_id, band?, status?: open/closed, summary?` | incident exists; at least one field given; incident `closed` → reject any update (`"incident 'inc_x' is closed"`) | apply given fields; `status=closed` sets `closed_at=now`; always `updated_at=now` when changed | every given field already equals the current value | fields equal requested values | auto |
| `create_emergency_task` | `incident_id, title: str(1..120), description: str(1..500), priority, zone_id?, assigned_crew_id?` | incident open; zone exists if given else defaults to the incident's zone; crew exists if given | insert `tasks` kind `emergency` | an open emergency task with the same title exists for the incident | task row open | auto |

`priority` defaults to `medium` wherever it appears. `create_task(...)` in `common.py` is the single
insertion helper for the four task kinds.

## 10. Registry

`ToolRegistry` holds tools by name; `register` rejects duplicate names. `build_registry()` returns a
new registry with all 21 tools (no module-level mutable state; the app will hang it on `app.state`).

`registry.describe() -> list[ToolSpec]` with `ToolSpec(name, description, kind: "read"|"action",
approval: "auto"|"required"|"conditional", input_schema: dict)` where `input_schema` is
`Input.model_json_schema()`. `conditional` is reported when the tool overrides `requires_approval`
(only `issue_preventive_alert`). This is what `recommend` will hand to the LLM later.

`registry.action(name)` / `registry.read(name)` return the typed tool or raise `KeyError`.

## 11. Testing strategy

- Real PostgreSQL from `docker-compose.yml` (image `pgvector/pgvector:pg16`, already cached locally),
  host port 5433. Tests use `TEST_DATABASE_URL`
  (default `postgresql+psycopg://gridline:gridline@localhost:5433/gridline_test`). The session fixture
  creates the `gridline_test` database if missing (connect to the `postgres` database with
  `AUTOCOMMIT`), then drops and creates the schema once per session using `asyncio.run` in a
  **sync** session-scoped fixture, so no async engine is shared across event loops.
- **Windows:** psycopg async refuses the default `ProactorEventLoop` (verified on this machine on
  2026-09-26). pytest-asyncio 1.4 deprecates overriding the `event_loop_policy` fixture, so
  `conftest.py` implements the `pytest_asyncio_loop_factories(config, item)` hook and returns
  `{"selector": asyncio.SelectorEventLoop}` on `sys.platform == "win32"` (`{"default":
  asyncio.new_event_loop}` elsewhere). The sync session fixture runs its coroutine with
  `asyncio.Runner(loop_factory=<same factory>)`, never `asyncio.run` or a policy. This exact setup
  was spiked on 2026-09-26 and passes with `filterwarnings = error`.
- `pytest-asyncio` in `auto` mode, `asyncio_default_fixture_loop_scope = "function"` (unset is a
  deprecation warning, hence an error), function-scoped loops. Per-test fixtures: `engine` (fresh
  `AsyncEngine`, disposed after), `session_factory`, `seeded` (truncate all + seed from the YAML),
  `session` (an `AsyncSession` for the tool call) and `check_session` (a **second** session used only
  to read state back, so tests prove the commit reached the database rather than the identity map).
- Executor tests use a small test-only `ActionTool` defined in the test module (sets a road's
  `closure_reason`) to cover: validation rejection, approval rejection, idempotent replay, unchanged,
  failed (apply raises) with rollback, rejected via `ToolRejected` from `check`, audit row content
  (before/after/affected/actor/approval_id), and that rejected/failed rows do not block a retry.
- Each tool module has tests for: executed path (state read back through `check_session`), unchanged
  path, every distinct rejection message, approval enforcement for required tools, `verify()` passing
  after execution and failing after the state is tampered with through `check_session`.
- Executor tests also cover `record_verification`: the stored `verification_json` matches the
  `VerificationResult`, and an unknown action id raises `KeyError`.
- Registry test: all 21 names present, kinds and approval modes match §9, every `input_schema` has
  `additionalProperties: false`.
- Seed tests: YAML loads into `CitySeed`; row counts per table; foreign keys resolve.

## 12. Configuration, dependencies, commands

`backend/pyproject.toml`: python `>=3.13`; runtime deps `sqlalchemy[asyncio]>=2.0,<2.2`,
`psycopg[binary]>=3.2`, `pydantic>=2.11`, `pydantic-settings>=2.6`, `pyyaml>=6`; dev deps `pytest>=8`,
`pytest-asyncio>=1.0`, `pyright>=1.1.400`, `ruff>=0.11`, `types-pyyaml`. Ruff: line length 110,
target py313, rules `E, F, I, UP, B, SIM`. Pyright: `strict = ["gridline"]`, tests at `basic`.
Pytest: `asyncio_mode = "auto"`, `testpaths = ["tests"]`, `filterwarnings = ["error"]` so output stays
pristine.

`Settings` (pydantic-settings, `env_file = backend/.env`): `database_url` (default the 5433 URL for
database `gridline`), `test_database_url` (default the `gridline_test` URL).

Commands (from `backend/`): `uv run pytest`, `uv run pyright`, `uv run ruff check .`,
`uv run ruff format --check .`. From repo root: `docker compose up -d db`.

## 13. ARCHITECTURE.md updates

§4 gains the new tables (`hospitals`, `ambulances`, `bed_reservations`, `evacuation_orders`,
`construction_restrictions`, `tasks`) and the extended `actions` columns; `crews` gains `kind`.
§10 replaces its tool table with the 22-tool catalogue and approval modes from §9 and notes that
`deploy_pumps` is pending. §11 lists the new post-conditions. Nothing else changes.

## 14. Non-goals

No API routes, no event publication, no simulation coupling, no approval records, no LLM code, no
frontend. No `release_hospital_beds`, `lift_evacuation_order`, `lift_construction_restriction` or
`complete_task` tools (natural follow-ups once the agent needs them).
