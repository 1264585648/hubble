from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable

from hubble.channels.models import ChannelMessage, ChannelSendResult, IncomingChannelMessage

ChannelMessageHandler = Callable[[IncomingChannelMessage], Awaitable[str]]


class ChannelAdapter(ABC):
    """Unified channel contract for both notifications and conversations."""

    name: str

    @abstractmethod
    async def send(self, message: ChannelMessage) -> ChannelSendResult:
        """Send a notification or thread reply."""

    async def listen(self, handler: ChannelMessageHandler) -> None:
        """Start listening for incoming messages.

        Channels that do not support conversations can keep the default no-op.
        """
        return None

    async def reply(self, incoming: IncomingChannelMessage, text: str) -> ChannelSendResult:
        return await self.send(
            ChannelMessage(
                title="Hubble Reply",
                body=text,
                incident_id=incoming.incident_id,
                alert_id=incoming.alert_id,
                thread_id=incoming.thread_id,
            )
        )


class ConsoleChannelAdapter(ChannelAdapter):
    name = "console"

    async def send(self, message: ChannelMessage) -> ChannelSendResult:
        print("=" * 80)
        print(f"[{message.severity.upper()}] {message.title}")
        print(message.body)
        print("=" * 80)
        return ChannelSendResult(ok=True, channel=self.name, thread_id=message.thread_id)


class ChannelRegistry:
    def __init__(self) -> None:
        self._channels: dict[str, ChannelAdapter] = {}

    def register(self, channel: ChannelAdapter) -> None:
        if channel.name in self._channels:
            raise ValueError(f"Channel already registered: {channel.name}")
        self._channels[channel.name] = channel

    def get(self, name: str) -> ChannelAdapter | None:
        return self._channels.get(name)

    def list_names(self) -> list[str]:
        return list(self._channels.keys())

    async def send(self, message: ChannelMessage, channels: list[str]) -> list[ChannelSendResult]:
        results: list[ChannelSendResult] = []
        for channel_name in channels:
            channel = self.get(channel_name)
            if not channel:
                results.append(
                    ChannelSendResult(
                        ok=False,
                        channel=channel_name,
                        error=f"Unknown channel: {channel_name}",
                    )
                )
                continue
            results.append(await channel.send(message))
        return results
