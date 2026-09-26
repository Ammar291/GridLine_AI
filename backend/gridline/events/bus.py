"""In-process event bus (spec §7.4). Publishing never blocks: a slow subscriber loses its oldest events."""

import asyncio
from collections.abc import Sequence

from gridline.events.envelope import Event


def normalize_prefixes(type_prefixes: Sequence[str] | None) -> tuple[str, ...]:
    """Strip each prefix and drop empty ones; no prefixes left means no filter."""
    return tuple(p.strip() for p in type_prefixes or () if p.strip())


class Subscription:
    def __init__(self, prefixes: tuple[str, ...], maxsize: int) -> None:
        self.prefixes = prefixes
        self.queue: asyncio.Queue[Event] = asyncio.Queue(maxsize=maxsize)
        self.dropped = 0

    def matches(self, event: Event) -> bool:
        return not self.prefixes or event.event_type.startswith(self.prefixes)

    def offer(self, event: Event) -> None:
        if self.queue.full():
            self.queue.get_nowait()
            self.dropped += 1
        self.queue.put_nowait(event)


class EventBus:
    """One instance lives on ``app.state.bus``. The DB writer will be one more subscriber."""

    def __init__(self, *, maxsize: int = 1000) -> None:
        self._maxsize = maxsize
        self._subscriptions: list[Subscription] = []

    def subscribe(
        self, type_prefixes: Sequence[str] | None = None, *, maxsize: int | None = None
    ) -> Subscription:
        subscription = Subscription(normalize_prefixes(type_prefixes), maxsize or self._maxsize)
        self._subscriptions.append(subscription)
        return subscription

    def unsubscribe(self, subscription: Subscription) -> None:
        if subscription in self._subscriptions:
            self._subscriptions.remove(subscription)

    def publish(self, event: Event) -> None:
        for subscription in list(self._subscriptions):
            if subscription.matches(event):
                subscription.offer(event)

    @property
    def subscriber_count(self) -> int:
        return len(self._subscriptions)
