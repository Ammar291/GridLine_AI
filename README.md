# GridLine AI

**A disaster intelligence system for a city.** GridLine AI watches a city as it runs, spots emerging threats
(landslides, floods, cascading failures) and runs one agent loop for each threat:

```
detect → reason → predict → recommend prevention → request approval → execute → verify
```

It reasons over live city state, a knowledge graph of city assets and a RAG corpus of policies, SOPs and past
incidents, and it cites the evidence behind each claim. It changes the city only through audited tools, only after
a human approves, and it checks each change by re-reading the world.

**Everything runs on your machine.** The LLM is a local [Ollama](https://ollama.com/) model, the embeddings run on
the CPU, and no cloud API key is needed.

This is a hackathon prototype. The design is in [ARCHITECTURE.md](ARCHITECTURE.md).

![GridLine AI dashboard during the cascading landslide and flood scenario](docs/screenshots/dashboard-live-3-cascade.png)

## Two data modes, one pipeline

| Mode | City | Data | Network |
|---|---|---|---|
| **DEMO** (default) | Nandipur, a fictional city | Everything is synthetic: zones, slopes, drains, roads, crews, shelters, policies, permits and 17 historical incidents | None |
| **LIVE** | Kalyan-Dombivli, Maharashtra | Real weather from [Open-Meteo](https://open-meteo.com/) (no API key). A failed fetch shows up as "unavailable". Readings are never estimated or filled in | Required |

You can switch modes at runtime from the dashboard or with `POST /api/source`. Both modes publish the same
normalized events on one event bus, and no code after the bus checks which mode is active.

## The demo story

On Hillview Terrace, the Phase 2 construction project keeps excavating slope SL-HV-1 while the monsoon rain gets
heavier. The simulation tracks the rain, soil saturation, cut depth and slope movement. The risk indices climb
until the slope fails. Its debris blocks drainage channel D-7, and Riverside, the district below, floods.

If the project is halted in time, the landslide never happens. `scripts/demo_smoke.py` checks both outcomes.

Six **DEMO buttons** add a fact to the world (rain, a cut, a blocked drain, a fire), then run one simulated hour.
The buttons set up conditions only. The risk levels and conclusions come from the physics, the indices and the
agent:

| Button | What it does |
|---|---|
| Heavy Rain | A monsoon cell drops 20 mm/h over the whole city for three hours |
| Landslide | PR-HT2 cuts SL-HV-1 to its planned 6 m while 60 mm/h of rain falls on Hillview |
| Drainage Block | Debris blocks 70 % of drain D-7 above Riverside |
| Flash Flood | A 70 mm/h cloudburst over Hillview and Riverside for two hours |
| Industrial Fire | A solvent warehouse catches fire in Mill Road Industrial |
| Cascading Disaster | SL-HV-1 fails, its debris blocks D-7, then 40 mm/h of rain floods Riverside |

There are also four scripted scenarios: `normal_city`, `hillside_landslide`, `flash_flood` and
`cascading_landslide_flood` (the default).

## How it works

```
Simulation engine ─tick─▶ risk indices ─▶ Event bus ─▶ WebSocket /ws ─▶ React dashboard
        ▲                                      │                            │
        │                          infrastructure.failure                   │ approve / reject
        │                                      ▼                            ▼
   city tools ◀── execute / verify ◀── LangGraph agent ◀────────── POST /api/agent/runs/{id}/approval
```

It all runs in one FastAPI process with one PostgreSQL database (pgvector) and one React frontend. There are no
microservices, no message broker and no second runtime.

**The agent** ([backend/gridline/agents/](backend/gridline/agents/)) is a LangGraph graph with 11 nodes. Each node
appears as a live step on the dashboard:

```
receive → observe → query_graph → retrieve → reason → assess → recommend → approval_gate
                                                                               ├─ approve → execute → verify → complete
                                                                               └─ reject  → complete
```

- `query_graph` walks the **knowledge graph**: the seeded city tables linked through their foreign keys (assets,
  zones, projects, past incidents).
- `retrieve` pulls cited evidence from the **RAG corpus**: 37 synthetic documents chunked by section and stored in
  pgvector. Citation IDs look like `dmp-2024#s4.2`.
- `reason` and `recommend` call **Ollama** (`qwen2.5:7b-instruct` by default) over its HTTP API. Replies are
  constrained to a JSON schema, and the prompts are Markdown files in
  [backend/gridline/llm/prompts/](backend/gridline/llm/prompts/). If Ollama is unreachable or times out, a
  deterministic heuristic reasoner builds the answer from the same inputs, and the dashboard labels the step as a
  fallback.
- `approval_gate` pauses the graph until the operator approves or rejects. Approval-required tools never run
  without a recorded decision.
- `execute` changes the city only through the **tool registry**: 21 typed tools (close road, send a rescue team,
  open a shelter, halt a project, and more). Each call runs in a transaction and writes an audit row.
- `verify` re-reads the database and the simulation state and compares them with each tool's declared
  post-condition.

### AI stack

| Part | What runs it |
|---|---|
| LLM (`reason`, `recommend`) | Ollama, `qwen2.5:7b-instruct`, local, JSON-schema output, temperature 0 |
| Fallback reasoner | Deterministic heuristic that reads the same state, graph and evidence |
| Agent orchestration | LangGraph |
| Embeddings | fastembed `BAAI/bge-small-en-v1.5` on the CPU. A hashed embedder takes over if the model can't load |
| Vector store | PostgreSQL 16 + pgvector |

## Quick start

### Prerequisites

- [Docker](https://www.docker.com/), for PostgreSQL 16 with pgvector
- Python 3.13 and [uv](https://docs.astral.sh/uv/)
- Node.js 20.19+ or 22.12+ and npm (required by Vite 8)
- [Ollama](https://ollama.com/)

### 1. Ollama

```bash
ollama pull qwen2.5:7b-instruct
ollama list                    # the model should be listed
```

The Ollama desktop app serves on `http://127.0.0.1:11434`. Without the app, start the server with `ollama serve`.
The backend connects to that address by default.

On AMD or Intel GPUs, Ollama can run the model through Vulkan. Set `OLLAMA_VULKAN=1` before starting the server,
and add `OLLAMA_IGPU_ENABLE=1` for an integrated GPU. `ollama ps` shows whether the model runs on the GPU or the CPU.

### 2. Database

```bash
docker compose up -d db        # PostgreSQL + pgvector on localhost:5433
```

The container creates two databases, `gridline` and `gridline_test`, with the `vector` extension enabled in both.

### 3. Backend

```bash
cd backend
uv sync
uv run python -m gridline.db.seed --reset   # load the synthetic Nandipur dataset and corpus
uv run gridline-ingest                      # chunk, embed and index the corpus for RAG
uv run uvicorn gridline.main:app            # http://localhost:8000
```

You can check the backend at `http://localhost:8000/api/health`. The interactive API docs are at
`http://localhost:8000/docs`.

The simulation alone needs no database. The knowledge graph, RAG and the tools do, so seed before running the
agent.

### 4. Frontend

```bash
cd frontend
npm install
npm run dev                    # http://localhost:5173, proxies /api and /ws to :8000
```

`npm run dev:mock` runs the dashboard against recorded fixtures, with no backend.

To run the agent with no LLM at all, for example on a machine without Ollama, set `LLM_PROVIDER=mock` in
`backend/.env`. Every LLM step then uses the heuristic reasoner.

## Configuration

Settings are read from `backend/.env`. Copy [backend/.env.example](backend/.env.example) to start. The defaults
match the Docker container, so the file is optional.

| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | `postgresql+psycopg://gridline:gridline@localhost:5433/gridline` | Main database |
| `TEST_DATABASE_URL` | `…/gridline_test` | Database used by the tests |
| `DATA_MODE` | `demo` | Mode at startup (`demo` or `live`) |
| `LIVE_POLL_SECONDS` | `300` | How often LIVE mode polls Open-Meteo |
| `LLM_PROVIDER` | `ollama` | `ollama`, or `mock` for the heuristic reasoner only |
| `OLLAMA_HOST` | `http://127.0.0.1:11434` | Ollama server |
| `OLLAMA_MODEL` | `qwen2.5:7b-instruct` | Model used for `reason` and `recommend` |
| `LLM_TIMEOUT_SECONDS` | `180` | Time allowed for one Ollama call before the heuristic fallback takes over |
| `EMBEDDING_PROVIDER` | `auto` | `fastembed` (local ONNX), `hashed` (offline fallback) or `auto` |
| `SIM_DEFAULT_SCENARIO` | `cascading_landslide_flood` | Scenario loaded at startup |
| `SIM_TICK_SECONDS` | `1.0` | Real seconds per tick at speed 1× |
| `SIM_MINUTES_PER_TICK` | `5` | Simulated minutes per tick |
| `SIM_AUTOSTART` | `false` | Start the DEMO simulation on boot |

## API at a glance

| Route | Purpose |
|---|---|
| `GET /api/health` | Liveness |
| `GET /api/city` | City map geometry and the list of DEMO triggers |
| `GET /api/simulation/status` · `/scenarios` · `/snapshot` | Simulation state |
| `POST /api/simulation/start` · `pause` · `resume` · `reset` · `advance` · `speed` · `scenario` | Simulation control |
| `POST /api/simulation/inject` · `trigger` | Inject a world fact, or fire a DEMO button |
| `GET /api/source` · `POST /api/source` | Read or switch the data mode |
| `GET /api/detector/bands` | Risk band thresholds |
| `GET /api/chunks/{chunk_id}` | The source text behind a citation |
| `POST /api/agent/runs/{run_id}/approval` | Approve or reject a waiting agent run |
| `WS /ws` | Live event stream. `?types=weather.,agent.` filters by event-type prefix |

The frontend's API types are generated from the backend OpenAPI schema with `npm run gen:api`. Do not write them by
hand.

## Development

```bash
# backend
cd backend
uv run pytest                              # needs the db container; DB tests skip if Postgres is down
uv run pyright && uv run ruff check . && uv run ruff format --check .

# frontend
cd frontend
npm test && npm run typecheck && npm run lint

# headless scenario check, from the repo root; run it before every demo
uv run python scripts/demo_smoke.py
```

The smoke script replays the cascading scenario for 300 ticks with seed 42. It checks that the six stages happen in
order, that the landslide blocks D-7 and that Riverside floods. It then replays the same storm with the project
halted at tick 60 and checks that the landslide does not happen. It needs no database and no network.

## Repository layout

```
GridLine_AI/
├── ARCHITECTURE.md        full system design
├── docker-compose.yml     PostgreSQL 16 + pgvector
├── scripts/               demo_smoke.py, database init SQL
├── docs/                  RAG usage guide, design specs and plans, screenshots
├── backend/
│   ├── data/city/         synthetic Nandipur dataset (YAML)
│   ├── data/corpus/       37 synthetic policy, SOP, incident and engineering documents (Markdown)
│   └── gridline/
│       ├── agents/        LangGraph workflow, nodes, runner, heuristic reasoner
│       ├── api/           FastAPI routers
│       ├── city/          typed city model and dataset validation
│       ├── db/            SQLAlchemy models, schema, seed CLI
│       ├── events/        event bus, envelopes, payloads, WebSocket
│       ├── kg/            knowledge graph over the city tables
│       ├── llm/           Ollama provider and Markdown prompts
│       ├── rag/           chunker, embedders, pgvector store, retriever, citations
│       ├── simulation/    clock, physics, scenarios, sensors, DEMO triggers
│       ├── sources/       DEMO and LIVE (Open-Meteo) data sources
│       ├── threats/       per-zone landslide and flood risk indices
│       └── tools/         21 audited, state-changing city tools
└── frontend/src/
    ├── api/               generated types, HTTP and mock clients, query hooks
    ├── live/              WebSocket store and event reducers
    └── components/        map, timeline, event feed, incident panel, approvals, actions log
```

More detail: [backend/README.md](backend/README.md) (dataset, seed, tools, tests) and [docs/rag.md](docs/rag.md)
(retrieval and citations).

## Status

**Built:** the synthetic city dataset and seed; the RAG layer; the simulation engine and scenarios; the event bus
and WebSocket; the 21 city tools; the DEMO/LIVE data sources; the per-zone risk indices; the 11-step LangGraph
workflow with human approval, execution and verification; and the live dashboard.

**Not built yet:** a full threat detector (hysteresis, incident lifecycle, `threat.*` events); the re-plan loop
after a failed verification; approvals that survive a restart (they are held in memory); and more than one agent
run at a time. Today, runs start on `infrastructure.failure` events.

## Data and privacy

All Nandipur places, organizations, people, assets, policies and events are fictional. LIVE mode uses only public
weather data from Open-Meteo, labelled with its source. The project contains no personal or confidential data.
