"""``GET /api/city`` and the ``CityMap`` dependency shared with the WebSocket snapshot."""

from typing import Annotated, cast

from fastapi import APIRouter, Depends
from starlette.requests import HTTPConnection

from gridline.api.city_map import CityMap, build_city_map
from gridline.city.dataset import load_city_data
from gridline.city.model import City
from gridline.config import Settings

router = APIRouter(tags=["city"])


def get_city_map(connection: HTTPConnection) -> CityMap:
    """The app's city map; built once on first use when the app was created with a prebuilt ``City``."""
    state = connection.app.state
    if state.city_map is None:
        settings = cast(Settings, state.settings)
        state.city_map = build_city_map(load_city_data(settings.resolved_data_dir()), cast(City, state.city))
    return cast(CityMap, state.city_map)


CityMapDep = Annotated[CityMap, Depends(get_city_map)]


@router.get("/city")
async def get_city(city_map: CityMapDep) -> CityMap:
    """Static geometry and attributes of every simulated asset, the scenarios and the inject presets."""
    return city_map
