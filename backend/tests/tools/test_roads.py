import pytest

from gridline.db.models import Road
from gridline.tools.base import EntityRef, ToolRejected
from gridline.tools.executor import execute_action
from gridline.tools.roads import CloseRoad, GetRoadStatus, ReopenRoad
from tests.tools.helpers import add_incident, fresh, tamper

CLOSE, REOPEN, STATUS = CloseRoad(), ReopenRoad(), GetRoadStatus()


async def _status(ctx, **filters):
    return await STATUS.run(STATUS.Input.model_validate(filters), ctx)


async def test_get_road_status_filters_by_road_and_zone(ctx):
    assert len((await _status(ctx)).items) == 14
    assert [r.id for r in (await _status(ctx, road_id="RD-01")).items] == ["RD-01"]
    assert [r.id for r in (await _status(ctx, zone_id="Z-HV")).items] == ["RD-01"]
    assert [r.id for r in (await _status(ctx, zone_id="Z-RS")).items] == ["RD-01", "RD-02", "RD-10", "RD-12"]
    with pytest.raises(ToolRejected, match=r"^road 'RD-99' not found$"):
        await _status(ctx, road_id="RD-99")
    with pytest.raises(ToolRejected, match=r"^zone 'Z-XX' not found$"):
        await _status(ctx, zone_id="Z-XX")


async def test_close_road_changes_the_database(ctx, check_session):
    incident = await add_incident(check_session)
    raw = {"road_id": "RD-01", "reason": "Slope movement above the road", "incident_id": incident}
    result = await execute_action(CLOSE, raw, ctx)
    assert result.status == "executed" and result.affected_entities == [EntityRef(kind="road", id="RD-01")]
    assert (
        result.before["road:RD-01"]["status"] == "open" and result.after["road:RD-01"]["status"] == "closed"
    )
    road = await fresh(check_session, Road, "RD-01")
    assert (road.status, road.closure_reason, road.incident_id) == ("closed", raw["reason"], incident)
    assert road.closed_at is not None
    assert result.incident_id == incident
    assert [r.status for r in (await _status(ctx, road_id="RD-01")).items] == ["closed"]


async def test_close_road_is_unchanged_when_already_closed(ctx):
    await execute_action(CLOSE, {"road_id": "RD-02", "reason": "flooding"}, ctx)
    again = await execute_action(CLOSE, {"road_id": "RD-02", "reason": "flooding"}, ctx)
    assert (again.status, again.message) == ("unchanged", "road 'RD-02' is already closed")
    assert again.before == again.after and again.affected_entities == []


async def test_close_road_rejections(ctx, ctx_no_approval, check_session):
    await add_incident(check_session, "inc_closed", status="closed")
    cases = [
        ({"road_id": "RD-99", "reason": "x"}, "road 'RD-99' not found"),
        ({"road_id": "RD-01", "reason": "x", "incident_id": "inc_nope"}, "incident 'inc_nope' not found"),
        ({"road_id": "RD-01", "reason": "x", "incident_id": "inc_closed"}, "incident 'inc_closed' is closed"),
    ]
    for raw, message in cases:
        result = await execute_action(CLOSE, raw, ctx)
        assert (result.status, result.message) == ("rejected", message)
    refused = await execute_action(CLOSE, {"road_id": "RD-01", "reason": "x"}, ctx_no_approval)
    assert (refused.status, refused.message) == ("rejected", "approval required for close_road")
    assert (await fresh(check_session, Road, "RD-01")).status == "open"
    blank = await execute_action(CLOSE, {"road_id": "RD-01", "reason": "  "}, ctx)
    assert blank.status == "rejected" and blank.message.startswith("reason:")


async def test_close_road_verify_reads_the_database(ctx, check_session):
    raw = {"road_id": "RD-01", "reason": "x"}
    result = await execute_action(CLOSE, raw, ctx)
    inp = CLOSE.Input.model_validate(raw)
    assert (await CLOSE.verify(inp, ctx, result)).status == "verified"
    await tamper(check_session, Road, "RD-01", status="open")
    failed = await CLOSE.verify(inp, ctx, result)
    assert failed.status == "failed" and failed.checks[0].observed == "open"


async def test_reopen_road_clears_the_closure(ctx, check_session):
    incident = await add_incident(check_session)
    await execute_action(CLOSE, {"road_id": "RD-01", "reason": "x", "incident_id": incident}, ctx)
    result = await execute_action(REOPEN, {"road_id": "RD-01", "reason": "Debris cleared"}, ctx)
    assert result.status == "executed" and result.after["road:RD-01"]["status"] == "open"
    road = await fresh(check_session, Road, "RD-01")
    assert (road.status, road.closure_reason, road.closed_at, road.incident_id) == ("open", None, None, None)


async def test_reopen_road_unchanged_rejections_and_approval(ctx, ctx_no_approval, check_session):
    same = await execute_action(REOPEN, {"road_id": "RD-03", "reason": "x"}, ctx)
    assert (same.status, same.message) == ("unchanged", "road 'RD-03' is already open")
    await tamper(check_session, Road, "RD-01", status="blocked", closure_reason="landslide debris")
    blocked = await execute_action(REOPEN, {"road_id": "RD-01", "reason": "x"}, ctx)
    assert (blocked.status, blocked.message) == (
        "rejected",
        "road 'RD-01' is blocked (landslide debris); clear it before reopening",
    )
    missing = await execute_action(REOPEN, {"road_id": "RD-99", "reason": "x"}, ctx)
    assert missing.message == "road 'RD-99' not found"
    await tamper(check_session, Road, "RD-02", status="closed")
    refused = await execute_action(REOPEN, {"road_id": "RD-02", "reason": "x"}, ctx_no_approval)
    assert (refused.status, refused.message) == ("rejected", "approval required for reopen_road")
    assert (await fresh(check_session, Road, "RD-02")).status == "closed"


async def test_reopen_road_verify(ctx, check_session):
    await tamper(check_session, Road, "RD-05", status="closed")
    raw = {"road_id": "RD-05", "reason": "x"}
    result = await execute_action(REOPEN, raw, ctx)
    inp = REOPEN.Input.model_validate(raw)
    assert (await REOPEN.verify(inp, ctx, result)).status == "verified"
    await tamper(check_session, Road, "RD-05", status="closed")
    assert (await REOPEN.verify(inp, ctx, result)).status == "failed"
