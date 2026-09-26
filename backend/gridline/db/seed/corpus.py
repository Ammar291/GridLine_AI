"""Parse the Markdown corpus: YAML front matter plus numbered ``##`` sections (spec §7).

``## 4.2 Title`` becomes section ``s4.2``; text before the first heading becomes ``s0`` when non-empty;
``###`` headings stay inside their parent section. Any other ``##`` line, or a repeated number, is a
``CorpusError``.
"""

import re
from pathlib import Path
from typing import Any, cast

import yaml
from pydantic import BaseModel, ValidationError

from gridline.city.schema_history import DocumentMeta, ImpactRecord, IncidentRecord
from gridline.config import BACKEND_DIR

HEADING = re.compile(r"^## (\d+(?:\.\d+)*) (.+)$")
PREAMBLE_HEADING = "Introduction"


class CorpusError(Exception):
    """A corpus file that cannot be parsed; the message names the file."""

    def __init__(self, file: str, message: str) -> None:
        super().__init__(f"{file}: {message}")
        self.file = file
        self.message = message


class ParsedSection(BaseModel):
    section: str
    heading: str
    text: str
    position: int


class ParsedDocument(BaseModel):
    meta: DocumentMeta
    sections: list[ParsedSection]
    incident: IncidentRecord | None
    impacts: list[ImpactRecord]
    source_path: str


def _split_front_matter(name: str, raw: str) -> tuple[dict[str, Any], str]:
    lines = raw.splitlines()
    if not lines or lines[0].strip() != "---":
        raise CorpusError(name, "missing YAML front matter (first line must be '---')")
    try:
        end = next(i for i, line in enumerate(lines[1:], start=1) if line.strip() == "---")
    except StopIteration:
        raise CorpusError(name, "front matter is not closed by a '---' line") from None
    try:
        loaded: object = yaml.safe_load("\n".join(lines[1:end]))
    except yaml.YAMLError as exc:
        raise CorpusError(name, f"invalid front matter YAML: {exc}") from exc
    if not isinstance(loaded, dict):
        raise CorpusError(name, "front matter must be a mapping")
    return {str(k): v for k, v in cast(dict[Any, Any], loaded).items()}, "\n".join(lines[end + 1 :])


def _split_sections(name: str, body: str) -> list[ParsedSection]:
    chunks: list[tuple[str, str, list[str]]] = [("s0", PREAMBLE_HEADING, [])]
    for line in body.splitlines():
        if line.startswith("## ") or line.rstrip() == "##":
            match = HEADING.match(line.rstrip())
            if match is None:
                raise CorpusError(name, f"heading is not numbered ('## N Title'): {line!r}")
            section = f"s{match.group(1)}"
            if any(existing == section for existing, _, _ in chunks):
                raise CorpusError(name, f"duplicate section number {section}: {line!r}")
            chunks.append((section, match.group(2).strip(), []))
        else:
            chunks[-1][2].append(line)
    sections: list[ParsedSection] = []
    for section, heading, text_lines in chunks:
        text = "\n".join(text_lines).strip()
        if section == "s0" and not text:
            continue
        if not text:
            raise CorpusError(name, f"section {section} ({heading}) is empty")
        sections.append(ParsedSection(section=section, heading=heading, text=text, position=len(sections)))
    return sections


def parse_document(path: Path) -> ParsedDocument:
    name = path.name
    front, body = _split_front_matter(name, path.read_text(encoding="utf-8"))
    incident_raw = front.pop("incident", None)
    impacts_raw: list[Any] = front.pop("impacts", None) or []
    try:
        meta = DocumentMeta.model_validate(front)
        incident = None if incident_raw is None else IncidentRecord.model_validate(incident_raw)
        impacts = [ImpactRecord.model_validate(item) for item in impacts_raw]
    except ValidationError as exc:
        raise CorpusError(name, f"invalid front matter: {exc}") from exc
    if meta.document_id != path.stem:
        raise CorpusError(name, f"document_id {meta.document_id!r} does not match the file name")
    if (meta.kind == "report") != (incident is not None and bool(impacts)):
        raise CorpusError(name, "reports, and only reports, carry 'incident' and non-empty 'impacts' blocks")
    return ParsedDocument(
        meta=meta,
        sections=_split_sections(name, body),
        incident=incident,
        impacts=impacts,
        source_path=_display_path(path),
    )


def _display_path(path: Path) -> str:
    """Path relative to ``backend/`` when inside it (stable across machines), else as given."""
    resolved = path.resolve()
    return resolved.relative_to(BACKEND_DIR).as_posix() if resolved.is_relative_to(BACKEND_DIR) else str(path)


def load_corpus(corpus_dir: Path) -> list[ParsedDocument]:
    """Parse every ``*.md`` file in ``corpus_dir``, sorted by file name."""
    return [parse_document(path) for path in sorted(corpus_dir.glob("*.md"))]
