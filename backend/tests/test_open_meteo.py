import copy
import json
from pathlib import Path
from typing import Any

import pytest

from gridline.events.payloads import WeatherForecast, WeatherObservation
from gridline.events.types import EventType, Severity
from gridline.simulation.severity import severity_for
from gridline.sources.open_meteo import (
    KALYAN_DOMBIVLI,
    KDMC_THRESHOLDS,
    STATION_ID,
    forecast_url,
    parse_forecast,
)

FIXTURE = Path(__file__).parent / "fixtures" / "open_meteo" / "kalyan_dombivli.json"


@pytest.fixture
def response() -> dict[str, Any]:
    """A real Open-Meteo response for Kalyan-Dombivli, captured 2026-09-26T10:30Z."""
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_url_targets_kalyan_dombivli() -> None:
    url = forecast_url(KALYAN_DOMBIVLI)
    assert url.startswith("https://api.open-meteo.com/v1/forecast?")
    assert "latitude=19.235" in url and "longitude=73.13" in url
    assert "past_hours=24" in url and "forecast_hours=24" in url and "timezone=UTC" in url


def test_parse_observation_uses_last_complete_hour_and_24h_sum(response: dict[str, Any]) -> None:
    reading = parse_forecast(response)
    obs = reading.observation
    assert isinstance(obs, WeatherObservation)
    assert obs.station_id == STATION_ID
    assert obs.rainfall_intensity_mm_h == 0.0  # the 10:00 hourly sum, the last one before 10:30
    assert obs.cumulative_rainfall_24h_mm == 0.8  # 0.2 + 0.1 + 0.5 over 11:00 yesterday .. 10:00 today
    assert (obs.temperature_c, obs.wind_speed_kmh, obs.wind_direction_deg) == (30.3, 13.1, 262)
    assert reading.observed_at.isoformat() == "2026-09-26T10:30:00+00:00"


def test_parse_forecast_covers_hours_after_now(response: dict[str, Any]) -> None:
    forecast = parse_forecast(response).forecast
    assert isinstance(forecast, WeatherForecast)
    assert forecast.expected_total_mm == 0.4
    assert forecast.peak_intensity_mm_h == 0.1
    assert forecast.confidence == 0.3  # highest hourly precipitation probability in the window
    assert forecast.horizon_h == 23
    assert len(forecast.hourly) == 23
    assert forecast.hourly[0].time.isoformat() == "2026-09-26T11:00:00+00:00"
    assert forecast.issued_sim_time.isoformat() == "2026-09-26T10:30:00+00:00"
    assert "Open-Meteo" in forecast.summary


def test_heavy_rain_is_banded_with_imd_categories(response: dict[str, Any]) -> None:
    heavy = copy.deepcopy(response)
    precip: list[float] = heavy["hourly"]["precipitation"]
    for i in range(1, 25):
        precip[i] = 6.0  # 144 mm in 24 h: IMD "very heavy" (115.6 - 204.4 mm)
    obs = parse_forecast(heavy).observation
    assert obs.cumulative_rainfall_24h_mm == 144.0
    assert severity_for(EventType.WEATHER_OBSERVATION, obs, KDMC_THRESHOLDS) == Severity.HIGH


def test_malformed_response_raises() -> None:
    with pytest.raises(ValueError):
        parse_forecast({"current": {}})
