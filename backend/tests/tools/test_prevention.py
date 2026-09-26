from sqlalchemy import delete

from gridline.db.models import Alert, Task
from gridline.tools.base import EntityRef
from gridline.tools.common import ids_in
from gridline.tools.executor import execute_action
from gridline.tools.prevention import CreateInspectionOrder, CreateMonitoringTask, IssuePreventiveAlert
from tests.tools.helpers import add_incident, count, fresh, tamper

INSPECT, MONITOR, ALERT = CreateInspectionOrder(), CreateMonitoringTask(), IssuePreventiveAlert()


# --- create_inspection_order --------------------------------------------------------------------------------


async def test_inspection_order_creates_a_task_in_the_target_zone(ctx_no_approval, check_session):
    incident = await add_incident(check_session)
    raw = {"target_kind": "slope", "target_id": "SL-HV-1", "priority": "high", "reason": "Cracks reported"}
    result = await execute_action(INSPECT, {**raw, "incident_id": incident}, ctx_no_approval)  # auto
    assert result.status == "executed" and result.incident_id == incident
    [task_id] = ids_in(result, "task")
    assert result.affected_entities == [EntityRef(kind="task", id=task_id)]
    task = await fresh(check_session, Task, task_id)
    assert (task.kind, task.title, task.description, task.priority, task.zone_id) == (
        "inspection",
        "Inspect slope SL-HV-1",
        "Cracks reported",
        "high",
        "Z-HV",
    )
    assert (task.target_kind, task.target_id, task.status, task.incident_id) == (
        "slope",
        "SL-HV-1",
        "open",
        incident,
    )
    channel = await execute_action(
        INSPECT, {"target_kind": "channel", "target_id": "D-7", "reason": "x"}, ctx_no_approval
    )
    assert (
        await fresh(check_session, Task, ids_in(channel, "task")[0])
    ).zone_id == "Z-HV"  # D-7's upstream zone
    zone = await execute_action(
        INSPECT, {"target_kind": "zone", "target_id": "Z-RS", "reason": "x"}, ctx_no_approval
    )
    assert (await fresh(check_session, Task, ids_in(zone, "task")[0])).zone_id == "Z-RS"


async def test_inspection_order_unchanged_and_rejections(ctx, check_session):
    raw = {"target_kind": "bridge", "target_id": "BR-4", "reason": "Scour check"}
    first = await execute_action(INSPECT, raw, ctx)
    [task_id] = ids_in(first, "task")
    again = await execute_action(INSPECT, {**raw, "reason": "again"}, ctx)
    assert (again.status, again.message) == (
        "unchanged",
        f"open inspection task '{task_id}' already exists for bridge 'BR-4'",
    )
    assert ids_in(again, "task") == [task_id]
    await add_incident(check_session, "inc_closed", status="closed")
    cases = [
        ({**raw, "target_id": "BR-99"}, "bridge 'BR-99' not found"),
        ({**raw, "target_kind": "project", "target_id": "PR-XX"}, "project 'PR-XX' not found"),
        ({**raw, "target_id": "BR-1", "incident_id": "inc_closed"}, "incident 'inc_closed' is closed"),
    ]
    for case, message in cases:
        assert (await execute_action(INSPECT, case, ctx)).message == message
    bad_kind = await execute_action(INSPECT, {**raw, "target_kind": "tunnel"}, ctx)
    assert bad_kind.status == "rejected" and bad_kind.message.startswith("target_kind:")
    assert await count(check_session, Task) == 1


async def test_inspection_order_verify(ctx, check_session):
    raw = {"target_kind": "road", "target_id": "RD-01", "reason": "x"}
    result = await execute_action(INSPECT, raw, ctx)
    inp = INSPECT.Input.model_validate(raw)
    assert (await INSPECT.verify(inp, ctx, result)).status == "verified"
    await tamper(check_session, Task, ids_in(result, "task")[0], status="done")
    assert (await INSPECT.verify(inp, ctx, result)).status == "failed"


# --- create_monitoring_task ---------------------------------------------------------------------------------

MONITOR_RAW = {
    "target_kind": "project",
    "target_id": "PR-HT2",
    "metric": "excavation_depth_m",
    "interval_minutes": 30,
    "reason": "Excavation continues during heavy rain",
}


async def test_monitoring_task_stores_metric_and_interval(ctx_no_approval, check_session):
    result = await execute_action(MONITOR, MONITOR_RAW, ctx_no_approval)
    assert result.status == "executed"
    task = await fresh(check_session, Task, ids_in(result, "task")[0])
    assert (task.kind, task.title, task.metric, task.interval_minutes, task.zone_id) == (
        "monitoring",
        "Monitor excavation_depth_m on project PR-HT2",
        "excavation_depth_m",
        30,
        "Z-HV",
    )
    again = await execute_action(MONITOR, {**MONITOR_RAW, "interval_minutes": 15}, ctx_no_approval)
    assert again.status == "unchanged" and ids_in(again, "task") == [task.id]
    assert again.message == (
        f"open monitoring task '{task.id}' already monitors excavation_depth_m on project 'PR-HT2'"
    )
    other = await execute_action(MONITOR, {**MONITOR_RAW, "metric": "saturation"}, ctx_no_approval)
    assert other.status == "executed"


async def test_monitoring_task_rejections_and_verify(ctx, check_session):
    for field, value in [("interval_minutes", 4), ("interval_minutes", 1441), ("metric", "m" * 65)]:
        result = await execute_action(MONITOR, {**MONITOR_RAW, field: value}, ctx)
        assert result.status == "rejected" and result.message.startswith(f"{field}:")
    missing = await execute_action(
        MONITOR, {**MONITOR_RAW, "target_kind": "slope", "target_id": "SL-XX"}, ctx
    )
    assert missing.message == "slope 'SL-XX' not found"
    result = await execute_action(MONITOR, MONITOR_RAW, ctx)
    inp = MONITOR.Input.model_validate(MONITOR_RAW)
    assert (await MONITOR.verify(inp, ctx, result)).status == "verified"
    await tamper(check_session, Task, ids_in(result, "task")[0], interval_minutes=60)
    assert (await MONITOR.verify(inp, ctx, result)).status == "failed"


# --- issue_preventive_alert ---------------------------------------------------------------------------------


async def test_alert_approval_is_conditional(ctx, ctx_no_approval, check_session):
    advisory = {"zone_id": "Z-HV", "level": "advisory", "message": "Avoid Hill Road below SL-HV-1."}
    result = await execute_action(ALERT, advisory, ctx_no_approval)
    assert result.status == "executed"
    [alert_id] = ids_in(result, "alert")
    row = await fresh(check_session, Alert, alert_id)
    assert (row.zone_id, row.level, row.message) == ("Z-HV", "advisory", advisory["message"])
    for level in ("warning", "evacuate"):
        refused = await execute_action(ALERT, {**advisory, "level": level}, ctx_no_approval)
        assert (refused.status, refused.message) == (
            "rejected",
            "approval required for issue_preventive_alert",
        )
    approved = await execute_action(ALERT, {**advisory, "level": "warning"}, ctx)
    assert approved.status == "executed"
    assert await count(check_session, Alert) == 2


async def test_alert_unchanged_rejections_and_verify(ctx, check_session):
    raw = {"zone_id": "Z-RS", "level": "warning", "message": "Flood warning for Riverside."}
    first = await execute_action(ALERT, raw, ctx)
    [alert_id] = ids_in(first, "alert")
    again = await execute_action(ALERT, raw, ctx)
    assert (again.status, again.message) == (
        "unchanged",
        f"alert '{alert_id}' with this level and message exists",
    )
    assert (await execute_action(ALERT, {**raw, "zone_id": "Z-XX"}, ctx)).message == "zone 'Z-XX' not found"
    empty = await execute_action(ALERT, {**raw, "message": ""}, ctx)
    assert empty.status == "rejected" and empty.message.startswith("message:")
    inp = ALERT.Input.model_validate(raw)
    assert (await ALERT.verify(inp, ctx, first)).status == "verified"
    await check_session.execute(delete(Alert).where(Alert.id == alert_id))
    await check_session.commit()
    assert (await ALERT.verify(inp, ctx, first)).status == "failed"
