from gridline.db.models import EvacuationOrder, Shelter, Task
from gridline.tools.base import EntityRef
from gridline.tools.common import ids_in
from gridline.tools.evacuation import CreateEvacuationOrder, CreateEvacuationTask
from gridline.tools.executor import execute_action
from tests.tools.helpers import add_incident, count, fresh, tamper

ORDER, TASK = CreateEvacuationOrder(), CreateEvacuationTask()
VOLUNTARY = {"zone_id": "Z-RS", "level": "voluntary", "reason": "D-7 may overflow into Riverside"}


async def _open_shelter(check_session, shelter_id: str = "S-1") -> None:
    await tamper(check_session, Shelter, shelter_id, status="open")


# --- create_evacuation_order --------------------------------------------------------------------------------


async def test_evacuation_order_is_created_active(ctx, check_session):
    await _open_shelter(check_session)
    incident = await add_incident(check_session, zone_id="Z-RS", hazard="flood")
    result = await execute_action(ORDER, {**VOLUNTARY, "shelter_id": "S-1", "incident_id": incident}, ctx)
    assert result.status == "executed" and result.incident_id == incident
    [order_id] = ids_in(result, "evacuation_order")
    assert order_id.startswith("evac_") and result.affected_entities == [
        EntityRef(kind="evacuation_order", id=order_id)
    ]
    order = await fresh(check_session, EvacuationOrder, order_id)
    assert (order.zone_id, order.level, order.status, order.shelter_id, order.incident_id) == (
        "Z-RS",
        "voluntary",
        "active",
        "S-1",
        incident,
    )


async def test_escalation_updates_the_active_order_in_place(ctx, check_session):
    first = await execute_action(ORDER, VOLUNTARY, ctx)
    [order_id] = ids_in(first, "evacuation_order")
    mandatory = {**VOLUNTARY, "level": "mandatory", "reason": "Riverside Bypass under water"}
    escalated = await execute_action(ORDER, mandatory, ctx)
    assert escalated.status == "executed" and ids_in(escalated, "evacuation_order") == [order_id]
    key = f"evacuation_order:{order_id}"
    assert (escalated.before[key]["level"], escalated.after[key]["level"]) == ("voluntary", "mandatory")
    order = await fresh(check_session, EvacuationOrder, order_id)
    assert (order.level, order.reason) == (
        "mandatory",
        mandatory["reason"],
    ) and order.updated_at > order.issued_at
    assert await count(check_session, EvacuationOrder) == 1
    for level in ("mandatory", "voluntary"):
        same = await execute_action(ORDER, {**VOLUNTARY, "level": level}, ctx)
        assert (same.status, same.message) == (
            "unchanged",
            f"active mandatory evacuation order '{order_id}' already covers zone 'Z-RS'",
        )


async def test_evacuation_order_rejections(ctx, ctx_no_approval, check_session):
    await add_incident(check_session, "inc_closed", status="closed")
    await _open_shelter(check_session, "S-5")
    cases = [
        ({**VOLUNTARY, "zone_id": "Z-XX"}, "zone 'Z-XX' not found"),
        ({**VOLUNTARY, "shelter_id": "S-99"}, "shelter 'S-99' not found"),
        ({**VOLUNTARY, "shelter_id": "S-2"}, "shelter 'S-2' is not open; open it first"),
        (
            {**VOLUNTARY, "shelter_id": "S-5"},
            "shelter 'S-5' is inside zone 'Z-RS'; choose a shelter outside the evacuated zone",
        ),
        ({**VOLUNTARY, "incident_id": "inc_closed"}, "incident 'inc_closed' is closed"),
    ]
    for raw, message in cases:
        result = await execute_action(ORDER, raw, ctx)
        assert (result.status, result.message) == ("rejected", message)
    refused = await execute_action(ORDER, VOLUNTARY, ctx_no_approval)
    assert (refused.status, refused.message) == ("rejected", "approval required for create_evacuation_order")
    assert await count(check_session, EvacuationOrder) == 0


async def test_evacuation_order_verify(ctx, check_session):
    raw = {**VOLUNTARY, "level": "mandatory"}
    result = await execute_action(ORDER, raw, ctx)
    inp = ORDER.Input.model_validate(raw)
    assert (await ORDER.verify(inp, ctx, result)).status == "verified"
    [order_id] = ids_in(result, "evacuation_order")
    await tamper(check_session, EvacuationOrder, order_id, level="voluntary")
    assert (await ORDER.verify(inp, ctx, result)).status == "failed"
    await tamper(check_session, EvacuationOrder, order_id, level="mandatory", status="lifted")
    assert (await ORDER.verify(inp, ctx, result)).status == "failed"


# --- create_evacuation_task ---------------------------------------------------------------------------------


async def test_evacuation_task_needs_an_active_order(ctx_no_approval):
    raw = {"zone_id": "Z-RS", "description": "Door-to-door warning along RD-02"}
    result = await execute_action(TASK, raw, ctx_no_approval)
    assert (result.status, result.message) == ("rejected", "no active evacuation order for zone 'Z-RS'")
    missing = await execute_action(TASK, {**raw, "zone_id": "Z-XX"}, ctx_no_approval)
    assert missing.message == "zone 'Z-XX' not found"


async def test_evacuation_task_is_linked_to_the_order(ctx, ctx_no_approval, check_session):
    incident = await add_incident(check_session, zone_id="Z-RS", hazard="flood")
    order = await execute_action(ORDER, {**VOLUNTARY, "incident_id": incident}, ctx)
    [order_id] = ids_in(order, "evacuation_order")
    raw = {"zone_id": "Z-RS", "description": "Door-to-door warning along RD-02", "assigned_crew_id": "C-8"}
    result = await execute_action(TASK, {**raw, "priority": "high"}, ctx_no_approval)  # auto
    assert result.status == "executed" and result.incident_id == incident
    task = await fresh(check_session, Task, ids_in(result, "task")[0])
    assert (task.kind, task.title, task.zone_id, task.evacuation_order_id, task.incident_id) == (
        "evacuation",
        "Evacuate Riverside (voluntary)",
        "Z-RS",
        order_id,
        incident,
    )
    assert (task.assigned_crew_id, task.priority, task.description) == ("C-8", "high", raw["description"])
    again = await execute_action(TASK, raw, ctx_no_approval)
    assert (again.status, again.message) == (
        "unchanged",
        f"open evacuation task '{task.id}' with this description exists for order '{order_id}'",
    )
    crew = await execute_action(TASK, {**raw, "description": "other", "assigned_crew_id": "C-99"}, ctx)
    assert crew.message == "crew 'C-99' not found"


async def test_evacuation_task_verify(ctx, check_session):
    await execute_action(ORDER, VOLUNTARY, ctx)
    raw = {"zone_id": "Z-RS", "description": "Open the school gates"}
    result = await execute_action(TASK, raw, ctx)
    inp = TASK.Input.model_validate(raw)
    assert (await TASK.verify(inp, ctx, result)).status == "verified"
    await tamper(check_session, Task, ids_in(result, "task")[0], status="cancelled")
    assert (await TASK.verify(inp, ctx, result)).status == "failed"
