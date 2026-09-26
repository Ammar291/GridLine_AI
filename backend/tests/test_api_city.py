"""GET /api/city, the city in the WebSocket snapshot, inject presets, and the contract in /openapi.json."""

from typing import Any

import pytest
from fastapi.testclient import TestClient

from gridline.api.city_map import CityMap, build_city_map
from gridline.api.event_models import Event, SimSnapshotEvent
from gridline.api.injections import INJECTION_PRESETS
from gridline.city.dataset import load_city_data
from gridline.city.model import City
from gridline.config import Settings
from gridline.events.types import EventType
from gridline.main import create_app
from gridline.simulation.engine import SimulationEngine
from gridline.simulation.scenarios import SCENARIOS
from tests.conftest import DATA_DIR


@pytest.fixture(scope="module")
def city_map(city: City) -> CityMap:
    return build_city_map(load_city_data(DATA_DIR), city)


@pytest.fixture
def client(settings: Settings, city: City, city_map: CityMap) -> Any:
    with TestClient(create_app(settings, city=city, city_map=city_map)) as client:
        yield client


def test_get_city_returns_the_built_map(client: TestClient, city_map: CityMap) -> None:
    response = client.get("/api/city")
    assert response.status_code == 200
    assert response.json() == city_map.model_dump(mode="json")


def test_city_is_built_on_first_use_when_not_given(settings: Settings, city: City, city_map: CityMap) -> None:
    with TestClient(create_app(settings, city=city)) as client:
        assert client.get("/api/city").json() == city_map.model_dump(mode="json")


def test_snapshot_frame_carries_status_world_and_city(client: TestClient, city_map: CityMap) -> None:
    with client.websocket_connect("/ws") as ws:
        frame = ws.receive_json()
    snapshot = SimSnapshotEvent.model_validate(frame)
    assert snapshot.payload.city == city_map
    assert snapshot.payload.world.tick == 0 and snapshot.payload.status.state == "idle"
    assert Event.model_validate(frame).root.event_type == EventType.SIM_SNAPSHOT


@pytest.mark.parametrize("preset", INJECTION_PRESETS, ids=lambda p: p.id)
def test_every_preset_injects_cleanly_in_every_scenario(city: City, preset: Any) -> None:
    for scenario in SCENARIOS:
        engine = SimulationEngine(city)
        engine.reset(scenario, 42)
        request = preset.request
        events = engine.inject(request.event_type, request.payload, location=request.location)
        assert events[0].event_type == request.event_type


def test_inject_answers_typed_events(client: TestClient) -> None:
    preset = next(p for p in INJECTION_PRESETS if p.id == "slope_failure")
    response = client.post("/api/simulation/inject", json=preset.request.model_dump(mode="json"))
    assert response.status_code == 200, response.text
    kinds = [Event.model_validate(e).root.event_type for e in response.json()]
    assert kinds[0] == EventType.INFRASTRUCTURE_FAILURE
    assert EventType.INFRASTRUCTURE_DRAINAGE_OBSTRUCTION in kinds


def test_openapi_exports_the_city_and_the_typed_event_union(client: TestClient) -> None:
    schema = client.get("/openapi.json").json()
    assert {"/api/city", "/api/chunks/{chunk_id}"} <= set(schema["paths"])
    components = schema["components"]["schemas"]
    assert {"CityMap", "WorldSnapshot", "SimSnapshotEvent", "InjectRequest", "StoredChunk"} <= set(components)
    mapping = components["Event"]["discriminator"]["mapping"]
    assert set(mapping) == {t.value for t in EventType}
    assert mapping["sim.tick"] == "#/components/schemas/SimTickEvent"
