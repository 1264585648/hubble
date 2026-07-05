from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from hubble.events.models import EventEnvelope


class Adapter(ABC):
    """Convert raw external input into EventEnvelope.

    Adapter implementations must not call alert core, reasoning, tools or channels.
    """

    name: str

    @abstractmethod
    def to_event(self, raw: dict[str, Any]) -> EventEnvelope:
        """Convert raw payload into an immutable event envelope."""
