from __future__ import annotations

from collections import defaultdict
from collections.abc import Awaitable, Callable

from hubble.events.models import EventEnvelope, EventRecord

EventHandler = Callable[[EventEnvelope], Awaitable[None]]


class InMemoryEventBus:
    """Small async event bus used by the MVP runtime.

    The contract intentionally mirrors what a future Redis Streams, NATS or Kafka-backed
    implementation should expose: publish, subscribe and replay.
    """

    def __init__(self) -> None:
        self._handlers: dict[str, list[EventHandler]] = defaultdict(list)
        self._wildcard_handlers: list[EventHandler] = []
        self._records: list[EventRecord] = []

    def subscribe(self, event_type: str, handler: EventHandler) -> None:
        if event_type == "*":
            self._wildcard_handlers.append(handler)
            return
        self._handlers[event_type].append(handler)

    async def publish(self, event: EventEnvelope) -> None:
        record = EventRecord(envelope=event)
        self._records.append(record)

        handlers = [*self._handlers.get(event.type, []), *self._wildcard_handlers]
        try:
            for handler in handlers:
                await handler(event)
        except Exception as exc:  # noqa: BLE001 - event boundary should record failures
            record.error = str(exc)
            raise
        else:
            record.delivered = True

    def replay(self) -> list[EventEnvelope]:
        return [record.envelope for record in self._records]

    def records(self) -> list[EventRecord]:
        return list(self._records)
