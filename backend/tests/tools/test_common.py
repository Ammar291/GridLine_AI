from datetime import UTC, datetime

import pytest

from gridline.db.models import Crew, Incident, Road
from gridline.tools.base import ActionResult, ToolRejected
from gridline.tools.common import (
    check,
    ids_in,
    open_access_roads,
    require,
    require_open_access,
    require_open_incident,
    require_road_open,
    verification,
)

NOW = datetime(2026, 7, 14, 6, 0, tzinfo=UTC)


async def test_require_names_the_missing_entity(session):
    crew = await require(session, Crew, "C-1", "crew")
    assert crew.name == "Rescue Alpha"
    with pytest.raises(ToolRejected, match=r"^road 'RD-99' not found$"):
        await require(session, Road, "RD-99", "road", lock=True)


async def test_require_open_incident(session):
    with pytest.raises(ToolRejected, match=r"^incident 'inc_x' not found$"):
        await require_open_incident(session, "inc_x")
    session.add(
        Incident(
            id="inc_x", zone_id="Z-HV", hazard="landslide", band="watch", status="closed", title="t",
            summary="s", opened_at=NOW, updated_at=NOW, closed_at=NOW,
        )
    )  # fmt: skip
    await session.flush()
    with pytest.raises(ToolRejected, match=r"^incident 'inc_x' is closed$"):
        await require_open_incident(session, "inc_x")


async def test_access_roads_link_the_zone_to_another_zone(session):
    assert [r.id for r in await open_access_roads(session, "Z-HV")] == ["RD-01"]
    assert [r.id for r in await open_access_roads(session, "Z-TH")] == ["RD-01"]  # RD-11 is local to Z-TH
    assert [r.id for r in await open_access_roads(session, "Z-CL")] == ["RD-10"]  # passes through Z-CL
    road = await session.get(Road, "RD-01")
    assert road is not None
    road.status = "closed"
    await session.flush()
    for zone in ("Z-HV", "Z-TH"):
        with pytest.raises(ToolRejected, match=rf"^zone '{zone}' has no open access road$"):
            await require_open_access(session, zone)
    await require_open_access(session, "Z-RS")  # still has RD-02, RD-10 and RD-12


async def test_require_road_open_names_the_owner(session):
    await require_road_open(session, "RD-01", "shelter 'S-6'")
    road = await session.get(Road, "RD-01")
    assert road is not None
    road.status = "blocked"
    await session.flush()
    with pytest.raises(ToolRejected, match=r"^shelter 'S-6' access road 'RD-01' is blocked$"):
        await require_road_open(session, "RD-01", "shelter 'S-6'")


def test_verification_is_verified_only_when_every_check_passes():
    assert verification(check("a", 1, 1), check("b", "x", "x")).status == "verified"
    failed = verification(check("a", 1, 1), check("b", "open", "closed"))
    assert failed.status == "failed" and [c.passed for c in failed.checks] == [True, False]
    assert verification().status == "failed"


def test_ids_in_reads_the_result_snapshot_keys():
    result = ActionResult(
        action_id="act_1", action_type="t", status="unchanged", before={}, timestamp=NOW, sim_time=None,
        after={"task:task_1": {}, "incident:inc_1": {}, "task:task_2": {}}, affected_entities=[], message="m",
        actor="agent", approval_id=None, idempotency_key=None, incident_id=None,
    )  # fmt: skip
    assert ids_in(result, "task") == ["task_1", "task_2"]
    assert ids_in(result, "alert") == []
