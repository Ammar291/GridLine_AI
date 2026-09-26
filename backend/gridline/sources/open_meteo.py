"""Open-Meteo for LIVE mode: real modelled weather for Kalyan-Dombivli, no API key needed.

Open-Meteo's hourly ``precipitation`` is the sum over the preceding hour, so the value stamped at or before
``current.time`` is the latest rainfall intensity (mm/h) and the 24 values up to it are the 24 h total. The
numbers are gridded model analysis and forecast, not a rain gauge, and every event names Open-Meteo as its
source. Nothing here is estimated or filled in: a response missing a field raises ``ValueError``.
"""

import asyncio
import json
import urllib.request
from datetime import UTC, datetime
from typing import Any, cast
from urllib.parse import urlencode

from pydantic import BaseModel, ConfigDict

from gridline.city.model import PolicyThresholds
from gridline.events.payloads import HourlyPrecipitation, WeatherForecast, WeatherObservation

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
SOURCE = "open-meteo:forecast-api"
STATION_ID = "OM-KDMC"  # the Open-Meteo grid cell over Kalyan-Dombivli, not a physical station
WINDOW_H = 24


class Place(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    latitude: float
    longitude: float


KALYAN_DOMBIVLI = Place(id="kalyan-dombivli", name="Kalyan-Dombivli", latitude=19.235, longitude=73.13)

# Public, non-city-specific bands so live readings get a severity the same way simulated ones do.
KDMC_THRESHOLDS = PolicyThresholds(
    rain_1h_watch_mm_h=7.6,  # "heavy rain" rate, over 7.6 mm/h
    rain_1h_warning_mm_h=50.0,  # "violent rain" rate, over 50 mm/h
    rain_24h_watch_mm=64.5,  # IMD heavy rainfall
    rain_24h_warning_mm=115.6,  # IMD very heavy rainfall
    rain_24h_critical_mm=204.5,  # IMD extremely heavy rainfall
    wind_watch_kmh=62.0,  # Beaufort 8, gale
    wind_warning_kmh=89.0,  # Beaufort 10, storm
    wind_critical_kmh=118.0,  # Beaufort 12, hurricane force
    # Live mode has no soil probes, drainage gauges or flood-depth readings, so these bands never apply.
    saturation_warning=0.70,
    saturation_critical=0.85,
    channel_ratio_watch=0.8,
    channel_ratio_critical=1.0,
    road_closure_depth_cm=30.0,
    landslide_rain_gauge_ids=(STATION_ID,),  # apply the 24 h bands to the one live station
)


class LiveReading(BaseModel):
    observed_at: datetime
    observation: WeatherObservation
    forecast: WeatherForecast


def forecast_url(place: Place, base_url: str = FORECAST_URL) -> str:
    query = {
        "latitude": place.latitude,
        "longitude": place.longitude,
        "current": "temperature_2m,precipitation,wind_speed_10m,wind_direction_10m",
        "hourly": "precipitation,precipitation_probability",
        "past_hours": WINDOW_H,
        "forecast_hours": WINDOW_H,
        "timezone": "UTC",
    }
    return f"{base_url}?{urlencode(query, safe=',')}"


async def fetch_json(url: str, timeout_s: float = 15.0) -> dict[str, Any]:
    """GET ``url`` in a worker thread (urllib, no extra dependency) and decode the JSON body."""

    def get() -> dict[str, Any]:
        request = urllib.request.Request(url, headers={"User-Agent": "GridLine-AI/0.1"})
        with urllib.request.urlopen(request, timeout=timeout_s) as response:
            return cast(dict[str, Any], json.loads(response.read()))

    return await asyncio.to_thread(get)


def _utc(text: str) -> datetime:
    return datetime.fromisoformat(text).replace(tzinfo=UTC)


def parse_forecast(data: dict[str, Any]) -> LiveReading:
    try:
        current = cast(dict[str, Any], data["current"])
        hourly = cast(dict[str, Any], data["hourly"])
        now = _utc(current["time"])
        times = [_utc(t) for t in cast(list[str], hourly["time"])]
        precip = [float(v or 0.0) for v in cast(list[float | None], hourly["precipitation"])]
        raw_probs = cast(list[float | None], hourly.get("precipitation_probability") or [None] * len(times))
        probs = [None if v is None else float(v) / 100 for v in raw_probs]
        past = [i for i, t in enumerate(times) if t <= now][-WINDOW_H:]
        ahead = [i for i, t in enumerate(times) if t > now][:WINDOW_H]
        if not past or not ahead:
            raise ValueError("hourly series does not span the current time")
        observation = WeatherObservation(
            station_id=STATION_ID,
            rainfall_intensity_mm_h=round(precip[past[-1]], 2),
            cumulative_rainfall_24h_mm=round(sum(precip[i] for i in past), 1),
            temperature_c=float(current["temperature_2m"]),
            wind_speed_kmh=float(current["wind_speed_10m"]),
            wind_direction_deg=float(current["wind_direction_10m"]) % 360,
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"unexpected Open-Meteo response: {exc}") from exc
    total = round(sum(precip[i] for i in ahead), 1)
    peak = round(max(precip[i] for i in ahead), 2)
    known = [p for i in ahead if (p := probs[i]) is not None]
    chance = round(max(known), 2) if known else 0.0
    forecast = WeatherForecast(
        issued_sim_time=now,
        horizon_h=len(ahead),
        expected_total_mm=total,
        peak_intensity_mm_h=peak,
        confidence=chance,
        summary=(
            f"Open-Meteo model forecast: {total} mm over the next {len(ahead)} h, peak {peak} mm/h, "
            f"highest hourly precipitation probability {round(chance * 100)}%."
        ),
        hourly=[
            HourlyPrecipitation(time=times[i], precipitation_mm=round(precip[i], 2), probability=probs[i])
            for i in ahead
        ],
    )
    return LiveReading(observed_at=now, observation=observation, forecast=forecast)
