"""Evacuation tools: ``create_evacuation_order`` and ``create_evacuation_task`` (spec §9 Evacuation).

A zone has at most one ``active`` order. Asking for a higher level escalates that order in place (spec D10);
asking for the same or a lower level leaves it unchanged. Evacuation tasks hang off the active order.
"""

from dataclasses import dataclass

from sqlalchemy import select

from gridline.db.models import Crew, EvacuationOrder, Shelter, Task, Zone
from gridline.tools.base import (
    ActionInput,
    ActionResult,
    ActionTool,
    Applied,
    EntityRef,
    Plan,
    ToolContext,
    ToolRejected,
    VerificationResult,
)
from gridline.tools.common import (
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
from gridline.tools.shelters import OPEN_STATUSES
from gridline.tools.vocab import EntityId, EvacuationLevel, Priority, Reason, Text500, evacuation_rank


async def active_order(ctx: ToolContext, zone_id: str, *, lock: bool = False) -> EvacuationOrder | None:
    stmt = select(EvacuationOrder).where(
        EvacuationOrder.zone_id == zone_id, EvacuationOrder.status == "active"
    )
    if lock:
        stmt = stmt.with_for_update()
    rows = await fetch_all(ctx.session, stmt.order_by(EvacuationOrder.issued_at).limit(1))
    return rows[0] if rows else None


def _order_ref(order_id: str) -> EntityRef:
    return EntityRef(kind="evacuation_order", id=order_id)


class EvacuationOrderInput(ActionInput):
    zone_id: EntityId
    level: EvacuationLevel
    reason: Reason
    shelter_id: EntityId | None = None
    incident_id: EntityId | None = None


class CreateEvacuationOrder(ActionTool[EvacuationOrderInput, EvacuationOrder | None]):
    name = "create_evacuation_order"
    description = (
        "Order a zone evacuated (voluntary or mandatory), optionally to an open shelter outside the zone. A "
        "higher level escalates the zone's active order. Needs approval."
    )
    approval_required = True
    Input = EvacuationOrderInput

    async def check(self, inp: EvacuationOrderInput, ctx: ToolContext) -> Plan[EvacuationOrder | None]:
        s = ctx.session
        await require(s, Zone, inp.zone_id, "zone")
        if inp.shelter_id is not None:
            shelter = await require(s, Shelter, inp.shelter_id, "shelter")
            if shelter.status not in OPEN_STATUSES:
                raise ToolRejected(f"shelter '{shelter.id}' is not open; open it first")
            if shelter.zone_id == inp.zone_id:
                raise ToolRejected(
                    f"shelter '{shelter.id}' is inside zone '{inp.zone_id}'; "
                    "choose a shelter outside the evacuated zone"
                )
        if inp.incident_id is not None:
            await require_open_incident(s, inp.incident_id)
        order = await active_order(ctx, inp.zone_id, lock=True)
        if order is None:
            return Plan(refs=[], data=None)
        return Plan(refs=[_order_ref(order.id)], data=order, incident_id=order.incident_id)

    async def apply(
        self, inp: EvacuationOrderInput, ctx: ToolContext, plan: Plan[EvacuationOrder | None]
    ) -> Applied:
        order, now = plan.data, utcnow()
        if order is None:
            order = EvacuationOrder(
                id=new_id("evac"),
                zone_id=inp.zone_id,
                level=inp.level,
                reason=inp.reason,
                shelter_id=inp.shelter_id,
                incident_id=inp.incident_id,
                status="active",
                issued_at=now,
                updated_at=now,
            )
            ctx.session.add(order)
            message = f"{inp.level} evacuation order '{order.id}' issued for zone '{inp.zone_id}'"
            return Applied(True, message, [_order_ref(order.id)], incident_id=inp.incident_id)
        if evacuation_rank(order.level) >= evacuation_rank(inp.level):
            message = (
                f"active {order.level} evacuation order '{order.id}' already covers zone '{inp.zone_id}'"
            )
            return Applied(False, message)
        order.level, order.reason, order.updated_at = inp.level, inp.reason, now
        order.shelter_id = inp.shelter_id or order.shelter_id
        order.incident_id = inp.incident_id or order.incident_id
        message = f"evacuation order '{order.id}' for zone '{inp.zone_id}' escalated to {inp.level}"
        return Applied(True, message, incident_id=order.incident_id)

    async def verify(
        self, inp: EvacuationOrderInput, ctx: ToolContext, result: ActionResult
    ) -> VerificationResult:
        ids = ids_in(result, "evacuation_order")
        order = await reread(ctx.session, EvacuationOrder, ids[0]) if ids else None
        level_ok = order is not None and evacuation_rank(order.level) >= evacuation_rank(inp.level)
        return verification(
            check("order active", "active", order.status if order else None),
            check(f"order level at least {inp.level}", True, level_ok),
        )


class EvacuationTaskInput(ActionInput):
    zone_id: EntityId
    description: Text500
    priority: Priority = "medium"
    assigned_crew_id: EntityId | None = None


@dataclass(frozen=True)
class _EvacuationTaskPlan:
    order: EvacuationOrder
    zone_name: str
    existing: Task | None


class CreateEvacuationTask(ActionTool[EvacuationTaskInput, _EvacuationTaskPlan]):
    name = "create_evacuation_task"
    description = (
        "Add a work item to the zone's active evacuation order (e.g. door-to-door warnings), optionally "
        "assigned to a crew (the crew's status is not changed)."
    )
    approval_required = False
    Input = EvacuationTaskInput

    async def check(self, inp: EvacuationTaskInput, ctx: ToolContext) -> Plan[_EvacuationTaskPlan]:
        zone = await require(ctx.session, Zone, inp.zone_id, "zone")
        order = await active_order(ctx, zone.id)
        if order is None:
            raise ToolRejected(f"no active evacuation order for zone '{zone.id}'")
        if inp.assigned_crew_id is not None:
            await require(ctx.session, Crew, inp.assigned_crew_id, "crew")
        same = (Task.evacuation_order_id == order.id, Task.description == inp.description)
        existing = await first_open_task(ctx.session, "evacuation", *same)
        refs = [EntityRef(kind="task", id=existing.id)] if existing else []
        return Plan(
            refs=refs, data=_EvacuationTaskPlan(order, zone.name, existing), incident_id=order.incident_id
        )

    async def apply(
        self, inp: EvacuationTaskInput, ctx: ToolContext, plan: Plan[_EvacuationTaskPlan]
    ) -> Applied:
        order, existing = plan.data.order, plan.data.existing
        if existing is not None:
            message = (
                f"open evacuation task '{existing.id}' with this description exists for order '{order.id}'"
            )
            return Applied(False, message)
        task = create_task(
            ctx.session,
            kind="evacuation",
            title=f"Evacuate {plan.data.zone_name} ({order.level})",
            description=inp.description,
            priority=inp.priority,
            zone_id=inp.zone_id,
            created_by=ctx.actor,
            assigned_crew_id=inp.assigned_crew_id,
            incident_id=order.incident_id,
            evacuation_order_id=order.id,
        )
        created = [EntityRef(kind="task", id=task.id)]
        return Applied(True, f"evacuation task '{task.id}' added to order '{order.id}'", created)

    async def verify(
        self, inp: EvacuationTaskInput, ctx: ToolContext, result: ActionResult
    ) -> VerificationResult:
        return await verify_open_task(ctx.session, result, kind="evacuation", zone_id=inp.zone_id)
