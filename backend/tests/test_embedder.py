import math
import os

import pytest

from gridline.rag.embedder import FastEmbedEmbedder, HashedEmbedder, build_embedder


def _cos(a, b):
    return sum(x * y for x, y in zip(a, b, strict=True))


def test_hashed_embedder_shape_and_norm():
    e = HashedEmbedder()
    assert e.name == "hashed:v1" and e.dimension == 384
    vec = e.embed_query("landslide warning threshold")
    assert len(vec) == 384
    assert math.isclose(math.sqrt(sum(x * x for x in vec)), 1.0, rel_tol=1e-6)


def test_hashed_embedder_is_deterministic():
    text = "Excavation must halt when saturation exceeds 0.70."
    assert HashedEmbedder().embed_documents([text]) == HashedEmbedder().embed_documents([text])


def test_hashed_embedder_related_text_is_closer():
    e = HashedEmbedder()
    q = e.embed_query("landslide index warning band threshold")
    related, unrelated = e.embed_documents(
        [
            "The landslide index enters the warning band at 0.60.",
            "Stall holders leave through the north gate.",
        ]
    )
    assert _cos(q, related) > _cos(q, unrelated)


def test_hashed_embedder_treats_asset_ids_as_tokens():
    e = HashedEmbedder()
    q = e.embed_query("D-7 blocked")
    same_id, other_id = e.embed_documents(
        ["Debris blocked D-7 below the culvert.", "Debris blocked D-3 below culvert 7."]
    )
    assert _cos(q, same_id) > _cos(q, other_id)


def test_hashed_embedder_matches_inflections():
    e = HashedEmbedder()
    q = e.embed_query("widening of the road, drains blocking")
    inflected, other = e.embed_documents(
        ["The road was widened and the drain was blocked.", "The road was resurfaced and the verge cut."]
    )
    assert _cos(q, inflected) > _cos(q, other)


def test_hashed_embedder_finds_years_inside_dates():
    e = HashedEmbedder()
    q = e.embed_query("culvert changes in 2025")
    same_year, other_year = e.embed_documents(
        ["CH-01 — 2025-05-20 — culvert rebuilt", "CH-01 — 2024-05-20 — culvert rebuilt"]
    )
    assert _cos(q, same_year) > _cos(q, other_year)


def test_hashed_embedder_blank_or_stopword_text_is_zero_vector():
    e = HashedEmbedder()
    assert all(x == 0.0 for x in e.embed_query(""))
    assert all(x == 0.0 for x in e.embed_query("the and of"))


def test_hashed_embedder_empty_batch():
    assert HashedEmbedder().embed_documents([]) == []


def test_build_embedder_hashed():
    assert isinstance(build_embedder("hashed", "ignored"), HashedEmbedder)


def test_build_embedder_fastembed_is_lazy():
    e = build_embedder("fastembed", "BAAI/bge-small-en-v1.5")
    assert isinstance(e, FastEmbedEmbedder)
    assert e.name == "fastembed:BAAI/bge-small-en-v1.5" and e.dimension == 384


def test_build_embedder_auto_falls_back_when_model_unavailable(monkeypatch, caplog):
    def offline(self):
        raise RuntimeError("offline")

    monkeypatch.setattr(FastEmbedEmbedder, "warm_up", offline)
    e = build_embedder("auto", "BAAI/bge-small-en-v1.5")
    assert isinstance(e, HashedEmbedder)
    assert "falling back to hashed" in caplog.text


def test_build_embedder_auto_uses_fastembed_when_it_loads(monkeypatch):
    monkeypatch.setattr(FastEmbedEmbedder, "warm_up", lambda self: None)
    assert isinstance(build_embedder("auto", "BAAI/bge-small-en-v1.5"), FastEmbedEmbedder)


@pytest.mark.skipif(
    os.environ.get("GRIDLINE_TEST_FASTEMBED") != "1", reason="set GRIDLINE_TEST_FASTEMBED=1 to run"
)
def test_fastembed_real_model():
    e = FastEmbedEmbedder("BAAI/bge-small-en-v1.5")
    q = e.embed_query("landslide index warning band threshold")
    docs = e.embed_documents(
        ["The landslide index enters the warning band at 0.60.", "Stall holders leave via the gate."]
    )
    assert len(q) == 384 and _cos(q, docs[0]) > _cos(q, docs[1])
