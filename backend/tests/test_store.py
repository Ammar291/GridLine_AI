import pytest

from gridline.db.seed.corpus import ParsedDocument, load_corpus
from gridline.rag.chunker import chunk_document
from gridline.rag.embedder import HashedEmbedder
from gridline.rag.models import IngestError, RetrievalFilters
from gridline.rag.store import ChunkStore
from tests.conftest import RAG_FIXTURES

EMBEDDER = HashedEmbedder()


async def _index(store: ChunkStore, doc: ParsedDocument, content_hash: str) -> None:
    chunks = chunk_document(doc)
    vectors = EMBEDDER.embed_documents([c.embedding_text for c in chunks])
    await store.replace_chunks(doc.meta.document_id, content_hash, EMBEDDER.name, chunks, vectors)


async def _index_fixtures(store: ChunkStore) -> dict[str, ParsedDocument]:
    docs = {d.meta.document_id: d for d in load_corpus(RAG_FIXTURES)}
    for doc_id, doc in docs.items():
        await _index(store, doc, f"hash-{doc_id}")
    return docs


@pytest.fixture
def store(rag_documents) -> ChunkStore:
    return ChunkStore(rag_documents)


async def test_replace_chunks_and_list(store):
    docs = await _index_fixtures(store)
    records = {r.id: r for r in await store.list_documents()}
    assert set(docs) <= set(records)  # seeded Nandipur documents may be listed too
    policy = records["test-policy"]
    assert policy.kind == "policy" and policy.title == "Test Disaster Policy"
    assert policy.content_hash == "hash-test-policy" and policy.embedding_model == "hashed:v1"
    assert await store.count_chunks() == 9
    assert await store.embedding_models() == {"hashed:v1"}


async def test_replace_chunks_drops_old_chunk_ids(store):
    docs = await _index_fixtures(store)
    fire = docs["test-fire-sop"]
    sections = [s.model_copy(update={"section": "s9"}) if s.section == "s2" else s for s in fire.sections]
    await _index(store, fire.model_copy(update={"sections": sections}), "hash-2")
    assert await store.get_chunk("test-fire-sop#s2") is None
    assert await store.get_chunk("test-fire-sop#s9") is not None
    assert await store.get_chunk("test-fire-sop#s1") is not None
    assert next(r for r in await store.list_documents() if r.id == "test-fire-sop").content_hash == "hash-2"


async def test_replace_chunks_refuses_unseeded_document(store):
    doc = load_corpus(RAG_FIXTURES)[0]
    ghost = doc.model_copy(update={"meta": doc.meta.model_copy(update={"document_id": "ghost-doc"})})
    with pytest.raises(IngestError, match="ghost-doc"):
        await _index(store, ghost, "h")
    assert await store.count_chunks() == 0


async def test_replace_chunks_rejects_mismatched_vectors(store):
    chunks = chunk_document(load_corpus(RAG_FIXTURES)[0])
    with pytest.raises(ValueError, match="embeddings"):
        await store.replace_chunks(chunks[0].document_id, "h", EMBEDDER.name, chunks, [])


async def test_remove_chunks_keeps_the_document_row(store):
    await _index_fixtures(store)
    assert await store.remove_chunks("test-fire-sop") is True
    assert await store.remove_chunks("test-fire-sop") is False
    assert await store.get_chunk("test-fire-sop#s1") is None
    record = next(r for r in await store.list_documents() if r.id == "test-fire-sop")
    assert record.content_hash == "" and record.embedding_model == ""  # seeded row stays, just unindexed
    assert await store.count_chunks() == 7


async def test_get_chunk_returns_stored_fields(store):
    await _index_fixtures(store)
    chunk = await store.get_chunk("test-policy#s4.2")
    assert chunk is not None
    assert chunk.chunk_id == "test-policy#s4.2" and chunk.document_id == "test-policy"
    assert chunk.document_title == "Test Disaster Policy"
    assert chunk.section_id == "s4.2" and chunk.section == "Slope construction halt rule"
    assert chunk.source == "Test Municipal Corporation, Disaster Cell"
    assert chunk.kind == "policy" and chunk.hazards == ["landslide", "flood"] and chunk.zone_ids == []
    assert "25 degrees" in chunk.text
    assert chunk.metadata["section_title"] == "Slope construction halt rule"
    assert chunk.metadata["version"] == "1.0"
    assert chunk.category == "policy" and chunk.metadata["category"] == "policy"
    assert await store.get_chunk("test-policy#s99") is None


async def test_search_ranks_by_similarity_and_builds_citations(store):
    await _index_fixtures(store)
    results = await store.search(EMBEDDER.embed_query("landslide index warning band threshold"), top_k=3)
    assert len(results) == 3
    assert results[0].chunk_id == "test-policy#s4.1"
    sims = [r.similarity for r in results]
    assert sims == sorted(sims, reverse=True) and all(-1.0 <= s <= 1.0 for s in sims)
    top = results[0]
    assert top.citation.id == top.chunk_id and top.citation.text == top.text
    assert top.citation.document_title == top.document_title and top.citation.section == top.section
    assert top.citation.source == top.source


async def test_search_kind_filter(store):
    await _index_fixtures(store)
    q = EMBEDDER.embed_query("evacuation route pump units")
    results = await store.search(q, top_k=10, filters=RetrievalFilters(kinds=["report"]))
    assert results and all(r.kind == "report" for r in results)


async def test_search_category_filter(store):
    await _index_fixtures(store)
    q = EMBEDDER.embed_query("flood riverside pump units evacuation market fire")
    reports = await store.search(q, top_k=10, filters=RetrievalFilters(categories=["incident_report"]))
    assert reports and {r.document_id for r in reports} == {"test-riverside-report"}
    assert all(r.category == r.metadata["category"] == "incident_report" for r in reports)
    rules = await store.search(q, top_k=10, filters=RetrievalFilters(categories=["policy", "sop"]))
    assert {r.document_id for r in rules} == {"test-policy", "test-fire-sop"}
    assert all(r.category in ("policy", "sop") for r in rules)
    unused = RetrievalFilters(categories=["engineering_report"])
    assert await store.search(q, top_k=10, filters=unused) == []


async def test_search_category_filter_intersects_other_filters(store):
    await _index_fixtures(store)
    q = EMBEDDER.embed_query("flood riverside pump units evacuation market fire")
    sop_in_riverside = RetrievalFilters(categories=["sop"], zone_ids=["Z-RS"])
    assert await store.search(q, top_k=10, filters=sop_in_riverside) == []
    policy_on_floods = RetrievalFilters(categories=["policy"], hazards=["flood"], zone_ids=["Z-RS"])
    results = await store.search(q, top_k=10, filters=policy_on_floods)
    assert results and {r.document_id for r in results} == {"test-policy"}


async def test_search_hazard_filter_excludes_other_hazard(store):
    await _index_fixtures(store)
    q = EMBEDDER.embed_query("market fire smoke stalls evacuation")
    results = await store.search(q, top_k=10, filters=RetrievalFilters(hazards=["landslide"]))
    assert results and all(r.document_id != "test-fire-sop" for r in results)
    assert any(r.document_id == "test-policy" for r in results)  # policy covers landslide


async def test_search_city_wide_chunk_matches_zone_filter(store):
    await _index_fixtures(store)
    q = EMBEDDER.embed_query("flood riverside pump")
    results = await store.search(q, top_k=10, filters=RetrievalFilters(zone_ids=["Z-RS"]))
    ids = {r.document_id for r in results}
    assert "test-riverside-report" in ids and "test-policy" in ids and "test-fire-sop" not in ids
    assert all(r.zone_ids == [] or "Z-RS" in r.zone_ids for r in results)


async def test_search_combined_filters_intersect(store):
    await _index_fixtures(store)
    q = EMBEDDER.embed_query("flood")
    filters = RetrievalFilters(zone_ids=["Z-RS"], kinds=["sop"])
    assert await store.search(q, top_k=10, filters=filters) == []


async def test_search_document_ids_filter(store):
    await _index_fixtures(store)
    q = EMBEDDER.embed_query("crews market")
    results = await store.search(q, top_k=10, filters=RetrievalFilters(document_ids=["test-fire-sop"]))
    assert results and {r.document_id for r in results} == {"test-fire-sop"}


async def test_search_empty_store_returns_empty(store):
    assert await store.search(EMBEDDER.embed_query("landslide"), top_k=5) == []


async def test_search_top_k_is_honoured(store):
    await _index_fixtures(store)
    assert len(await store.search(EMBEDDER.embed_query("flood riverside pump"), top_k=2)) == 2


async def test_search_with_zero_vector_returns_empty(store):
    await _index_fixtures(store)
    assert await store.search([0.0] * EMBEDDER.dimension, top_k=5) == []
