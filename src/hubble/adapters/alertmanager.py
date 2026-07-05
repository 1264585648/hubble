from __future__ import annotations

from typing import Any

from hubble.adapters.base import Adapter
from hubble.events.models import EventEnvelope


class AlertmanagerWebhookAdapter(Adapter):
    """Convert Prometheus Alertmanager webhook payloads into alert events.

    Alertmanager sends a batch containing `alerts[]`. Hubble converts each item into one
    `alert.received` event so downstream Alert / Incident lifecycle remains unchanged.
    """

    def __init__(self, source: str = "alertmanager") -> None:
        self.name = source

    def to_event(self, raw: dict[str, Any]) -> EventEnvelope:
        events = self.to_events(raw)
        if not events:
            return EventEnvelope(type="alert.received", source=self.name, data=raw)
        return events[0]

    def to_events(self, raw: dict[str, Any]) -> list[EventEnvelope]:
        alerts = raw.get("alerts") or []
        if not isinstance(alerts, list):
            alerts = []

        common_labels = _string_dict(raw.get("commonLabels") or {})
        common_annotations = _string_dict(raw.get("commonAnnotations") or {})
        group_labels = _string_dict(raw.get("groupLabels") or {})

        if not alerts:
            return [
                EventEnvelope(
                    type="alert.received",
                    source=self.name,
                    subject=_subject(common_labels, raw),
                    data={
                        "title": (
                            _subject(common_labels, raw) or "Alertmanager notification"
                        ),
                        "description": _description(common_annotations),
                        "severity": common_labels.get("severity", "unknown"),
                        "status": str(raw.get("status") or "firing"),
                        "labels": common_labels,
                        "annotations": common_annotations,
                        "group_labels": group_labels,
                        "raw": raw,
                    },
                )
            ]

        events: list[EventEnvelope] = []
        for item in alerts:
            if not isinstance(item, dict):
                continue

            labels = {**common_labels, **_string_dict(item.get("labels") or {})}
            annotations = {
                **common_annotations,
                **_string_dict(item.get("annotations") or {}),
            }
            title = labels.get("alertname") or raw.get("receiver") or "Alertmanager alert"
            status = str(item.get("status") or raw.get("status") or "firing")

            events.append(
                EventEnvelope(
                    type="alert.received",
                    source=self.name,
                    subject=title,
                    data={
                        "title": title,
                        "description": _description(annotations),
                        "severity": labels.get("severity", "unknown"),
                        "status": status,
                        "labels": labels,
                        "annotations": annotations,
                        "group_labels": group_labels,
                        "starts_at": item.get("startsAt"),
                        "ends_at": item.get("endsAt"),
                        "generator_url": item.get("generatorURL"),
                        "fingerprint": item.get("fingerprint"),
                        "raw": item,
                        "raw_batch": {
                            "receiver": raw.get("receiver"),
                            "status": raw.get("status"),
                            "groupKey": raw.get("groupKey"),
                            "externalURL": raw.get("externalURL"),
                            "version": raw.get("version"),
                        },
                    },
                )
            )
        return events


def _subject(labels: dict[str, str], raw: dict[str, Any]) -> str | None:
    return labels.get("alertname") or raw.get("receiver")


def _description(annotations: dict[str, str]) -> str:
    return annotations.get("description") or annotations.get("summary") or ""


def _string_dict(value: dict[str, Any]) -> dict[str, str]:
    return {str(key): str(item) for key, item in value.items()}
