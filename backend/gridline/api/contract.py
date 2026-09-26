"""What the frontend consumes from the backend at build time: the OpenAPI schema and the mock-mode fixtures.

``backend/scripts/export_contract.py`` writes these files into ``frontend/``; the frontend generates its types
from the schema (``npm run gen:api``) and its mock mode serves the same city the backend builds. A test keeps
the committed files equal to what this module renders, so a backend change cannot silently skew them.
"""

import json
from pathlib import Path
from typing import Any

from gridline.api.city_map import build_city_map
from gridline.city.dataset import load_city_data
from gridline.city.nandipur import city_from_data
from gridline.main import create_app
from gridline.simulation.engine import SimulationEngine

MOCK_SCENARIO = "hillside_landslide"  # the scenario the frontend's mock replay scripts
MOCK_SEED = 42


def _json(value: Any, indent: int) -> str:
    return json.dumps(value, indent=indent, ensure_ascii=False) + "\n"


def contract_files(data_dir: Path) -> dict[str, str]:
    """Paths relative to ``frontend/`` -> file contents."""
    data = load_city_data(data_dir)
    city = city_from_data(data)
    city_map = build_city_map(data, city)
    engine = SimulationEngine(city)
    engine.reset(MOCK_SCENARIO, MOCK_SEED)
    openapi = create_app(city=city, city_map=city_map).openapi()  # the schema does not depend on settings
    return {
        "openapi.json": _json(openapi, 2),
        "src/mock/fixtures/nandipur.city.json": _json(city_map.model_dump(mode="json"), 1),
        "src/mock/fixtures/nandipur.world.json": _json(engine.snapshot().model_dump(mode="json"), 1),
    }
