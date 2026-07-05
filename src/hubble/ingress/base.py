from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from typing import Any

from hubble.core.models import AlertEvent

AlertHandler = Callable[[AlertEvent], Awaitable[None]]


class Ingress(ABC):
    """Base interface for alert ingress plugins."""

    name: str

    @abstractmethod
    async def start(self, handler: AlertHandler) -> None:
        """Start receiving alerts and pass normalized AlertEvent to handler."""


class WebhookNormalizer:
    """Default best-effort normalizer for generic webhook payloads."""

    @staticmethod
    def normalize(source: str, payload: dict[str, Any]) -> AlertEvent:
        labels = payload.get("labels") or {}
        annotations = payload.get("annotations") or {}

        title = (
            payload.get("title")
            or payload.get("alertname")
            or labels.get("alertname")
            or payload.get("name")
            or "Untitled alert"
        )
        description = (
            payload.get("description")
            or annotations.get("description")
            or annotations.get("summary")
            or payload.get("message")
            or ""
        )
        severity = payload.get("severity") or labels.get("severity") or "unknown"
        status = payload.get("status") or "firing"

        return AlertEvent(
            source=source,
            title=str(title),
            description=str(description),
            severity=severity if severity in {"critical", "high", "medium", "low", "info"} else "unknown",
            status=status if status in {"firing", "resolved", "acknowledged", "suppressed"} else "firing",
            labels={str(k): str(v) for k, v in labels.items()},
            annotations={str(k): str(v) for k, v in annotations.items()},
            raw=payload,
        )
