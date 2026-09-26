"""Executor behaviour (spec §7-§8) with a test-only tool that sets a road's closure_reason."""

from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select

from gridline.db.models import Action, Road
from gridline.tools.base import (
    ActionInput,
    ActionResult,
    ActionTool,
    Applied,
    EntityRef,
    Plan,
    ToolContext,
    ToolRejected,
    VerificationCheck,
    VerificationResult,
)
from gridline.tools.executor import execute_action, record_verification

SIM_TIME = datetime(2026, 7, 14, 6, 0, tzinfo=UTC)


class SetReasonInput(ActionInput):
    road_id: str
    reason: str
    incident_id: str | None = None
    applied_incident: str | None = None
    explode: bool = False


class SetReason(ActionTool[SetReasonInput, Road]):
    name = "set_closure_reason"
    description = "test tool"
    approval_required = True
    Input = SetReasonInput

    async def check(self, inp, ctx):
        road = await ctx.session.get(Road, inp.road_id)
        if road is None:
            raise ToolRejected(f"road '{inp.road_id}' not found")
        plan_incident = "inc_plan" if inp.incident_id == "use_plan" else None
        return Plan(refs=[EntityRef(kind="road", id=road.id)], data=road, incident_id=plan_incident)

    async def apply(self, inp, ctx, plan):
        road = plan.data
        if road.closure_reason == inp.reason:
            return Applied(changed=False, message="already set")
        road.closure_reason = inp.reason
        if inp.explode:
            await ctx.session.flush()
            raise RuntimeError("boom")
        return Applied(changed=True, message=f"reason set on {road.id}", incident_id=inp.applied_incident)

    async def verify(self, inp, ctx, result):
        road = await ctx.session.get(Road, inp.road_id, populate_existing=True)
        observed = road.closure_reason if road else None
        check = VerificationCheck(
            name="reason", passed=observed == inp.reason, expected=inp.reason, observed=observed
        )
        return VerificationResult(status="verified" if check.passed else "failed", checks=[check])


TOOL = SetReason()


async def _audit(check_session, action_id: str) -> Action:
    row = await check_session.get(Action, action_id, populate_existing=True)
    assert row is not None
    return row


async def _count_actions(check_session) -> int:
    return (await check_session.execute(select(func.count()).select_from(Action))).scalar_one()


async def _reason(check_session, road_id: str = "RD-01") -> str | None:
    road = await check_session.get(Road, road_id, populate_existing=True)
    assert road is not None
    return road.closure_reason


async def test_invalid_input_is_rejected_and_audited(ctx, check_session):
    raw = {"road_id": "RD-01", "surprise": 1}
    result = await execute_action(TOOL, raw, ctx)
    assert result.status == "rejected" and result.before == {} and result.after == {}
    assert (
        "reason: Field required" in result.message
        and "surprise: Extra inputs are not permitted" in result.message
    )
    row = await _audit(check_session, result.action_id)
    assert (row.status, row.input_json, row.idempotency_key, row.affected_entities_json) == (
        "rejected",
        raw,
        None,
        [],
    )


async def test_approval_required_is_rejected_without_approval_id(ctx_no_approval, check_session):
    result = await execute_action(TOOL, {"road_id": "RD-01", "reason": "x"}, ctx_no_approval)
    assert (result.status, result.message) == ("rejected", "approval required for set_closure_reason")
    assert await _reason(check_session) is None
    assert (await _audit(check_session, result.action_id)).status == "rejected"


async def test_check_rejection_is_audited_with_the_input_incident(ctx, check_session):
    result = await execute_action(
        TOOL, {"road_id": "RD-99", "reason": "x", "incident_id": "inc_missing"}, ctx
    )
    assert (result.status, result.message) == ("rejected", "road 'RD-99' not found")
    assert (await _audit(check_session, result.action_id)).incident_id == "inc_missing"  # plain string, no FK


async def test_executed_changes_state_and_writes_the_audit_row(tool_session, check_session):
    ctx = ToolContext(
        session=tool_session, actor="operator", approval_id="apr_1", run_id="run_1", sim_time=SIM_TIME
    )
    result = await execute_action(
        TOOL, {"road_id": "RD-01", "reason": "debris", "incident_id": "inc_in"}, ctx
    )
    assert result.status == "executed" and result.action_type == "set_closure_reason"
    assert result.before["road:RD-01"]["closure_reason"] is None
    assert result.after["road:RD-01"]["closure_reason"] == "debris"
    assert result.affected_entities == [EntityRef(kind="road", id="RD-01")]
    assert await _reason(check_session) == "debris"
    row = await _audit(check_session, result.action_id)
    assert row.id.startswith("act_") and len(row.id) == 16
    assert (row.actor, row.approval_id, row.run_id, row.incident_id) == (
        "operator",
        "apr_1",
        "run_1",
        "inc_in",
    )
    assert row.sim_time == SIM_TIME and row.executed_at.tzinfo is not None
    assert row.before_json == result.before and row.after_json == result.after
    assert row.affected_entities_json == [{"kind": "road", "id": "RD-01"}]


async def test_incident_precedence_is_applied_then_plan_then_input(ctx, check_session):
    first = await execute_action(TOOL, {"road_id": "RD-01", "reason": "a", "incident_id": "use_plan"}, ctx)
    assert (await _audit(check_session, first.action_id)).incident_id == "inc_plan"
    raw = {"road_id": "RD-01", "reason": "b", "incident_id": "use_plan", "applied_incident": "inc_applied"}
    second = await execute_action(TOOL, raw, ctx)
    assert second.incident_id == "inc_applied"


async def test_unchanged_when_the_city_is_already_in_the_requested_state(ctx):
    await execute_action(TOOL, {"road_id": "RD-01", "reason": "debris"}, ctx)
    again = await execute_action(TOOL, {"road_id": "RD-01", "reason": "debris"}, ctx)
    assert again.status == "unchanged" and again.message == "already set"
    assert again.before == again.after and again.affected_entities == []


async def test_idempotent_replay_returns_the_first_result(ctx, check_session):
    raw = {"road_id": "RD-01", "reason": "debris", "idempotency_key": "plan-1"}
    first = await execute_action(TOOL, raw, ctx)
    road = await check_session.get(Road, "RD-01")
    assert road is not None
    road.closure_reason = "changed elsewhere"
    await check_session.commit()
    second = await execute_action(TOOL, raw, ctx)
    assert second.replayed and not first.replayed
    assert second.model_dump(exclude={"replayed"}) == first.model_dump(exclude={"replayed"})
    assert await _count_actions(check_session) == 1
    assert await _reason(check_session) == "changed elsewhere"  # nothing ran twice


async def test_replay_refuses_a_key_reused_with_different_input(ctx, check_session):
    await execute_action(TOOL, {"road_id": "RD-01", "reason": "a", "idempotency_key": "k"}, ctx)
    other = await execute_action(TOOL, {"road_id": "RD-01", "reason": "b", "idempotency_key": "k"}, ctx)
    assert (other.status, other.message) == (
        "rejected",
        "idempotency key 'k' was already used with a different input",
    )
    assert await _reason(check_session) == "a"


async def test_rejected_then_retry_with_same_key_executes(ctx, ctx_no_approval, check_session):
    raw = {"road_id": "RD-01", "reason": "debris", "idempotency_key": "k1"}
    refused = await execute_action(TOOL, raw, ctx_no_approval)
    assert refused.status == "rejected"
    row = await _audit(check_session, refused.action_id)
    assert row.idempotency_key is None and row.input_json["idempotency_key"] == "k1"
    retried = await execute_action(TOOL, raw, ctx)
    assert retried.status == "executed" and retried.idempotency_key == "k1" and not retried.replayed


async def test_apply_exception_rolls_back_and_records_failed(ctx, check_session):
    raw = {"road_id": "RD-01", "reason": "debris", "explode": True, "idempotency_key": "k2"}
    result = await execute_action(TOOL, raw, ctx)
    assert (result.status, result.message) == ("failed", "RuntimeError: boom")
    assert result.affected_entities == [] and result.before == {}
    assert await _reason(check_session) is None  # the flushed change was rolled back
    assert (await _audit(check_session, result.action_id)).status == "failed"
    retried = await execute_action(TOOL, {**raw, "explode": False}, ctx)
    assert retried.status == "executed"


async def test_check_sees_changes_made_by_another_session(ctx, check_session):
    await execute_action(TOOL, {"road_id": "RD-01", "reason": "a"}, ctx)
    road = await check_session.get(Road, "RD-01")
    assert road is not None
    road.closure_reason = "b"
    await check_session.commit()
    result = await execute_action(TOOL, {"road_id": "RD-01", "reason": "b"}, ctx)
    assert result.status == "unchanged"  # the tool session's identity map still held "a"


async def test_record_verification_stores_the_result(ctx, check_session):
    raw = {"road_id": "RD-01", "reason": "debris"}
    result = await execute_action(TOOL, raw, ctx)
    verification = await TOOL.verify(SetReasonInput.model_validate(raw), ctx, result)
    assert verification.status == "verified"
    await record_verification(ctx.session, result.action_id, verification)
    assert (await _audit(check_session, result.action_id)).verification_json == verification.model_dump(
        mode="json"
    )
    with pytest.raises(KeyError):
        await record_verification(ctx.session, "act_missing", verification)


def test_action_result_round_trips_as_json():
    result = ActionResult(
        action_id="act_1", action_type="t", status="executed", before={}, after={}, timestamp=SIM_TIME,
        sim_time=None, affected_entities=[EntityRef(kind="road", id="RD-01")], message="m", actor="agent",
        approval_id=None, idempotency_key=None, incident_id=None,
    )  # fmt: skip
    assert ActionResult.model_validate_json(result.model_dump_json()) == result
