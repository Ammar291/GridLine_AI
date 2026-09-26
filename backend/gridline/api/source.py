"""``/api/source``: which data source feeds the bus (LIVE or DEMO), switchable without a restart."""

from fastapi import APIRouter
from pydantic import BaseModel

from gridline.api.deps import SourcesDep
from gridline.events.payloads import DataMode, SourceStatus

router = APIRouter(prefix="/source", tags=["source"])


class SourceSwitch(BaseModel):
    mode: DataMode


@router.get("")
async def get_source(sources: SourcesDep) -> SourceStatus:
    return sources.status()


@router.post("")
async def switch_source(body: SourceSwitch, sources: SourcesDep) -> SourceStatus:
    """Stop the current source and start ``mode``'s; a ``source.status`` event announces the change."""
    return await sources.switch(body.mode)
