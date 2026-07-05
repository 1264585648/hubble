from __future__ import annotations

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
