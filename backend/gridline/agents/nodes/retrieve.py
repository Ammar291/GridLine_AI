"""``retrieve``: targeted RAG queries for the trigger's hazard and zone (ARCHITECTURE section 7.3)."""

# pyright: reportTypedDictNotRequiredAccess=false
# (each node reads keys its predecessors set; the graph's edges guarantee they ran)

from gridline.agents.state import Node, ThreatTrigger, WorkflowState, WorkflowUpdate
from gridline.agents.steps import WorkflowChunk, WorkflowEvidenceOutput
from gridline.rag.models import RetrievalFilters, RetrievedChunk
from gridline.rag.retriever import Retriever

PER_QUERY = 4
MAX_CHUNKS = 8


def queries(trigger: ThreatTrigger) -> list[str]:
    return [
        f"{trigger.hazard} warning thresholds and halt rules",
        f"past {trigger.hazard} incidents, causes and lessons",
        f"construction and infrastructure changes raising {trigger.hazard} risk",
    ]


async def retrieve_evidence(retriever: Retriever | None, trigger: ThreatTrigger) -> list[RetrievedChunk]:
    """Best chunks across the queries, deduplicated; ``[]`` without a retriever (never invented)."""
    if retriever is None:
        return []
    filters = RetrievalFilters(
        hazards=[trigger.hazard], zone_ids=[trigger.zone_id] if trigger.zone_id else None
    )
    best: dict[str, RetrievedChunk] = {}
    for query in queries(trigger):
        for chunk in await retriever.retrieve(query, filters, top_k=PER_QUERY):
            if chunk.chunk_id not in best or chunk.similarity > best[chunk.chunk_id].similarity:
                best[chunk.chunk_id] = chunk
    return sorted(best.values(), key=lambda c: -c.similarity)[:MAX_CHUNKS]


def make_retrieve(retriever: Retriever | None) -> Node:
    async def retrieve(state: WorkflowState) -> WorkflowUpdate:
        trigger = state["trigger"]
        chunks = await retrieve_evidence(retriever, trigger)
        out = WorkflowEvidenceOutput(
            queries=queries(trigger),
            chunks=[
                WorkflowChunk(
                    chunk_id=c.chunk_id,
                    document_id=c.document_id,
                    document_title=c.document_title,
                    section=c.section,
                    kind=str(c.kind),
                    similarity=round(c.similarity, 3),
                )
                for c in chunks
            ],
        )
        return {"retrieved": chunks, "step_output": out}

    return retrieve
