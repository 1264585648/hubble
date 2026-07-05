from __future__ import annotations

from typing import Any

from hubble.alerts.models import Alert, AlertLifecycleResult
from hubble.events.models import EventEnvelope

VALID_SEVERITIES = {"critical", "high", "medium", "low", "info", "unknown"}
VALID_STATUSES = {"firing", "resolved", "acknowledged", "suppressed"}


class AlertLifecycleService:
    """Normalize, fingerprint and deduplicate alerts.

    This layer owns alert state transitions only. It must not call models, tools or channels.
    """

    def __init__(self) -> None:
        self._alerts_by_id: dict[str, Alert] = {}
        self._alerts_by_fingerprint: dict[str, Alert] = {}

    def handle_event(self, event: EventEnvelope) -> AlertLifecycleResult:
        alert = self._normalize(event)
        alert.fingerprint = alert.stable_fingerprint()

        existing = self._alerts_by_fingerprint.get(alert.fingerprint)
        if existing and existing.status == alert.status:
            return AlertLifecycleResult(
                alert=existing,
                is_duplicate=True,
                deduped_alert_id=existing.id,
            )

        self._alerts_by_id[alert.id] = alert
        self._alerts_by_fingerprint[alert.fingerprint] = alert
        return AlertLifecycleResult(alert=alert)

    def get(self, alert_id: str) -> Alert | None:
        return self._alerts_by_id.get(alert_id)

    def list_alerts(self) -> list[Alert]:
        return list(self._alerts_by_id.values())

    def _normalize(self, event: EventEnvelope) -> Alert:
        payload = event.data
        labels = _string_dict(payload.get("labels") or {})
        annotations = _string_dict(payload.get("annotations") or {})

        title = (
            payload.get("title")
            or payload.get("alertname")
            or labels.get("alertname")
            or payload.get("name")
            or event.subject
            or "Untitled alert"
        )
        description = (
            payload.get("description")
            or annotations.get("description")
            or annotations.get("summary")
            or payload.get("message")
            or ""
        )
        severity = str(payload.get("severity") or labels.get("severity") or "unknown")
        status = str(payload.get("status") or "firing")

        return Alert(
            source=event.source,
            title=str(title),
            description=str(description),
            severity=severity if severity in VALID_SEVERITIES else "unknown",
            status=status if status in VALID_STATUSES else "firing",
            labels=labels,
            annotations=annotations,
            raw_event_id=event.id,
            raw=payload,
        )


def _string_dict(value: dict[str, Any]) -> dict[str, str]:
    return {str(key): str(item) for key, item in value.items()}
