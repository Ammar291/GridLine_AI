import pytest

from gridline.db.models import EvacuationOrder, Road, Shelter
from gridline.tools.base import EntityRef, ToolRejected
from gridline.tools.executor import execute_action
from gridline.tools.shelters import CloseShelter, GetShelterCapacity, OpenShelter
from tests.tools.helpers import NOW, add_incident, fresh, tamper

CAPACITY, OPEN, CLOSE = GetShelterCapacity(), OpenShelter(), CloseShelter()


async def _items(ctx, **filters):
    return (await CAPACITY.run(CAPACITY.Input.model_validate(filters), ctx)).items


async def test_get_shelter_capacity(ctx):
    assert [s.id for s in await _items(ctx)] == [f"S-{n}" for n in range(1, 9)]
    [s1] = await _items(ctx, shelter_id="S-1")
    assert (s1.status, s1.capacity_persons, s1.current_occupancy, s1.available) == ("closed", 800, 0, 800)
    assert [s.id for s in await _items(ctx, zone_id="Z-RS")] == ["S-5"]
    with pytest.raises(ToolRejected, match=r"^shelter 'S-99' not found$"):
        await _items(ctx, shelter_id="S-99")
    with pytest.raises(ToolRejected, match=r"^zone 'Z-XX' not found$"):
        await _items(ctx, zone_id="Z-XX")


async def test_open_shelter_changes_the_database(ctx, check_session):
    incident = await add_incident(check_session, zone_id="Z-RS", hazard="flood")
    result = await execute_action(OPEN, {"shelter_id": "S-1", "incident_id": incident}, ctx)
    assert result.status == "executed" and result.affected_entities == [EntityRef(kind="shelter", id="S-1")]
    assert (result.before["shelter:S-1"]["status"], result.after["shelter:S-1"]["status"]) == (
        "closed",
        "open",
    )
    shelter = await fresh(check_session, Shelter, "S-1")
    assert (shelter.status, shelter.incident_id) == ("open", incident) and shelter.opened_at is not None
    assert [s.status for s in await _items(ctx, shelter_id="S-1")] == ["open"]
    again = await execute_action(OPEN, {"shelter_id": "S-1"}, ctx)
    assert (again.status, again.message) == ("unchanged", "shelter 'S-1' is already open")


async def test_open_shelter_rejections(ctx, ctx_no_approval, check_session):
    await add_incident(check_session, "inc_closed", status="closed")
    assert (await execute_action(OPEN, {"shelter_id": "S-99"}, ctx)).message == "shelter 'S-99' not found"
    closed_incident = await execute_action(OPEN, {"shelter_id": "S-1", "incident_id": "inc_closed"}, ctx)
    assert closed_incident.message == "incident 'inc_closed' is closed"
    await tamper(check_session, Road, "RD-01", status="closed")
    cut_off = await execute_action(OPEN, {"shelter_id": "S-6"}, ctx)
    assert (cut_off.status, cut_off.message) == ("rejected", "shelter 'S-6' access road 'RD-01' is closed")
    refused = await execute_action(OPEN, {"shelter_id": "S-3"}, ctx_no_approval)
    assert (refused.status, refused.message) == ("rejected", "approval required for open_shelter")
    assert (await fresh(check_session, Shelter, "S-3")).status == "closed"


async def test_open_shelter_verify(ctx, check_session):
    result = await execute_action(OPEN, {"shelter_id": "S-3"}, ctx)
    inp = OPEN.Input.model_validate({"shelter_id": "S-3"})
    assert (await OPEN.verify(inp, ctx, result)).status == "verified"
    await tamper(check_session, Shelter, "S-3", status="closed")
    assert (await OPEN.verify(inp, ctx, result)).status == "failed"


async def test_close_shelter_changes_the_database(ctx, check_session):
    await execute_action(OPEN, {"shelter_id": "S-2"}, ctx)
    result = await execute_action(CLOSE, {"shelter_id": "S-2", "reason": "Stand down"}, ctx)
    assert result.status == "executed" and result.after["shelter:S-2"]["status"] == "closed"
    shelter = await fresh(check_session, Shelter, "S-2")
    assert (shelter.status, shelter.opened_at, shelter.incident_id) == ("closed", None, None)
    again = await execute_action(CLOSE, {"shelter_id": "S-3", "reason": "x"}, ctx)
    assert (again.status, again.message) == ("unchanged", "shelter 'S-3' is already closed")


async def test_close_shelter_checks_occupants_orders_and_approval(ctx, ctx_no_approval, check_session):
    await tamper(check_session, Shelter, "S-1", status="open", current_occupancy=12)
    occupied = await execute_action(CLOSE, {"shelter_id": "S-1", "reason": "x"}, ctx)
    assert (occupied.status, occupied.message) == ("rejected", "shelter 'S-1' has 12 occupants")
    await tamper(check_session, Shelter, "S-2", status="open")
    check_session.add(
        EvacuationOrder(
            id="evac_t", zone_id="Z-RS", level="voluntary", reason="t", shelter_id="S-2", status="active",
            issued_at=NOW, updated_at=NOW,
        )
    )  # fmt: skip
    await check_session.commit()
    ordered = await execute_action(CLOSE, {"shelter_id": "S-2", "reason": "x"}, ctx)
    assert ordered.message == "shelter 'S-2' is the destination of active evacuation order 'evac_t'"
    missing = await execute_action(CLOSE, {"shelter_id": "S-99", "reason": "x"}, ctx)
    assert missing.message == "shelter 'S-99' not found"
    await tamper(check_session, Shelter, "S-4", status="open")
    refused = await execute_action(CLOSE, {"shelter_id": "S-4", "reason": "x"}, ctx_no_approval)
    assert (refused.status, refused.message) == ("rejected", "approval required for close_shelter")
    assert (await fresh(check_session, Shelter, "S-4")).status == "open"


async def test_close_shelter_verify(ctx, check_session):
    await tamper(check_session, Shelter, "S-4", status="open")
    raw = {"shelter_id": "S-4", "reason": "x"}
    result = await execute_action(CLOSE, raw, ctx)
    inp = CLOSE.Input.model_validate(raw)
    assert (await CLOSE.verify(inp, ctx, result)).status == "verified"
    await tamper(check_session, Shelter, "S-4", status="open")
    assert (await CLOSE.verify(inp, ctx, result)).status == "failed"
