# RAG layer design — GridLine AI

Date: 2026-09-26. Status: approved for planning (implements ARCHITECTURE.md §4 `documents`/`chunks`, §6 corpus, §7 RAG).

## 1. Goal

Give the City Disaster Brain a retrieval layer that returns **evidence with verifiable citations** from a synthetic
Nandipur knowledge base. Every result points at a real stored chunk; the layer never fabricates a citation. It runs
fully offline, works with PostgreSQL + pgvector, and exposes one call:

```python
results = await retriever.retrieve(query, filters=None, top_k=8)
```

Out of scope (later milestones): LangGraph agent, LLM providers, REST API, WebSockets, frontend, city state tables.

## 2. What is said vs. assumed

Stated by the brief: ten knowledge categories; Postgres + pgvector; document/chunk/evidence model; ingestion, chunking,
embeddings, semantic retrieval, metadata filtering (disaster type, city zone); citations with title, section, source,
relevant text; result fields `chunk_id, text, similarity, document_id, document_title, section, source, metadata`;
an ingest command; configurable embedding provider with local model support; tests for ingestion, retrieval, filtering,
citations, empty results; usage docs.

Assumed (override if wrong):

- A1. No LLM is called anywhere in this layer. Retrieval is embedding similarity only. The provider switch the brief
  asks for is the **embedding** provider; the LLM provider switch lands with the agent milestone.
- A2. Two embedding providers: `fastembed` (local ONNX `BAAI/bge-small-en-v1.5`, 384-dim, one-time download) and
  `hashed` (deterministic feature-hashing, 384-dim, zero downloads). `auto` prefers fastembed and falls back to
  hashed with a logged warning. Tests use `hashed` so they are fast, deterministic and offline.
- A3. The database container publishes host port **5433** (5432 is taken on the dev machine). ARCHITECTURE §14 is
  updated to match.
- A4. Zone and hazard IDs in the corpus are the canonical seed IDs (§5 below) so the later city model can join on them.
- A5. The corpus is about 30 Markdown documents written for this task; they are the seed corpus for the whole product.

## 3. Package layout

```
backend/
├── pyproject.toml            uv; deps: sqlalchemy[asyncio], psycopg[binary], pgvector, pydantic, pydantic-settings,
│                             pyyaml, numpy, fastembed; dev: pytest, pytest-asyncio, pyright, ruff
├── .env.example
├── data/corpus/*.md          synthetic knowledge base (Markdown + YAML front matter)
├── gridline/
│   ├── config.py             Settings (pydantic-settings): database_url, embedding_provider, embedding_model,
│   │                         corpus_dir, rag_top_k
│   ├── db/engine.py          create_engine(url) -> AsyncEngine; session_factory(engine)
│   ├── db/models.py          Base, Document, Chunk (SQLAlchemy 2.x mapped classes)
│   ├── db/schema.py          create_schema(engine): CREATE EXTENSION vector; create_all; drop_schema for tests/reset
│   └── rag/
│       ├── models.py         Pydantic: DocumentKind, CorpusDocument, ChunkDraft, RetrievalFilters, Citation,
│       │                     RetrievedChunk, IngestReport
│       ├── corpus.py         load_corpus(dir) -> list[CorpusDocument]   (front matter parsing + validation)
│       ├── chunker.py        chunk_document(doc) -> list[ChunkDraft]     (heading split, size split, stable IDs)
│       ├── embedder.py       Embedder protocol; FastEmbedEmbedder; HashedEmbedder; build_embedder(settings)
│       ├── store.py          ChunkStore: upsert_document, delete_document, search, get_chunk, list_documents
│       ├── retriever.py      Retriever.retrieve(query, filters, top_k, min_similarity)
│       ├── citations.py      citation_id(); validate_citation_ids(); format_citation()
│       └── ingest.py         ingest(settings, corpus_dir, reset) -> IngestReport; CLI main()
└── tests/
docker-compose.yml            pgvector/pgvector:pg16, host port 5433, creates gridline + gridline_test databases
docs/rag.md                   usage documentation
```

Every file stays under about 300 lines. Nothing is module-level mutable state; `Retriever` and `ChunkStore` are
constructed with their dependencies.

## 4. Data model

**`documents`** — one row per corpus file.

| column | type | notes |
|---|---|---|
| id | text PK | the front-matter `slug`, e.g. `dmp-2024` |
| title | text | |
| kind | text | one of the ten `DocumentKind` values |
| source | text | issuing body, e.g. `Nandipur Municipal Corporation, Disaster Management Cell` |
| source_path | text | relative path of the Markdown file |
| date | date nullable | document date from front matter |
| zone_ids | text[] | canonical zone IDs; empty means city-wide |
| hazards | text[] | e.g. `{landslide, flood}`; empty means all hazards |
| content_hash | text | sha256 of the file; unchanged hash + same embedding model = skip on re-ingest |
| embedding_model | text | embedder name used for this document's chunks |
| metadata | jsonb | remaining front-matter fields (tags, etc.) |
| ingested_at | timestamptz | |

**`chunks`** — one row per section part.

| column | type | notes |
|---|---|---|
| id | text PK | **the citation ID**: `{document_id}#{section_id}`, e.g. `dmp-2024#s4.2`, `dmp-2024#s4.2-p2` |
| document_id | text FK → documents ON DELETE CASCADE | |
| section_id | text | `s4.2` from a numbered heading, else a slug of the heading; `intro` for text before the first heading |
| section_title | text | heading text without numbering |
| position | int | order within the document |
| text | text | chunk body (what is shown as the citation's relevant text) |
| embedding | vector(384) | HNSW index, `vector_cosine_ops` |
| kind, zone_ids, hazards | denormalised from the document | so filters need no join |
| metadata | jsonb | document metadata plus `section_title`, `word_count`, `part`, `source_path` |

The `DocumentKind` values map the brief's ten categories one-to-one:
`policy, sop, procedure, incident_report, infrastructure_report, engineering_report, construction_safety,
evacuation, resource_rules, change_log`.

## 5. Corpus format

```markdown
---
title: Nandipur Disaster Management Policy 2024
slug: dmp-2024
kind: policy
source: Nandipur Municipal Corporation, Disaster Management Cell
date: 2024-03-15
zone_ids: []            # [] = city-wide; otherwise canonical IDs
hazards: [landslide, flood]
tags: [thresholds, halt-rules]
---

# Nandipur Disaster Management Policy 2024

## 1. Purpose
...

## 4.2 Slope construction halt rule
...
```

Validation at load time: required `title, slug, kind, source`; slug is `^[a-z0-9][a-z0-9-]*$` and unique across the
corpus; kind is a `DocumentKind`; zone_ids ⊆ canonical zones; hazards ⊆ canonical hazards. A bad file fails ingestion
with the file name and the reason.

Canonical IDs (shared with the future city seed):

- zones: `hillview, riverside, old_town, market_ward, station_road, lakeside`
- hazards: `landslide, flood, fire, storm` (fire/storm exist mainly so hazard filtering has something to exclude)

## 6. Chunking

`chunk_document(doc, max_words=350, min_words=25)`:

1. Split the body on `##`/`###` headings. Text before the first heading becomes section `intro`.
2. `section_id`: if the heading starts with a number like `4.2`, use `s4.2`; otherwise a slug of the heading
   (`evacuation-triggers`). Duplicate IDs within one document get `-2`, `-3` suffixes.
3. Sections longer than `max_words` are split at paragraph boundaries into parts `-p1`, `-p2`, ... (a section with a
   single part keeps the plain ID). Sections shorter than `min_words` are merged into the previous chunk of the same
   document, except the intro.
4. The stored `text` is the section body. The embedding input is `"{title} — {section_title}\n{text}"` so short
   sections still carry document context.
5. Chunk IDs are a pure function of the file content, so re-ingesting an unchanged file produces identical IDs and
   citations stay valid across runs.

## 7. Embedding

```python
class Embedder(Protocol):
    name: str          # e.g. "fastembed:BAAI/bge-small-en-v1.5" or "hashed:v1"
    dimension: int     # always 384 here
    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...
    def embed_query(self, text: str) -> list[float]: ...
```

- `FastEmbedEmbedder`: wraps `fastembed.TextEmbedding`; `embed_query` uses the model's query prefix
  (`query_embed`). Model loads lazily on first use.
- `HashedEmbedder`: lowercase word tokens plus word bigrams, each hashed (sha1) into one of 384 buckets with a sign
  bit, L2-normalised. Deterministic across processes and platforms; no downloads. Good enough for lexical-overlap
  retrieval, and honest about it in the docs.
- `build_embedder(settings)`: `fastembed` → FastEmbed or raise; `hashed` → Hashed; `auto` → try FastEmbed (import
  and model init), on any failure log a warning and return Hashed.
- Embedding is CPU-bound and synchronous; async callers use `asyncio.to_thread`.
- The store records `embedding_model` per document. `Retriever` refuses to search when the live embedder name differs
  from the one the corpus was indexed with (`EmbeddingModelMismatchError` telling the user to re-ingest). Mixing
  vector spaces would produce silently wrong similarities.

## 8. Retrieval

```python
class RetrievalFilters(BaseModel):
    kinds: list[DocumentKind] | None = None      # any-of
    hazards: list[str] | None = None             # any-of; a chunk with empty hazards matches every hazard filter
    zone_ids: list[str] | None = None            # any-of; a chunk with empty zone_ids (city-wide) matches every zone filter
    document_ids: list[str] | None = None        # any-of

class Citation(BaseModel):
    id: str                 # == chunk_id, e.g. "dmp-2024#s4.2"
    document_title: str
    section: str            # section title
    source: str
    text: str               # the chunk text

class RetrievedChunk(BaseModel):
    chunk_id: str
    text: str
    similarity: float       # 1 - cosine distance, in [-1, 1]
    document_id: str
    document_title: str
    section: str
    source: str
    metadata: dict[str, Any]
    citation: Citation

class Retriever:
    def __init__(self, store: ChunkStore, embedder: Embedder) -> None: ...
    async def retrieve(self, query: str, filters: RetrievalFilters | None = None,
                       top_k: int = 8, min_similarity: float = 0.0) -> list[RetrievedChunk]: ...
```

SQL (SQLAlchemy Core): `1 - (embedding <=> :q)` as similarity, `ORDER BY embedding <=> :q LIMIT top_k`, with
`kind IN (...)`, `hazards && :hazards OR cardinality(hazards) = 0`, likewise for zones, `document_id IN (...)`.
Results below `min_similarity` are dropped after the query. Empty query string raises `ValueError`. An empty store,
a filter that matches nothing, or a threshold nobody meets all return `[]`, never a fabricated result.

`citations.py`:

- `citation_id(document_id, section_id) -> str`
- `validate_citation_ids(cited: Iterable[str], allowed: Iterable[str]) -> list[str]` returns the unknown IDs; the
  future grounding validator calls this with the IDs the model was shown.
- `format_citation(c: Citation) -> str` → `"[dmp-2024#s4.2] Nandipur Disaster Management Policy 2024 — 4.2 Slope
  construction halt rule (Nandipur Municipal Corporation, Disaster Management Cell)"`.

## 9. Ingestion

`ingest(settings, corpus_dir, *, reset=False) -> IngestReport`:

1. `create_schema(engine)` (extension, tables, index) — idempotent.
2. `load_corpus(corpus_dir)`; fail fast on any invalid file.
3. `build_embedder(settings)`.
4. Per document: compute `content_hash`; if a row exists with the same hash and `embedding_model`, count as
   `unchanged` and skip. Otherwise chunk, embed (batched), and in one transaction delete the old chunks and upsert
   document + chunks. Documents in the DB but no longer in the corpus are deleted.
5. `reset=True` drops and recreates `documents`/`chunks` first.
6. Report: `documents_added, documents_updated, documents_unchanged, documents_removed, chunks_written,
   embedding_model, duration_s`.

CLI: `uv run gridline-ingest [--corpus PATH] [--reset] [--provider auto|fastembed|hashed]` (entry point
`gridline.rag.ingest:main`). Prints the report as one line per field.

## 10. Configuration

`backend/.env` (example committed as `.env.example`):

```
DATABASE_URL=postgresql+psycopg://gridline:gridline@localhost:5433/gridline
TEST_DATABASE_URL=postgresql+psycopg://gridline:gridline@localhost:5433/gridline_test
EMBEDDING_PROVIDER=auto          # auto | fastembed | hashed
EMBEDDING_MODEL=BAAI/bge-small-en-v1.5
CORPUS_DIR=data/corpus
RAG_TOP_K=8
```

`docker-compose.yml` runs `pgvector/pgvector:pg16` with a named volume and an init script that creates
`gridline_test` next to `gridline`.

## 11. Synthetic corpus (about 30 documents)

Written from one canonical fact sheet so documents agree with each other and with the future city seed:

- **Zones.** Hillview (hillside, 32° slope, weathered laterite over shale, drains to D-7), Riverside (downstream of
  D-7, low-lying), Old Town (D-3), Market Ward, Station Road (pump depot), Lakeside (D-11).
- **Drainage.** D-7 "Kalinadi drain" design capacity 18 m³/s; culvert under Hill Road narrowed in 2025 from 2.4 m to
  1.6 m, current capacity 11 m³/s. D-3 9 m³/s. D-11 12 m³/s.
- **Roads.** Hill Road (only access to Hillview, widened 2025), Riverside Bypass (designated evacuation route),
  Kalinadi Bridge Road, Station Road, Market Street, Old Town Ring, Lake Road, Temple Lane.
- **Project.** Hillview Terrace Phase 2, permit HT-2026-014 issued 2026-02-10 to Meridian Hill Developers (fictional),
  planned excavation 6 m on the 32° slope. Conditions: halt when 24-h rain exceeds 60 mm, or soil saturation exceeds
  0.70, or the zone is in `warning` or higher; max unsupported cut 2.5 m; daily inspection in monsoon.
- **Sensors.** RG-01, RG-02 (Hillview), RG-03 (Riverside), RG-04 (Old Town); SM-01, SM-02 (Hillview), SM-03
  (Riverside); CL-D7, CL-D3 channel gauges.
- **Assets.** Crews C-1 (drainage), C-2 (rescue and roads), C-3 (engineering); shelters S-1 Riverside Community Hall
  (400), S-2 Station Road School (650); pump depot at Station Road with four 1.5 m³/s units.
- **Thresholds (policy).** Landslide index: watch ≥ 0.40, warning ≥ 0.60, critical ≥ 0.80. Flood index: watch ≥ 0.35,
  warning ≥ 0.55, critical ≥ 0.75. Rain: heavy > 60 mm/24 h, very heavy > 100 mm, extreme > 150 mm. Halt excavation
  on slopes above 25° when saturation > 0.70 or band ≥ warning.
- **History.** 2014-07-22 Hillview landslide (180 mm/24 h) blocked D-7 for 30 h, Riverside flooded to 1.2 m.
  2019-08-09 landslide (130 mm) during unpermitted terracing, D-7 partly blocked, Riverside 0.6 m. 2022-09-03 minor
  slump (90 mm), early halt prevented failure. 2021-07-15 Riverside flash flood (110 mm in 6 h, D-7 at 95%).
  2018-03 Market Ward market fire (hazard `fire`, for filter tests).
- **No personal data.** No names of individuals anywhere; organisations are fictional.

Distribution across kinds: policy 3, sop 5, procedure 3, incident_report 5, infrastructure_report 3,
engineering_report 3, construction_safety 3, evacuation 3, resource_rules 3, change_log 3.

## 12. Error handling

- Invalid corpus file → `CorpusError(path, reason)`; ingestion stops before touching the DB.
- Embedding model mismatch → `EmbeddingModelMismatchError`; retrieval refuses rather than returning nonsense.
- Empty query → `ValueError`. DB unreachable → SQLAlchemy error surfaces unchanged (no silent fallback store).
- fastembed unavailable under `auto` → warning + hashed embedder; under `fastembed` → the original exception.

## 13. Testing

Pure tests (no DB): corpus parsing and validation; chunker (heading split, numbered IDs, size split, min merge,
stability); hashed embedder (dimension, determinism, unit norm, related texts closer than unrelated);
citations (ID format, validator rejects unknown IDs and accepts known ones, formatter).

DB tests (`TEST_DATABASE_URL`; skipped with a clear reason if unreachable; fixture creates schema and truncates):

- ingestion: fixture corpus ingested → document and chunk counts; re-run is `unchanged`; edited file → `updated`,
  old chunk IDs gone; removed file → `removed`.
- retrieval: on the real corpus with the hashed embedder, a threshold query returns the policy threshold chunk in the
  top 3; results are sorted by similarity; every result has non-empty `document_title, section, source, text` and
  `citation.id == chunk_id`; `top_k` is honoured.
- metadata filtering: `kinds=[incident_report]` returns only reports; `hazards=[landslide]` never returns the fire
  report; `zone_ids=[riverside]` returns Riverside or city-wide chunks only; combined filters intersect.
- citations: each returned `Citation` matches the DB row it points at (re-read by `get_chunk`); `validate_citation_ids`
  on a fabricated ID reports it.
- empty results: empty store → `[]`; impossible filter → `[]`; `min_similarity=0.99` → `[]`; empty query raises.
- embedder mismatch: ingest with `hashed:v1`, retrieve with a differently named embedder → error.

One optional test runs the fastembed model when `GRIDLINE_TEST_FASTEMBED=1`.

## 14. Documentation

`docs/rag.md`: prerequisites, starting the DB, ingesting, using `Retriever` (code sample), filters, result and
citation shapes, embedding providers and the mismatch rule, adding a document (front matter schema, canonical IDs),
running the tests. ARCHITECTURE §4/§7/§14 are touched only where this design refines them (filter columns, port).

## 15. Revision (2026-09-26, coordination with parallel sessions)

Four other sessions build other subsystems in this repository at the same time. The city-data-layer design owns
`gridline/db/base.py`, `gridline/db/engine.py`, the `documents` and `document_sections` tables, and the shared
33-document corpus in `backend/data/corpus/` (front matter `document_id, title, kind, source, version,
effective_date, hazards, zone_ids, ...`; numbered `##` headings; section ids `s4.2`; intro `s0`). This design is
revised accordingly:

- **RAG owns exactly one table, `chunks`.** It carries the document fields retrieval and citations need
  (`document_id, document_title, document_kind, source, source_path, document_date, zone_ids, hazards,
  content_hash, embedding_model`) so it needs no join and no `documents` table of its own. §4's `documents`
  table is dropped from this design; `DocumentRecord` is derived with `SELECT DISTINCT` over `chunks`.
- **Chunk ids equal the city corpus section ids** (`document_id#s4.2`; intro is `s0`; `###` headings stay inside
  their parent section; only very long sections get `-p2` parts).
- **The corpus loader accepts both front-matter dialects** (`slug`/`date` and `document_id`/`effective_date`),
  maps the city kinds `report → incident_report`, `permit → construction_safety`, `profile → engineering_report`
  onto the ten RAG kinds, keeps every other key as metadata, and validates `hazards`/`zone_ids` only as lists of
  non-empty strings (the city data layer owns the id vocabulary; §5's closed sets are withdrawn).
- **No second corpus.** §11 is withdrawn: RAG ingests the shared corpus. The three fixture documents under
  `backend/tests/fixtures/corpus/` remain the test corpus; end-to-end tests on the shared corpus skip with a
  reason until it lands.
- Shared files (`pyproject.toml`, `.env.example`, `config.py`, `db/base.py`, `db/engine.py`,
  `db/models/__init__.py`, `tests/conftest.py`, `docker-compose.yml`) are edited additively only.
