from pathlib import Path

import pytest

from gridline.db.seed.corpus import CorpusError, load_corpus, parse_document

CORPUS = Path(__file__).resolve().parents[1] / "data" / "corpus"

FRONT_MATTER = (
    "---\ndocument_id: x\ntitle: T\nkind: policy\nsource: S\nversion: '1'\n"
    "effective_date: 2024-01-01\nhazards: []\nzone_ids: []\nsummary: s\n---\n"
)


def _section_key(section: str) -> list[int]:
    return [int(p) for p in section[1:].split(".")]


def test_all_documents_parse_with_expected_count() -> None:
    docs = load_corpus(CORPUS)
    assert len(docs) == 33
    assert {d.meta.kind for d in docs} == {"policy", "sop", "report", "permit", "change_log", "profile"}
    assert all(d.meta.document_id == Path(d.source_path).stem for d in docs)


def test_section_ids_follow_heading_numbers() -> None:
    doc = next(d for d in load_corpus(CORPUS) if d.meta.document_id == "dmp-2024")
    ids = [s.section for s in doc.sections]
    assert ids[0] == "s0"  # preamble before the first heading
    assert "s4.2" in ids
    numbered = ids[1:]
    assert numbered == sorted(numbered, key=_section_key)
    assert [s.position for s in doc.sections] == list(range(len(doc.sections)))
    assert all(s.text.strip() for s in doc.sections)
    s42 = next(s for s in doc.sections if s.section == "s4.2")
    assert s42.heading == "Landslide thresholds"


def test_change_log_has_one_section_per_year() -> None:
    doc = next(d for d in load_corpus(CORPUS) if d.meta.kind == "change_log")
    assert [s.section for s in doc.sections if s.section != "s0"] == [f"s{y}" for y in range(2018, 2027)]


def test_reports_carry_incident_blocks() -> None:
    reports = [d for d in load_corpus(CORPUS) if d.meta.kind == "report"]
    assert len(reports) == 17
    assert all(d.incident is not None and d.impacts for d in reports)
    assert all(d.incident is None and not d.impacts for d in load_corpus(CORPUS) if d.meta.kind != "report")


def test_triple_hash_stays_inside_parent_section(tmp_path: Path) -> None:
    doc_path = tmp_path / "x.md"
    doc_path.write_text(FRONT_MATTER + "## 1 Purpose\nintro\n### Detail\nmore\n## 2 Scope\ntext\n")
    doc = parse_document(doc_path)
    assert [s.section for s in doc.sections] == ["s1", "s2"]
    assert "### Detail" in doc.sections[0].text and "more" in doc.sections[0].text


def test_unnumbered_heading_rejected(tmp_path: Path) -> None:
    bad = tmp_path / "x.md"
    bad.write_text(FRONT_MATTER + "## Purpose\ntext\n")
    with pytest.raises(CorpusError) as err:
        parse_document(bad)
    assert "x.md" in str(err.value) and "## Purpose" in str(err.value)


def test_duplicate_section_number_rejected(tmp_path: Path) -> None:
    bad = tmp_path / "x.md"
    bad.write_text(FRONT_MATTER + "## 1 Purpose\ntext\n## 1 Again\ntext\n")
    with pytest.raises(CorpusError) as err:
        parse_document(bad)
    assert "x.md" in str(err.value) and "1 Again" in str(err.value)


def test_missing_front_matter_rejected(tmp_path: Path) -> None:
    bad = tmp_path / "x.md"
    bad.write_text("## 1 Purpose\ntext\n")
    with pytest.raises(CorpusError):
        parse_document(bad)


def test_unknown_front_matter_key_rejected(tmp_path: Path) -> None:
    bad = tmp_path / "x.md"
    bad.write_text(FRONT_MATTER.replace("summary: s", "summary: s\nsumary: typo") + "## 1 P\ntext\n")
    with pytest.raises(CorpusError):
        parse_document(bad)


def test_report_without_incident_rejected(tmp_path: Path) -> None:
    bad = tmp_path / "x.md"
    bad.write_text(FRONT_MATTER.replace("kind: policy", "kind: report") + "## 1 Summary\ntext\n")
    with pytest.raises(CorpusError):
        parse_document(bad)
