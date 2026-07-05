from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class EventEnvelope(BaseModel):
    """Stable event contract between layers.

    Inspired by CloudEvents, but intentionally lightweight. Every external input should be
    converted into EventEnvelope before it enters Hubble's alert lifecycle core.
    """

    id: str = Field(default_factory=lambda: str(uuid4()))
    type: str
    source: str
    subject: str | None = None
    time: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    data: dict[str, Any] = Field(default_factory=dict)
    datacontenttype: str = "application/json"
    trace_id: str | None = None
    tenant_id: str | None = None
    extensions: dict[str, Any] = Field(default_factory=dict)


class EventRecord(BaseModel):
    """Stored event plus delivery metadata."""

    envelope: EventEnvelope
    delivered: bool = False
    error: str | None = None
