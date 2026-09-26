from gridline.db.models import Incident, Task
from gridline.tools.base import EntityRef
from gridline.tools.common import ids_in
from gridline.tools.executor import execute_action
from gridline.tools.incidents import CreateEmergencyTask, CreateIncident, UpdateIncident
from tests.tools.helpers import add_incident, count, fresh, tamper

CREATE, UPDATE, TASK = CreateIncident(), UpdateIncident(), CreateEmergencyTask()
LANDSLIDE = {
    "zone_id": "Z-HV",
    "hazard": "landslide",
    "band": "warning",
    "title": "Landslide risk above Hill Road",
    "summary": "Saturation on SL-HV-1 is above the warning threshold while PR-HT2 keeps excavating.",
}


# --- create_incident ----------------------------------------------------------------------------------------


async def test_create_incident_inserts_an_open_incident(ctx_no_approval, check_session):
    result = await execute_action(CREATE, LANDSLIDE, ctx_no_approval)  # auto: no approval needed
    assert result.status == "executed"
    [incident_id] = ids_in(result, "incident")
    assert incident_id.startswith("inc_") and result.incident_id == incident_id
    assert result.affected_entities == [EntityRef(kind="incident", id=incident_id)] and result.before == {}
    row = await fresh(check_session, Incident, incident_id)
    assert (row.zone_id, row.hazard, row.band, row.status, row.title) == (
        "Z-HV",
        "landslide",
        "warning",
        "open",
        LANDSLIDE["title"],
    )
    assert row.opened_at == row.updated_at and row.closed_at is None


async def test_create_incident_is_unchanged_while_one_is_open_for_zone_and_hazard(ctx, check_session):
    first = await execute_action(CREATE, LANDSLIDE, ctx)
    [incident_id] = ids_in(first, "incident")
    again = await execute_action(CREATE, {**LANDSLIDE, "band": "critical"}, ctx)
    assert (again.status, again.message) == (
        "unchanged",
        f"incident '{incident_id}' is already open for landslide in zone 'Z-HV'",
    )
    assert list(again.after) == [f"incident:{incident_id}"] and again.incident_id == incident_id
    flood = await execute_action(CREATE, {**LANDSLIDE, "hazard": "flood"}, ctx)
    assert flood.status == "executed"
    await tamper(check_session, Incident, incident_id, status="closed")
    reopened = await execute_action(CREATE, LANDSLIDE, ctx)
    assert reopened.status == "executed" and ids_in(reopened, "incident") != [incident_id]
    assert await count(check_session, Incident) == 3


async def test_create_incident_rejections(ctx):
    assert (
        await execute_action(CREATE, {**LANDSLIDE, "zone_id": "Z-XX"}, ctx)
    ).message == "zone 'Z-XX' not found"
    for field, value in [("hazard", "meteor"), ("band", "normal"), ("title", "")]:
        result = await execute_action(CREATE, {**LANDSLIDE, field: value}, ctx)
        assert result.status == "rejected" and result.message.startswith(f"{field}:")


async def test_create_incident_verify(ctx, check_session):
    result = await execute_action(CREATE, LANDSLIDE, ctx)
    inp = CREATE.Input.model_validate(LANDSLIDE)
    assert (await CREATE.verify(inp, ctx, result)).status == "verified"
    await tamper(check_session, Incident, result.incident_id, status="closed")
    assert (await CREATE.verify(inp, ctx, result)).status == "failed"


# --- update_incident ----------------------------------------------------------------------------------------


async def test_update_incident_changes_fields(ctx_no_approval, check_session):
    incident = await add_incident(check_session)
    raw = {"incident_id": incident, "band": "critical", "summary": "Tension cracks observed."}
    result = await execute_action(UPDATE, raw, ctx_no_approval)
    assert result.status == "executed" and result.affected_entities == [
        EntityRef(kind="incident", id=incident)
    ]
    assert (result.before[f"incident:{incident}"]["band"], result.after[f"incident:{incident}"]["band"]) == (
        "warning",
        "critical",
    )
    row = await fresh(check_session, Incident, incident)
    assert (row.band, row.summary, row.status, row.closed_at) == ("critical", raw["summary"], "open", None)
    assert row.updated_at > row.opened_at
    closed = await execute_action(UPDATE, {"incident_id": incident, "status": "closed"}, ctx_no_approval)
    assert closed.status == "executed"
    row = await fresh(check_session, Incident, incident)
    assert row.status == "closed" and row.closed_at is not None


async def test_update_incident_unchanged_and_rejections(ctx, check_session):
    incident = await add_incident(check_session)
    same = await execute_action(UPDATE, {"incident_id": incident, "band": "warning"}, ctx)
    assert (same.status, same.message) == (
        "unchanged",
        f"incident '{incident}' already has the requested values",
    )
    missing = await execute_action(UPDATE, {"incident_id": "inc_nope", "band": "watch"}, ctx)
    assert missing.message == "incident 'inc_nope' not found"
    empty = await execute_action(UPDATE, {"incident_id": incident}, ctx)
    assert (
        empty.status == "rejected" and "at least one of band, status or summary is required" in empty.message
    )
    await add_incident(check_session, "inc_closed", status="closed")
    closed = await execute_action(UPDATE, {"incident_id": "inc_closed", "band": "watch"}, ctx)
    assert (closed.status, closed.message) == ("rejected", "incident 'inc_closed' is closed")


async def test_update_incident_verify(ctx, check_session):
    incident = await add_incident(check_session)
    raw = {"incident_id": incident, "band": "critical"}
    result = await execute_action(UPDATE, raw, ctx)
    inp = UPDATE.Input.model_validate(raw)
    assert (await UPDATE.verify(inp, ctx, result)).status == "verified"
    await tamper(check_session, Incident, incident, band="watch")
    assert (await UPDATE.verify(inp, ctx, result)).status == "failed"


# --- create_emergency_task ----------------------------------------------------------------------------------


async def test_create_emergency_task_defaults_to_the_incident_zone(ctx_no_approval, check_session):
    incident = await add_incident(check_session, zone_id="Z-RS", hazard="flood")
    raw = {
        "incident_id": incident,
        "title": "Sandbag RD-02",
        "description": "Sandbag the low point of RD-02.",
    }
    result = await execute_action(TASK, raw, ctx_no_approval)
    assert result.status == "executed" and result.incident_id == incident
    [task_id] = ids_in(result, "task")
    task = await fresh(check_session, Task, task_id)
    assert (task.kind, task.zone_id, task.priority, task.status, task.incident_id, task.created_by) == (
        "emergency",
        "Z-RS",
        "medium",
        "open",
        incident,
        "agent",
    )
    again = await execute_action(TASK, {**raw, "description": "other words"}, ctx_no_approval)
    assert (again.status, again.message) == (
        "unchanged",
        f"open emergency task '{task_id}' already exists for incident '{incident}' with this title",
    )
    crewed = {
        **raw,
        "title": "Pump D-7 outfall",
        "zone_id": "Z-OT",
        "assigned_crew_id": "C-2",
        "priority": "high",
    }
    other = await execute_action(TASK, crewed, ctx_no_approval)
    [other_id] = ids_in(other, "task")
    other_task = await fresh(check_session, Task, other_id)
    assert (other_task.zone_id, other_task.assigned_crew_id, other_task.priority) == ("Z-OT", "C-2", "high")


async def test_create_emergency_task_rejections_and_verify(ctx, check_session):
    incident = await add_incident(check_session)
    await add_incident(check_session, "inc_closed", status="closed")
    base = {"incident_id": incident, "title": "t", "description": "d"}
    cases = [
        ({**base, "incident_id": "inc_nope"}, "incident 'inc_nope' not found"),
        ({**base, "incident_id": "inc_closed"}, "incident 'inc_closed' is closed"),
        ({**base, "zone_id": "Z-XX"}, "zone 'Z-XX' not found"),
        ({**base, "assigned_crew_id": "C-99"}, "crew 'C-99' not found"),
    ]
    for raw, message in cases:
        assert (await execute_action(TASK, raw, ctx)).message == message
    result = await execute_action(TASK, base, ctx)
    inp = TASK.Input.model_validate(base)
    assert (await TASK.verify(inp, ctx, result)).status == "verified"
    await tamper(check_session, Task, ids_in(result, "task")[0], status="cancelled")
    assert (await TASK.verify(inp, ctx, result)).status == "failed"
