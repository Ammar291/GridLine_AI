"""FastAPI app factory. Shared services hang off ``app.state`` and are injected via ``gridline.api.deps``.

``uv run uvicorn gridline.main:app`` serves it. The lifespan builds city -> engine -> bus -> runner, loads the
default scenario and seed, optionally autostarts, and shuts the runner down on exit. No database is needed.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from gridline import __version__
from gridline.api.errors import install_error_handlers
from gridline.api.health import router as health_router
from gridline.api.simulation import router as simulation_router
from gridline.city.model import City
from gridline.city.nandipur import build_nandipur
from gridline.config import Settings
from gridline.events.bus import EventBus
from gridline.events.websocket import router as websocket_router
from gridline.simulation.engine import SimulationEngine
from gridline.simulation.runner import SimulationRunner


def create_app(settings: Settings | None = None, *, city: City | None = None) -> FastAPI:
    """``city`` lets tests reuse one loaded Nandipur; by default it is built from ``settings.data_dir``."""
    resolved = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
        nandipur = city or build_nandipur(resolved.resolved_data_dir())
        engine = SimulationEngine(nandipur, minutes_per_tick=resolved.sim_minutes_per_tick)
        bus = EventBus(maxsize=resolved.event_queue_size)
        runner = SimulationRunner(engine, bus, tick_seconds=resolved.sim_tick_seconds)
        await runner.select_scenario(resolved.sim_default_scenario, resolved.sim_default_seed)
        if resolved.sim_autostart:
            await runner.start()
        app.state.settings = resolved
        app.state.city = nandipur
        app.state.bus = bus
        app.state.runner = runner
        try:
            yield
        finally:
            await runner.shutdown()

    app = FastAPI(title="GridLine AI", version=__version__, lifespan=lifespan)
    install_error_handlers(app)
    app.include_router(health_router, prefix="/api")
    app.include_router(simulation_router, prefix="/api")
    app.include_router(websocket_router)
    return app


app = create_app()
