"""The data-source seam: DEMO (Nandipur simulation) and LIVE (real weather) feed the same event bus.

Both publish the same normalized ``Event`` envelopes and payload models, so everything downstream of the bus
(WebSocket, dashboard, and the threat detector and agent when they land) is shared and mode-agnostic.
"""

from datetime import UTC, datetime
from typing import Protocol

from gridline.events.envelope import Event, new_event
from gridline.events.payloads import DataMode, SourceStatus
from gridline.events.types import EventType, Severity

MANAGER_SOURCE = "source:manager"


def utcnow() -> datetime:
    return datetime.now(UTC)


class DataSource(Protocol):
    @property
    def mode(self) -> DataMode: ...

    async def start(self) -> None:
        """Begin producing events on the bus."""
        ...

    async def stop(self) -> None:
        """Stop producing events; ``start`` may be called again later."""
        ...

    def status(self) -> SourceStatus: ...

    def latest(self) -> list[Event]:
        """The most recent state-bearing events, replayed to a client that connects mid-stream."""
        ...


def status_event(
    status: SourceStatus, *, event_id: str, now: datetime, source: str = MANAGER_SOURCE
) -> Event:
    return new_event(
        EventType.SOURCE_STATUS,
        status,
        event_id=event_id,
        timestamp=now,
        sim_time=now,
        source=source,
        location=None,
        severity=Severity.INFO,
    )
