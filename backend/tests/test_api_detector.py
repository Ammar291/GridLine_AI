from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient

from gridline.city.model import City
from gridline.config import Settings
from gridline.main import create_app


@pytest.fixture
async def client(settings: Settings, city: City) -> AsyncIterator[AsyncClient]:
    app = create_app(settings, city=city)
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client,
    ):
        yield client


async def test_bands_are_the_index_thresholds(client: AsyncClient) -> None:
    response = await client.get("/api/detector/bands")
    assert response.status_code == 200
    edges = {"watch": 0.35, "warning": 0.55, "critical": 0.75}
    assert response.json() == {"landslide": edges, "flood": edges}
