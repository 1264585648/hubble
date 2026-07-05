from __future__ import annotations

from typing import Any

from hubble.adapters.base import Adapter
from hubble.events.models import EventEnvelope


class GenericWebhookAdapter(Adapter):
    """Best-effort generic webhook adapter.

    Specific adapters such as Alertmanager, Grafana and Sentry should later subclass or
    replace this implementation with stronger payload schemas.
    """

    def __init__(self, source: str) -> None:
        self.name = source

    def to_event(self, raw: dict[str, Any]) -> EventEnvelope:
        labels = raw.get("labels") or {}
        subject = (
            raw.get("title")
            or raw.get("alertname")
            or labels.get("alertname")
            or raw.get("name")
        )
        return EventEnvelope(
            type="alert.ingested",
            source=self.name,
            subject=str(subject) if subject else None,
            data=raw,
        )
