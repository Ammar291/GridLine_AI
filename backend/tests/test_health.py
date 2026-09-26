from fastapi.testclient import TestClient

from gridline.city.model import City
from gridline.config import Settings
from gridline.main import create_app


def test_health(settings: Settings, city: City) -> None:
    with TestClient(create_app(settings, city=city)) as client:
        response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": "0.1.0"}
