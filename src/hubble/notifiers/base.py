from __future__ import annotations

from abc import ABC, abstractmethod

from hubble.core.models import Notification, SendResult


class Notifier(ABC):
    """Base interface for notification channels."""

    name: str

    @abstractmethod
    async def send(self, notification: Notification) -> SendResult:
        """Send a notification."""


class ConsoleNotifier(Notifier):
    """Development notifier that prints messages to stdout."""

    name = "console"

    async def send(self, notification: Notification) -> SendResult:
        print("=" * 80)
        print(f"[{notification.severity.upper()}] {notification.title}")
        print(notification.body)
        print("=" * 80)
        return SendResult(ok=True, metadata={"channel": self.name})


class NotifierRegistry:
    """Registry for notification channels."""

    def __init__(self) -> None:
        self._notifiers: dict[str, Notifier] = {}

    def register(self, notifier: Notifier) -> None:
        if notifier.name in self._notifiers:
            raise ValueError(f"Notifier already registered: {notifier.name}")
        self._notifiers[notifier.name] = notifier

    def get(self, name: str) -> Notifier | None:
        return self._notifiers.get(name)

    def list_names(self) -> list[str]:
        return list(self._notifiers.keys())

    async def send(self, notification: Notification, channels: list[str] | None = None) -> list[SendResult]:
        target_names = channels or self.list_names()
        results: list[SendResult] = []
        for name in target_names:
            notifier = self.get(name)
            if not notifier:
                results.append(SendResult(ok=False, error=f"Unknown notifier: {name}"))
                continue
            results.append(await notifier.send(notification))
        return results
