"""``approval_gate``, ``execute``, ``verify``, ``complete``: the plan meets the city (rules 5 and 6).

Nothing executes before the operator's decision. Execution goes through the tool executor (audited,
idempotent), verification re-reads the database through each tool's own post-conditions, and ``complete``
reports the affected rows as they are now in the database, not as the model expected them to be.
"""

# pyright: reportTypedDictNotRequiredAccess=false
# (each node reads keys its predecessors set; the graph's edges guarantee they ran)

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

from langgraph.types import interrupt
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from gridline.agents.state import Node, WorkflowState, WorkflowUpdate
from gridline.agents.steps import (
    WorkflowActionResult,
    WorkflowActionVerification,
    WorkflowApprovalOutput,
    WorkflowCheck,
    WorkflowCompletionOutput,
    WorkflowDecision,
    WorkflowEntityState,
    WorkflowExecutionOutput,
    WorkflowVerificationOutput,
)
from gridline.tools.base import ActionResult, EntityRef, ToolContext
from gridline.tools.executor import execute_action, record_verification
from gridline.tools.registry import ToolRegistry
from gridline.tools.snapshot import snapshot

Sessions = async_sessionmaker[AsyncSession]
ProjectHalted = Callable[[str], Awaitable[None]]
SHOWN_FIELDS = (
    "status",
    "activity",
    "kind",
    "level",
    "priority",
    "metric",
    "interval_minutes",
    "target_kind",
    "target_id",
    "excavation_depth_m",
    "depth_limit_m",
    "zone_id",
    "message",
    "reason",
)
MAX_FIELDS = 7


def approval_id(run_id: str) -> str:
    return f"apr-{run_id}"


async def approval_gate(state: WorkflowState) -> WorkflowUpdate:
    waiting = WorkflowApprovalOutput(
        approval_id=approval_id(state["run_id"]), action_ids=[a.action_id for a in state.get("plan", [])]
    )
    # Pauses the run until POST /api/agent/runs/{id}/approval resumes it with the operator's decision.
    decision = WorkflowDecision.model_validate(interrupt(waiting.model_dump(mode="json")))
    out = waiting.model_copy(
        update={"decision": decision.decision, "note": decision.note, "decided_at": datetime.now(UTC)}
    )
    return {"decision": decision, "step_output": out}


def after_approval(state: WorkflowState) -> str:
    return "execute" if state["decision"].decision == "approve" else "complete"


def _context(session: AsyncSession, state: WorkflowState) -> ToolContext:
    return ToolContext(
        session=session,
        actor="agent",
        approval_id=approval_id(state["run_id"]),
        run_id=state["run_id"],
        sim_time=state["world"].sim_time,
    )


def halted_projects(result: ActionResult) -> list[str]:
    """Projects the database now shows halted after this action (read from its after-snapshot)."""
    if result.status not in ("executed", "unchanged"):
        return []
    return [
        key.split(":", 1)[1]
        for key, row in result.after.items()
        if key.startswith("project:") and row.get("status") == "halted"
    ]


def make_execute(registry: ToolRegistry, sessions: Sessions, on_project_halted: ProjectHalted | None) -> Node:
    async def execute(state: WorkflowState) -> WorkflowUpdate:
        plan = state.get("plan", [])
        results: list[ActionResult] = []
        for action in plan:
            async with sessions() as session:
                results.append(
                    await execute_action(registry.action(action.tool), action.input, _context(session, state))
                )
        if on_project_halted is not None:  # the map is drawn from the simulation: carry the DB halt into it
            for project_id in dict.fromkeys(p for r in results for p in halted_projects(r)):
                await on_project_halted(project_id)
        out = WorkflowExecutionOutput(
            results=[
                WorkflowActionResult(
                    action_id=a.action_id,
                    tool=a.tool,
                    status=r.status,
                    message=r.message,
                    affected_entities=[e.key for e in r.affected_entities],
                )
                for a, r in zip(plan, results, strict=True)
            ]
        )
        return {"results": results, "step_output": out}

    return execute


def _text(value: Any) -> str:
    return value if isinstance(value, str) else str(value)


def make_verify(registry: ToolRegistry, sessions: Sessions) -> Node:
    async def verify(state: WorkflowState) -> WorkflowUpdate:
        per_action: list[WorkflowActionVerification] = []
        for action, result in zip(state.get("plan", []), state.get("results", []), strict=True):
            if result.status not in ("executed", "unchanged"):
                continue
            tool = registry.action(action.tool)
            async with sessions() as session:
                outcome = await tool.verify(
                    tool.Input.model_validate(action.input), _context(session, state), result
                )
                await record_verification(session, result.action_id, outcome)
            per_action.append(
                WorkflowActionVerification(
                    action_id=action.action_id,
                    tool=action.tool,
                    status=outcome.status,
                    checks=[
                        WorkflowCheck(
                            name=c.name,
                            passed=c.passed,
                            expected=_text(c.expected),
                            observed=_text(c.observed),
                        )
                        for c in outcome.checks
                    ],
                )
            )
        passed = sum(v.status == "verified" for v in per_action)
        status = (
            "verified"
            if per_action and passed == len(per_action) == len(state.get("plan", []))
            else "failed"
            if passed == 0
            else "partially_verified"
        )
        out = WorkflowVerificationOutput(status=status, per_action=per_action)
        return {"step_output": out, "verification": out}

    return verify


def _fields(row: dict[str, Any]) -> dict[str, Any]:
    shown = {k: row[k] for k in SHOWN_FIELDS if row.get(k) not in (None, "")}
    return {
        k: (v.isoformat() if isinstance(v, datetime) else (v[:160] if isinstance(v, str) else v))
        for k, v in list(shown.items())[:MAX_FIELDS]
    }


def make_complete(sessions: Sessions) -> Node:
    async def complete(state: WorkflowState) -> WorkflowUpdate:
        if state["decision"].decision == "reject":
            return {"step_output": WorkflowCompletionOutput(outcome="rejected", entities=[])}
        refs: list[EntityRef] = list(
            dict.fromkeys(e for r in state.get("results", []) for e in r.affected_entities)
        )
        async with sessions() as session:
            rows = await snapshot(session, refs)
        entities = [
            WorkflowEntityState(
                kind=ref.kind,
                id=ref.id,
                name=str(rows[ref.key].get("name") or rows[ref.key].get("title") or ref.id),
                fields=_fields(rows[ref.key]),
            )
            for ref in refs
            if ref.key in rows
        ]
        verification = state.get("verification")
        ok = verification is not None and verification.status == "verified"
        out = WorkflowCompletionOutput(
            outcome="completed" if ok else "completed_with_failures", entities=entities
        )
        return {"step_output": out}

    return complete
