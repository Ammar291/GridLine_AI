from gridline.rag.citations import build_citation, citation_id, format_citation, validate_citation_ids
from gridline.rag.models import StoredChunk


def _chunk() -> StoredChunk:
    return StoredChunk(
        chunk_id="dmp-2024#s5",
        document_id="dmp-2024",
        document_title="Nandipur Disaster Management Policy",
        section_id="s5",
        section="Construction halt rule on steep slopes",
        source="NMC Disaster Management Cell",
        kind="policy",
        category="policy",
        zone_ids=[],
        hazards=["landslide"],
        text="All excavation ... shall be halted ...",
        metadata={},
    )


def test_citation_id_format():
    assert citation_id("dmp-2024", "s4.2") == "dmp-2024#s4.2"
    assert citation_id("dmp-2024", "s4.2-p2") == "dmp-2024#s4.2-p2"


def test_build_citation_copies_chunk_fields():
    c = build_citation(_chunk())
    assert c.id == "dmp-2024#s5"
    assert c.document_title == "Nandipur Disaster Management Policy"
    assert c.section == "Construction halt rule on steep slopes"
    assert c.source == "NMC Disaster Management Cell"
    assert c.text == "All excavation ... shall be halted ..."


def test_format_citation():
    assert format_citation(build_citation(_chunk())) == (
        "[dmp-2024#s5] Nandipur Disaster Management Policy — Construction halt rule on steep slopes "
        "(NMC Disaster Management Cell)"
    )


def test_validate_rejects_unknown_and_keeps_order():
    allowed = ["dmp-2024#s4.2", "sop-crew-dispatch-2023#s2"]
    cited = ["dmp-2024#s4.2", "made-up#s9", "sop-crew-dispatch-2023#s2", "made-up#s9", "other#x"]
    assert validate_citation_ids(cited, allowed) == ["made-up#s9", "other#x"]


def test_validate_accepts_all_known():
    assert validate_citation_ids(["a#s1", "b#s2"], {"a#s1", "b#s2", "c#s3"}) == []


def test_validate_empty_inputs():
    assert validate_citation_ids([], []) == []
    assert validate_citation_ids(["a#s1"], []) == ["a#s1"]
