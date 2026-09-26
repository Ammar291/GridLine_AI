"""LIVE mode: polls Open-Meteo for Kalyan-Dombivli and publishes the readings as normal weather events.

A failed poll (offline, timeout, bad payload) publishes a ``source.status`` carrying the error and nothing
else: live mode never invents a reading. The last good readings stay available with their own timestamps.
"""

import asyncio
import contextlib
import logging
from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Any

from pydantic import BaseModel

from gridline.events.bus import EventBus
from gridline.events.envelope import Event, new_event
from gridline.events.payloads import DataMode, SourceStatus
from gridline.events.types import EventType
from gridline.simulation.severity import severity_for
from gridline.sources.base import status_event, utcnow
from gridline.sources.open_meteo import (
    FORECAST_URL,
    KALYAN_DOMBIVLI,
    KDMC_THRESHOLDS,
    SOURCE,
    Place,
    fetch_json,
    forecast_url,
    parse_forecast,
)

logger = logging.getLogger(__name__)

Fetch = Callable[[str], Awaitable[dict[str, Any]]]


class LiveDataSource:
    def __init__(
        self,
        bus: EventBus,
        *,
        fetch: Fetch = fetch_json,
        poll_seconds: float = 300.0,
        place: Place = KALYAN_DOMBIVLI,
        base_url: str = FORECAST_URL,
        clock: Callable[[], datetime] = utcnow,
    ) -> None:
        self.bus = bus
        self.place = place
        self.poll_seconds = poll_seconds
        self._fetch = fetch
        self._url = forecast_url(place, base_url)
        self._clock = clock
        self._task: asyncio.Task[None] | None = None
        self._first_poll = asyncio.Event()
        self._latest: list[Event] = []
        self._counter = 0
        self._last_updated: datetime | None = None
        self._last_error: str | None = None

    @property
    def mode(self) -> DataMode:
        return "live"

    def status(self) -> SourceStatus:
        return SourceStatus(
            mode="live",
            label=f"LIVE — {self.place.name}",
            city=self.place.name,
            provider="Open-Meteo",
            latitude=self.place.latitude,
            longitude=self.place.longitude,
            poll_seconds=self.poll_seconds,
            last_updated=self._last_updated,
            last_error=self._last_error,
        )

    def latest(self) -> list[Event]:
        return list(self._latest)

    async def start(self) -> None:
        if self._task is None:
            self._first_poll.clear()
            self._task = asyncio.create_task(self._loop(), name="live-weather")

    async def stop(self) -> None:
        task, self._task = self._task, None
        if task is not None:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

    async def wait_first_poll(self) -> None:
        await self._first_poll.wait()

    async def poll_once(self) -> None:
        try:
            reading = parse_forecast(await self._fetch(self._url))
        except Exception as exc:  # offline or a bad payload: report it and keep polling
            logger.warning("live weather poll failed: %s", exc)
            self._last_error = f"{type(exc).__name__}: {exc}"
        else:
            self._latest = [
                self._event(EventType.WEATHER_OBSERVATION, reading.observation, reading.observed_at),
                self._event(EventType.WEATHER_FORECAST, reading.forecast, reading.observed_at),
            ]
            self._last_updated, self._last_error = self._clock(), None
            for event in self._latest:
                self.bus.publish(event)
        self.bus.publish(
            status_event(self.status(), event_id=self._next_id(), now=self._clock(), source=SOURCE)
        )
        self._first_poll.set()

    async def _loop(self) -> None:
        while True:
            await self.poll_once()
            await asyncio.sleep(self.poll_seconds)

    def _next_id(self) -> str:
        self._counter += 1
        return f"live-{self._counter:06d}"

    def _event(self, event_type: EventType, payload: BaseModel, observed_at: datetime) -> Event:
        return new_event(
            event_type,
            payload,
            event_id=self._next_id(),
            timestamp=self._clock(),
            sim_time=observed_at,
            source=SOURCE,
            location=self.place.id,
            severity=severity_for(event_type, payload, KDMC_THRESHOLDS),
        )
