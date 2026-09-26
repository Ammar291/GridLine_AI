"""FastAPI app factory. Shared services hang off ``app.state`` and are injected via ``gridline.api.deps``.

``uv run uvicorn gridline.main:app`` serves it. The lifespan loads the city data once, builds city -> engine
-> bus -> runner and the dashboard's city map, loads the default scenario and seed, optionally autostarts,
and shuts the runner down on exit. The database engine connects lazily: only the knowledge-base routes use
it, so the simulation runs without Postgres.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from gridline import __version__
from gridline.api.chunks import router as chunks_router
from gridline.api.city import router as city_router
from gridline.api.city_map import CityMap, build_city_map
from gridline.api.errors import install_error_handlers
from gridline.api.health import router as health_router
from gridline.api.simulation import router as simulation_router
from gridline.city.dataset import load_city_data
from gridline.city.model import City
from gridline.city.nandipur import city_from_data
from gridline.config import Settings
from gridline.db.engine import create_engine, session_factory
from gridline.events.bus import EventBus
from gridline.events.websocket import router as websocket_router
from gridline.rag.store import ChunkStore
from gridline.simulation.engine import SimulationEngine
from gridline.simulation.runner import SimulationRunner


def create_app(
    settings: Settings | None = None, *, city: City | None = None, city_map: CityMap | None = None
) -> FastAPI:
    """``city`` and ``city_map`` let tests reuse one loaded Nandipur; by default both come from the data.

    Given only ``city``, the map is built on first use (``gridline.api.city.get_city_map``).
    """
    resolved = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
        nandipur, dashboard_map = city, city_map
        if nandipur is None:
            data = load_city_data(resolved.resolved_data_dir())
            nandipur = city_from_data(data)
            dashboard_map = dashboard_map or build_city_map(data, nandipur)
        engine = SimulationEngine(nandipur, minutes_per_tick=resolved.sim_minutes_per_tick)
        bus = EventBus(maxsize=resolved.event_queue_size)
        runner = SimulationRunner(engine, bus, tick_seconds=resolved.sim_tick_seconds)
        await runner.select_scenario(resolved.sim_default_scenario, resolved.sim_default_seed)
        if resolved.sim_autostart:
            await runner.start()
        database = create_engine(resolved.database_url)
        app.state.settings = resolved
        app.state.city = nandipur
        app.state.city_map = dashboard_map
        app.state.bus = bus
        app.state.runner = runner
        app.state.chunks = ChunkStore(session_factory(database))
        try:
            yield
        finally:
            await runner.shutdown()
            await database.dispose()

    app = FastAPI(title="GridLine AI", version=__version__, lifespan=lifespan)
    install_error_handlers(app)
    app.include_router(health_router, prefix="/api")
    app.include_router(city_router, prefix="/api")
    app.include_router(chunks_router, prefix="/api")
    app.include_router(simulation_router, prefix="/api")
    app.include_router(websocket_router)
    return app


app = create_app()
