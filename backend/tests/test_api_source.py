from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient

from gridline.city.model import City
from gridline.config import Settings
from gridline.main import create_app


@pytest.fixture
async def client(settings: Settings, city: City) -> AsyncIterator[AsyncClient]:
    # Live polling is pointed at an unroutable URL: these tests must never touch the network.
    settings.live_forecast_base_url = "http://127.0.0.1:9/v1/forecast"
    app = create_app(settings, city=city)
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client,
    ):
        yield client


async def test_default_mode_is_demo(client: AsyncClient) -> None:
    body = (await client.get("/api/source")).json()
    assert body["mode"] == "demo" and body["label"] == "DEMO — Nandipur" and body["city"] == "Nandipur"


async def test_switch_to_live_and_back(client: AsyncClient) -> None:
    live = await client.post("/api/source", json={"mode": "live"})
    assert live.status_code == 200, live.text
    assert live.json()["label"] == "LIVE — Kalyan-Dombivli"
    assert live.json()["provider"] == "Open-Meteo"
    assert (await client.get("/api/source")).json()["mode"] == "live"
    demo = await client.post("/api/source", json={"mode": "demo"})
    assert demo.json()["mode"] == "demo"


async def test_simulation_cannot_start_in_live_mode(client: AsyncClient) -> None:
    await client.post("/api/source", json={"mode": "live"})
    response = await client.post("/api/simulation/start", json={})
    assert response.status_code == 409
    assert "DEMO" in response.json()["detail"]


async def test_unknown_mode_is_rejected(client: AsyncClient) -> None:
    response = await client.post("/api/source", json={"mode": "staging"})
    assert response.status_code == 422
