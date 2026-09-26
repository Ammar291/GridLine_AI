"""The one retrieval entry point: ``retrieve(query, filters, top_k)`` -> evidence with citations (spec §8)."""

import asyncio

from gridline.rag.embedder import Embedder
from gridline.rag.models import EmbeddingModelMismatchError, RetrievalFilters, RetrievedChunk
from gridline.rag.store import ChunkStore


class Retriever:
    def __init__(self, store: ChunkStore, embedder: Embedder) -> None:
        self._store = store
        self._embedder = embedder

    async def retrieve(
        self,
        query: str,
        filters: RetrievalFilters | None = None,
        top_k: int = 8,
        min_similarity: float = 0.0,
    ) -> list[RetrievedChunk]:
        """Stored chunks most similar to ``query``, best first; ``[]`` when nothing qualifies."""
        if not query.strip():
            raise ValueError("query must not be blank")
        if top_k <= 0:
            raise ValueError("top_k must be positive")
        await self._ensure_same_embedding_model()
        vector = await asyncio.to_thread(self._embedder.embed_query, query)
        results = await self._store.search(vector, top_k=top_k, filters=filters)
        return [r for r in results if r.similarity >= min_similarity]

    async def _ensure_same_embedding_model(self) -> None:
        """Vectors from different embedders live in different spaces; comparing them would be nonsense."""
        indexed = await self._store.embedding_models()
        if indexed and indexed != {self._embedder.name}:
            raise EmbeddingModelMismatchError(
                f"corpus was indexed with {sorted(indexed)} but the live embedder is "
                f"'{self._embedder.name}'; re-run `uv run gridline-ingest` with the current provider"
            )
