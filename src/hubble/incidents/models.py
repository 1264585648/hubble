from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field

from hubble.alerts.models import AlertSeverity

IncidentStatus = Literal["open", "investigating", "mitigated", "resolved"]


class IncidentTimelineItem(BaseModel):
    at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    type: str
    message: str
    ref_id: str | None = None


class Incident(BaseModel):
    """A group of related alerts that should be handled as one operational issue."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    title: str
    severity: AlertSeverity = "unknown"
    status: IncidentStatus = "open"
    alert_ids: list[str] = Field(default_factory=list)
    alert_fingerprints: list[str] = Field(default_factory=list)
    affected_services: list[str] = Field(default_factory=list)
    owner_team: str | None = None
    thread_id: str | None = None
    current_summary: str | None = None
    last_analysis_id: str | None = None
    timeline: list[IncidentTimelineItem] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    resolved_at: datetime | None = None
