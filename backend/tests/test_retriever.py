import pytest
from pydantic import ValidationError

from gridline.db.seed.corpus import load_corpus
from gridline.rag.chunker import chunk_document
from gridline.rag.embedder import HashedEmbedder
from gridline.rag.models import EmbeddingModelMismatchError, RetrievalFilters
from gridline.rag.retriever import Retriever
from gridline.rag.store import ChunkStore
from tests.conftest import RAG_FIXTURES


class RenamedEmbedder(HashedEmbedder):
    @property
    def name(self) -> str:
        return "hashed:v999"


@pytest.fixture
async def loaded_store(rag_documents) -> ChunkStore:
    store = ChunkStore(rag_documents)
    embedder = HashedEmbedder()
    for doc in load_corpus(RAG_FIXTURES):
        chunks = chunk_document(doc)
        vectors = embedder.embed_documents([c.embedding_text for c in chunks])
        await store.replace_chunks(doc.meta.document_id, "h", embedder.name, chunks, vectors)
    return store


async def test_retrieve_returns_policy_chunk_with_full_citation(loaded_store):
    results = await Retriever(loaded_store, HashedEmbedder()).retrieve(
        "landslide index warning band threshold", top_k=3
    )
    r = results[0]
    assert r.chunk_id == "test-policy#s4.1"
    assert r.document_id == "test-policy" and r.document_title == "Test Disaster Policy"
    assert r.section == "Risk index bands" and r.source == "Test Municipal Corporation, Disaster Cell"
    assert "0.60" in r.text and r.metadata["section_title"] == "Risk index bands"
    assert r.citation.id == r.chunk_id and r.citation.text == r.text


async def test_retrieve_top_k_and_ordering(loaded_store):
    results = await Retriever(loaded_store, HashedEmbedder()).retrieve("flood pump riverside", top_k=4)
    assert len(results) == 4
    assert [r.similarity for r in results] == sorted((r.similarity for r in results), reverse=True)


async def test_retrieve_applies_filters(loaded_store):
    retriever = Retriever(loaded_store, HashedEmbedder())
    only_sop = await retriever.retrieve("fire market", filters=RetrievalFilters(kinds=["sop"]), top_k=10)
    assert only_sop and all(r.kind == "sop" for r in only_sop)
    no_fire = await retriever.retrieve("fire market", filters=RetrievalFilters(hazards=["flood"]), top_k=10)
    assert no_fire and all(r.document_id != "test-fire-sop" for r in no_fire)
    reports = RetrievalFilters(categories=["incident_report"])
    only_reports = await retriever.retrieve("fire market flood", filters=reports, top_k=10)
    assert only_reports and all(r.category == "incident_report" for r in only_reports)


def test_category_filter_is_a_closed_set():
    assert RetrievalFilters(categories=["engineering_report", "evacuation"]).categories == [
        "engineering_report",
        "evacuation",
    ]
    with pytest.raises(ValidationError):
        RetrievalFilters.model_validate({"categories": ["gossip"]})


async def test_retrieve_min_similarity_can_empty_results(loaded_store):
    retriever = Retriever(loaded_store, HashedEmbedder())
    assert await retriever.retrieve("landslide index warning band threshold", min_similarity=0.99) == []


async def test_retrieve_impossible_filter_returns_empty(loaded_store):
    retriever = Retriever(loaded_store, HashedEmbedder())
    assert await retriever.retrieve("landslide", filters=RetrievalFilters(document_ids=["nope"])) == []


async def test_retrieve_on_empty_store_returns_empty(rag_documents):
    assert await Retriever(ChunkStore(rag_documents), HashedEmbedder()).retrieve("landslide") == []


async def test_retrieve_rejects_blank_query(loaded_store):
    with pytest.raises(ValueError, match="query"):
        await Retriever(loaded_store, HashedEmbedder()).retrieve("   ")


async def test_retrieve_rejects_bad_top_k(loaded_store):
    with pytest.raises(ValueError, match="top_k"):
        await Retriever(loaded_store, HashedEmbedder()).retrieve("landslide", top_k=0)


async def test_retrieve_refuses_mismatched_embedder(loaded_store):
    retriever = Retriever(loaded_store, RenamedEmbedder())
    with pytest.raises(EmbeddingModelMismatchError, match="hashed:v1"):
        await retriever.retrieve("landslide")


async def test_mismatch_is_detected_after_a_reindex(loaded_store):
    retriever = Retriever(loaded_store, HashedEmbedder())
    assert await retriever.retrieve("landslide")
    renamed = RenamedEmbedder()
    for doc in load_corpus(RAG_FIXTURES):  # the corpus is re-embedded by another process
        chunks = chunk_document(doc)
        vectors = renamed.embed_documents([c.embedding_text for c in chunks])
        await loaded_store.replace_chunks(doc.meta.document_id, "h", renamed.name, chunks, vectors)
    with pytest.raises(EmbeddingModelMismatchError, match="hashed:v999"):
        await retriever.retrieve("landslide")
