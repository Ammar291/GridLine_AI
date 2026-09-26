"""FastAPI dependencies: shared services live on ``app.state`` and are injected from here (HTTP and WS)."""

from typing import Annotated, cast

from fastapi import Depends
from starlette.requests import HTTPConnection

from gridline.agents.runner import AgentRunner
from gridline.config import Settings
from gridline.errors import InvalidTransition
from gridline.events.bus import EventBus
from gridline.rag.store import ChunkStore
from gridline.simulation.runner import SimulationRunner
from gridline.sources.manager import DataSourceManager


def get_runner(connection: HTTPConnection) -> SimulationRunner:
    return cast(SimulationRunner, connection.app.state.runner)


def get_sources(connection: HTTPConnection) -> DataSourceManager:
    return cast(DataSourceManager, connection.app.state.sources)


def get_demo_runner(connection: HTTPConnection) -> SimulationRunner:
    """The runner, for routes that advance the simulation: refused while LIVE mode is feeding the bus."""
    if get_sources(connection).mode != "demo":
        raise InvalidTransition("the simulation only runs in DEMO mode; switch to DEMO — Nandipur first")
    return get_runner(connection)


def get_bus(connection: HTTPConnection) -> EventBus:
    return cast(EventBus, connection.app.state.bus)


def get_settings(connection: HTTPConnection) -> Settings:
    return cast(Settings, connection.app.state.settings)


def get_agent(connection: HTTPConnection) -> AgentRunner:
    return cast(AgentRunner, connection.app.state.agent)


def get_chunk_store(connection: HTTPConnection) -> ChunkStore:
    return cast(ChunkStore, connection.app.state.chunks)


RunnerDep = Annotated[SimulationRunner, Depends(get_runner)]
DemoRunnerDep = Annotated[SimulationRunner, Depends(get_demo_runner)]
SourcesDep = Annotated[DataSourceManager, Depends(get_sources)]
BusDep = Annotated[EventBus, Depends(get_bus)]
SettingsDep = Annotated[Settings, Depends(get_settings)]
ChunkStoreDep = Annotated[ChunkStore, Depends(get_chunk_store)]
AgentDep = Annotated[AgentRunner, Depends(get_agent)]
