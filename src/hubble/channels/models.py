from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from hubble.alerts.models import AlertSeverity


class ChannelMessage(BaseModel):
    title: str
    body: str
    severity: AlertSeverity = "unknown"
    incident_id: str | None = None
    alert_id: str | None = None
    thread_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ChannelSendResult(BaseModel):
    ok: bool
    channel: str
    message_id: str | None = None
    thread_id: str | None = None
    error: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class IncomingChannelMessage(BaseModel):
    channel: str
    thread_id: str | None = None
    sender_id: str | None = None
    text: str
    incident_id: str | None = None
    alert_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
