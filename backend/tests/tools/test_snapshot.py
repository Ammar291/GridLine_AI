import json
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from gridline.db.models import Incident, Road
from gridline.tools.base import EntityRef
from gridline.tools.snapshot import ENTITY_MODELS, row_to_dict, snapshot


def test_entity_ref_key_and_kinds():
    assert EntityRef(kind="road", id="RD-01").key == "road:RD-01"
    with pytest.raises(ValidationError):
        EntityRef(kind="spaceship", id="X-1")  # type: ignore[arg-type]
    assert {"road", "crew", "ambulance", "shelter", "hospital_bed", "incident", "task", "project"} <= set(
        ENTITY_MODELS
    )


def test_row_to_dict_is_json_safe():
    at = datetime(2026, 7, 14, 6, 0, tzinfo=UTC)
    row = Incident(
        id="inc_1", zone_id="Z-HV", hazard="landslide", band="watch", status="open", title="t", summary="s",
        opened_at=at, updated_at=at, closed_at=None,
    )  # fmt: skip
    d = row_to_dict(row)
    assert d["opened_at"] == "2026-07-14T06:00:00Z" and d["closed_at"] is None and d["zone_id"] == "Z-HV"
    json.dumps(d)


async def test_snapshot_reads_rows_by_ref(session):
    refs = [
        EntityRef(kind="road", id="RD-01"),
        EntityRef(kind="crew", id="C-1"),
        EntityRef(kind="road", id="RD-99"),
    ]
    snap = await snapshot(session, refs)
    assert set(snap) == {"road:RD-01", "crew:C-1"}  # a missing row is omitted, not invented
    assert snap["road:RD-01"]["status"] == "open" and snap["road:RD-01"]["name"] == "Hill Road"
    assert snap["crew:C-1"]["kind"] == "rescue"
    json.dumps(snap)


async def test_snapshot_reflects_unflushed_identity_map_state(session):
    road = await session.get(Road, "RD-02")
    assert road is not None
    road.status = "closed"
    snap = await snapshot(session, [EntityRef(kind="road", id="RD-02")])
    assert snap["road:RD-02"]["status"] == "closed"
