# Live Agent Workflow (MVP): Design

Date: 2026-09-26. Status: design approved in chat; this written spec awaits review.
Implements an MVP slice of ARCHITECTURE.md §8 (LangGraph agent), §9 (LLM provider) and §12 (events) with
a local Ollama model, and a dashboard panel that shows the real graph execution step by step.

## 1. Purpose and scope

When a disaster is triggered, the operator sees a **LIVE AGENT WORKFLOW** panel that walks through eleven
steps as the LangGraph run executes them, each showing the output that step actually produced:

```
 1 EVENT RECEIVED          5 AI REASONING            9 EXECUTING ACTIONS
 2 SITUATION ANALYSIS      6 THREAT ASSESSMENT      10 VERIFYING
 3 KNOWLEDGE GRAPH QUERY   7 ACTION PLAN            11 COMPLETED
 4 RAG EVIDENCE RETRIEVED  8 WAITING FOR HUMAN APPROVAL  [ APPROVE ACTIONS ]
```

Every step update is a real event published by the backend while the graph runs, delivered over the
existing WebSocket. Nothing on the panel is scripted or replayed.

**In scope**

- LLM provider layer (`gridline/llm/`): Ollama over its HTTP API, plus a mock provider backed by the
  existing heuristic reasoner, used as a labelled fallback.
- The incident graph grown from `observe → retrieve → assess` to eleven nodes, one per panel step,
  with a LangGraph `interrupt()` approval gate, tool execution and tool verification.
- `AgentRunner`: starts a run per `infrastructure.failure`, translates LangGraph's task stream into
  `agent.step` events, resumes on the operator's decision.
- Contract: event type `agent.step`, run state in the WebSocket `sim.snapshot`, one approval route.
- Frontend `WorkflowPanel` with the approve / reject control.
- Tests, demo smoke extension, docs (CLAUDE.md, ARCHITECTURE.md) and a local Ollama-on-Vulkan setup note.

**Out of scope (MVP gaps, accepted in review)**

- **Durable approvals.** LangGraph `InMemorySaver`; a backend restart loses a waiting run.
- **Concurrency.** One run at a time; a failure arriving while a run is active (including waiting for
  approval) is logged and does not start a second run.
- **Re-plan.** A failed verification is shown in red and reported by COMPLETED, but does not loop back to
  `recommend`. This is a known exception to non-negotiable 6 until the re-plan milestone.
- The pending dashboard contract (`openapi.pending.yaml`: `agent.node.*`, `approval.*`, `action.*`,
  incidents) stays pending; the Incident, Approvals and Actions panels are unchanged.
- Simulation coupling: tools change the database, not the running simulation (unchanged from §10).
- Threat detection before failure (§5 detector): the trigger is a failure event.
- LIVE mode (Open-Meteo) produces no failures, so no runs start there.

## 2. Decisions

| # | Decision | Why |
|---|---|---|
| D1 | The LLM is a local Ollama model (`qwen2.5:7b-instruct`, already pulled), called over Ollama's HTTP API with `urllib` in a worker thread, as `sources/open_meteo.py` does. No LLM client library; no Anthropic provider is built. | User instruction; supersedes CLAUDE.md's "anthropic SDK only" rule, which is updated (§11). |
| D2 | If an LLM call fails (unreachable, timeout, invalid output), that node falls back to the mock provider and says so in its output (`provider: "mock"`, `fallback_reason`). | User choice: the demo always completes and the failure stays visible. |
| D3 | A new event type `agent.step` and `Workflow*` schema names, instead of realizing the pending `agent.node.*` contract. | User choice (approach A): smallest change that shows the real execution. Names are prefixed because `ThreatAssessment`, `Claim`, `VerificationResult`, `ActionVerification` … already exist in `openapi.pending.yaml`, and the type generator fails on a collision. |
| D4 | Eleven graph nodes map one-to-one to the eleven panel steps. | The panel is then a direct view of LangGraph's task stream, with no translation layer to fake or get wrong. |
| D5 | Step events come from LangGraph's own `astream(..., stream_mode="tasks")` (task start, result, error, interrupts), not from wrappers inside the nodes. | "Consume the actual LangGraph execution state". Nodes stay plain functions returning state updates. |
| D6 | `recommend` chooses from a **candidate list** of valid tool calls built in code from the knowledge graph, the hazard and the tool registry. The model decides which to take and writes each rationale and citation list. | A 7B local model cannot invent a tool, an argument or an entity ID; every chosen call passes the tool's input validation. Candidates are derived from city data, not scripted per scenario. |
| D7 | The JSON schema sent to Ollama constrains `citation_ids` to an enum of the IDs present in the input and `candidate_id` to the candidate IDs. The grounding validator still runs on every output. | Grammar-constrained decoding makes ungrounded IDs impossible for Ollama; the validator keeps non-negotiable 4 for any provider. |
| D8 | Threat level uses the domain's `Band` vocabulary (`normal`, `watch`, `warning`, `critical`); the panel reads "Landslide risk: CRITICAL". | `Severity` is a sensor-band label ("never a threat assessment"); `Band` is the threat vocabulary in `tools/vocab.py` and the pending contract. Override if you want a HIGH/LOW scale. |
| D9 | Nothing executes before the operator decides, including auto-approval tools; one decision covers the plan. | Simplest correct reading of non-negotiable 5 for a demo. Actions run with `actor="agent"` and the run's `approval_id`, recorded on each `actions` row. |
| D10 | The current run is part of the WebSocket `sim.snapshot` payload (`agent_run`); there is no separate GET route. | `sim.snapshot` is sent per connection only, so a browser that connects mid-run is brought up to date with no second source and no race. |
| D11 | No commits unless asked (CLAUDE.md). Work continues on a feature branch `feature/live-agent-workflow` cut from the current `main` working tree. | CLAUDE.md "commit only when asked" overrides the brainstorming skill's "commit the spec". |

## 3. Environment: Ollama on Vulkan

Found during design: Ollama had auto-updated 0.34.1 → 0.34.4 overnight and the silent installer was cut
off mid-copy (`upgrade.log` ends at 00:33 inside `rocm_v7_1`), so `lib/ollama/vulkan` was never
extracted and the server fell back to CPU. Fixed by re-running the signed 0.34.4 installer to
completion; the server log now reports `library=Vulkan … AMD Radeon 760M Graphics` and `ollama ps`
shows `100% GPU` (qwen2.5 7B: about 8 tok/s generation).

The Radeon 760M iGPU needs, in the user environment before the Ollama server starts (already set):
`OLLAMA_VULKAN=1`, `OLLAMA_IGPU_ENABLE=1`, `OLLAMA_KEEP_ALIVE=30m`, `OLLAMA_FLASH_ATTENTION=1`,
`OLLAMA_KV_CACHE_TYPE=q8_0`, `OLLAMA_NUM_PARALLEL=3`. Check: `ollama ps` → PROCESSOR `100% GPU`.
If it says CPU, check `%LOCALAPPDATA%\Programs\Ollama\lib\ollama\vulkan` exists and the server log's
`inference compute` line. This goes into CLAUDE.md as an environment note.

At about 8 tok/s, generation dominates latency, so outputs are kept short (§5.2): target under 60 s
per LLM step, 180 s timeout.

## 4. LLM provider layer (`gridline/llm/`)

```python
class LLMProvider(Protocol):
    name: str                     # "ollama" | "mock"
    model: str | None
    async def complete_structured(self, *, system: str, user: str, schema: dict[str, Any],
                                  output: type[T]) -> T: ...
```

- `ollama.py`: `OllamaProvider(host, model, timeout_s)`. `POST {host}/api/chat` with
  `stream: false`, `format: <schema>`, `keep_alive: "30m"`,
  `options: {temperature: 0, num_ctx: 8192, num_predict: 1024}`, messages `[system, user]`.
  Parses `message.content` with `output.model_validate_json`. Raises `LLMError` on connection error,
  timeout, an `error` field, or validation failure. Runs `urllib` in `asyncio.to_thread`.
- The schema is built per call: the Pydantic model's JSON schema with the `citation_ids` items and
  `candidate_id` narrowed to enums of the IDs in this run's input (D7).
- There is no mock provider class: the mock path is the existing `HeuristicReasoner` (§5.2), which the
  LLM nodes call when the provider is absent (`llm_provider=mock`) or raises `LLMError`.
- `prompts/reason.md`, `prompts/recommend.md`: Markdown prompts, rendered with `str.format`-style
  fields from the node's context. They instruct: cite only the given IDs, output the decision and
  explanation only, and keep it short.
- Settings (`config.py`, `backend/.env`): `llm_provider: Literal["ollama", "mock"] = "ollama"`,
  `ollama_host = "http://127.0.0.1:11434"` (IPv4; `localhost` can stall on `::1`),
  `ollama_model = "qwen2.5:7b-instruct"`, `llm_timeout_seconds = 180`.
  `llm_provider=mock` skips Ollama entirely (offline runs and tests).

## 5. The graph (`gridline/agents/`)

### 5.1 State

`WorkflowState` (TypedDict, replaces `ReasoningState`): `run_id`, `trigger_event` (the failure `Event`),
`world` (`WorldSnapshot`), `recent_events`, then filled by nodes: `trigger` (`ThreatTrigger`),
`signals`, `graph` (`KgSubgraph`), `retrieved`, `context` (`ReasoningContext`), `reasoning`
(`ReasoningResult`), `assessment`, `candidates`, `plan`, `decision`, `results`, `verification`, and
`step_output` (the display output of the node that just ran; the runner reads it from the task result).

### 5.2 Nodes

| # | Node | Kind | Does | `step_output` model (`node` discriminator) |
|---|---|---|---|---|
| 1 | `receive` | code | Parses the failure into a `ThreatTrigger`; resolves asset and zone names from the city. | `WorkflowReceiveOutput`: `event_id, hazard, failure_kind, asset {table,id,name}, zone_id, zone_name, description, sim_time, citation_id` |
| 2 | `observe` | code | `latest_signals(recent_events)`; a headline naming the top three signals by severity in plain words (metric, value, unit, source, sensor band). | `WorkflowObserveOutput`: `headline, signals[{id, event_type, source, zone_id, severity, summary}]` |
| 3 | `query_graph` | code | `kg.traverse(asset, max_depth=3)`; builds chains `project → asset → drain → downstream zone` (each part present only if the graph has it). | `WorkflowGraphOutput`: `start {table,id,name}, entity_count, edge_count, paths[{nodes[{table,id,name}], relations[str], citation_ids[]}]` |
| 4 | `retrieve` | code | Existing `retrieve_evidence` (three hazard queries, filters, dedupe, top 8). | `WorkflowEvidenceOutput`: `queries[], chunks[{chunk_id, document_id, document_title, section, kind, similarity}]` |
| 5 | `reason` | LLM | Builds `ReasoningContext` (signals relevant to the graph, graph, evidence, state facts); asks the provider for `ReasoningResult {summary ≤ 600 chars, band, confidence 0..1, claims ≤ 5 [{text ≤ 240, citation_ids ≥ 1}]}`. On `LLMError`: heuristic reasoner, labelled. | `WorkflowReasoningOutput`: `provider, model, fallback_reason, duration_ms, summary, claims[{text, citation_ids}]` |
| 6 | `assess` | code | `validate_citation_ids` over all claims; drops claims citing unknown IDs and lists those IDs; affected zones = downstream zones of the graph paths plus the trigger zone. | `WorkflowAssessmentOutput`: `hazard, band, confidence, grounded, cited_count, ungrounded_ids[], affected_zone_ids[]` |
| 7 | `recommend` | LLM | Builds candidates (§5.3); asks the provider for `PlanChoice {actions 1..6 [{candidate_id, rationale ≤ 280, citation_ids ≥ 1}]}`; validates each chosen call through the tool's `Input` model. On `LLMError`: heuristic choice, labelled. | `WorkflowPlanOutput`: `provider, model, fallback_reason, duration_ms, candidate_count, actions[{action_id, candidate_id, tool, input, label, rationale, citation_ids, requires_approval}]` |
| 8 | `approval_gate` | interrupt | `decision = interrupt(<waiting output>)`; returns the decision. | `WorkflowApprovalOutput`: `approval_id, action_ids[], decision: approve \| reject \| null, note, decided_at` |
| 9 | `execute` | tools | For each planned action in order: `execute_action(tool, input, ctx)` with `actor="agent"`, `approval_id`, `run_id`, sim time; idempotency key `"{run_id}:{candidate_id}"`. | `WorkflowExecutionOutput`: `results[{action_id, tool, status: executed \| unchanged \| rejected \| failed, message, affected_entities[]}]` |
| 10 | `verify` | tools | For each `executed`/`unchanged` result: `tool.verify(...)`, then `record_verification`. Plan status: `verified`, `partially_verified` or `failed`. | `WorkflowVerificationOutput`: `status, per_action[{action_id, tool, status, checks[{name, passed, expected, observed}]}]` |
| 11 | `complete` | code | Reads every affected entity fresh from the DB (`tools.snapshot.snapshot`). Outcome `completed`, `completed_with_failures`, or `rejected`. | `WorkflowCompletionOutput`: `outcome, entities[{kind, id, name, fields}]` |

Edges: linear `receive → … → approval_gate`; `approval_gate → execute` on approve, `→ complete` on reject;
`execute → verify → complete → END`.

The mock path extends `HeuristicReasoner` with `reason(context) -> ReasoningResult` (band from the worst
relevant signal: critical → critical, high → warning, moderate → watch, else normal; claims from its
contributing factors) and `recommend(context, assessment, candidates) -> PlanChoice` (takes every
candidate, rationale and citations from the candidate's own evidence). It reads the same inputs as the
LLM; nothing is scenario-specific.

### 5.3 Candidate actions

`candidates(hazard, graph, world) -> list[Candidate]`, at most 10, each
`{candidate_id, tool, input (without reason/message), label, citation_ids}`:

- `halt:<project>` → `create_construction_restriction {project_id, kind: "halt"}` for each project the
  graph links to the threatened asset whose live status is not already halted. Cites the KG edge and the
  project's state fact.
- `inspect:<kind>:<id>` → `create_inspection_order {target_kind, target_id, priority: "high"}` for the
  threatened asset and for each drain leaving it. Cites the trigger and the edge.
- `monitor:<kind>:<id>` → `create_monitoring_task {target_kind, target_id, metric, interval_minutes: 15}`
  for the threatened asset; metric by target kind (`slope` → `soil_saturation`, `channel` →
  `flow_capacity`, `bridge` → `scour`, `road` → `debris`).
- `alert:<zone>` → `issue_preventive_alert {zone_id, level: "warning"}` for the trigger zone and each
  downstream zone. Cites the path edges.

The model's rationale becomes the tool's `reason` (restriction, inspection, monitoring) or `message`
(alert), truncated to the 500-character limit. Action IDs are `"{run_id}-a{n}"`.

## 6. Runner (`gridline/agents/runner.py`)

`AgentRunner(bus, city, sim_runner, kg, retriever, sessions, registry, provider)` on `app.state.agent`.

- `start()` subscribes to `infrastructure.failure` on the bus; `shutdown()` cancels the tasks.
- On a failure event with no active run: create `run_id = "run-<8 hex>"` and a `WorkflowRun`, take a
  world snapshot and the last 500 bus events from its own rolling buffer (it also subscribes to
  `weather.`, `environment.` and `infrastructure.` to keep that buffer), and start the graph task.
- It drives the graph with `graph.astream(input, config={"configurable": {"thread_id": run_id}},
  stream_mode="tasks")` and maps each task event to one `agent.step` event:
  - task start → `status: running`, `output: null`
  - task result with interrupts → `status: waiting`, `output` = the interrupt value
  - task result with error → `status: failed`, `error` = the message; the run ends
  - task result → `status: done`, `output` = `result["step_output"]`
- `decide(run_id, decision)` checks that the run's `approval_gate` step is `waiting` (404 unknown run,
  409 otherwise), then streams `Command(resume=decision)` in a new task, the same way.
- An exception outside a node (for example the stream itself) is published as a `failed` step on the
  node that was running and logged; it is never swallowed.
- Run status is derived from the steps, never stored twice: `failed` if any step failed; `waiting` if
  `approval_gate` is waiting; `rejected` or `completed` when `complete` is done (by its outcome);
  otherwise `running`. The same rule is written once in the backend and once in the frontend.

## 7. Contract

- `EventType.AGENT_STEP = "agent.step"`; envelope `source="agent"`, `location` = trigger zone,
  `severity="info"`, `incident_id=None`. Payload model `WorkflowStep`:
  `run_id, node (WorkflowNode, 11 literals), index 1..11, status (running | done | waiting | failed),
  started_at, finished_at | null, duration_ms | null, output (discriminated union on node) | null,
  error | null`. Registered in `PAYLOAD_MODELS` and in the `Event` union in `api/event_models.py`
  as `AgentStepEvent`.
- The step models live in a leaf module `gridline/agents/steps.py` (imports only pydantic and leaf
  model modules) so `events/payloads.py` can import it without a cycle.
- `WorkflowRun`: `run_id, trigger_event_id, hazard, zone_id, asset_id, provider, model, started_at,
  steps[WorkflowStep]` (the latest state of each node reached, in index order).
- `sim.snapshot` payload gains `agent_run: WorkflowRun | null` (default null; the mock fixtures stay valid).
- `POST /api/agent/runs/{run_id}/approval`, body `WorkflowDecision {decision: approve | reject, note?}`,
  returns 202 with the `WorkflowRun` (the graph resumes in the background; progress arrives as events).
  404 unknown run, 409 not waiting. Operation id `decideRunApproval`.
- `backend/scripts/export_contract.py` regenerates `frontend/openapi.json`; `npm run gen:api` regenerates
  `schema.d.ts`. `openapi.pending.yaml` is not edited.

## 8. Frontend

- `live/types.ts`: `agentRun: WorkflowRun | null` in `LiveState`. `applySnapshot` takes it from
  `payload.agent_run`; `applyAgentStep` (new `live/applyAgentStep.ts`) upserts the step by `node`, and an
  event with a different `run_id` starts a new run. `runStatus(run)` implements §6's rule.
- `api/client.ts` + `http.ts`: `decideRunApproval(runId, decision)`; `MockApiClient` rejects (mock mode has
  no agent, so the panel never appears there); `test/fakeClient.ts` records calls.
- `components/workflow/`: `WorkflowPanel` (header: "LIVE AGENT WORKFLOW", trigger, provider badge; amber
  "mock — Ollama unavailable: …" when a step fell back), `WorkflowStepRow` (number, label, status icon:
  pending / spinner / done / waiting / failed, duration), and one small presentational body per node:
  trigger facts; observe headline and signals; graph paths as entity chips joined by arrows with the
  relation; evidence titles and sections as citation chips; reasoning summary and claims with citation
  chips; band chip and confidence; action list; approval controls; execution results; verification checks
  (expected vs observed); final entity state. Steps not reached are shown dimmed; the active step scrolls
  into view. A hook `useDecideRunApproval` wraps the mutation (TanStack Query).
- Step 8 shows **[ APPROVE ACTIONS ]** (primary) and **Reject** (secondary) while waiting; both disable
  while the request is in flight; an error from the route is shown inline.
- `App.tsx`: the `incident` slot renders `WorkflowPanel` once `agentRun` is set, `IncidentPanel` before.
- Built with the frontend-design skill inside the existing tokens and `ui/` components.

## 9. Error handling

| Failure | What the operator sees |
|---|---|
| Ollama unreachable, timeout, invalid JSON | Step 5 or 7 done with the mock output, amber badge, `fallback_reason` text |
| Postgres down or KG query error | Step 3 `failed` with the error; run status `failed` |
| No corpus indexed | Step 4 done with "no documents retrieved"; reasoning proceeds on the rest |
| Model cites an unknown ID (mock or future provider) | Step 6 lists the rejected IDs; those claims are dropped |
| Tool rejects or fails | Step 9 shows `rejected`/`failed` with the tool's message; step 10 skips it; outcome `completed_with_failures` |
| Verification fails | Step 10 red with expected vs observed; outcome `completed_with_failures` |
| Approve on a run that is not waiting | Route 409; inline error on the panel |
| Failure event while a run is active | Logged at WARNING; no second run (MVP gap) |

## 10. Testing and verification

Tests are written before the code they cover (TDD).

**Backend** (`uv run pytest`, real Postgres test DB as the existing suites use)
- `test_llm_ollama.py`: request body (model, `format` schema with enums, options), parsing, and
  `LLMError` on connection error, timeout, `error` field and invalid JSON (HTTP layer faked).
- `test_agent_candidates.py`: candidates from the real seeded KG for SL-HV-1 include
  `halt:PR-HT2`, `inspect:slope:SL-HV-1`, `monitor:slope:SL-HV-1`, `alert:Z-RS`; every candidate's input
  validates against its tool.
- `test_agent_workflow.py` (integration: real KG, RAG with the hashed embedder, tools and DB; LLM
  replaced by a scripted fake provider): trigger → the bus receives `agent.step` for nodes 1..8 in order,
  each `running` then `done`, and 8 `waiting`; the DB is unchanged before the decision; approve →
  9..11 `done`, PR-HT2 `halted` in a fresh session, `outcome: completed`. A second test: reject → no
  `actions` rows, `outcome: rejected`. A third: provider raises → steps 5 and 7 `provider: "mock"` with a
  `fallback_reason`, run still completes.
- `test_api_agent.py`: 404, 409, 202 happy path; `sim.snapshot` carries `agent_run`.
- Event and contract tests: `agent.step` payload validation and OpenAPI export (existing suites extended).
- `test_llm_ollama_live.py`, marker `ollama`, skipped when Ollama is unreachable: real `reason` and
  `recommend` calls on the landslide context return schema-valid, grounded output.
- `scripts/demo_smoke.py` gains an agent pass with `llm_provider=mock` against the DB: failure → approve
  → verified. It must stay green.

**Frontend** (`npm test`, `npm run typecheck`, lint)
- `applyAgentStep.test.ts`: upsert order, new run replaces old, snapshot seeding, `runStatus`.
- `WorkflowPanel.test.tsx`: renders each step's output from fixture events; APPROVE calls
  `decideRunApproval`; waiting, failed and fallback states render.

**Done when** all suites, pyright, ruff, typecheck and lint are clean; the smoke script is green; and in
the running app, injecting "Landslide at Hillview Terrace" shows all eleven steps with qwen2.5 on Vulkan
(`ollama ps` → GPU), APPROVE executes and verifies, and COMPLETED shows PR-HT2 halted. A screenshot of
the finished run is saved to `docs/screenshots/`.

## 11. Documentation

- CLAUDE.md: the LLM bullet becomes "LLM calls go through `gridline/llm/`: Ollama over its HTTP API (no
  client library), mock fallback"; default model `qwen2.5:7b-instruct`; the Ollama-on-Vulkan environment
  note from §3; the model-routing line is unchanged.
- ARCHITECTURE.md: §8 (eleven nodes, runner, MVP gaps), §9 (Ollama and mock providers, A3/A4
  assumptions), §12 (`agent.step`, snapshot `agent_run`, approval route).

## 12. Files

New: `gridline/llm/{__init__,base,ollama}.py`, `gridline/llm/prompts/{reason,recommend}.md`,
`gridline/agents/{steps,candidates,runner}.py`, `gridline/agents/nodes/{receive,query_graph,reason,recommend,approval,execute,verify,complete}.py`,
`gridline/api/agent.py`, `frontend/src/components/workflow/*`, `frontend/src/live/applyAgentStep.ts`, tests above.
Changed: `agents/graph.py`, `agents/state.py`, `agents/reasoner.py`, `agents/nodes/{observe,retrieve,assess}.py`,
`config.py`, `main.py`, `api/deps.py`, `api/event_models.py`, `events/{types,payloads,websocket}.py`,
`tests/test_reasoning_graph.py`, `scripts/demo_smoke.py`, `frontend/openapi.json`, `frontend/src/api/*`,
`frontend/src/live/{types,applyEvent}.ts`, `frontend/src/App.tsx`, `frontend/src/mock/MockApiClient.ts`,
`frontend/src/test/fakeClient.ts`, CLAUDE.md, ARCHITECTURE.md.
