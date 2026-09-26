import pytest

from gridline.db.models import BedReservation, HospitalBed, Road
from gridline.tools.base import EntityRef, ToolRejected
from gridline.tools.common import ids_in
from gridline.tools.executor import execute_action
from gridline.tools.hospitals import GetHospitalCapacity, ReserveHospitalBeds
from tests.tools.helpers import add_incident, count, fresh, tamper

CAPACITY, RESERVE = GetHospitalCapacity(), ReserveHospitalBeds()


async def _items(ctx, **filters):
    return (await CAPACITY.run(CAPACITY.Input.model_validate(filters), ctx)).items


async def test_get_hospital_capacity_by_bed_type(ctx):
    assert [h.id for h in await _items(ctx)] == ["H-1", "H-2", "H-3", "H-4", "H-5"]
    [h1] = await _items(ctx, hospital_id="H-1")
    assert [b.bed_type for b in h1.beds] == ["emergency", "general", "icu", "maternity", "pediatric"]
    general = next(b for b in h1.beds if b.bed_type == "general")
    assert (general.total, general.available, general.reserved, general.occupied) == (300, 66, 0, 234)
    assert (h1.available_beds, h1.reserved_beds) == (95, 0)
    assert [h.id for h in await _items(ctx, zone_id="Z-RS")] == ["H-2"]
    with pytest.raises(ToolRejected, match=r"^hospital 'H-9' not found$"):
        await _items(ctx, hospital_id="H-9")
    with pytest.raises(ToolRejected, match=r"^zone 'Z-XX' not found$"):
        await _items(ctx, zone_id="Z-XX")


async def test_reserve_hospital_beds_moves_beds_and_records_the_reservation(ctx, check_session):
    incident = await add_incident(check_session, zone_id="Z-RS", hazard="flood")
    raw = {"hospital_id": "H-2", "beds": 5, "incident_id": incident}
    result = await execute_action(RESERVE, raw, ctx)
    assert result.status == "executed" and result.incident_id == incident
    [resv_id] = ids_in(result, "bed_reservation")
    assert resv_id.startswith("resv_")
    assert result.affected_entities == [
        EntityRef(kind="hospital_bed", id="H-2-general"),
        EntityRef(kind="bed_reservation", id=resv_id),
    ]
    assert result.before["hospital_bed:H-2-general"]["available"] == 12
    assert result.after["hospital_bed:H-2-general"]["available"] == 7
    bed = await fresh(check_session, HospitalBed, "H-2-general")
    assert (bed.available, bed.reserved) == (7, 5)
    resv = await fresh(check_session, BedReservation, resv_id)
    assert (resv.hospital_id, resv.bed_type, resv.beds, resv.status, resv.incident_id) == (
        "H-2",
        "general",
        5,
        "active",
        incident,
    )
    [h2] = await _items(ctx, hospital_id="H-2")
    assert (h2.reserved_beds, next(b.occupied for b in h2.beds if b.bed_type == "general")) == (5, 44)


async def test_reserve_hospital_beds_is_never_unchanged(ctx, check_session):
    incident = await add_incident(check_session)
    raw = {"hospital_id": "H-1", "bed_type": "icu", "beds": 2, "incident_id": incident}
    assert (await execute_action(RESERVE, raw, ctx)).status == "executed"
    assert (await execute_action(RESERVE, raw, ctx)).status == "executed"
    assert (await fresh(check_session, HospitalBed, "H-1-icu")).available == 4
    assert await count(check_session, BedReservation) == 2
    replay = await execute_action(RESERVE, {**raw, "idempotency_key": "k"}, ctx)
    assert (await execute_action(RESERVE, {**raw, "idempotency_key": "k"}, ctx)).action_id == replay.action_id
    assert await count(check_session, BedReservation) == 3


async def test_reserve_hospital_beds_rejections(ctx, ctx_no_approval, check_session):
    incident = await add_incident(check_session)
    await add_incident(check_session, "inc_closed", status="closed")
    base = {"hospital_id": "H-2", "beds": 5, "incident_id": incident}
    cases = [
        ({**base, "hospital_id": "H-9"}, "hospital 'H-9' not found"),
        ({**base, "incident_id": "inc_closed"}, "incident 'inc_closed' is closed"),
        ({**base, "bed_type": "burn"}, "hospital 'H-2' has no 'burn' beds"),
        ({**base, "beds": 20}, "hospital 'H-2' has 12 general beds available, 20 requested"),
    ]
    for raw, message in cases:
        result = await execute_action(RESERVE, raw, ctx)
        assert (result.status, result.message) == ("rejected", message)
    no_incident = await execute_action(RESERVE, {"hospital_id": "H-2", "beds": 1}, ctx)
    assert no_incident.status == "rejected" and "incident_id: Field required" in no_incident.message
    zero = await execute_action(RESERVE, {**base, "beds": 0}, ctx)
    assert zero.status == "rejected" and zero.message.startswith("beds:")
    await tamper(check_session, Road, "RD-02", status="closed")
    cut_off = await execute_action(RESERVE, base, ctx)
    assert cut_off.message == "hospital 'H-2' access road 'RD-02' is closed"
    refused = await execute_action(RESERVE, {**base, "hospital_id": "H-3"}, ctx_no_approval)
    assert (refused.status, refused.message) == ("rejected", "approval required for reserve_hospital_beds")
    assert await count(check_session, BedReservation) == 0
    assert (await fresh(check_session, HospitalBed, "H-2-general")).available == 12


async def test_reserve_hospital_beds_verify(ctx, check_session):
    incident = await add_incident(check_session)
    raw = {"hospital_id": "H-4", "bed_type": "emergency", "beds": 3, "incident_id": incident}
    result = await execute_action(RESERVE, raw, ctx)
    inp = RESERVE.Input.model_validate(raw)
    assert (await RESERVE.verify(inp, ctx, result)).status == "verified"
    [resv_id] = ids_in(result, "bed_reservation")
    await tamper(check_session, BedReservation, resv_id, status="released")
    assert (await RESERVE.verify(inp, ctx, result)).status == "failed"
    await tamper(check_session, BedReservation, resv_id, status="active")
    await tamper(check_session, HospitalBed, "H-4-emergency", reserved=0)
    assert (await RESERVE.verify(inp, ctx, result)).status == "failed"
