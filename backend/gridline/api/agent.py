"""``/api/agent``: the operator's decision on a live agent run waiting at its approval gate."""

from fastapi import APIRouter, HTTPException, status

from gridline.agents.runner import UnknownRun
from gridline.agents.steps import WorkflowDecision, WorkflowRun
from gridline.api.deps import AgentDep

router = APIRouter(prefix="/agent", tags=["agent"])


@router.post(
    "/runs/{run_id}/approval",
    status_code=status.HTTP_202_ACCEPTED,
    operation_id="decideRunApproval",
    responses={
        404: {"description": "No such run"},
        409: {"description": "The run is not waiting for approval"},
    },
)
async def decide_run_approval(run_id: str, body: WorkflowDecision, agent: AgentDep) -> WorkflowRun:
    """Record the decision and resume the graph; progress arrives as ``agent.step`` events."""
    try:
        return await agent.decide(run_id, body)
    except UnknownRun as exc:
        raise HTTPException(status_code=404, detail=f"unknown run {run_id}") from exc
