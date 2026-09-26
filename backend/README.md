# GridLine AI backend

Python 3.13 package `gridline`, managed with [uv](https://docs.astral.sh/uv/). This README covers the
Nandipur city data layer: the synthetic dataset, the seed command and the tests. The design is in
`docs/superpowers/specs/2026-09-26-nandipur-city-data-layer-design.md`.

## Prerequisites

- Python 3.13 and `uv`
- Docker, for PostgreSQL 16 with pgvector (`pgvector/pgvector:pg16`, see `../docker-compose.yml`)

PostgreSQL is required, for tests too. There is no SQLite fallback: the RAG `chunks` table uses a pgvector
`vector` column with an HNSW index, and `documents` uses PostgreSQL arrays.

## Database

```bash
docker compose up -d db          # from the repository root; listens on localhost:5433
cp .env.example .env             # optional: DATABASE_URL and TEST_DATABASE_URL defaults already match
```

The container creates two databases, `gridline` (development) and `gridline_test` (tests), both with the
`vector` extension.

## Seed

```bash
cd backend
uv sync
uv run python -m gridline.db.seed --reset
```

`--reset` drops and recreates every table, then loads the dataset and commits. Without `--reset` the command
creates any missing tables and seeds an empty database; if the database is already seeded it writes nothing.
Other options: `--database-url URL` (default `DATABASE_URL`) and `--data-dir PATH` (default `backend/data`).
The command prints one line per table with its row count.

Before writing anything the seed validates every YAML record and corpus front matter with Pydantic
(unknown keys fail) and checks every cross-reference. A bad id fails with the table, record and field named,
for example `shelters S-5: school_id references unknown schools id 'SC-99'`.

## RAG index

```bash
uv run gridline-ingest             # after seeding: chunk, embed and store the corpus in `chunks`
```

One chunk per corpus section, so citation ids like `dmp-2024#s4.2` resolve to a `chunks` row. Ingestion
writes only `chunks` and each document's `content_hash`/`embedding_model`; unchanged files are skipped.
`EMBEDDING_PROVIDER=auto` uses the local fastembed model when it can load and the offline `hashed` embedder
otherwise. Usage, filters and the Python API: `../docs/rag.md`.

## Tests

```bash
cd backend
uv run pytest                      # needs the db container; DB tests skip when Postgres is unreachable
uv run pyright && uv run ruff check . && uv run ruff format --check .
```

Tests use `TEST_DATABASE_URL` (default `postgresql+psycopg://gridline:gridline@localhost:5433/gridline_test`).
The schema is dropped and recreated once per test session and seeded once by the `seeded` fixture.
`test_corpus.py`, `test_consistency.py`, `test_chunker.py`, `test_embedder.py` and `test_citations.py` are
pure Python and need no database.

## Data layout

```
data/city/          one YAML file per area; each maps table name -> list of records
  city.yaml zones.yaml geography.yaml drainage.yaml roads.yaml utilities.yaml
  emergency.yaml population.yaml infrastructure_changes.yaml policy_thresholds.yaml
data/corpus/        33 Markdown documents: policies, SOPs, 17 incident reports, a permit,
                    the 2018-2026 infrastructure change log and two profiles
```

YAML keys equal the ORM column names. Computed columns are never typed in YAML: every `elevation_m`,
zone area / elevation range / SVG path, road minimum elevation, tunnel low point, hill summit elevation and
population density come from `gridline/city/terrain.py` at seed time.

Corpus documents start with YAML front matter (`document_id`, `title`, `kind`, `source`, `version`,
`effective_date`, `hazards`, `zone_ids`, optional `supersedes`, `summary`). Reports also carry the
`incident:` block and `impacts:` list that seed `historical_incidents` and `historical_incident_impacts`.
Body headings must be numbered, `## 4 Title` or `## 4.2 Title`, and become sections `s4` / `s4.2` with
citation ids like `[dmp-2024#s4.2]`; text before the first heading is section `s0`.

Code map:

- `gridline/city/schema_*.py` Pydantic record models, `dataset.py` loader, `consistency.py` +
  `references.py` cross-reference checks
- `gridline/db/models/` SQLAlchemy tables; `gridline/db/schema.py` create / drop
- `gridline/db/seed/` corpus parser, row builders, `seed()` / `reset_and_seed()` and the CLI
- `gridline/rag/` chunker, embedders, `ChunkStore`, `Retriever`, citations and `gridline-ingest`

All places, organisations, people, assets and events are fictional.
