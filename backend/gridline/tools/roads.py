"""Road tools: ``get_road_status``, ``close_road``, ``reopen_road`` (spec §9 Infrastructure)."""

from sqlalchemy import or_, select

from gridline.db.models import Road, Zone
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
    reread,
    utcnow,
    verification,
)
from gridline.tools.views import RoadsResult, RoadView
from gridline.tools.vocab import EntityId, Reason


class RoadQuery(ReadInput):
    road_id: EntityId | None = None
    zone_id: EntityId | None = None


class GetRoadStatus(ReadTool[RoadQuery, RoadsResult]):
    name = "get_road_status"
    description = (
        "Status of roads (open, blocked or closed), closure reason and evacuation-route flags. Filter by "
        "road_id, or by zone_id for every road that runs in, from or to that zone."
    )
    Input = RoadQuery
    Output = RoadsResult

    async def run(self, inp: RoadQuery, ctx: ToolContext) -> RoadsResult:
        stmt = select(Road).order_by(Road.id)
        if inp.road_id is not None:
            await require(ctx.session, Road, inp.road_id, "road")
            stmt = stmt.where(Road.id == inp.road_id)
        if inp.zone_id is not None:
            await require(ctx.session, Zone, inp.zone_id, "zone")
            z = inp.zone_id
            stmt = stmt.where(or_(Road.zone_id == z, Road.from_zone_id == z, Road.to_zone_id == z))
        roads = await fetch_all(ctx.session, stmt)
        return RoadsResult(items=[RoadView.model_validate(r) for r in roads])


def _road_ref(road_id: str) -> EntityRef:
    return EntityRef(kind="road", id=road_id)


class CloseRoadInput(ActionInput):
    road_id: EntityId
    reason: Reason
    incident_id: EntityId | None = None


class CloseRoad(ActionTool[CloseRoadInput, Road]):
    name = "close_road"
    description = (
        "Close a road to traffic (e.g. below an unstable slope or under floodwater). Needs approval."
    )
    approval_required = True
    Input = CloseRoadInput

    async def check(self, inp: CloseRoadInput, ctx: ToolContext) -> Plan[Road]:
        road = await require(ctx.session, Road, inp.road_id, "road", lock=True)
        if inp.incident_id is not None:
            await require_open_incident(ctx.session, inp.incident_id)
        return Plan(refs=[_road_ref(road.id)], data=road)

    async def apply(self, inp: CloseRoadInput, ctx: ToolContext, plan: Plan[Road]) -> Applied:
        road = plan.data
        if road.status == "closed":
            return Applied(changed=False, message=f"road '{road.id}' is already closed")
        road.status, road.closure_reason, road.closed_at = "closed", inp.reason, utcnow()
        road.incident_id = inp.incident_id
        return Applied(changed=True, message=f"road '{road.id}' ({road.name}) closed: {inp.reason}")

    async def verify(self, inp: CloseRoadInput, ctx: ToolContext, result: ActionResult) -> VerificationResult:
        road = await reread(ctx.session, Road, inp.road_id)
        return verification(check("road closed", "closed", road.status if road else None))


class ReopenRoadInput(ActionInput):
    road_id: EntityId
    reason: Reason


class ReopenRoad(ActionTool[ReopenRoadInput, Road]):
    name = "reopen_road"
    description = "Reopen a closed road. A road blocked by debris must be cleared first. Needs approval."
    approval_required = True
    Input = ReopenRoadInput

    async def check(self, inp: ReopenRoadInput, ctx: ToolContext) -> Plan[Road]:
        road = await require(ctx.session, Road, inp.road_id, "road", lock=True)
        if road.status == "blocked":
            cause = f" ({road.closure_reason})" if road.closure_reason else ""
            raise ToolRejected(f"road '{road.id}' is blocked{cause}; clear it before reopening")
        return Plan(refs=[_road_ref(road.id)], data=road, incident_id=road.incident_id)

    async def apply(self, inp: ReopenRoadInput, ctx: ToolContext, plan: Plan[Road]) -> Applied:
        road = plan.data
        if road.status == "open":
            return Applied(changed=False, message=f"road '{road.id}' is already open")
        road.status, road.closure_reason, road.closed_at, road.incident_id = "open", None, None, None
        return Applied(changed=True, message=f"road '{road.id}' ({road.name}) reopened: {inp.reason}")

    async def verify(
        self, inp: ReopenRoadInput, ctx: ToolContext, result: ActionResult
    ) -> VerificationResult:
        road = await reread(ctx.session, Road, inp.road_id)
        return verification(check("road open", "open", road.status if road else None))
