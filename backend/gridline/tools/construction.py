"""``create_construction_restriction`` (spec §9 Prevention): halt a project or cap its excavation depth.

``halt_construction`` from ARCHITECTURE §10 is ``create_construction_restriction(kind="halt")``. Stopping the
excavation in the simulation is the simulation's job (spec D6); this tool changes the database.
"""

import math
from typing import Annotated, Self

from pydantic import Field, model_validator
from sqlalchemy import select

from gridline.db.models import ConstructionRestriction, Project
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
    fetch_all,
    ids_in,
    new_id,
    require,
    require_open_incident,
    reread,
    utcnow,
    verification,
)
from gridline.tools.vocab import EntityId, Reason, RestrictionKind

RESTRICTABLE_STATUSES = frozenset({"active", "halted", "planned"})
Found = tuple[Project, ConstructionRestriction | None]  # the project and an identical active restriction


class RestrictionInput(ActionInput):
    project_id: EntityId
    kind: RestrictionKind
    max_depth_m: Annotated[float, Field(gt=0)] | None = None
    reason: Reason
    incident_id: EntityId | None = None

    @model_validator(mode="after")
    def _depth_matches_kind(self) -> Self:
        if self.kind == "depth_limit" and self.max_depth_m is None:
            raise ValueError("max_depth_m is required for kind 'depth_limit'")
        if self.kind == "halt" and self.max_depth_m is not None:
            raise ValueError("max_depth_m only applies to kind 'depth_limit'")
        return self


class CreateConstructionRestriction(ActionTool[RestrictionInput, Found]):
    name = "create_construction_restriction"
    description = (
        "Halt a construction project (kind 'halt') or cap its excavation depth (kind 'depth_limit' with "
        "max_depth_m between the current and the planned depth). Needs approval."
    )
    approval_required = True
    Input = RestrictionInput

    async def check(self, inp: RestrictionInput, ctx: ToolContext) -> Plan[Found]:
        project = await require(ctx.session, Project, inp.project_id, "project", lock=True)
        if project.status not in RESTRICTABLE_STATUSES:
            only = "only active, halted or planned projects can be restricted"
            raise ToolRejected(f"project '{project.id}' is {project.status}; {only}")
        if inp.max_depth_m is not None:
            _check_depth_limit(project, inp.max_depth_m)
        if inp.incident_id is not None:
            await require_open_incident(ctx.session, inp.incident_id)
        depth = ConstructionRestriction.max_depth_m
        same_depth = depth.is_(None) if inp.max_depth_m is None else depth == inp.max_depth_m
        same = select(ConstructionRestriction).where(
            ConstructionRestriction.project_id == project.id,
            ConstructionRestriction.kind == inp.kind,
            same_depth,
            ConstructionRestriction.status == "active",
        )
        existing = next(iter(await fetch_all(ctx.session, same.limit(1))), None)
        refs = [EntityRef(kind="project", id=project.id)]
        if existing is not None:
            refs.append(EntityRef(kind="construction_restriction", id=existing.id))
        return Plan(refs=refs, data=(project, existing))

    async def apply(self, inp: RestrictionInput, ctx: ToolContext, plan: Plan[Found]) -> Applied:
        project, existing = plan.data
        if existing is not None:
            return Applied(
                False,
                f"active {inp.kind} restriction '{existing.id}' already exists for project '{project.id}'",
            )
        restriction = ConstructionRestriction(
            id=new_id("restr"),
            project_id=project.id,
            kind=inp.kind,
            max_depth_m=inp.max_depth_m,
            reason=inp.reason,
            incident_id=inp.incident_id,
            status="active",
            issued_at=utcnow(),
        )
        ctx.session.add(restriction)
        if inp.max_depth_m is None:
            project.status = "halted"
            message = f"project '{project.id}' ({project.name}) halted: {inp.reason}"
        else:
            project.depth_limit_m = min(project.depth_limit_m or math.inf, inp.max_depth_m)
            message = f"depth limit {inp.max_depth_m} m set on project '{project.id}' ({project.name})"
        return Applied(True, message, [EntityRef(kind="construction_restriction", id=restriction.id)])

    async def verify(
        self, inp: RestrictionInput, ctx: ToolContext, result: ActionResult
    ) -> VerificationResult:
        ids = ids_in(result, "construction_restriction")
        restriction = await reread(ctx.session, ConstructionRestriction, ids[0]) if ids else None
        project = await reread(ctx.session, Project, inp.project_id)
        checks = [check("restriction active", "active", restriction.status if restriction else None)]
        if inp.max_depth_m is None:
            checks.append(check("project halted", "halted", project.status if project else None))
        else:
            limit = project.depth_limit_m if project else None
            checks.append(check("depth limit in force", True, limit is not None and limit <= inp.max_depth_m))
        return verification(*checks)


def _check_depth_limit(project: Project, max_depth_m: float) -> None:
    if project.planned_depth_m is None:
        raise ToolRejected(f"project '{project.id}' has no excavation depth to limit")
    if max_depth_m > project.planned_depth_m:
        planned = project.planned_depth_m
        raise ToolRejected(
            f"max_depth_m {max_depth_m} exceeds the planned depth {planned} of project '{project.id}'"
        )
    depth = project.excavation_depth_m
    if depth is not None and max_depth_m < depth:
        raise ToolRejected(
            f"max_depth_m {max_depth_m} is below the current excavation depth {depth} of project "
            f"'{project.id}'; use kind 'halt'"
        )
