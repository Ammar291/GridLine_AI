"""``recommend``: the model picks from valid candidate tool calls and justifies each (spec D6)."""

# pyright: reportTypedDictNotRequiredAccess=false
# (each node reads keys its predecessors set; the graph's edges guarantee they ran)

import logging

from pydantic import ValidationError

from gridline.agents.candidates import build_candidates
from gridline.agents.nodes.llm_call import ask
from gridline.agents.reasoner import HeuristicReasoner, evidence_lines
from gridline.agents.state import Candidate, Node, PlanChoice, WorkflowState, WorkflowUpdate
from gridline.agents.steps import WorkflowAction, WorkflowPlanOutput
from gridline.llm.base import LLMProvider
from gridline.tools.registry import ToolRegistry

log = logging.getLogger(__name__)
TEXT_LIMIT = 500


def candidate_line(c: Candidate) -> str:
    return f"- {c.candidate_id}: {c.label} (because {c.why}) [{', '.join(c.citation_ids)}]"


def to_actions(
    choice: PlanChoice, candidates: list[Candidate], registry: ToolRegistry, run_id: str, allowed: set[str]
) -> list[WorkflowAction]:
    """The chosen candidates as validated tool calls, in the model's order, each at most once."""
    by_id = {c.candidate_id: c for c in candidates}
    actions: list[WorkflowAction] = []
    for pick in choice.actions:
        candidate = by_id.get(pick.candidate_id)
        if candidate is None or any(a.candidate_id == candidate.candidate_id for a in actions):
            continue
        text = " ".join(pick.rationale.split())[:TEXT_LIMIT] or candidate.why
        raw = {
            **candidate.input,
            candidate.text_field: text,
            "idempotency_key": f"{run_id}:{candidate.candidate_id}",
        }
        tool = registry.action(candidate.tool)
        try:
            inp = tool.Input.model_validate(raw)
        except ValidationError as exc:
            log.warning("dropping candidate %s: %s", candidate.candidate_id, exc)
            continue
        cites = [c for c in pick.citation_ids if c in allowed] or candidate.citation_ids
        actions.append(
            WorkflowAction(
                action_id=f"{run_id}-a{len(actions) + 1}",
                candidate_id=candidate.candidate_id,
                tool=candidate.tool,
                input=inp.model_dump(mode="json", exclude_none=True),
                label=candidate.label,
                rationale=text,
                citation_ids=list(dict.fromkeys(cites)),
                requires_approval=tool.requires_approval(inp),
            )
        )
    return actions


def make_recommend(provider: LLMProvider | None, registry: ToolRegistry) -> Node:
    async def recommend(state: WorkflowState) -> WorkflowUpdate:
        context, reasoning, assessment = state["context"], state["reasoning"], state["assessment"]
        candidates = build_candidates(context, state["world"])
        allowed = context.citation_ids()
        choice, meta = await ask(
            provider,
            prompt="recommend",
            fields={
                "hazard": assessment.hazard,
                "band": assessment.band,
                "confidence": assessment.confidence,
                "summary": reasoning.summary,
                "candidates": "\n".join(candidate_line(c) for c in candidates),
                "evidence": "\n".join(evidence_lines(context)),
            },
            output=PlanChoice,
            enums={
                "candidate_id": [c.candidate_id for c in candidates],
                "citation_ids": sorted(allowed),
            },
            fallback=lambda: HeuristicReasoner().recommend(candidates),
        )
        plan = to_actions(choice, candidates, registry, state["run_id"], allowed) if candidates else []
        out = WorkflowPlanOutput(
            provider=meta.provider,
            model=meta.model,
            fallback_reason=meta.fallback_reason,
            duration_ms=meta.duration_ms,
            candidate_count=len(candidates),
            actions=plan,
        )
        return {"plan": plan, "step_output": out}

    return recommend
