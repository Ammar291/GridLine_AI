from pathlib import Path

import pytest

from gridline.db.seed.corpus import CorpusError, ParsedDocument, load_corpus, parse_document
from gridline.rag.chunker import chunk_document

FIXTURES = Path(__file__).parent / "fixtures" / "corpus"
FRONT_MATTER = (
    "---\ndocument_id: {doc_id}\ntitle: Doc\nkind: policy\nsource: S\nversion: '1'\n"
    "effective_date: 2024-01-01\nhazards: [landslide]\nzone_ids: [Z-HV]\nsummary: s\n---\n"
)


def _fixture(doc_id: str) -> ParsedDocument:
    return next(d for d in load_corpus(FIXTURES) if d.meta.document_id == doc_id)


def _write(tmp_path: Path, body: str, doc_id: str = "d") -> ParsedDocument:
    path = tmp_path / f"{doc_id}.md"
    path.write_text(FRONT_MATTER.format(doc_id=doc_id) + body, encoding="utf-8")
    return parse_document(path)


def test_one_chunk_per_section_with_citation_ids():
    policy = _fixture("test-policy")
    chunks = chunk_document(policy)
    assert [c.chunk_id for c in chunks] == [
        "test-policy#s0",
        "test-policy#s1",
        "test-policy#s4.1",
        "test-policy#s4.2",
        "test-policy#s5",
    ]
    halt = chunks[3]
    assert halt.document_id == "test-policy" and halt.section_id == "s4.2"
    assert halt.section_title == "Slope construction halt rule"
    assert halt.position == 3
    assert "25 degrees" in halt.text and "## 4.2" not in halt.text
    assert halt.embedding_text.startswith("Test Disaster Policy — Slope construction halt rule\n")
    assert halt.kind == "policy" and halt.hazards == ["landslide", "flood"] and halt.zone_ids == []
    assert halt.metadata["section_title"] == "Slope construction halt rule"
    assert halt.metadata["source_path"] == "tests/fixtures/corpus/test-policy.md"
    assert halt.metadata["version"] == "1.0" and halt.metadata["effective_date"] == "2024-03-15"
    assert halt.metadata["part"] == 1 and halt.metadata["word_count"] == len(halt.text.split())
    assert chunk_document(policy) == chunks  # a pure function of the file: same ids on every run


def test_chunk_ids_equal_section_citation_ids():
    for doc in load_corpus(FIXTURES):
        chunks = chunk_document(doc)
        assert [c.chunk_id for c in chunks] == [f"{doc.meta.document_id}#{s.section}" for s in doc.sections]
        assert all(c.text.strip() for c in chunks)


def test_preamble_is_section_s0():
    first = chunk_document(_fixture("test-policy"))[0]
    assert first.section_id == "s0" and first.section_title == "Introduction"
    assert first.text.startswith("This policy applies to every zone")


def test_no_s0_chunk_without_preamble():
    assert [c.section_id for c in chunk_document(_fixture("test-fire-sop"))] == ["s1", "s2"]


def test_long_section_is_split_into_parts_at_paragraphs(tmp_path):
    para = " ".join(["lorem"] * 120) + "\n\n"
    chunks = chunk_document(_write(tmp_path, "## 1 Long\n\n" + para * 4), max_words=200)
    assert [c.chunk_id for c in chunks] == ["d#s1", "d#s1-p2", "d#s1-p3", "d#s1-p4"]
    assert all(c.section_title == "Long" for c in chunks)
    assert [c.metadata["part"] for c in chunks] == [1, 2, 3, 4]
    assert [c.position for c in chunks] == [0, 1, 2, 3]
    assert all(len(c.text.split()) == 120 for c in chunks)


def test_paragraphs_are_packed_up_to_max_words(tmp_path):
    para = " ".join(["w"] * 60) + "\n\n"
    chunks = chunk_document(_write(tmp_path, "## 1 A\n\n" + para * 5), max_words=150)
    assert [len(c.text.split()) for c in chunks] == [120, 120, 60]


def test_short_sections_stay_citable_on_their_own(tmp_path):
    body = "## 1 A\n\n" + "alpha " * 60 + "\n\n## 2 Tiny\n\nJust a few words.\n\n## 3 C\n\n" + "gamma " * 60
    chunks = chunk_document(_write(tmp_path, body))
    assert [c.section_id for c in chunks] == ["s1", "s2", "s3"]
    assert chunks[1].text == "Just a few words."


def test_repeated_heading_text_gets_distinct_chunk_ids(tmp_path):
    body = "## 3 Notes\n\n" + "one " * 30 + "\n\n## 5 Notes\n\n" + "two " * 30
    chunks = chunk_document(_write(tmp_path, body))
    assert [c.chunk_id for c in chunks] == ["d#s3", "d#s5"]
    assert [c.section_title for c in chunks] == ["Notes", "Notes"]


def test_colliding_headings_are_rejected_before_chunking(tmp_path):
    with pytest.raises(CorpusError, match="duplicate section"):
        _write(tmp_path, "## 1 Notes\n\none\n\n## 1 Notes\n\ntwo\n")
    with pytest.raises(CorpusError, match="not numbered"):
        _write(tmp_path, "## Notes\n\none\n\n## Notes\n\ntwo\n")


def test_chunker_refuses_colliding_section_ids():
    doc = _fixture("test-fire-sop")
    twin = doc.sections[0].model_copy(update={"position": 1})
    with pytest.raises(ValueError, match="test-fire-sop#s1"):
        chunk_document(doc.model_copy(update={"sections": [doc.sections[0], twin]}))


def test_h3_stays_inside_parent_section(tmp_path):
    body = "## 1 A\n\n" + "alpha " * 30 + "\n\n### Detail\n\n" + "beta " * 30
    chunks = chunk_document(_write(tmp_path, body))
    assert [c.section_id for c in chunks] == ["s1"]
    assert "### Detail" in chunks[0].text and "beta" in chunks[0].text
