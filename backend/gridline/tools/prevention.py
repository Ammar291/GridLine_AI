"""Prevention tools (spec §9 Prevention): inspection orders, monitoring tasks and preventive alerts.

``create_construction_restriction`` lives in ``gridline.tools.construction``.
"""

from collections.abc import Mapping
from types import MappingProxyType
from typing import Annotated

from pydantic import Field, StringConstraints
from sqlalchemy import select

from gridline.db.base import Base
from gridline.db.models import (
    Alert,
    Bridge,
    DrainageChannel,
    Hospital,
    Project,
    Road,
    Shelter,
    Slope,
    Task,
    Zone,
)
from gridline.tools.base import (
    ActionInput,
    ActionResult,
    ActionTool,
    Applied,
    EntityRef,
    Plan,
    ToolContext,
    VerificationResult,
)
from gridline.tools.common import (
    TaskPlan,
    check,
    create_task,
    fetch_all,
    first_open_task,
    ids_in,
    new_id,
    require,
    require_open_incident,
    reread,
    utcnow,
    verification,
    verify_open_task,
)
from gridline.tools.vocab import AlertLevel, EntityId, Priority, Reason, TargetKind, Text500

# Where each target kind lives and which column holds its zone (a channel belongs to its upstream zone).
TARGETS: Mapping[str, tuple[type[Base], str]] = MappingProxyType(
    {
        "zone": (Zone, "id"),
        "road": (Road, "zone_id"),
        "bridge": (Bridge, "zone_id"),
        "channel": (DrainageChannel, "upstream_zone_id"),
        "slope": (Slope, "zone_id"),
        "project": (Project, "zone_id"),
        "shelter": (Shelter, "zone_id"),
        "hospital": (Hospital, "zone_id"),
    }
)
Metric = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)]


async def target_zone(ctx: ToolContext, kind: TargetKind, target_id: str) -> str:
    """The zone of a task target, or ``"<kind> '<id>' not found"``."""
    model, zone_column = TARGETS[kind]
    row = await require(ctx.session, model, target_id, kind)
    return str(getattr(row, zone_column))


def _task_ref(task: Task | None) -> list[EntityRef]:
    return [EntityRef(kind="task", id=task.id)] if task else []


class InspectionInput(ActionInput):
    target_kind: TargetKind
    target_id: EntityId
    priority: Priority = "medium"
    reason: Reason
    incident_id: EntityId | None = None


class CreateInspectionOrder(ActionTool[InspectionInput, TaskPlan]):
    name = "create_inspection_order"
    description = "Order an inspection of a zone, road, bridge, channel, slope, project, shelter or hospital."
    approval_required = False
    Input = InspectionInput

    async def check(self, inp: InspectionInput, ctx: ToolContext) -> Plan[TaskPlan]:
        zone_id = await target_zone(ctx, inp.target_kind, inp.target_id)
        if inp.incident_id is not None:
            await require_open_incident(ctx.session, inp.incident_id)
        same = (Task.target_kind == inp.target_kind, Task.target_id == inp.target_id)
        existing = await first_open_task(ctx.session, "inspection", *same)
        return Plan(refs=_task_ref(existing), data=TaskPlan(existing, zone_id))

    async def apply(self, inp: InspectionInput, ctx: ToolContext, plan: Plan[TaskPlan]) -> Applied:
        target = f"{inp.target_kind} '{inp.target_id}'"
        if plan.data.existing is not None:
            return Applied(
                False, f"open inspection task '{plan.data.existing.id}' already exists for {target}"
            )
        task = create_task(
            ctx.session,
            kind="inspection",
            title=f"Inspect {inp.target_kind} {inp.target_id}",
            description=inp.reason,
            priority=inp.priority,
            zone_id=plan.data.zone_id,
            created_by=ctx.actor,
            target_kind=inp.target_kind,
            target_id=inp.target_id,
            incident_id=inp.incident_id,
        )
        return Applied(True, f"inspection task '{task.id}' created for {target}", _task_ref(task))

    async def verify(
        self, inp: InspectionInput, ctx: ToolContext, result: ActionResult
    ) -> VerificationResult:
        return await verify_open_task(ctx.session, result, kind="inspection", target_id=inp.target_id)


class MonitoringInput(ActionInput):
    target_kind: TargetKind
    target_id: EntityId
    metric: Metric
    interval_minutes: Annotated[int, Field(ge=5, le=1440)]
    reason: Reason
    priority: Priority = "medium"
    incident_id: EntityId | None = None


class CreateMonitoringTask(ActionTool[MonitoringInput, TaskPlan]):
    name = "create_monitoring_task"
    description = (
        "Watch one metric on an asset every interval_minutes (5 to 1440), e.g. saturation on a slope."
    )
    approval_required = False
    Input = MonitoringInput

    async def check(self, inp: MonitoringInput, ctx: ToolContext) -> Plan[TaskPlan]:
        zone_id = await target_zone(ctx, inp.target_kind, inp.target_id)
        if inp.incident_id is not None:
            await require_open_incident(ctx.session, inp.incident_id)
        same = (
            Task.target_kind == inp.target_kind,
            Task.target_id == inp.target_id,
            Task.metric == inp.metric,
        )
        existing = await first_open_task(ctx.session, "monitoring", *same)
        return Plan(refs=_task_ref(existing), data=TaskPlan(existing, zone_id))

    async def apply(self, inp: MonitoringInput, ctx: ToolContext, plan: Plan[TaskPlan]) -> Applied:
        target = f"{inp.target_kind} '{inp.target_id}'"
        if plan.data.existing is not None:
            message = (
                f"open monitoring task '{plan.data.existing.id}' already monitors {inp.metric} on {target}"
            )
            return Applied(False, message)
        task = create_task(
            ctx.session,
            kind="monitoring",
            title=f"Monitor {inp.metric} on {inp.target_kind} {inp.target_id}",
            description=inp.reason,
            priority=inp.priority,
            zone_id=plan.data.zone_id,
            created_by=ctx.actor,
            target_kind=inp.target_kind,
            target_id=inp.target_id,
            metric=inp.metric,
            interval_minutes=inp.interval_minutes,
            incident_id=inp.incident_id,
        )
        return Applied(
            True, f"monitoring task '{task.id}' created for {inp.metric} on {target}", _task_ref(task)
        )

    async def verify(
        self, inp: MonitoringInput, ctx: ToolContext, result: ActionResult
    ) -> VerificationResult:
        return await verify_open_task(
            ctx.session, result, metric=inp.metric, interval_minutes=inp.interval_minutes
        )


class AlertInput(ActionInput):
    zone_id: EntityId
    level: AlertLevel
    message: Text500
    incident_id: EntityId | None = None


class IssuePreventiveAlert(ActionTool[AlertInput, Alert | None]):
    name = "issue_preventive_alert"
    description = (
        "Issue a public alert to a zone. 'advisory' runs without approval; 'warning' and 'evacuate' need "
        "approval."
    )
    approval_required = True
    Input = AlertInput

    def requires_approval(self, inp: AlertInput) -> bool:
        return inp.level != "advisory"

    async def check(self, inp: AlertInput, ctx: ToolContext) -> Plan[Alert | None]:
        await require(ctx.session, Zone, inp.zone_id, "zone")
        if inp.incident_id is not None:
            await require_open_incident(ctx.session, inp.incident_id)
        same = select(Alert).where(
            Alert.zone_id == inp.zone_id, Alert.level == inp.level, Alert.message == inp.message
        )
        existing = next(iter(await fetch_all(ctx.session, same.limit(1))), None)
        refs = [EntityRef(kind="alert", id=existing.id)] if existing else []
        return Plan(refs=refs, data=existing)

    async def apply(self, inp: AlertInput, ctx: ToolContext, plan: Plan[Alert | None]) -> Applied:
        if plan.data is not None:
            return Applied(False, f"alert '{plan.data.id}' with this level and message exists")
        alert = Alert(
            id=new_id("alert"),
            zone_id=inp.zone_id,
            level=inp.level,
            message=inp.message,
            incident_id=inp.incident_id,
            issued_at=utcnow(),
        )
        ctx.session.add(alert)
        created = [EntityRef(kind="alert", id=alert.id)]
        return Applied(True, f"{inp.level} alert '{alert.id}' issued for zone '{inp.zone_id}'", created)

    async def verify(self, inp: AlertInput, ctx: ToolContext, result: ActionResult) -> VerificationResult:
        ids = ids_in(result, "alert")
        alert = await reread(ctx.session, Alert, ids[0]) if ids else None
        return verification(
            check("alert exists", True, alert is not None),
            check("alert level", inp.level, alert.level if alert else None),
        )
