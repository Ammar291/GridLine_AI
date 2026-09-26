"""End-to-end retrieval on the seeded Nandipur corpus (backend/data/corpus) with the hashed embedder."""

import re
from typing import get_args

import pytest
from sqlalchemy import func, select, text

from gridline.city.schema_history import DocumentCategory
from gridline.db.engine import session_factory
from gridline.db.models import Chunk, Document, DocumentSection, Project
from gridline.db.schema import truncate_corpus
from gridline.rag.citations import validate_citation_ids
from gridline.rag.embedder import HashedEmbedder
from gridline.rag.ingest import ingest
from gridline.rag.models import RetrievalFilters
from gridline.rag.retriever import Retriever
from gridline.rag.store import ChunkStore
from tests.conftest import DATA_DIR

CORPUS = DATA_DIR / "corpus"
DOCUMENTS = 37
SECTIONS = 313


@pytest.fixture(scope="module")
async def indexed(seeded, db_engine, db_url):
    """Sessions on the seeded test database with the real corpus indexed once for this (read-only) module."""
    await truncate_corpus(db_engine)
    report = await ingest(database_url=db_url, corpus_dir=CORPUS, embedder=HashedEmbedder())
    assert report.documents_added == DOCUMENTS and report.documents_removed == 0
    yield session_factory(db_engine)
    await truncate_corpus(db_engine)  # leave the seeded database as the seed left it


@pytest.fixture
def retriever(indexed):
    return Retriever(ChunkStore(indexed), HashedEmbedder())


async def test_every_section_and_threshold_citation_is_a_chunk(retriever, indexed):
    async with indexed() as s:
        chunk_ids = set((await s.execute(select(Chunk.id))).scalars())
        section_ids = set((await s.execute(select(DocumentSection.id))).scalars())
        threshold_ids = set(
            (await s.execute(text("select document_id || '#' || section from policy_thresholds"))).scalars()
        )
    assert len(section_ids) == SECTIONS and section_ids <= chunk_ids
    assert {re.sub(r"-p\d+$", "", c) for c in chunk_ids} == section_ids  # parts only extend a section
    assert threshold_ids and threshold_ids <= chunk_ids  # the detector's thresholds are citable evidence


async def test_reingest_is_a_noop_and_keeps_city_rows(retriever, indexed, db_url):
    report = await ingest(database_url=db_url, corpus_dir=CORPUS, embedder=HashedEmbedder())
    assert report.documents_unchanged == DOCUMENTS and report.chunks_written == 0
    async with indexed() as s:
        assert (await s.execute(select(func.count()).select_from(Document))).scalar_one() == DOCUMENTS
        permit = (await s.execute(select(Project.permit_doc_id).where(Project.id == "PR-HT2"))).scalar_one()
    assert permit == "permit-ht-2026-014"


async def test_threshold_query_hits_policy_bands(retriever):
    results = await retriever.retrieve("landslide index warning threshold", top_k=3)
    hit = next(r for r in results if r.chunk_id == "dmp-2024#s4.2")
    assert "warning at ≥ 0.55" in hit.text and hit.kind == "policy"
    assert hit.citation.document_title == "Nandipur Disaster Management Policy"
    assert hit.citation.section == "Landslide thresholds"


async def test_history_query_filtered_to_hillview_reports(retriever):
    results = await retriever.retrieve(
        "previous Hillview landslide blocked drain D-7 and flooded Riverside",
        filters=RetrievalFilters(kinds=["report"], zone_ids=["Z-HV"]),
        top_k=5,
    )
    assert results and all(r.kind == "report" for r in results)
    assert all("Z-HV" in r.zone_ids or r.zone_ids == [] for r in results)
    assert "rep-2019-ls-01" in {r.document_id for r in results}  # the 2019 slide that blocked D-7


async def test_hazard_filter_never_returns_fire_reports(retriever):
    query = "fire in the covered cloth market stalls"
    filtered = await retriever.retrieve(query, filters=RetrievalFilters(hazards=["landslide"]), top_k=10)
    assert filtered and all("landslide" in r.hazards or r.hazards == [] for r in filtered)
    assert all(r.document_id != "rep-2015-uf-01" for r in filtered)
    unfiltered = await retriever.retrieve(query, top_k=3)
    assert unfiltered[0].document_id == "rep-2015-uf-01"


async def test_change_log_query_finds_culvert_narrowing(retriever):
    results = await retriever.retrieve(
        "D-7 culvert rebuilt Hill Road widening 2025 capacity",
        filters=RetrievalFilters(kinds=["change_log"]),
        top_k=3,
    )
    assert results[0].chunk_id == "changelog-infra-2018-2026#s2025"
    assert "capacity 42 → 27 m3/s" in results[0].text


async def test_every_citation_points_at_a_stored_chunk(retriever, indexed):
    store = ChunkStore(indexed)
    results = await retriever.retrieve("pump deployment Riverside flood", top_k=8)
    assert len(results) == 8
    for r in results:
        stored = await store.get_chunk(r.citation.id)
        assert stored is not None
        assert stored.text == r.citation.text and stored.document_title == r.citation.document_title
        assert stored.section == r.citation.section and stored.source == r.citation.source
    allowed = [r.citation.id for r in results]
    assert validate_citation_ids([*allowed, "dmp-2024#s99"], allowed) == ["dmp-2024#s99"]


async def test_large_top_k_and_filtered_search_are_complete(retriever, indexed):
    """HNSW yields at most ef_search (default 40) candidates and filters after the scan; none may be cut."""
    store = ChunkStore(indexed)
    query = HashedEmbedder().embed_query("flood")
    assert len(await store.search(query, top_k=100)) == 100
    fire = RetrievalFilters(hazards=["urban_fire"])
    async with indexed() as s:
        count = "select count(*) from chunks where 'urban_fire' = any(hazards) or cardinality(hazards) = 0"
        matching = (await s.execute(text(count))).scalar_one()
    assert matching > 40
    assert len(await store.search(query, top_k=500, filters=fire)) == matching


async def test_empty_results_are_empty_not_fabricated(retriever):
    nothing = RetrievalFilters(kinds=["permit"], zone_ids=["Z-LK"])
    assert await retriever.retrieve("landslide", filters=nothing) == []
    no_such_pair = RetrievalFilters(kinds=["report"], categories=["evacuation"])
    assert await retriever.retrieve("landslide", filters=no_such_pair) == []
    assert await retriever.retrieve("landslide", min_similarity=0.999) == []


async def test_every_category_is_indexed(indexed):
    async with indexed() as s:
        count = "select metadata->>'category', count(distinct document_id) from chunks group by 1"
        documents = {category: n for category, n in (await s.execute(text(count))).all()}
    assert set(documents) == set(get_args(DocumentCategory))
    assert documents["infrastructure_report"] >= 2 and documents["engineering_report"] >= 3


@pytest.mark.parametrize(
    "category",
    ["infrastructure_report", "engineering_report", "incident_report", "evacuation", "construction_safety"],
)
async def test_category_filter_returns_only_that_category(retriever, category):
    results = await retriever.retrieve(
        "D-7 culvert capacity, Hillview slope saturation and Riverside flooding",
        filters=RetrievalFilters(categories=[category]),
        top_k=10,
    )
    assert results and all(r.category == r.metadata["category"] == category for r in results)


async def test_bridge_inspection_answers_a_scour_question(retriever):
    results = await retriever.retrieve("Kalinadi Bridge BR-1 pier 3 scour depth inspection", top_k=3)
    assert results[0].document_id == "inspection-br1-2025"
    assert results[0].category == "infrastructure_report" and results[0].kind == "profile"


async def test_channel_survey_answers_a_d7_condition_question(retriever):
    query = "condition of the D-7 channel lining, silt and trash racks"
    results = await retriever.retrieve(query, top_k=3)
    assert "survey-d7-2026" in {r.document_id for r in results}
    filtered = await retriever.retrieve(query, filters=RetrievalFilters(categories=["infrastructure_report"]))
    assert filtered[0].document_id == "survey-d7-2026"


async def test_slope_assessment_answers_a_stability_question(retriever):
    query = "SL-HV-1 factor of safety with saturation and unsupported cut"
    results = await retriever.retrieve(query, top_k=3)
    assert results[0].document_id == "geotech-sl-hv-1-2025" and results[0].category == "engineering_report"


async def test_hydraulic_study_answers_a_design_flow_question(retriever):
    query = "D-7 design peak flow by return period against the BR-4 culvert capacity"
    results = await retriever.retrieve(query, top_k=3)
    assert "hydraulics-d7-2026" in {r.document_id for r in results}
    engineering = RetrievalFilters(categories=["engineering_report"])
    assert (await retriever.retrieve(query, filters=engineering))[0].document_id == "hydraulics-d7-2026"
