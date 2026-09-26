"""FastAPI dependencies: shared services live on ``app.state`` and are injected from here (HTTP and WS)."""

from typing import Annotated, cast

from fastapi import Depends
from starlette.requests import HTTPConnection

from gridline.config import Settings
from gridline.events.bus import EventBus
from gridline.rag.store import ChunkStore
from gridline.simulation.runner import SimulationRunner


def get_runner(connection: HTTPConnection) -> SimulationRunner:
    return cast(SimulationRunner, connection.app.state.runner)


def get_bus(connection: HTTPConnection) -> EventBus:
    return cast(EventBus, connection.app.state.bus)


def get_settings(connection: HTTPConnection) -> Settings:
    return cast(Settings, connection.app.state.settings)


def get_chunk_store(connection: HTTPConnection) -> ChunkStore:
    return cast(ChunkStore, connection.app.state.chunks)


RunnerDep = Annotated[SimulationRunner, Depends(get_runner)]
BusDep = Annotated[EventBus, Depends(get_bus)]
SettingsDep = Annotated[Settings, Depends(get_settings)]
ChunkStoreDep = Annotated[ChunkStore, Depends(get_chunk_store)]
