from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field

from hubble.events.models import EventEnvelope

IntakeAction = Literal["allow", "drop", "rewrite", "tag"]


class IntakeRule(BaseModel):
    """Rule evaluated before an event becomes an Alert.

    Match syntax is intentionally small for the MVP. It is designed to be replaced by a
    stronger DSL later without changing the surrounding runtime contract.
    """

    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    enabled: bool = True
    priority: int = 100
    match: dict[str, Any] = Field(default_factory=dict)
    action: IntakeAction = "allow"
    reason: str = ""
    add_labels: dict[str, str] = Field(default_factory=dict)
    set_fields: dict[str, Any] = Field(default_factory=dict)
    stop_processing: bool = True

    matched_count: int = 0
    allowed_count: int = 0
    filtered_count: int = 0
    tag_count: int = 0
    rewrite_count: int = 0
    last_matched_at: datetime | None = None


class IntakeDecision(BaseModel):
    """Result of evaluating an EventEnvelope against intake rules."""

    allowed: bool = True
    action: IntakeAction = "allow"
    matched_rule_id: str | None = None
    matched_rule_name: str | None = None
    reason: str = "default allow"
    event: EventEnvelope


class IntakeDryRunRequest(BaseModel):
    """Request for testing a payload against saved rules or one temporary rule."""

    source: str = "dry-run"
    payload: dict[str, Any] = Field(default_factory=dict)
    rule: IntakeRule | None = None


class IntakeDryRunResponse(BaseModel):
    """Dry-run result. It must not create alerts, incidents or publish formal events."""

    decision: IntakeDecision
    rule: IntakeRule | None = None
    would_create_alert: bool
