from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable

from hubble.core.models import SessionMessage

SessionHandler = Callable[[SessionMessage], Awaitable[str]]


class SessionAdapter(ABC):
    """Base interface for interactive chat adapters."""

    name: str

    @abstractmethod
    async def start(self, handler: SessionHandler) -> None:
        """Start listening to messages."""

    @abstractmethod
    async def reply(self, message: SessionMessage, text: str) -> None:
        """Reply to a session message."""
