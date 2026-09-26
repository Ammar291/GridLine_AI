"""The incident graph (ARCHITECTURE section 8, live agent workflow MVP): eleven nodes, one per dashboard step.

``receive → observe → query_graph → retrieve → reason → assess → recommend → approval_gate`` then, on
approve, ``execute → verify → complete``; on reject, straight to ``complete``.
"""

from dataclasses import dataclass
from typing import Any

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from gridline.agents.nodes.act import (
    ProjectHalted,
    after_approval,
    approval_gate,
    make_complete,
    make_execute,
    make_verify,
)
from gridline.agents.nodes.assess import assess, make_reason
from gridline.agents.nodes.observe import observe
from gridline.agents.nodes.receive import make_query_graph, make_receive
from gridline.agents.nodes.recommend import make_recommend
from gridline.agents.nodes.retrieve import make_retrieve
from gridline.agents.state import WorkflowState
from gridline.agents.steps import NODES
from gridline.city.model import City
from gridline.kg.query import KnowledgeGraph
from gridline.llm.base import LLMProvider
from gridline.rag.retriever import Retriever
from gridline.tools.registry import ToolRegistry


@dataclass
class AgentDeps:
    city: City
    kg: KnowledgeGraph
    retriever: Retriever | None
    sessions: async_sessionmaker[AsyncSession]
    registry: ToolRegistry
    provider: LLMProvider | None  # None: the offline heuristic reasoner answers every LLM step
    on_project_halted: ProjectHalted | None = None


def build_workflow_graph(deps: AgentDeps, checkpointer: BaseCheckpointSaver[Any]) -> Any:
    # LangGraph's cache and store generics stay unknown under strict pyright, so the builder is untyped.
    builder: Any = StateGraph(WorkflowState)
    nodes: dict[str, Any] = {
        "receive": make_receive(deps.city),
        "observe": observe,
        "query_graph": make_query_graph(deps.kg),
        "retrieve": make_retrieve(deps.retriever),
        "reason": make_reason(deps.provider),
        "assess": assess,
        "recommend": make_recommend(deps.provider, deps.registry),
        "approval_gate": approval_gate,
        "execute": make_execute(deps.registry, deps.sessions, deps.on_project_halted),
        "verify": make_verify(deps.registry, deps.sessions),
        "complete": make_complete(deps.sessions),
    }
    assert tuple(nodes) == NODES
    for name, node in nodes.items():
        builder.add_node(name, node)
    builder.add_edge(START, "receive")
    for a, b in zip(NODES[:7], NODES[1:8], strict=True):  # receive … recommend → approval_gate
        builder.add_edge(a, b)
    builder.add_conditional_edges("approval_gate", after_approval, ["execute", "complete"])
    builder.add_edge("execute", "verify")
    builder.add_edge("verify", "complete")
    builder.add_edge("complete", END)
    return builder.compile(checkpointer=checkpointer)
