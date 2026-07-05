from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class PolicyDecision(BaseModel):
    """Result of evaluating an alert/incident against policy rules."""

    should_notify: bool = True
    should_analyze: bool = True
    channels: list[str] = Field(default_factory=lambda: ["console"])
    enrich_tools: list[str] = Field(default_factory=list)
    escalation_channels: list[str] = Field(default_factory=list)
    require_approval: bool = False
    reason: str = "default policy"


class PolicyRule(BaseModel):
    """Declarative rule for routing, enrichment and approval decisions."""

    name: str
    enabled: bool = True
    priority: int = 100
    match: dict[str, Any] = Field(default_factory=dict)
    should_notify: bool = True
    should_analyze: bool = True
    channels: list[str] = Field(default_factory=lambda: ["console"])
    enrich_tools: list[str] = Field(default_factory=list)
    escalation_channels: list[str] = Field(default_factory=list)
    require_approval: bool = False
    stop_processing: bool = True
