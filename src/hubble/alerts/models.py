from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field

AlertSeverity = Literal["critical", "high", "medium", "low", "info", "unknown"]
AlertStatus = Literal["firing", "resolved", "acknowledged", "suppressed"]


class Alert(BaseModel):
    """Normalized alert object owned by the alert lifecycle core."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    source: str
    title: str
    description: str = ""
    severity: AlertSeverity = "unknown"
    status: AlertStatus = "firing"
    labels: dict[str, str] = Field(default_factory=dict)
    annotations: dict[str, str] = Field(default_factory=dict)
    fingerprint: str | None = None
    starts_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    ends_at: datetime | None = None
    raw_event_id: str | None = None
    incident_id: str | None = None
    raw: dict[str, Any] = Field(default_factory=dict)

    def stable_fingerprint(self) -> str:
        if self.fingerprint:
            return self.fingerprint

        payload = {
            "source": self.source,
            "title": self.title,
            "labels": self.labels,
        }
        encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()[:24]


class AlertLifecycleResult(BaseModel):
    alert: Alert
    is_duplicate: bool = False
    deduped_alert_id: str | None = None
