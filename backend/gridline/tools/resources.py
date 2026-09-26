"""Response resources: rescue teams (crews that rescue people) and ambulances (spec §9 Resources).

Dispatch changes the database only: status, target zone, incident and time. Travel to the target zone is the
simulation's job (spec D6), so ``location_zone_id`` is left alone.
"""

from typing import Annotated

from pydantic import StringConstraints
from sqlalchemy import select

from gridline.db.models import Ambulance, Crew, Hospital, Zone
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
    require_open_access,
    require_open_incident,
    require_road_open,
    reread,
    utcnow,
    verification,
)
from gridline.tools.views import AmbulancesResult, AmbulanceView, CrewView, RescueTeamsResult
from gridline.tools.vocab import RESCUE_CREW_KINDS, EntityId

CrewTask = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]


class ZoneFilter(ReadInput):
    zone_id: EntityId | None = None


def _ensure_dispatchable(
    label: str, status: str, target: str | None, incident: str | None, zone_id: str, incident_id: str | None
) -> None:
    """Available, or already dispatched to this zone for this incident (then the call is ``unchanged``)."""
    if status == "dispatched":
        if (target, incident) != (zone_id, incident_id):
            raise ToolRejected(f"{label} is already dispatched to zone '{target}'")
    elif status != "available":
        raise ToolRejected(f"{label} is not available (status '{status}')")


class GetAvailableRescueTeams(ReadTool[ZoneFilter, RescueTeamsResult]):
    name = "get_available_rescue_teams"
    description = (
        "Rescue teams (crews of kind rescue, hill_rescue or boat) that are available now, with members and "
        "capabilities; optionally only those currently located in zone_id."
    )
    Input = ZoneFilter
    Output = RescueTeamsResult

    async def run(self, inp: ZoneFilter, ctx: ToolContext) -> RescueTeamsResult:
        stmt = (
            select(Crew).where(Crew.kind.in_(RESCUE_CREW_KINDS), Crew.status == "available").order_by(Crew.id)
        )
        if inp.zone_id is not None:
            await require(ctx.session, Zone, inp.zone_id, "zone")
            stmt = stmt.where(Crew.location_zone_id == inp.zone_id)
        return RescueTeamsResult(
            items=[CrewView.model_validate(c) for c in await fetch_all(ctx.session, stmt)]
        )


class DispatchRescueTeamInput(ActionInput):
    crew_id: EntityId
    zone_id: EntityId
    task: CrewTask
    incident_id: EntityId | None = None


class DispatchRescueTeam(ActionTool[DispatchRescueTeamInput, Crew]):
    name = "dispatch_rescue_team"
    description = (
        "Send an available rescue team to a zone with a task. The zone must have an open access road. "
        "Needs approval."
    )
    approval_required = True
    Input = DispatchRescueTeamInput

    async def check(self, inp: DispatchRescueTeamInput, ctx: ToolContext) -> Plan[Crew]:
        s = ctx.session
        crew = await require(s, Crew, inp.crew_id, "crew", lock=True)
        if crew.kind not in RESCUE_CREW_KINDS:
            raise ToolRejected(f"crew '{crew.id}' is not a rescue team (kind '{crew.kind}')")
        await require(s, Zone, inp.zone_id, "zone")
        if inp.incident_id is not None:
            await require_open_incident(s, inp.incident_id)
        await require_open_access(s, inp.zone_id)
        label = f"crew '{crew.id}'"
        _ensure_dispatchable(
            label, crew.status, crew.target_zone_id, crew.incident_id, inp.zone_id, inp.incident_id
        )
        return Plan(refs=[EntityRef(kind="crew", id=crew.id)], data=crew)

    async def apply(self, inp: DispatchRescueTeamInput, ctx: ToolContext, plan: Plan[Crew]) -> Applied:
        crew = plan.data
        if crew.status == "dispatched":
            return Applied(
                changed=False, message=f"crew '{crew.id}' is already dispatched to zone '{inp.zone_id}'"
            )
        crew.status, crew.target_zone_id, crew.task = "dispatched", inp.zone_id, inp.task
        crew.incident_id, crew.dispatched_at = inp.incident_id, utcnow()
        return Applied(
            changed=True, message=f"crew '{crew.id}' ({crew.name}) dispatched to zone '{inp.zone_id}'"
        )

    async def verify(
        self, inp: DispatchRescueTeamInput, ctx: ToolContext, result: ActionResult
    ) -> VerificationResult:
        crew = await reread(ctx.session, Crew, inp.crew_id)
        return verification(
            check("crew dispatched", "dispatched", crew.status if crew else None),
            check("crew target zone", inp.zone_id, crew.target_zone_id if crew else None),
        )


class GetAvailableAmbulances(ReadTool[ZoneFilter, AmbulancesResult]):
    name = "get_available_ambulances"
    description = (
        "Ambulances that are available now (ALS or BLS, base hospital); optionally only those in zone_id."
    )
    Input = ZoneFilter
    Output = AmbulancesResult

    async def run(self, inp: ZoneFilter, ctx: ToolContext) -> AmbulancesResult:
        stmt = select(Ambulance).where(Ambulance.status == "available").order_by(Ambulance.id)
        if inp.zone_id is not None:
            await require(ctx.session, Zone, inp.zone_id, "zone")
            stmt = stmt.where(Ambulance.location_zone_id == inp.zone_id)
        items = [AmbulanceView.model_validate(a) for a in await fetch_all(ctx.session, stmt)]
        return AmbulancesResult(items=items)


class DispatchAmbulanceInput(ActionInput):
    ambulance_id: EntityId
    zone_id: EntityId
    incident_id: EntityId | None = None
    destination_hospital_id: EntityId | None = None


class DispatchAmbulance(ActionTool[DispatchAmbulanceInput, Ambulance]):
    name = "dispatch_ambulance"
    description = (
        "Send an available ambulance to a zone, optionally naming the hospital it will take patients to. The "
        "zone and the destination hospital must be reachable over open roads. Needs approval."
    )
    approval_required = True
    Input = DispatchAmbulanceInput

    async def check(self, inp: DispatchAmbulanceInput, ctx: ToolContext) -> Plan[Ambulance]:
        s = ctx.session
        amb = await require(s, Ambulance, inp.ambulance_id, "ambulance", lock=True)
        await require(s, Zone, inp.zone_id, "zone")
        if inp.destination_hospital_id is not None:
            hospital = await require(s, Hospital, inp.destination_hospital_id, "hospital")
            await require_road_open(s, hospital.access_road_id, f"hospital '{hospital.id}'")
        if inp.incident_id is not None:
            await require_open_incident(s, inp.incident_id)
        await require_open_access(s, inp.zone_id)
        label = f"ambulance '{amb.id}'"
        _ensure_dispatchable(
            label, amb.status, amb.target_zone_id, amb.incident_id, inp.zone_id, inp.incident_id
        )
        return Plan(refs=[EntityRef(kind="ambulance", id=amb.id)], data=amb)

    async def apply(self, inp: DispatchAmbulanceInput, ctx: ToolContext, plan: Plan[Ambulance]) -> Applied:
        amb = plan.data
        if amb.status == "dispatched":
            return Applied(
                changed=False, message=f"ambulance '{amb.id}' is already dispatched to zone '{inp.zone_id}'"
            )
        amb.status, amb.target_zone_id, amb.destination_hospital_id = (
            "dispatched",
            inp.zone_id,
            inp.destination_hospital_id,
        )
        amb.incident_id, amb.dispatched_at = inp.incident_id, utcnow()
        return Applied(changed=True, message=f"ambulance '{amb.id}' dispatched to zone '{inp.zone_id}'")

    async def verify(
        self, inp: DispatchAmbulanceInput, ctx: ToolContext, result: ActionResult
    ) -> VerificationResult:
        amb = await reread(ctx.session, Ambulance, inp.ambulance_id)
        return verification(
            check("ambulance dispatched", "dispatched", amb.status if amb else None),
            check("ambulance target zone", inp.zone_id, amb.target_zone_id if amb else None),
        )
