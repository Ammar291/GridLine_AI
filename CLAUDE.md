# GridLine AI — Project Constitution

GridLine AI is a hackathon prototype: an AI-powered City Disaster Intelligence Brain for the fictional city
of Nandipur. It continuously monitors a synthetic city, and for every emerging threat runs
`detect → reason → predict → recommend prevention → request approval → execute → verify → re-plan`
using RAG and a LangGraph agent. The design lives in [ARCHITECTURE.md](ARCHITECTURE.md); read it before
touching any subsystem. This file is the set of rules that do not change.

## Non-negotiables

1. **Synthetic data only.** Every place, person, sensor, policy, permit and historical event is invented.
   Never import real-city, personal, or confidential data, not even as an example.
2. **One process, one database, one frontend.** FastAPI + PostgreSQL (pgvector) + React. No microservices,
   Kafka, Kubernetes, Celery, Redis, or any second runtime.
3. **No hardcoded AI answers.** Every assessment, prediction and recommendation is produced from the
   current city state and retrieved documents, by the Anthropic provider or by the deterministic mock
   reasoner that reads the same inputs. Scripted simulation events and seed data are allowed; scripted
   conclusions are not.
4. **Citations are mandatory and verified.** LLM outputs are structured, every factual claim cites a
   retrieved chunk or live reading by ID, and the grounding validator rejects IDs that were not in the input.
5. **State changes only through tools.** The agent mutates the city solely through the tool registry.
   Approval-required tools never execute without a recorded decision, including in demo mode.
6. **Verification reads the world, not the model.** A tool is verified by re-reading DB and simulation
   state against its declared post-condition. Failures route to re-plan; they are never hidden.
7. **Runs offline.** With no `ANTHROPIC_API_KEY` the whole system still runs on the mock provider and
   local embeddings. Never make a feature depend on network access.
8. **Do not overengineer.** Prefer a small typed function over an abstraction. Add a dependency only when
   it removes more code than it adds. YAGNI.

## How work is done here

- **Model routing.** Claude Fable handles orchestration, design, planning, problem solving and review.
  Coding tasks are delegated to Claude Opus 5.5 subagents (`model: "opus"` on the Agent tool) with a
  complete, self-contained brief per task.
- **Process.** New features start with the brainstorming skill; multi-step work gets a written plan
  (writing-plans) and is executed with subagent-driven development. Every implementation task follows
  test-driven development. Nothing is called done until verification-before-completion has been run
  with real command output. Use frontend-design and dataviz when building UI or charts, and code-review
  before finishing a branch.
- **Plugins in use:** superpowers, code-review, code-simplifier, frontend-design, claude-md-management.
  No MCP servers are configured for this project as of 2026-09-26; if one is added, list it here.
- **Git.** Work on feature branches off `main`. Commit only when asked. Commit messages end with the
  attribution line the session provides.

## Code conventions

**Backend (Python 3.13, uv)**
- Fully typed; `pyright` strict on `gridline/`, `ruff` for lint and format. Pydantic v2 for every
  boundary model (API, LLM schemas, tool inputs, events). SQLAlchemy 2.x typed mapped classes.
- Async everywhere on the request path. No module-level mutable state; shared services hang off
  `app.state` and are injected via FastAPI dependencies.
- One module per concern, files under about 300 lines. Prompts are Markdown files in
  `gridline/llm/prompts/`, never inline strings.
- Anthropic calls go through the official `anthropic` SDK only, via `gridline/llm/anthropic.py`.
  Default model `claude-opus-5`; adaptive thinking; effort from config. No other LLM client libraries.
- Configuration via `pydantic-settings` from `backend/.env`; secrets never in code or logs.

**Frontend (TypeScript, React 19, Vite, Tailwind v4)**
- `strict: true`, no `any`, no default exports except `App`. API types are generated from the backend
  OpenAPI schema; do not hand-write payload types.
- Server state through TanStack Query; live state through the WebSocket store. Components are small and
  presentational; data access lives in hooks.

**Both**
- Every event type, tool and API route has a typed payload model and a test.
- Naming follows the domain: zone, channel, project, crew, incident, run, step, approval, action, claim,
  citation. Do not invent synonyms.

## Commands (once the skeleton exists)

```
scripts/dev.ps1  |  scripts/dev.sh        start db + backend + frontend
cd backend && uv run pytest               backend tests
cd backend && uv run pyright && uv run ruff check .
cd frontend && npm test && npm run typecheck
uv run python scripts/demo_smoke.py       headless primary scenario, must pass before any demo
```

## Definition of done for any task

Tests written first and passing, types clean, lint clean, the change visible in the running app when it is
user-facing, and the demo smoke script still green.
