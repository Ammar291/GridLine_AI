from gridline.db.models import ConstructionRestriction, Project
from gridline.tools.base import EntityRef
from gridline.tools.common import ids_in
from gridline.tools.construction import CreateConstructionRestriction
from gridline.tools.executor import execute_action
from tests.tools.helpers import add_incident, count, fresh, tamper

RESTRICT = CreateConstructionRestriction()


async def test_halt_restriction_halts_the_project(ctx, check_session):
    incident = await add_incident(check_session)
    raw = {"project_id": "PR-HT2", "kind": "halt", "reason": "dmp-2024 s5 halt rule", "incident_id": incident}
    result = await execute_action(RESTRICT, raw, ctx)
    assert result.status == "executed"
    [restriction_id] = ids_in(result, "construction_restriction")
    assert result.affected_entities == [
        EntityRef(kind="project", id="PR-HT2"),
        EntityRef(kind="construction_restriction", id=restriction_id),
    ]
    assert (result.before["project:PR-HT2"]["status"], result.after["project:PR-HT2"]["status"]) == (
        "active",
        "halted",
    )
    assert (await fresh(check_session, Project, "PR-HT2")).status == "halted"
    row = await fresh(check_session, ConstructionRestriction, restriction_id)
    assert (row.kind, row.status, row.max_depth_m, row.incident_id) == ("halt", "active", None, incident)
    again = await execute_action(RESTRICT, raw, ctx)
    assert (again.status, again.message) == (
        "unchanged",
        f"active halt restriction '{restriction_id}' already exists for project 'PR-HT2'",
    )


async def test_depth_limit_keeps_the_tightest_limit(ctx, check_session):
    base = {"project_id": "PR-HT2", "kind": "depth_limit", "reason": "Limit cut depth"}
    first = await execute_action(RESTRICT, {**base, "max_depth_m": 4.0}, ctx)
    assert first.status == "executed" and first.after["project:PR-HT2"]["depth_limit_m"] == 4.0
    looser = await execute_action(RESTRICT, {**base, "max_depth_m": 5.0}, ctx)
    assert looser.status == "executed"
    assert [r.kind for r in looser.affected_entities] == ["construction_restriction"]  # project unchanged
    tighter = await execute_action(RESTRICT, {**base, "max_depth_m": 3.0}, ctx)
    assert tighter.after["project:PR-HT2"]["depth_limit_m"] == 3.0
    project = await fresh(check_session, Project, "PR-HT2")
    assert (project.status, project.depth_limit_m) == ("active", 3.0)
    assert await count(check_session, ConstructionRestriction) == 3


async def test_construction_restriction_rejections(ctx, ctx_no_approval, check_session):
    base = {"project_id": "PR-HT2", "kind": "depth_limit", "reason": "x"}
    cases = [
        ({**base, "project_id": "PR-XX", "max_depth_m": 4.0}, "project 'PR-XX' not found"),
        (
            {**base, "project_id": "PR-HT1", "kind": "halt"},
            "project 'PR-HT1' is completed; only active, halted or planned projects can be restricted",
        ),
        ({**base, "max_depth_m": 7.0}, "max_depth_m 7.0 exceeds the planned depth 6.0 of project 'PR-HT2'"),
        (
            {**base, "max_depth_m": 2.0},
            "max_depth_m 2.0 is below the current excavation depth 2.5 of project 'PR-HT2'; use kind 'halt'",
        ),
        (
            {**base, "project_id": "PR-D3R", "max_depth_m": 2.0},
            "project 'PR-D3R' has no excavation depth to limit",
        ),
        ({**base, "max_depth_m": 4.0, "incident_id": "inc_nope"}, "incident 'inc_nope' not found"),
    ]
    for raw, message in cases:
        result = await execute_action(RESTRICT, raw, ctx)
        assert (result.status, result.message) == ("rejected", message)
    no_depth = await execute_action(RESTRICT, base, ctx)
    assert (
        no_depth.status == "rejected" and "max_depth_m is required for kind 'depth_limit'" in no_depth.message
    )
    halt_depth = await execute_action(RESTRICT, {**base, "kind": "halt", "max_depth_m": 4.0}, ctx)
    assert "max_depth_m only applies to kind 'depth_limit'" in halt_depth.message
    refused = await execute_action(RESTRICT, {**base, "kind": "halt"}, ctx_no_approval)
    assert (refused.status, refused.message) == (
        "rejected",
        "approval required for create_construction_restriction",
    )
    assert (await fresh(check_session, Project, "PR-HT2")).status == "active"
    assert await count(check_session, ConstructionRestriction) == 0


async def test_construction_restriction_verify(ctx, check_session):
    halt = {"project_id": "PR-TQ", "kind": "halt", "reason": "x"}
    result = await execute_action(RESTRICT, halt, ctx)
    inp = RESTRICT.Input.model_validate(halt)
    assert (await RESTRICT.verify(inp, ctx, result)).status == "verified"
    await tamper(check_session, Project, "PR-TQ", status="active")
    assert (await RESTRICT.verify(inp, ctx, result)).status == "failed"
    limit = {"project_id": "PR-HT2", "kind": "depth_limit", "max_depth_m": 4.0, "reason": "x"}
    limited = await execute_action(RESTRICT, limit, ctx)
    limit_inp = RESTRICT.Input.model_validate(limit)
    assert (await RESTRICT.verify(limit_inp, ctx, limited)).status == "verified"
    await tamper(check_session, Project, "PR-HT2", depth_limit_m=None)
    assert (await RESTRICT.verify(limit_inp, ctx, limited)).status == "failed"
