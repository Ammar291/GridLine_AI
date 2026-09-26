import asyncio
from collections.abc import AsyncIterator
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from gridline.city.model import City
from gridline.config import Settings
from gridline.main import create_app


@pytest.fixture
async def client(settings: Settings, city: City) -> AsyncIterator[AsyncClient]:
    app = create_app(settings, city=city)
    transport = ASGITransport(app=app)
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=transport, base_url="http://test") as client,
    ):
        yield client


async def post(client: AsyncClient, path: str, body: dict[str, Any] | None = None, expect: int = 200) -> Any:
    response = await client.post(f"/api/simulation/{path}", json=body)
    assert response.status_code == expect, response.text
    return response.json()


async def test_health(client: AsyncClient) -> None:
    response = await client.get("/api/health")
    assert response.json() == {"status": "ok", "version": "0.1.0"}


async def test_status_scenarios_and_snapshot(client: AsyncClient) -> None:
    status = (await client.get("/api/simulation/status")).json()
    assert status["state"] == "idle" and status["running"] is False
    assert (status["scenario"], status["seed"], status["tick"]) == ("cascading_landslide_flood", 42, 0)
    assert status["stage"]["name"] == "construction_and_rain"
    assert (status["minutes_per_tick"], status["tick_seconds"]) == (5, 0.01)
    assert status["sim_time"] == "2026-07-14T06:00:00Z"
    scenarios = (await client.get("/api/simulation/scenarios")).json()
    assert [s["name"] for s in scenarios] == [
        "normal_city",
        "hillside_landslide",
        "flash_flood",
        "cascading_landslide_flood",
    ]
    assert scenarios[3]["duration_ticks"] == 300 and len(scenarios[3]["stages"]) == 6
    snapshot = (await client.get("/api/simulation/snapshot")).json()
    assert snapshot["tick"] == 0
    assert snapshot["channels"]["D-7"]["capacity_m3s"] == 27
    assert snapshot["projects"]["PR-HT2"]["excavation_depth_m"] == 2.5


async def test_select_scenario_and_advance(client: AsyncClient) -> None:
    status = await post(client, "scenario", {"scenario": "flash_flood", "seed": 7})
    assert (status["scenario"], status["seed"], status["state"], status["tick"]) == (
        "flash_flood",
        7,
        "idle",
        0,
    )
    await post(client, "scenario", {"scenario": "volcano"}, expect=422)
    advanced = await post(client, "advance", {"ticks": 3})
    assert advanced["status"]["tick"] == 3 and advanced["events_emitted"] > 3
    assert (await post(client, "advance"))["status"]["tick"] == 4  # body optional, one tick
    await post(client, "advance", {"ticks": 0}, expect=422)
    await post(client, "advance", {"ticks": 1001}, expect=422)


async def test_runner_transitions_and_conflicts(client: AsyncClient) -> None:
    await post(client, "resume", expect=409)
    await post(client, "pause", expect=409)
    started = await post(client, "start", {"scenario": "normal_city", "speed": 4, "seed": 3})
    assert (started["state"], started["scenario"], started["speed"], started["seed"]) == (
        "running",
        "normal_city",
        4.0,
        3,
    )
    conflict = await post(client, "start", expect=409)
    assert "already running" in conflict["detail"]
    await post(client, "advance", {"ticks": 1}, expect=409)
    assert (await post(client, "pause"))["state"] == "paused"
    await post(client, "start", expect=409)
    assert (await post(client, "resume"))["state"] == "running"
    await asyncio.sleep(0.05)
    reset = await post(client, "reset")
    assert (reset["state"], reset["tick"], reset["scenario"], reset["seed"]) == ("idle", 0, "normal_city", 3)
    await asyncio.sleep(0.05)
    assert (await client.get("/api/simulation/status")).json()["tick"] == 0


async def test_select_while_running_stops_ticking(client: AsyncClient) -> None:
    await post(client, "start")
    await asyncio.sleep(0.05)
    status = await post(client, "scenario", {"scenario": "hillside_landslide"})
    assert (status["state"], status["tick"], status["seed"]) == ("idle", 0, 42)
    await asyncio.sleep(0.05)
    assert (await client.get("/api/simulation/status")).json()["tick"] == 0


async def test_speed(client: AsyncClient) -> None:
    assert (await post(client, "speed", {"speed": 2}))["speed"] == 2.0
    await post(client, "speed", {"speed": 0.1}, expect=422)
    await post(client, "speed", {"speed": 11}, expect=422)
    await post(client, "start", {"speed": 20}, expect=422)


async def test_inject(client: AsyncClient) -> None:
    events = await post(
        client,
        "inject",
        {
            "event_type": "infrastructure.road",
            "location": "Z-LK",
            "payload": {"road_id": "RD-02", "status": "blocked", "reason": "tree fall"},
        },
    )
    assert len(events) == 1
    event = events[0]
    assert set(event) == {
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
    assert (event["location"], event["source"], event["severity"]) == ("Z-RS", "operator:api", "high")
    cascade = await post(
        client,
        "inject",
        {
            "event_type": "infrastructure.failure",
            "severity": "high",
            "source": "operator:drill",
            "payload": {
                "asset_id": "SL-HV-1",
                "asset_kind": "slope",
                "failure_kind": "landslide",
                "description": "d",
            },
        },
    )
    assert [e["source"] for e in cascade] == ["operator:drill"] + ["simulation:engine"] * 4
    assert cascade[0]["severity"] == "high"
    snapshot = (await client.get("/api/simulation/snapshot")).json()
    assert (
        snapshot["roads"]["RD-02"]["status"] == "blocked"
        and snapshot["channels"]["D-7"]["blocked_fraction"] == 0.7
    )


@pytest.mark.parametrize(
    "body",
    [
        {"event_type": "weather.observation", "payload": {"station_id": "RG-02"}},  # not injectable
        {"event_type": "sim.tick", "payload": {}},  # not injectable
        {
            "event_type": "infrastructure.road",
            "payload": {"road_id": "RD-99", "status": "closed"},
        },  # unknown id
        {
            "event_type": "infrastructure.road",
            "payload": {"road_id": "RD-01", "status": "flooded"},
        },  # bad payload
        {
            "event_type": "infrastructure.road",
            "payload": {"road_id": "RD-01", "status": "closed", "extra": 1},
        },
        {
            "event_type": "emergency.hospital",
            "payload": {"hospital_id": "H-2", "beds_occupied": 99, "er_status": "busy"},
        },  # more beds than exist
        {"event_type": "volcano.eruption", "payload": {}},  # unknown event type
        {
            "event_type": "weather.forecast",
            "location": "Z-XX",
            "payload": {
                "issued_sim_time": "2026-07-14T06:00:00Z",
                "horizon_h": 6,
                "expected_total_mm": 1,
                "peak_intensity_mm_h": 1,
                "confidence": 0.5,
                "summary": "s",
            },
        },  # unknown zone
    ],
)
async def test_inject_rejections(client: AsyncClient, body: dict[str, Any]) -> None:
    rejected = await post(client, "inject", body, expect=422)
    assert rejected["detail"]
