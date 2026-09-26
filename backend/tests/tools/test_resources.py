import pytest

from gridline.db.models import Ambulance, Crew, Road
from gridline.tools.base import EntityRef, ToolRejected
from gridline.tools.executor import execute_action
from gridline.tools.resources import (
    DispatchAmbulance,
    DispatchRescueTeam,
    GetAvailableAmbulances,
    GetAvailableRescueTeams,
)
from tests.tools.helpers import add_incident, fresh, tamper

TEAMS, DISPATCH = GetAvailableRescueTeams(), DispatchRescueTeam()
AMBULANCES, SEND = GetAvailableAmbulances(), DispatchAmbulance()


async def _ids(tool, ctx, **filters) -> list[str]:
    return [item.id for item in (await tool.run(tool.Input.model_validate(filters), ctx)).items]


# --- rescue teams -------------------------------------------------------------------------------------------


async def test_available_rescue_teams_are_rescue_crews_that_are_available(ctx, check_session):
    assert await _ids(TEAMS, ctx) == ["C-1", "C-4", "C-7"]  # rescue, hill_rescue, boat; not drainage/road/...
    assert await _ids(TEAMS, ctx, zone_id="Z-RS") == ["C-4"]
    await tamper(check_session, Crew, "C-7", status="off_duty")
    assert await _ids(TEAMS, ctx) == ["C-1", "C-4"]
    with pytest.raises(ToolRejected, match=r"^zone 'Z-XX' not found$"):
        await _ids(TEAMS, ctx, zone_id="Z-XX")


async def test_dispatch_rescue_team_changes_the_crew(ctx, check_session):
    incident = await add_incident(check_session)
    raw = {"crew_id": "C-4", "zone_id": "Z-HV", "task": "Search below slope SL-HV-1", "incident_id": incident}
    result = await execute_action(DISPATCH, raw, ctx)
    assert result.status == "executed" and result.affected_entities == [EntityRef(kind="crew", id="C-4")]
    assert result.before["crew:C-4"]["status"] == "available"
    crew = await fresh(check_session, Crew, "C-4")
    assert (crew.status, crew.target_zone_id, crew.task, crew.incident_id) == (
        "dispatched",
        "Z-HV",
        raw["task"],
        incident,
    )
    assert (
        crew.dispatched_at is not None and crew.location_zone_id == "Z-RS"
    )  # travel is the simulation's job
    assert await _ids(TEAMS, ctx) == ["C-1", "C-7"]
    again = await execute_action(DISPATCH, raw, ctx)
    assert (again.status, again.message) == ("unchanged", "crew 'C-4' is already dispatched to zone 'Z-HV'")


async def test_dispatch_rescue_team_rejections(ctx, ctx_no_approval, check_session):
    await add_incident(check_session, "inc_closed", status="closed")
    base = {"crew_id": "C-1", "zone_id": "Z-HV", "task": "Search"}
    cases = [
        ({**base, "crew_id": "C-99"}, "crew 'C-99' not found"),
        ({**base, "crew_id": "C-2"}, "crew 'C-2' is not a rescue team (kind 'drainage')"),
        ({**base, "zone_id": "Z-XX"}, "zone 'Z-XX' not found"),
        ({**base, "incident_id": "inc_closed"}, "incident 'inc_closed' is closed"),
    ]
    for raw, message in cases:
        assert (await execute_action(DISPATCH, raw, ctx)).message == message
    refused = await execute_action(DISPATCH, base, ctx_no_approval)
    assert (refused.status, refused.message) == ("rejected", "approval required for dispatch_rescue_team")
    assert (await fresh(check_session, Crew, "C-1")).status == "available"
    too_long = await execute_action(DISPATCH, {**base, "task": "x" * 201}, ctx)
    assert too_long.status == "rejected" and too_long.message.startswith("task:")


async def test_dispatch_rescue_team_checks_city_state(ctx, check_session):
    await tamper(check_session, Road, "RD-01", status="closed")
    cut_off = await execute_action(DISPATCH, {"crew_id": "C-1", "zone_id": "Z-HV", "task": "Search"}, ctx)
    assert (cut_off.status, cut_off.message) == ("rejected", "zone 'Z-HV' has no open access road")
    await execute_action(DISPATCH, {"crew_id": "C-1", "zone_id": "Z-RS", "task": "Search"}, ctx)
    elsewhere = await execute_action(DISPATCH, {"crew_id": "C-1", "zone_id": "Z-OT", "task": "Search"}, ctx)
    assert elsewhere.message == "crew 'C-1' is already dispatched to zone 'Z-RS'"
    await tamper(check_session, Crew, "C-4", status="busy")
    busy = await execute_action(DISPATCH, {"crew_id": "C-4", "zone_id": "Z-RS", "task": "Search"}, ctx)
    assert busy.message == "crew 'C-4' is not available (status 'busy')"


async def test_dispatch_rescue_team_verify(ctx, check_session):
    raw = {"crew_id": "C-7", "zone_id": "Z-RS", "task": "Boat evacuation"}
    result = await execute_action(DISPATCH, raw, ctx)
    inp = DISPATCH.Input.model_validate(raw)
    assert (await DISPATCH.verify(inp, ctx, result)).status == "verified"
    await tamper(check_session, Crew, "C-7", target_zone_id="Z-LK")
    failed = await DISPATCH.verify(inp, ctx, result)
    assert failed.status == "failed" and [c.passed for c in failed.checks] == [True, False]


# --- ambulances ---------------------------------------------------------------------------------------------


async def test_available_ambulances(ctx):
    ids = await _ids(AMBULANCES, ctx)
    assert len(ids) == 13 and "AMB-05" not in ids  # AMB-05 is in maintenance
    assert await _ids(AMBULANCES, ctx, zone_id="Z-RS") == ["AMB-06", "AMB-07"]


async def test_dispatch_ambulance_changes_the_ambulance(ctx, check_session):
    incident = await add_incident(check_session, zone_id="Z-RS", hazard="flood")
    raw = {
        "ambulance_id": "AMB-06",
        "zone_id": "Z-RS",
        "incident_id": incident,
        "destination_hospital_id": "H-1",
    }
    result = await execute_action(SEND, raw, ctx)
    assert result.status == "executed" and result.affected_entities == [
        EntityRef(kind="ambulance", id="AMB-06")
    ]
    amb = await fresh(check_session, Ambulance, "AMB-06")
    assert (amb.status, amb.target_zone_id, amb.destination_hospital_id, amb.incident_id) == (
        "dispatched",
        "Z-RS",
        "H-1",
        incident,
    )
    assert amb.dispatched_at is not None
    assert await _ids(AMBULANCES, ctx, zone_id="Z-RS") == ["AMB-07"]
    again = await execute_action(SEND, raw, ctx)
    assert (again.status, again.message) == (
        "unchanged",
        "ambulance 'AMB-06' is already dispatched to zone 'Z-RS'",
    )


async def test_dispatch_ambulance_rejections(ctx, ctx_no_approval, check_session):
    base = {"ambulance_id": "AMB-01", "zone_id": "Z-RS"}
    cases = [
        ({**base, "ambulance_id": "AMB-99"}, "ambulance 'AMB-99' not found"),
        ({**base, "ambulance_id": "AMB-05"}, "ambulance 'AMB-05' is not available (status 'maintenance')"),
        ({**base, "zone_id": "Z-XX"}, "zone 'Z-XX' not found"),
        ({**base, "destination_hospital_id": "H-9"}, "hospital 'H-9' not found"),
        ({**base, "incident_id": "inc_nope"}, "incident 'inc_nope' not found"),
    ]
    for raw, message in cases:
        assert (await execute_action(SEND, raw, ctx)).message == message
    await tamper(check_session, Road, "RD-02", status="closed")
    closed = await execute_action(SEND, {**base, "destination_hospital_id": "H-2"}, ctx)
    assert closed.message == "hospital 'H-2' access road 'RD-02' is closed"
    await tamper(check_session, Road, "RD-01", status="closed")
    cut_off = await execute_action(SEND, {**base, "zone_id": "Z-HV"}, ctx)
    assert cut_off.message == "zone 'Z-HV' has no open access road"
    await execute_action(SEND, base, ctx)
    elsewhere = await execute_action(SEND, {**base, "zone_id": "Z-OT"}, ctx)
    assert elsewhere.message == "ambulance 'AMB-01' is already dispatched to zone 'Z-RS'"
    refused = await execute_action(SEND, {**base, "ambulance_id": "AMB-02"}, ctx_no_approval)
    assert (refused.status, refused.message) == ("rejected", "approval required for dispatch_ambulance")
    assert (await fresh(check_session, Ambulance, "AMB-02")).status == "available"


async def test_dispatch_ambulance_verify(ctx, check_session):
    raw = {"ambulance_id": "AMB-10", "zone_id": "Z-LK"}
    result = await execute_action(SEND, raw, ctx)
    inp = SEND.Input.model_validate(raw)
    assert (await SEND.verify(inp, ctx, result)).status == "verified"
    await tamper(check_session, Ambulance, "AMB-10", status="available")
    assert (await SEND.verify(inp, ctx, result)).status == "failed"
