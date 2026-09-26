"""Shelter tools: ``get_shelter_capacity``, ``open_shelter``, ``close_shelter`` (spec §9 Shelters)."""

from sqlalchemy import select

from gridline.db.models import EvacuationOrder, Shelter, Zone
from gridline.tools.base import (
    ActionInput,
    ActionResult,
    ActionTool,
    Applied,
    EntityRef,
    Plan,
    ReadInput,
    ReadTool,
    ToolContext,
    ToolRejected,
    VerificationResult,
)
from gridline.tools.common import (
    check,
    fetch_all,
    require,
    require_open_incident,
    require_road_open,
    reread,
    utcnow,
    verification,
)
from gridline.tools.views import SheltersResult, ShelterView
from gridline.tools.vocab import EntityId, Reason

OPEN_STATUSES = frozenset({"open", "full"})  # "full" is an open shelter at capacity


class ShelterQuery(ReadInput):
    shelter_id: EntityId | None = None
    zone_id: EntityId | None = None


class GetShelterCapacity(ReadTool[ShelterQuery, SheltersResult]):
    name = "get_shelter_capacity"
    description = (
        "Shelters with status, capacity, current occupancy and free places; filter by shelter_id or zone_id."
    )
    Input = ShelterQuery
    Output = SheltersResult

    async def run(self, inp: ShelterQuery, ctx: ToolContext) -> SheltersResult:
        stmt = select(Shelter).order_by(Shelter.id)
        if inp.shelter_id is not None:
            await require(ctx.session, Shelter, inp.shelter_id, "shelter")
            stmt = stmt.where(Shelter.id == inp.shelter_id)
        if inp.zone_id is not None:
            await require(ctx.session, Zone, inp.zone_id, "zone")
            stmt = stmt.where(Shelter.zone_id == inp.zone_id)
        return SheltersResult(
            items=[ShelterView.model_validate(s) for s in await fetch_all(ctx.session, stmt)]
        )


def _shelter_ref(shelter_id: str) -> EntityRef:
    return EntityRef(kind="shelter", id=shelter_id)


class OpenShelterInput(ActionInput):
    shelter_id: EntityId
    incident_id: EntityId | None = None


class OpenShelter(ActionTool[OpenShelterInput, Shelter]):
    name = "open_shelter"
    description = (
        "Open a shelter so evacuees can be sent there; its access road must be open. Needs approval."
    )
    approval_required = True
    Input = OpenShelterInput

    async def check(self, inp: OpenShelterInput, ctx: ToolContext) -> Plan[Shelter]:
        shelter = await require(ctx.session, Shelter, inp.shelter_id, "shelter", lock=True)
        if inp.incident_id is not None:
            await require_open_incident(ctx.session, inp.incident_id)
        if shelter.status not in OPEN_STATUSES:
            await require_road_open(ctx.session, shelter.access_road_id, f"shelter '{shelter.id}'")
        return Plan(refs=[_shelter_ref(shelter.id)], data=shelter)

    async def apply(self, inp: OpenShelterInput, ctx: ToolContext, plan: Plan[Shelter]) -> Applied:
        shelter = plan.data
        if shelter.status in OPEN_STATUSES:
            return Applied(changed=False, message=f"shelter '{shelter.id}' is already open")
        shelter.status, shelter.opened_at, shelter.incident_id = "open", utcnow(), inp.incident_id
        return Applied(changed=True, message=f"shelter '{shelter.id}' ({shelter.name}) opened")

    async def verify(
        self, inp: OpenShelterInput, ctx: ToolContext, result: ActionResult
    ) -> VerificationResult:
        shelter = await reread(ctx.session, Shelter, inp.shelter_id)
        return verification(check("shelter open", "open", shelter.status if shelter else None))


class CloseShelterInput(ActionInput):
    shelter_id: EntityId
    reason: Reason


class CloseShelter(ActionTool[CloseShelterInput, Shelter]):
    name = "close_shelter"
    description = (
        "Close an empty shelter that is not the destination of an active evacuation order. Needs approval."
    )
    approval_required = True
    Input = CloseShelterInput

    async def check(self, inp: CloseShelterInput, ctx: ToolContext) -> Plan[Shelter]:
        shelter = await require(ctx.session, Shelter, inp.shelter_id, "shelter", lock=True)
        if shelter.current_occupancy > 0:
            raise ToolRejected(f"shelter '{shelter.id}' has {shelter.current_occupancy} occupants")
        orders = select(EvacuationOrder).where(
            EvacuationOrder.shelter_id == shelter.id, EvacuationOrder.status == "active"
        )
        active = await fetch_all(ctx.session, orders.order_by(EvacuationOrder.id).limit(1))
        if active:
            order_id = active[0].id
            raise ToolRejected(
                f"shelter '{shelter.id}' is the destination of active evacuation order '{order_id}'"
            )
        return Plan(refs=[_shelter_ref(shelter.id)], data=shelter, incident_id=shelter.incident_id)

    async def apply(self, inp: CloseShelterInput, ctx: ToolContext, plan: Plan[Shelter]) -> Applied:
        shelter = plan.data
        if shelter.status == "closed":
            return Applied(changed=False, message=f"shelter '{shelter.id}' is already closed")
        shelter.status, shelter.opened_at, shelter.incident_id = "closed", None, None
        return Applied(changed=True, message=f"shelter '{shelter.id}' ({shelter.name}) closed: {inp.reason}")

    async def verify(
        self, inp: CloseShelterInput, ctx: ToolContext, result: ActionResult
    ) -> VerificationResult:
        shelter = await reread(ctx.session, Shelter, inp.shelter_id)
        return verification(check("shelter closed", "closed", shelter.status if shelter else None))
