"""``GET /api/chunks/{chunk_id}``: the corpus section behind a citation id (``dmp-2024#s4.2``)."""

from fastapi import APIRouter, HTTPException
from sqlalchemy.exc import DBAPIError

from gridline.api.deps import ChunkStoreDep
from gridline.rag.models import StoredChunk

router = APIRouter(tags=["sources"])


@router.get("/chunks/{chunk_id}", responses={404: {"description": "Unknown chunk"}, 503: {}})
async def get_chunk(chunk_id: str, chunks: ChunkStoreDep) -> StoredChunk:
    try:
        chunk = await chunks.get_chunk(chunk_id)
    except DBAPIError as exc:
        raise HTTPException(
            503, "The knowledge base is not reachable; seed and ingest the database."
        ) from exc
    if chunk is None:
        raise HTTPException(404, f"No chunk {chunk_id!r} in the knowledge base.")
    return chunk
