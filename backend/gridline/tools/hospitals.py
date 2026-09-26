"""Hospital tools: ``get_hospital_capacity`` and ``reserve_hospital_beds`` (spec §9 Hospitals).

Beds are counted per type in ``hospital_beds``. A reservation moves beds from ``available`` to ``reserved`` on
that row and inserts a ``bed_reservations`` row in the same transaction, so ``occupied = total - available -
reserved`` is unchanged and the audit's before/after shows exactly which bed pool was drawn down.
"""

from collections import defaultdict
from typing import Annotated

from pydantic import Field
from sqlalchemy import select

from gridline.db.models import BedReservation, Hospital, HospitalBed, Zone
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
    ids_in,
    new_id,
    require,
    require_open_incident,
    require_road_open,
    reread,
    utcnow,
    verification,
)
from gridline.tools.views import BedView, HospitalsResult, HospitalView
from gridline.tools.vocab import EntityId


class HospitalQuery(ReadInput):
    hospital_id: EntityId | None = None
    zone_id: EntityId | None = None


class GetHospitalCapacity(ReadTool[HospitalQuery, HospitalsResult]):
    name = "get_hospital_capacity"
    description = (
        "Hospitals with beds per type (total, available, reserved, occupied); filter by hospital_id or "
        "zone_id."
    )
    Input = HospitalQuery
    Output = HospitalsResult

    async def run(self, inp: HospitalQuery, ctx: ToolContext) -> HospitalsResult:
        stmt = select(Hospital).order_by(Hospital.id)
        if inp.hospital_id is not None:
            await require(ctx.session, Hospital, inp.hospital_id, "hospital")
            stmt = stmt.where(Hospital.id == inp.hospital_id)
        if inp.zone_id is not None:
            await require(ctx.session, Zone, inp.zone_id, "zone")
            stmt = stmt.where(Hospital.zone_id == inp.zone_id)
        hospitals = await fetch_all(ctx.session, stmt)
        beds: defaultdict[str, list[BedView]] = defaultdict(list)
        bed_rows = select(HospitalBed).where(HospitalBed.hospital_id.in_([h.id for h in hospitals]))
        for bed in await fetch_all(ctx.session, bed_rows.order_by(HospitalBed.id)):
            beds[bed.hospital_id].append(BedView.model_validate(bed))
        items = [
            HospitalView(
                id=h.id,
                name=h.name,
                kind=h.kind,
                zone_id=h.zone_id,
                status=h.status,
                access_road_id=h.access_road_id,
                beds=beds[h.id],
            )
            for h in hospitals
        ]
        return HospitalsResult(items=items)


class ReserveHospitalBedsInput(ActionInput):
    hospital_id: EntityId
    incident_id: EntityId
    beds: Annotated[int, Field(ge=1, le=500)]
    bed_type: EntityId = Field(default="general", description="general, icu, emergency, pediatric, ...")


class ReserveHospitalBeds(ActionTool[ReserveHospitalBedsInput, HospitalBed]):
    name = "reserve_hospital_beds"
    description = (
        "Hold beds of one type at a hospital for an open incident. The hospital must have that many "
        "available and an open access road. Needs approval."
    )
    approval_required = True
    Input = ReserveHospitalBedsInput

    async def check(self, inp: ReserveHospitalBedsInput, ctx: ToolContext) -> Plan[HospitalBed]:
        s = ctx.session
        hospital = await require(s, Hospital, inp.hospital_id, "hospital")
        await require_open_incident(s, inp.incident_id)
        pool = select(HospitalBed).where(
            HospitalBed.hospital_id == hospital.id, HospitalBed.bed_type == inp.bed_type
        )
        rows = await fetch_all(s, pool.with_for_update())
        if not rows:
            raise ToolRejected(f"hospital '{hospital.id}' has no '{inp.bed_type}' beds")
        bed = rows[0]
        if bed.available < inp.beds:
            have = f"{bed.available} {inp.bed_type} beds available"
            raise ToolRejected(f"hospital '{hospital.id}' has {have}, {inp.beds} requested")
        await require_road_open(s, hospital.access_road_id, f"hospital '{hospital.id}'")
        return Plan(refs=[EntityRef(kind="hospital_bed", id=bed.id)], data=bed, incident_id=inp.incident_id)

    async def apply(
        self, inp: ReserveHospitalBedsInput, ctx: ToolContext, plan: Plan[HospitalBed]
    ) -> Applied:
        bed = plan.data
        reservation = BedReservation(
            id=new_id("resv"),
            hospital_id=bed.hospital_id,
            hospital_bed_id=bed.id,
            bed_type=bed.bed_type,
            incident_id=inp.incident_id,
            beds=inp.beds,
            status="active",
            created_at=utcnow(),
        )
        ctx.session.add(reservation)
        bed.available -= inp.beds
        bed.reserved += inp.beds
        return Applied(
            changed=True,
            message=f"{inp.beds} {bed.bed_type} beds reserved at hospital '{bed.hospital_id}'",
            created=[EntityRef(kind="bed_reservation", id=reservation.id)],
        )

    async def verify(
        self, inp: ReserveHospitalBedsInput, ctx: ToolContext, result: ActionResult
    ) -> VerificationResult:
        ids = ids_in(result, "bed_reservation")
        resv = await reread(ctx.session, BedReservation, ids[0]) if ids else None
        bed = await reread(ctx.session, HospitalBed, resv.hospital_bed_id) if resv else None
        return verification(
            check("reservation active", "active", resv.status if resv else None),
            check("reservation beds", inp.beds, resv.beds if resv else None),
            check("beds held on the pool", True, bed is not None and bed.reserved >= inp.beds),
        )
