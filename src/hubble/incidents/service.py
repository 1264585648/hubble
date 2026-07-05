from __future__ import annotations

from datetime import datetime, timezone

from hubble.alerts.models import Alert
from hubble.incidents.models import Incident, IncidentTimelineItem

SEVERITY_RANK = {
    "unknown": 0,
    "info": 1,
    "low": 2,
    "medium": 3,
    "high": 4,
    "critical": 5,
}


class IncidentLifecycleService:
    """Group alerts into incidents and maintain incident timeline."""

    def __init__(self, group_by: list[str] | None = None) -> None:
        self.group_by = group_by or ["service", "env", "region"]
        self._incidents_by_id: dict[str, Incident] = {}
        self._incident_by_group_key: dict[str, Incident] = {}

    def attach_alert(self, alert: Alert) -> Incident:
        group_key = self._group_key(alert)
        incident = self._incident_by_group_key.get(group_key)

        if not incident:
            incident = Incident(
                title=alert.title,
                severity=alert.severity,
                alert_ids=[alert.id],
                alert_fingerprints=[alert.fingerprint or alert.stable_fingerprint()],
                affected_services=_affected_services(alert),
                timeline=[
                    IncidentTimelineItem(
                        type="incident.created",
                        message=f"Incident created from alert {alert.title}",
                        ref_id=alert.id,
                    )
                ],
            )
            self._incidents_by_id[incident.id] = incident
            self._incident_by_group_key[group_key] = incident
            alert.incident_id = incident.id
            return incident

        if alert.id not in incident.alert_ids:
            incident.alert_ids.append(alert.id)
        fingerprint = alert.fingerprint or alert.stable_fingerprint()
        if fingerprint not in incident.alert_fingerprints:
            incident.alert_fingerprints.append(fingerprint)
        for service in _affected_services(alert):
            if service not in incident.affected_services:
                incident.affected_services.append(service)

        if SEVERITY_RANK[alert.severity] > SEVERITY_RANK[incident.severity]:
            incident.severity = alert.severity

        incident.updated_at = datetime.now(timezone.utc)
        incident.timeline.append(
            IncidentTimelineItem(
                type="alert.attached",
                message=f"Alert attached: {alert.title}",
                ref_id=alert.id,
            )
        )
        alert.incident_id = incident.id
        return incident

    def get(self, incident_id: str) -> Incident | None:
        return self._incidents_by_id.get(incident_id)

    def list_incidents(self) -> list[Incident]:
        return list(self._incidents_by_id.values())

    def _group_key(self, alert: Alert) -> str:
        parts = [alert.source]
        for label in self.group_by:
            parts.append(f"{label}={alert.labels.get(label, '-')}")
        return "|".join(parts)


def _affected_services(alert: Alert) -> list[str]:
    service = alert.labels.get("service") or alert.labels.get("service_name")
    return [service] if service else []
