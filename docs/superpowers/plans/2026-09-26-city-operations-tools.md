# City Operations Action Tool Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The 21 typed tools through which the agent (and later the operator) reads and changes the state of synthetic Nandipur in PostgreSQL: every action validates input and current city state, mutates the database in one transaction, writes an append-only audit row and returns an `ActionResult` with before/after state.

**Architecture:** `gridline/tools` sits on the existing data layer. Seven new operations tables live in `gridline/db/models/operations.py` on the single `Base`; the seeded asset tables (`roads`, `projects`, `crews`, `ambulances`, `shelters`, `hospital_beds`) gain nullable live columns. A generic `execute_action(tool, raw, ctx)` owns validation, idempotent replay, approval enforcement, snapshots, audit and commit; each tool only implements `check` (load + validate, raise `ToolRejected`), `apply` (mutate, no commit) and `verify` (re-read the database). `build_registry()` returns all 21 tools with JSON schemas. No routes, events, simulation coupling, LangGraph, RAG or frontend.

**Tech Stack:** Python 3.13, uv, SQLAlchemy 2.x async + psycopg 3, PostgreSQL 16 (pgvector image, host port 5433), Pydantic v2, pytest + pytest-asyncio, pyright strict, ruff.

**Spec:** `docs/superpowers/specs/2026-09-26-city-operations-tools-design.md`. The spec predates the data layer; where they disagree the **existing code wins** and the adaptations below apply.

## Adaptations to the existing data layer (read before any task)

| Spec | This plan | Why |
|---|---|---|
| §3 skeleton (pyproject, settings, engine, models.py, seed.py, YAML, compose) | Reuse `gridline/config.py`, `gridline/db/{base,engine,schema}.py`, `gridline/db/models/*`, `gridline/db/seed/`, `data/city/*.yaml`, `tests/conftest.py`. No second Base, seed or model for an existing table. | Already built by the data-layer plan. |
| §4 table shapes for zones/roads/projects/crews/ambulances/shelters/hospitals | Keep the data layer's tables and ids (`Z-HV`, `RD-01`, `PR-HT2`, `C-1`..`C-8`, `AMB-01`..`AMB-14`, `S-1`..`S-8`, `H-1`..`H-5`). Add only nullable live columns: roads `closure_reason, closed_at, incident_id`; projects `depth_limit_m`; crews `target_zone_id, task, incident_id, dispatched_at`; ambulances `target_zone_id, destination_hospital_id, incident_id, dispatched_at`; shelters `opened_at, incident_id`; hospital_beds `reserved` (default 0). | Seed values come from the YAML untouched (`None`/0). |
| D1 rescue teams = `crews.kind == "rescue"` | Rescue teams = crews with `kind in {"rescue", "hill_rescue", "boat"}` (C-1, C-4, C-7). | The dataset has eight crew kinds; three of them rescue people. |
| D9 `hospitals.reserved_beds` counter | Beds are per type in `hospital_beds`. `reserve_hospital_beds(..., bed_type="general")` moves beds from `available` to a new `reserved` column on that `hospital_beds` row and inserts `bed_reservations`. | Keeps the before/after legible on one row and uses the real bed types. |
| Road status `open`/`closed` | Vocabulary `open`/`blocked`/`closed` (simulation `RoadStatusValue`). `reopen_road` refuses a `blocked` road. "Open access road" = an `open` road whose `zone_id`/`from_zone_id`/`to_zone_id` include the zone and which links it to another zone. | Matches `events/payloads.py` and the road graph (RD-01 is Hillview's only access). |
| Project status `active`/`halted` | Data has `active`/`completed`/`planned`; restrictions refuse `completed` projects, `depth_limit` refuses projects without an excavation depth or a limit above planned / below current depth. | Real project rows. |
| Hazards `landslide/flood/fire/storm/other` | `gridline.city.schema_history.Hazard` (`flood, flash_flood, landslide, cyclone, urban_fire`). | One hazard vocabulary across corpus, RAG and incidents. |
| Inspection/monitoring targets | `zone, road, bridge, channel, slope, project, shelter, hospital` for both tools; the task's zone is the target's zone (`upstream_zone_id` for a channel). | D-7, BR-4 and SL-HV-1 are the demo's assets. |
| `verify(inp, ctx)` | `verify(inp, ctx, result)`; created/existing ids come from `result.after` (our own audit data, never model output). | A created task or reservation has a server-generated id. |
| `Plan.data: dict[str, Any]` | `Plan[P]` generic, `ActionTool[I, P]`, so `apply` gets typed rows. | pyright strict. |
| Extra state checks | `open_shelter` refuses a shelter whose `access_road_id` is not open; `dispatch_ambulance` refuses a destination hospital whose access road is not open; `close_shelter` refuses a shelter that is the destination of an active evacuation order; `create_evacuation_order` refuses a shelter inside the evacuated zone. Idempotency keys reused for a different tool or input are rejected. | "Validate current city state" with the relations the data actually has. |
| D7 branch/commits | Work in the current checkout; **no commits**. | Caller's instruction. |

## Global Constraints

- Synthetic data only (CLAUDE.md #1). One process, one database (#2). State changes only through tools; approval-required tools never execute without `ctx.approval_id` (#5). Verification re-reads the database (#6). Offline (#7).
- Existing suite (360 passed, 1 skipped) must stay green in any order. Tool tests commit for real, so the `tool_session` fixture restores the seeded live tables and empties the operations tables before and after each test (no per-test reseed: a reseed costs ~1 s).
- Tests prove mutation by reading back through a **second** session (`check_session`, `populate_existing=True`).
- Fully typed, `pyright` strict, `ruff check` + `ruff format --check` clean, files under ~300 lines, Pydantic v2 for every input/output (`extra="forbid"`), SQLAlchemy 2.x typed mapped classes, async, no module-level mutable state (`build_registry()` builds a new registry; constant maps are `MappingProxyType`/`frozenset`).
- Timestamps timezone-aware UTC. Created ids `<prefix>_<12 hex>`: `inc_ task_ alert_ evac_ restr_ resv_ act_`.
- Domain names only: zone, road, project, crew, ambulance, shelter, hospital, incident, alert, task, action.
- All commands from `backend/`. TDD: every step writes the failing test first and runs it to see it fail.

## Review Focus

1. Rejected and failed attempts are audited but never block a retry with the same idempotency key (Task 4 `test_rejected_then_retry_with_same_key_executes`).
2. A failure inside `apply` leaves no partial state: the mutation is rolled back and only the audit row remains (Task 4 `test_apply_exception_rolls_back_and_records_failed`).
3. Approval-required tools refuse without `approval_id`, including `issue_preventive_alert` at `warning`/`evacuate` but not `advisory` (every tool test module, Task 11 `test_alert_approval_is_conditional`).
4. A stale identity map cannot fool `check` or `verify`: the executor expires the session first, `verify` reads with `populate_existing` (Task 4 `test_check_sees_changes_made_by_another_session`, each tool's `verify` tamper test).
5. Tool tests are order-independent and leave the seeded database as they found it (Task 2 `test_restore_undoes_tool_writes`).

---

### Task 1: Operations schema

**Files:** Create `gridline/db/models/operations.py`; modify `gridline/db/base.py` (map `dt.datetime` to `DateTime(timezone=True)`), `gridline/db/models/{emergency,infrastructure,utilities,__init__}.py`; test `tests/test_operations_schema.py`.

**Interfaces:** `Incident, Alert, EvacuationOrder, ConstructionRestriction, Task, BedReservation, Action` mapped classes; `OPERATIONS_TABLES: frozenset[str]` (7 names) exported next to `EXPECTED_TABLES` (unchanged, 38). Partial unique indexes: one open incident per (zone, hazard), one active evacuation order per zone.

- [ ] Test: every operations table exists; the two partial unique indexes reject a second open incident / active order; `Base.metadata.tables == EXPECTED_TABLES | {"chunks"} | OPERATIONS_TABLES`; key columns and FKs (`crews.incident_id -> incidents`, `tasks.evacuation_order_id -> evacuation_orders`, `bed_reservations.hospital_bed_id -> hospital_beds`); `actions.idempotency_key` has a unique index; `actions.incident_id` has no FK; seeded crews/roads/shelters have `NULL` live columns and `hospital_beds.reserved == 0`. Run, see it fail.
- [ ] Implement the models (spec §4 columns, adapted as above). Run the new test and the whole suite (seed counts stay at the 38 tables).

### Task 2: Tool-test isolation fixtures

**Files:** Modify `tests/conftest.py`; create `tests/tools/__init__.py`, `tests/tools/helpers.py`, `tests/tools/test_isolation.py`.

**Interfaces:** session fixture `baseline` (rows of the six live tables read once after `seeded`); `restore(engine, baseline)` (restore live columns by primary key, then `DELETE` operations tables children-first); `tool_session` (restores before and after the test); `check_session`; `ctx` (`ToolContext` with `approval_id="apr_test"`) and `ctx_no_approval`; helpers `fresh`, `tamper`, `add_incident`, `count`.

The fixtures live in the root `tests/conftest.py`, not `tests/tools/conftest.py`: pytest 9 splits the collection tree when file arguments from different directories interleave, which hides a sub-directory conftest. They are not autouse: pytest-asyncio 1.4 fails an async autouse fixture on a sync test that follows async ones.

- [ ] Test: write a crew status, an incident and an action row through a session, run the restore, read back seed values and zero operations rows. See it fail, implement, pass.

### Task 3: Contract and snapshots

**Files:** Create `gridline/tools/__init__.py`, `gridline/tools/base.py`, `gridline/tools/snapshot.py`; test `tests/tools/test_snapshot.py`.

**Interfaces:** `ToolContext(session, actor="agent", approval_id=None, run_id=None, sim_time=None)`; `EntityRef(kind, id)` with `.key == "kind:id"`; `ActionStatus`; `ActionResult` (spec §6 plus `incident_id`); `VerificationCheck`, `VerificationResult`; `ToolRejected(reason)`; `Plan[P](refs, data, incident_id=None)`; `Applied(changed, message, created=[], incident_id=None)`; `ActionInput` (`extra="forbid"`, `idempotency_key`); `ReadInput`; `ActionTool[I, P]` (`name, description, approval_required, Input`, `requires_approval`, `check`, `apply`, `verify`); `ReadTool[I, O]` (`Input, Output, run`). `ENTITY_MODELS` (kind -> model), `row_to_dict(row)` (JSON-safe), `snapshot(session, refs) -> dict[str, dict]`.

- [ ] Tests: `row_to_dict` is JSON-safe (datetimes as ISO strings); `snapshot` keys are `kind:id`; unknown kind raises `KeyError`; missing row is omitted. Fail, implement, pass.

### Task 4: Executor

**Files:** Create `gridline/tools/executor.py`; test `tests/tools/test_executor.py` (test-only tool that sets a road's `closure_reason`, approval required, with a flag that raises in `apply`).

**Interfaces:** `execute_action(tool, raw, ctx) -> ActionResult`; `record_verification(session, action_id, result) -> None` (raises `KeyError`).

- [ ] Tests (spec §7, §11): validation rejected with flattened message and audit row; approval rejected; `ToolRejected` from check; executed (state read back via `check_session`, audit row before/after/affected/actor/approval_id/incident_id); unchanged (`before == after`, no affected); idempotent replay (`replayed=True`, one row); replay refused for another tool or different input; rejected/failed rows keep key only in `input_json` and do not block a retry; apply exception -> `failed`, rolled back; stale identity map refreshed; `record_verification` stores JSON, unknown id raises. Fail, implement, pass.

### Task 5: Shared lookups, vocabulary and views

**Files:** Create `gridline/tools/common.py`, `gridline/tools/vocab.py`, `gridline/tools/views.py`; test `tests/tools/test_common.py`.

**Interfaces:** `new_id(prefix)`, `utcnow()`, `require(session, Model, id, kind, lock=False)` and `require_zone/road/project/crew/ambulance/shelter/hospital`, `require_open_incident`, `open_access_roads(session, zone_id)`, `require_open_access(session, zone_id)`, `require_open_road(session, road_id, owner)`, `create_task(session, ...)`, `ids_in(result, kind)`, `check(name, expected, observed)` and `verification(checks)`. Literals `Priority, Band, TargetKind, AlertLevel, EvacuationLevel, RestrictionKind` and constrained string aliases. Views `CrewView, AmbulanceView, ShelterView, BedView, HospitalView, RoadView`.

- [ ] Tests: `require_*` messages (`"road 'RD-99' not found"`, `"incident 'inc_x' is closed"`), access-road rule (Z-HV loses access when RD-01 closes; Z-TH too; local RD-11 does not count). Fail, implement, pass.

### Tasks 6-12: Tool modules (one task each, same TDD recipe)

For each module: write tests for the executed path (state read back through `check_session`), the unchanged path, every distinct rejection message, approval enforcement for required tools, and `verify` passing after execution and failing after tampering through `check_session`; see them fail; implement; pass; pyright + ruff on the module.

| Task | Module / test | Tools (approval) |
|---|---|---|
| 6 | `roads.py` / `test_roads.py` | `get_road_status`, `close_road` (req), `reopen_road` (req) |
| 7 | `resources.py` / `test_resources.py` | `get_available_rescue_teams`, `dispatch_rescue_team` (req), `get_available_ambulances`, `dispatch_ambulance` (req) |
| 8 | `shelters.py` / `test_shelters.py` | `get_shelter_capacity`, `open_shelter` (req), `close_shelter` (req) |
| 9 | `hospitals.py` / `test_hospitals.py` | `get_hospital_capacity`, `reserve_hospital_beds` (req) |
| 10 | `incidents.py` / `test_incidents.py` | `create_incident`, `update_incident`, `create_emergency_task` (auto) |
| 11 | `prevention.py` / `test_prevention.py`, `construction.py` / `test_construction.py` (split to stay under 300 lines) | `create_inspection_order`, `create_monitoring_task` (auto), `issue_preventive_alert` (conditional); `create_construction_restriction` (req) |
| 12 | `evacuation.py` / `test_evacuation.py` | `create_evacuation_order` (req), `create_evacuation_task` (auto) |

Validation, effects, "unchanged" rules and post-conditions: spec §9 as adapted above.

### Task 13: Registry

**Files:** Create `gridline/tools/registry.py`; test `tests/tools/test_registry.py`.

**Interfaces:** `ToolSpec(name, description, kind, approval, input_schema)`; `ToolRegistry.register/action/read/describe/names`; `build_registry()`.

- [ ] Tests: 21 names; kinds and approval modes per spec §9 (`conditional` only for `issue_preventive_alert`); every `input_schema` has `additionalProperties: false`; duplicate registration raises; unknown name raises `KeyError`; two calls return independent registries. Fail, implement, pass.

### Task 14: Documentation

**Files:** Modify `ARCHITECTURE.md` §4, §10, §11; `backend/README.md` (short tools section).

- [ ] §4 gains the operations tables and live columns; §10 gets the contract, executor rules and the 21-tool catalogue with approval modes (`deploy_pumps` pending); §11 lists the post-conditions and `record_verification`.

### Task 15: Verification before completion

- [ ] `uv run pytest -q`; the same suite with test files in reverse order (`uv run pytest -q $(ls tests/test_*.py tests/tools/test_*.py | tac)`) to prove order independence; `uv run pyright`; `uv run ruff check . && uv run ruff format --check .`; `cd .. && uv run python scripts/demo_smoke.py`. Record the output lines.
