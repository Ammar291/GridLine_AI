from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient

from gridline.city.model import City
from gridline.config import Settings
from gridline.main import create_app


@pytest.fixture
async def client(settings: Settings, city: City) -> AsyncIterator[AsyncClient]:
    settings.live_forecast_base_url = (
        "http://127.0.0.1:9/v1/forecast"  # LIVE mode must never touch the network
    )
    app = create_app(settings, city=city)
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client,
    ):
        yield client


async def test_trigger_returns_its_events_and_advances_one_hour(client: AsyncClient) -> None:
    response = await client.post("/api/simulation/trigger", json={"trigger": "flash_flood"})
    assert response.status_code == 200, response.text
    events = response.json()
    assert events[0]["event_type"] == "scenario.trigger" and events[0]["payload"]["label"] == "Flash Flood"
    status = (await client.get("/api/simulation/status")).json()
    assert (status["tick"], status["state"]) == (12, "idle")


async def test_unknown_trigger_is_rejected(client: AsyncClient) -> None:
    response = await client.post("/api/simulation/trigger", json={"trigger": "meteor"})
    assert response.status_code == 422


async def test_trigger_is_refused_in_live_mode(client: AsyncClient) -> None:
    await client.post("/api/source", json={"mode": "live"})
    response = await client.post("/api/simulation/trigger", json={"trigger": "heavy_rain"})
    assert response.status_code == 409 and "DEMO" in response.json()["detail"]


async def test_the_city_lists_the_triggers_in_button_order(client: AsyncClient) -> None:
    city = (await client.get("/api/city")).json()
    assert [(t["id"], t["label"]) for t in city["triggers"]] == [
        ("heavy_rain", "Heavy Rain"),
        ("landslide", "Landslide"),
        ("drainage_block", "Drainage Block"),
        ("flash_flood", "Flash Flood"),
        ("industrial_fire", "Industrial Fire"),
        ("cascading_disaster", "Cascading Disaster"),
    ]
