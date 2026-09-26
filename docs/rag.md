# RAG layer: usage

The RAG layer returns **evidence, not answers**: the stored corpus sections most similar to a query, each
with a citation id that names a real row in `chunks` (`dmp-2024#s4.2`). It never calls an LLM and never
fabricates a result. An empty store, a filter that matches nothing or a similarity threshold nobody meets
all return `[]`. Code: `backend/gridline/rag/`. Design: `docs/superpowers/specs/2026-09-26-rag-layer-design.md`.

## Prerequisites

- Python 3.13 and `uv`; PostgreSQL 16 with pgvector (`docker compose up -d db` from the repository root,
  listening on `localhost:5433`).
- `backend/.env` is optional (copy `backend/.env.example`); the defaults already match the container.
- The database must be **seeded** first. Documents belong to the city data layer; ingestion only indexes them.

## Ingest

```bash
cd backend
uv run python -m gridline.db.seed      # once: documents, document_sections and the rest of the city
uv run gridline-ingest                 # chunk, embed and store the corpus
```

Sample output (first run on a freshly seeded database, without network access to download the model):

```
WARNING fastembed model BAAI/bge-small-en-v1.5 unavailable (ProxyError); falling back to hashed embedder
documents_added: 37
documents_updated: 0
documents_unchanged: 0
documents_removed: 0
chunks_written: 313
embedding_model: hashed:v1
duration_s: 1.21
```

Running it again reports `documents_unchanged: 37` and writes nothing: a document is re-embedded only when
its file's sha256 or the embedder changes. Flags:

| flag | meaning |
|---|---|
| `--corpus PATH` | corpus directory (default `CORPUS_DIR`, i.e. `backend/data/corpus`) |
| `--provider auto\|fastembed\|hashed` | override `EMBEDDING_PROVIDER` |
| `--reset` | clear every chunk and fingerprint first, then index everything |
| `--database-url URL` | override `DATABASE_URL` |
| `-v` | log each indexed document |

What ingestion writes: `chunks` rows, plus `content_hash`, `embedding_model` and `ingested_at` on each
`documents` row. It never inserts or deletes documents. A seeded document that is not in the corpus
directory is *unindexed* (its chunks go, its row stays) and counted as `documents_removed`. Every check runs
before the first write: a bad file (`CorpusError`, naming the file), a heading collision, or a corpus
document that is not seeded (`IngestError`) exits with status 1 and changes nothing.

## Use from Python

```python
import asyncio

from gridline.config import Settings
from gridline.db.engine import create_engine, session_factory
from gridline.rag.citations import format_citation
from gridline.rag.embedder import build_embedder
from gridline.rag.models import RetrievalFilters
from gridline.rag.retriever import Retriever
from gridline.rag.store import ChunkStore


async def main() -> None:
    settings = Settings()
    engine = create_engine(settings.database_url)
    embedder = build_embedder(settings.embedding_provider, settings.embedding_model)
    retriever = Retriever(ChunkStore(session_factory(engine)), embedder)
    results = await retriever.retrieve(
        "landslide debris blocked D-7 in Hillview",
        filters=RetrievalFilters(kinds=["report"], hazards=["landslide"], zone_ids=["Z-HV"]),
        top_k=5,
    )
    for r in results:
        print(f"{r.similarity:.3f} {format_citation(r.citation)}")
    engineering = await retriever.retrieve(
        "how stable is slope SL-HV-1 when the colluvium is saturated",
        filters=RetrievalFilters(categories=["engineering_report"]),
        top_k=5,
    )
    for r in engineering:
        print(f"{r.similarity:.3f} {r.category} {format_citation(r.citation)}")
    await engine.dispose()


asyncio.run(main())
```

```
0.225 [rep-2019-ls-01#s7] Post-incident review: Hill Road cut landslide (HI-2019-LS-01) — Lessons and recommendations (NMC-DMC Post-Incident Review Board)
0.194 [rep-2022-ls-01#s7] Post-incident review: Hillview Terrace Phase 1 cut-slope failure (HI-2022-LS-01) — Lessons and recommendations (NMC-DMC Post-Incident Review Board)
...
0.435 engineering_report [geo-profiles-2020#s1] Zone Geotechnical Profiles — Hillview (Z-HV) (State Geological Survey, Nandipur District Office)
0.296 engineering_report [geotech-sl-hv-1-2025#s2] Geotechnical Assessment of Slope SL-HV-1 for Hillview Terrace Phase 2 — Ground model (State Geological Survey, Nandipur District Office)
0.293 engineering_report [geotech-sl-hv-1-2025#s1] Geotechnical Assessment of Slope SL-HV-1 for Hillview Terrace Phase 2 — Site and slope geometry (State Geological Survey, Nandipur District Office)
...
```

`retrieve(query, filters=None, top_k=8, min_similarity=0.0)` raises `ValueError` for a blank query or
`top_k <= 0`, and `EmbeddingModelMismatchError` when the corpus was indexed with a different embedder.
`ChunkStore.get_chunk(chunk_id)` resolves a citation id back to its stored chunk (or `None`), and
`validate_citation_ids(cited, allowed)` returns the cited ids that were not in `allowed`, for the grounding
validator.

## Results and citations

`RetrievedChunk`: `chunk_id, text, similarity` (1 − cosine distance), `document_id, document_title, section`
(heading text), `section_id` (`s4.2`), `source` (issuing body), `kind, category, zone_ids, hazards`,
`metadata` (`category, section_title, part, word_count, source_path, version, effective_date`) and
`citation`.

`Citation`: `id` (always equal to `chunk_id`), `document_title, section, source, text`. `format_citation`
renders `[dmp-2024#s4.2] Nandipur Disaster Management Policy — Landslide thresholds (NMC Disaster Management
Cell)`.

## Filters

`RetrievalFilters` fields are any-of lists; `None` or `[]` means "no filter"; different fields intersect.

| field | values | note |
|---|---|---|
| `kinds` | `policy, sop, report, permit, change_log, profile` | the document's form (city data layer) |
| `categories` | the ten knowledge categories below | what the document is about |
| `hazards` | `flood, flash_flood, landslide, cyclone, urban_fire` | a chunk with no hazards matches every hazard |
| `zone_ids` | `Z-HV`, `Z-RS`, ... | a city-wide chunk (no zones) matches every zone |
| `document_ids` | `dmp-2024`, ... | |

An unknown kind, category or hazard is a validation error, not an empty result.

### Knowledge categories

Every corpus document names one of the brief's ten knowledge categories in its front matter (`category:`,
required). Filter by `categories` to ask for a topic ("engineering evidence about this slope"), by `kinds` to
ask for a form ("only post-incident reports"); combined, they intersect.

| # | brief category | `category` | documents |
|---|---|---|---|
| 1 | city policies | `policy` | dmp-2024, pol-flood-response-2024, pol-incident-escalation-2024, pol-road-closure-2021 |
| 2 | emergency SOPs | `sop` | sop-emergency-ops-2023, sop-landslide-prevention-2023 |
| 3 | disaster-management procedures | `procedure` | sop-crew-dispatch-2023, sop-pump-deployment-2022 |
| 4 | historical incidents | `incident_report` | the 17 post-incident reports rep-2012-fl-01 … rep-2025-ff-01 |
| 5 | infrastructure reports | `infrastructure_report` | survey-d7-2026 (D-7 condition survey), inspection-br1-2025 (BR-1 bridge inspection) |
| 6 | engineering reports | `engineering_report` | geo-profiles-2020, geotech-sl-hv-1-2025 (SL-HV-1 slope stability), hydraulics-d7-2026 (D-7 hydraulic capacity) |
| 7 | construction safety | `construction_safety` | pol-construction-hazard-2025, permit-ht-2026-014 |
| 8 | evacuation procedures | `evacuation` | pol-evacuation-2022, pol-shelter-activation-2024 |
| 9 | resource allocation rules | `resource_rules` | pol-resource-allocation-2023 |
| 10 | historical city changes | `change_log` | changelog-infra-2018-2026, city-profile-2026 (population and impervious cover 2018 → 2026) |

**Kind and category.** `kind` is the city data layer's document form and stays what the seed stores in
`documents.kind`; `category` is set per document, not derived from the kind. The pairs in use:

| kind | categories |
|---|---|
| `policy` | `policy`, `evacuation`, `resource_rules`, `construction_safety` |
| `sop` | `sop`, `procedure` |
| `report` | `incident_report` |
| `permit` | `construction_safety` |
| `change_log` | `change_log` |
| `profile` | `engineering_report`, `infrastructure_report`, `change_log` |

The parser enforces one rule: reports, and only reports, are `incident_report` (reports carry the `incident:`
block that seeds `historical_incidents`). Surveys, inspections and engineering studies use kind `profile`.

The category is stored in each chunk's `metadata` (the RAG layer owns only `chunks`; there is no category
column), and the filter compares `metadata->>'category'`. Results carry it both as `category` and as
`metadata["category"]`.

## Embedding providers

| `EMBEDDING_PROVIDER` | embedder name | behaviour |
|---|---|---|
| `auto` (default) | either of the below | tries fastembed; on any failure (not installed, no network, no cache) logs a warning and uses `hashed` |
| `fastembed` | `fastembed:BAAI/bge-small-en-v1.5` | local ONNX model, 384-dim, one-time download (~130 MB); errors surface |
| `hashed` | `hashed:v1` | feature hashing of stemmed words, asset ids (`d-7`, `rg-02`) and bigrams; deterministic, no downloads |

`hashed` is lexical, not semantic: it finds sections that share words with the query, so phrase queries
with the corpus's own vocabulary ("blocked", "D-7", "saturation") work best. Tests use it.

**Mismatch rule.** Vectors from different embedders are not comparable, so `Retriever` refuses to search
when the embedder that indexed `chunks` differs from the live one. Re-index with the current provider:
`uv run gridline-ingest` (changed embedder names re-embed every document automatically).

## Chunk ids and adding a document

Corpus files and their front matter are defined by the city data layer (`backend/README.md`): add the
Markdown file to `backend/data/corpus/` with a `category:` from the table above, then reseed
(`python -m gridline.db.seed --reset`; a plain seed writes nothing to an already seeded database) and ingest.
Documents record facts, rules and measurements; they never state the conclusion the agent is meant to reach
about the live city (CLAUDE.md non-negotiable 3). Numbered headings `## 4.2 Title` become section
`s4.2`; text before the first heading is `s0`; `###` stays inside its section. One chunk per section, with
chunk id `<document_id>#<section>`, so every `document_sections` id is also a chunk id. A section longer than
350 words is split at paragraph boundaries: the first part keeps `dmp-2024#s4.2`, later parts are
`dmp-2024#s4.2-p2`, `-p3`. The embedded text is `"<title> — <heading>\n<text>"`. Ids depend only on the file,
so unchanged files keep their citations valid across runs.

## Tests

```bash
cd backend
uv run pytest                                   # DB tests skip with a reason when Postgres is unreachable
GRIDLINE_TEST_FASTEMBED=1 uv run pytest tests/test_embedder.py::test_fastembed_real_model
```

RAG tests: `test_chunker`, `test_embedder`, `test_citations` (pure); `test_store`, `test_retriever`,
`test_ingest` (fixture corpus in `backend/tests/fixtures/corpus`, whose documents rows the `rag_documents`
fixture seeds and removes); `test_real_corpus` (the shipped corpus on the seeded test database: every
category indexed, category filters, and one retrieval per infrastructure and engineering report).
`test_corpus` pins each document's category and checks that all ten categories are in use.

## Notes

- **Windows.** psycopg's async driver needs a selector event loop. The CLI and tests handle it; other entry
  points should call `asyncio.run(main(), loop_factory=asyncio.SelectorEventLoop)` on `win32`.
- **HNSW.** pgvector applies `WHERE` filters after the index scan and yields at most `hnsw.ef_search`
  candidates (default 40). Search sets `hnsw.ef_search = 1000` per query, which keeps filtered and large
  `top_k` searches complete for a corpus of up to about a thousand chunks (313 today).
