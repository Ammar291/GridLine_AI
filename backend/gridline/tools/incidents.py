"""Incident tools: ``create_incident``, ``update_incident``, ``create_emergency_task`` (spec §9 Incidents)."""

from typing import Self

from pydantic import model_validator
from sqlalchemy import select

from gridline.db.models import Crew, Incident, Task, Zone
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
from gridline.tools.vocab import (
    Band,
    EntityId,
    Hazard,
    IncidentBand,
    IncidentStatus,
    Priority,
    Summary,
    Text500,
    Title,
)


def _incident_ref(incident_id: str) -> EntityRef:
    return EntityRef(kind="incident", id=incident_id)


class CreateIncidentInput(ActionInput):
    zone_id: EntityId
    hazard: Hazard
    band: IncidentBand
    title: Title
    summary: Summary


class CreateIncident(ActionTool[CreateIncidentInput, Incident | None]):
    name = "create_incident"
    description = (
        "Open an incident for a hazard in a zone. If one is already open for that zone and hazard, it is "
        "returned unchanged."
    )
    approval_required = False
    Input = CreateIncidentInput

    async def check(self, inp: CreateIncidentInput, ctx: ToolContext) -> Plan[Incident | None]:
        await require(ctx.session, Zone, inp.zone_id, "zone")
        stmt = select(Incident).where(
            Incident.zone_id == inp.zone_id, Incident.hazard == inp.hazard, Incident.status == "open"
        )
        open_ = await fetch_all(ctx.session, stmt.order_by(Incident.opened_at).limit(1))
        if open_:
            return Plan(refs=[_incident_ref(open_[0].id)], data=open_[0], incident_id=open_[0].id)
        return Plan(refs=[], data=None)

    async def apply(self, inp: CreateIncidentInput, ctx: ToolContext, plan: Plan[Incident | None]) -> Applied:
        if plan.data is not None:
            message = f"incident '{plan.data.id}' is already open for {inp.hazard} in zone '{inp.zone_id}'"
            return Applied(changed=False, message=message)
        now = utcnow()
        incident = Incident(
            id=new_id("inc"),
            zone_id=inp.zone_id,
            hazard=inp.hazard,
            band=inp.band,
            status="open",
            title=inp.title,
            summary=inp.summary,
            opened_at=now,
            updated_at=now,
            closed_at=None,
        )
        ctx.session.add(incident)
        return Applied(
            changed=True,
            message=f"incident '{incident.id}' opened: {inp.hazard} ({inp.band}) in zone '{inp.zone_id}'",
            created=[_incident_ref(incident.id)],
            incident_id=incident.id,
        )

    async def verify(
        self, inp: CreateIncidentInput, ctx: ToolContext, result: ActionResult
    ) -> VerificationResult:
        ids = ids_in(result, "incident")
        incident = await reread(ctx.session, Incident, ids[0]) if ids else None
        return verification(
            check("incident open", "open", incident.status if incident else None),
            check("incident zone", inp.zone_id, incident.zone_id if incident else None),
            check("incident hazard", inp.hazard, incident.hazard if incident else None),
        )


class UpdateIncidentInput(ActionInput):
    incident_id: EntityId
    band: Band | None = None
    status: IncidentStatus | None = None
    summary: Summary | None = None

    @model_validator(mode="after")
    def _something_to_update(self) -> Self:
        if self.band is None and self.status is None and self.summary is None:
            raise ValueError("at least one of band, status or summary is required")
        return self

    def requested(self) -> dict[str, str]:
        return {
            k: v for k, v in (("band", self.band), ("status", self.status), ("summary", self.summary)) if v
        }


class UpdateIncident(ActionTool[UpdateIncidentInput, Incident]):
    name = "update_incident"
    description = "Change an open incident's band, summary or status (closing it records closed_at)."
    approval_required = False
    Input = UpdateIncidentInput

    async def check(self, inp: UpdateIncidentInput, ctx: ToolContext) -> Plan[Incident]:
        incident = await require(ctx.session, Incident, inp.incident_id, "incident", lock=True)
        if incident.status == "closed":
            raise ToolRejected(f"incident '{incident.id}' is closed")
        return Plan(refs=[_incident_ref(incident.id)], data=incident, incident_id=incident.id)

    async def apply(self, inp: UpdateIncidentInput, ctx: ToolContext, plan: Plan[Incident]) -> Applied:
        incident = plan.data
        current = {"band": incident.band, "status": incident.status, "summary": incident.summary}
        changes = {k: v for k, v in inp.requested().items() if current[k] != v}
        if not changes:
            return Applied(
                changed=False, message=f"incident '{incident.id}' already has the requested values"
            )
        now = utcnow()
        if "band" in changes:
            incident.band = changes["band"]
        if "summary" in changes:
            incident.summary = changes["summary"]
        if "status" in changes:
            incident.status = changes["status"]
            incident.closed_at = now if incident.status == "closed" else None
        incident.updated_at = now
        return Applied(
            changed=True, message=f"incident '{incident.id}' updated: {', '.join(sorted(changes))}"
        )

    async def verify(
        self, inp: UpdateIncidentInput, ctx: ToolContext, result: ActionResult
    ) -> VerificationResult:
        incident = await reread(ctx.session, Incident, inp.incident_id)
        observed = (
            {}
            if incident is None
            else {"band": incident.band, "status": incident.status, "summary": incident.summary}
        )
        return verification(*(check(f"incident {k}", v, observed.get(k)) for k, v in inp.requested().items()))


class CreateEmergencyTaskInput(ActionInput):
    incident_id: EntityId
    title: Title
    description: Text500
    priority: Priority = "medium"
    zone_id: EntityId | None = None
    assigned_crew_id: EntityId | None = None


class CreateEmergencyTask(ActionTool[CreateEmergencyTaskInput, TaskPlan]):
    name = "create_emergency_task"
    description = (
        "Create an emergency work item for an open incident, in the incident's zone unless zone_id is given, "
        "optionally assigned to a crew (the crew's status is not changed)."
    )
    approval_required = False
    Input = CreateEmergencyTaskInput

    async def check(self, inp: CreateEmergencyTaskInput, ctx: ToolContext) -> Plan[TaskPlan]:
        s = ctx.session
        incident = await require_open_incident(s, inp.incident_id)
        zone_id = inp.zone_id or incident.zone_id
        await require(s, Zone, zone_id, "zone")
        if inp.assigned_crew_id is not None:
            await require(s, Crew, inp.assigned_crew_id, "crew")
        existing = await first_open_task(
            s, "emergency", Task.incident_id == incident.id, Task.title == inp.title
        )
        refs = [EntityRef(kind="task", id=existing.id)] if existing else []
        return Plan(refs=refs, data=TaskPlan(existing, zone_id), incident_id=incident.id)

    async def apply(self, inp: CreateEmergencyTaskInput, ctx: ToolContext, plan: Plan[TaskPlan]) -> Applied:
        if plan.data.existing is not None:
            message = (
                f"open emergency task '{plan.data.existing.id}' already exists for incident "
                f"'{inp.incident_id}' with this title"
            )
            return Applied(changed=False, message=message)
        task = create_task(
            ctx.session,
            kind="emergency",
            title=inp.title,
            description=inp.description,
            priority=inp.priority,
            zone_id=plan.data.zone_id,
            created_by=ctx.actor,
            assigned_crew_id=inp.assigned_crew_id,
            incident_id=inp.incident_id,
        )
        return Applied(
            changed=True,
            message=f"emergency task '{task.id}' created: {inp.title}",
            created=[EntityRef(kind="task", id=task.id)],
        )

    async def verify(
        self, inp: CreateEmergencyTaskInput, ctx: ToolContext, result: ActionResult
    ) -> VerificationResult:
        return await verify_open_task(ctx.session, result, kind="emergency", incident_id=inp.incident_id)
