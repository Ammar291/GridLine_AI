"""Holds both data sources and switches between them at runtime, without restarting the app."""

import asyncio
from collections.abc import Callable, Mapping
from datetime import datetime

from gridline.events.bus import EventBus
from gridline.events.envelope import Event
from gridline.events.payloads import DataMode, SourceStatus
from gridline.sources.base import DataSource, status_event, utcnow


class DataSourceManager:
    def __init__(
        self,
        sources: Mapping[DataMode, DataSource],
        bus: EventBus,
        *,
        mode: DataMode,
        clock: Callable[[], datetime] = utcnow,
    ) -> None:
        self.sources = dict(sources)
        self.bus = bus
        self._mode: DataMode = mode
        self._clock = clock
        self._counter = 0
        self._lock = asyncio.Lock()

    @property
    def mode(self) -> DataMode:
        return self._mode

    @property
    def active(self) -> DataSource:
        return self.sources[self._mode]

    def status(self) -> SourceStatus:
        return self.active.status()

    async def start(self) -> None:
        await self.active.start()

    async def switch(self, mode: DataMode) -> SourceStatus:
        """Stop the current source, start ``mode``'s, and announce it with one ``source.status``."""
        async with self._lock:
            if mode != self._mode:
                await self.active.stop()
                self._mode = mode
                await self.active.start()
                self.bus.publish(self._status_event())
        return self.status()

    def replay(self) -> list[Event]:
        """What a new client needs after its snapshot: the mode, then the source's latest state."""
        return [self._status_event(), *self.active.latest()]

    async def shutdown(self) -> None:
        for source in self.sources.values():
            await source.stop()

    def _status_event(self) -> Event:
        self._counter += 1
        return status_event(self.status(), event_id=f"src-{self._counter:06d}", now=self._clock())
