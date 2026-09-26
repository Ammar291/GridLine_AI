"""``execute_action``: the single path by which an action tool changes the city (spec §7-§8).

Order: validate input -> replay an earlier identical request -> enforce approval -> ``check`` -> before
snapshot -> ``apply`` + flush -> after snapshot -> audit row + commit. Tool-level problems never raise: they
come back as ``rejected`` or ``failed`` results, after a rollback, with their own audit row. Only a failure to
write the audit row itself propagates. ``verify`` is not called here; the caller runs it and stores the
outcome with ``record_verification``.
"""

import logging
from collections.abc import Mapping
from typing import Any

from pydantic import ValidationError
from pydantic_core import to_jsonable_python
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from gridline.db.models import Action
from gridline.tools.base import (
    ActionInput,
    ActionResult,
    ActionStatus,
    ActionTool,
    EntityRef,
    ToolContext,
    ToolRejected,
    VerificationResult,
)
from gridline.tools.common import new_id, utcnow
from gridline.tools.snapshot import snapshot

log = logging.getLogger(__name__)


def result_from_row(row: Action, *, replayed: bool = False) -> ActionResult:
    return ActionResult.model_validate(
        {
            "action_id": row.id,
            "action_type": row.tool,
            "status": row.status,
            "before": row.before_json,
            "after": row.after_json,
            "timestamp": row.executed_at,
            "sim_time": row.sim_time,
            "affected_entities": row.affected_entities_json,
            "message": row.message,
            "actor": row.actor,
            "approval_id": row.approval_id,
            "idempotency_key": row.idempotency_key,
            "incident_id": row.incident_id,
            "replayed": replayed,
        }
    )


def _flatten(exc: ValidationError) -> str:
    return "; ".join(f"{'.'.join(str(p) for p in e['loc']) or 'input'}: {e['msg']}" for e in exc.errors())


def _input_incident(inp: ActionInput) -> str | None:
    value = getattr(inp, "incident_id", None)
    return value if isinstance(value, str) else None


async def _refuse(
    tool: str,
    ctx: ToolContext,
    input_json: dict[str, Any],
    status: ActionStatus,
    message: str,
    incident_id: str | None,
) -> ActionResult:
    """Audit a rejected or failed attempt; its key stays in ``input_json`` only, so a retry is not blocked."""
    row = Action(
        id=new_id("act"),
        tool=tool,
        status=status,
        idempotency_key=None,
        actor=ctx.actor,
        approval_id=ctx.approval_id,
        run_id=ctx.run_id,
        incident_id=incident_id,
        input_json=input_json,
        before_json={},
        after_json={},
        affected_entities_json=[],
        message=message,
        sim_time=ctx.sim_time,
        executed_at=utcnow(),
        verification_json=None,
    )
    ctx.session.add(row)
    await ctx.session.commit()
    return result_from_row(row)


async def execute_action[I: ActionInput, P](
    tool: ActionTool[I, P], raw: Mapping[str, Any], ctx: ToolContext
) -> ActionResult:
    session = ctx.session
    session.expire_all()  # decide on the database, never on a stale identity map
    try:
        inp = tool.Input.model_validate(raw)
    except ValidationError as exc:
        raw_json: dict[str, Any] = to_jsonable_python(dict(raw), fallback=repr)
        return await _refuse(tool.name, ctx, raw_json, "rejected", _flatten(exc), None)
    input_json = inp.model_dump(mode="json")
    incident_id = _input_incident(inp)

    key = inp.idempotency_key
    if key is not None:
        prior = (
            await session.execute(select(Action).where(Action.idempotency_key == key))
        ).scalar_one_or_none()
        if prior is not None:
            if prior.tool != tool.name:
                message = f"idempotency key '{key}' was already used by {prior.tool}"
                return await _refuse(tool.name, ctx, input_json, "rejected", message, incident_id)
            if prior.input_json != input_json:
                message = f"idempotency key '{key}' was already used with a different input"
                return await _refuse(tool.name, ctx, input_json, "rejected", message, incident_id)
            return result_from_row(prior, replayed=True)

    if tool.requires_approval(inp) and ctx.approval_id is None:
        message = f"approval required for {tool.name}"
        return await _refuse(tool.name, ctx, input_json, "rejected", message, incident_id)

    try:
        plan = await tool.check(inp, ctx)
        before = await snapshot(session, plan.refs)
        applied = await tool.apply(inp, ctx, plan)
        await session.flush()
        after = await snapshot(session, [*plan.refs, *applied.created])
    except ToolRejected as exc:
        await session.rollback()
        return await _refuse(tool.name, ctx, input_json, "rejected", exc.reason, incident_id)
    except Exception as exc:
        log.exception("tool %s failed", tool.name)
        await session.rollback()
        return await _refuse(
            tool.name, ctx, input_json, "failed", f"{type(exc).__name__}: {exc}", incident_id
        )

    affected: list[EntityRef] = [r for r in plan.refs if before.get(r.key) != after.get(r.key)]
    affected += applied.created
    row = Action(
        id=new_id("act"),
        tool=tool.name,
        status="executed" if applied.changed else "unchanged",
        idempotency_key=key,
        actor=ctx.actor,
        approval_id=ctx.approval_id,
        run_id=ctx.run_id,
        incident_id=applied.incident_id or plan.incident_id or incident_id,
        input_json=input_json,
        before_json=before,
        after_json=after,
        affected_entities_json=[r.model_dump() for r in affected],
        message=applied.message,
        sim_time=ctx.sim_time,
        executed_at=utcnow(),
        verification_json=None,
    )
    session.add(row)
    await session.commit()
    return result_from_row(row)


async def record_verification(session: AsyncSession, action_id: str, result: VerificationResult) -> None:
    """Store a verification outcome on the action's audit row; ``KeyError`` if the action is unknown."""
    row = await session.get(Action, action_id)
    if row is None:
        raise KeyError(action_id)
    row.verification_json = result.model_dump(mode="json")
    await session.commit()
