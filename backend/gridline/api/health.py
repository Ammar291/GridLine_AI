"""Liveness."""

from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

from gridline import __version__

router = APIRouter(tags=["health"])


class Health(BaseModel):
    status: Literal["ok"]
    version: str


@router.get("/health", response_model=Health)
async def health() -> Health:
    return Health(status="ok", version=__version__)
