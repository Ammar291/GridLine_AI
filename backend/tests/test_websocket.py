import time
from typing import Any

import pytest
from fastapi.testclient import TestClient
from starlette.testclient import WebSocketTestSession

from gridline.api.city_map import CityMap, build_city_map
from gridline.city.dataset import load_city_data
from gridline.city.model import City
from gridline.config import Settings
from gridline.main import create_app
from tests.conftest import DATA_DIR

ENVELOPE = {
    "event_id",
    "timestamp",
    "sim_time",
    "event_type",
    "source",
    "location",
    "severity",
    "payload",
    "incident_id",
}


@pytest.fixture(scope="module")
def city_map(city: City) -> CityMap:
    return build_city_map(load_city_data(DATA_DIR), city)


@pytest.fixture
def client(settings: Settings, city: City, city_map: CityMap) -> Any:
    with TestClient(create_app(settings, city=city, city_map=city_map)) as client:
        yield client


def next_of(ws: WebSocketTestSession, event_type: str, limit: int = 500) -> dict[str, Any]:
    for _ in range(limit):
        frame = ws.receive_json()
        if frame["event_type"] == event_type:
            return frame
    raise AssertionError(f"no {event_type} frame")


def test_first_frame_is_a_snapshot(client: TestClient) -> None:
    with client.websocket_connect("/ws") as ws:
        frame = ws.receive_json()
    assert set(frame) == ENVELOPE
    assert (frame["event_type"], frame["event_id"], frame["source"]) == (
        "sim.snapshot",
        "evt-snapshot",
        "simulation:engine",
    )
    assert frame["payload"]["status"]["scenario"] == "cascading_landslide_flood"
    assert frame["payload"]["status"]["state"] == "idle"
    assert frame["payload"]["world"]["zones"]["Z-HV"]["saturation"] == 0.5


def test_bus_events_are_forwarded_with_every_envelope_field(client: TestClient) -> None:
    with client.websocket_connect("/ws") as ws:
        ws.receive_json()
        client.post("/api/simulation/advance", json={"ticks": 1})
        rain = next_of(ws, "weather.observation")
        tick = next_of(ws, "sim.tick")
    for frame in (rain, tick):
        assert set(frame) == ENVELOPE
    assert rain["source"].startswith("sensor:") and rain["location"] is not None
    assert tick["payload"]["tick"] == 1 and tick["sim_time"] == "2026-07-14T06:05:00Z"


def test_types_filter(client: TestClient) -> None:
    with client.websocket_connect("/ws?types=environment.soil,sim.tick") as ws:
        ws.receive_json()
        client.post("/api/simulation/advance", json={"ticks": 1})
        seen = {ws.receive_json()["event_type"] for _ in range(6)}
    assert seen <= {"environment.soil", "sim.tick", "sim.heartbeat"}
    assert {"environment.soil", "sim.tick"} <= seen


@pytest.mark.parametrize("query", ["?types=", "?types=,,", "?types= , "])
def test_empty_types_means_no_filter(client: TestClient, query: str) -> None:
    with client.websocket_connect(f"/ws{query}") as ws:
        assert ws.receive_json()["event_type"] == "sim.snapshot"
        client.post("/api/simulation/advance", json={"ticks": 1})
        assert next_of(ws, "sim.tick")["payload"]["tick"] == 1


def test_unmatched_prefix_yields_only_snapshot_and_heartbeats(client: TestClient) -> None:
    with client.websocket_connect("/ws?types=nope.") as ws:
        assert ws.receive_json()["event_type"] == "sim.snapshot"
        client.post("/api/simulation/advance", json={"ticks": 2})
        frames = [ws.receive_json() for _ in range(3)]
    assert {f["event_type"] for f in frames} == {"sim.heartbeat"}
    assert frames[0]["event_id"] == "evt-heartbeat" and frames[0]["payload"]["tick"] == 2


def test_heartbeat_when_idle(client: TestClient) -> None:
    with client.websocket_connect("/ws") as ws:
        ws.receive_json()
        heartbeat = ws.receive_json()
    assert heartbeat["event_type"] == "sim.heartbeat"
    assert set(heartbeat) == ENVELOPE
    assert heartbeat["payload"] == {"tick": 0, "sim_time": "2026-07-14T06:00:00Z"}


def test_disconnect_unsubscribes(client: TestClient) -> None:
    bus = client.app.state.bus  # type: ignore[attr-defined]
    with client.websocket_connect("/ws") as ws:
        ws.receive_json()
        assert bus.subscriber_count == 1
    deadline = time.monotonic() + 2
    while bus.subscriber_count and time.monotonic() < deadline:
        time.sleep(0.01)
    assert bus.subscriber_count == 0
