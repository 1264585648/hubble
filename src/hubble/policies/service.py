from __future__ import annotations

from typing import Any

from hubble.alerts.models import Alert
from hubble.incidents.models import Incident
from hubble.policies.models import PolicyDecision, PolicyRule


class PolicyEngine:
    """Thin rule boundary between lifecycle state and downstream actions.

    Rules decide whether to notify, analyze, enrich, escalate or require approval.
    They must not execute tools, call models or send notifications directly.
    """

    def __init__(self, rules: list[PolicyRule] | None = None) -> None:
        self._rules: list[PolicyRule] = sorted(
            rules or [],
            key=lambda item: item.priority,
        )

    def list_rules(self) -> list[PolicyRule]:
        return list(self._rules)

    def evaluate(self, alert: Alert, incident: Incident) -> PolicyDecision:
        if alert.status == "suppressed":
            return PolicyDecision(
                should_notify=False,
                should_analyze=False,
                channels=[],
                reason="alert is suppressed",
            )

        for rule in self._rules:
            if not rule.enabled or not _matches(rule.match, alert, incident):
                continue
            return PolicyDecision(
                should_notify=rule.should_notify,
                should_analyze=rule.should_analyze,
                channels=rule.channels,
                enrich_tools=rule.enrich_tools,
                escalation_channels=rule.escalation_channels,
                require_approval=rule.require_approval,
                reason=f"matched policy rule: {rule.name}",
            )

        if alert.severity in {"critical", "high"}:
            return PolicyDecision(
                should_notify=True,
                should_analyze=True,
                channels=["console"],
                enrich_tools=[],
                escalation_channels=[],
                reason="high severity alert uses default notification route",
            )

        return PolicyDecision(
            should_notify=True,
            should_analyze=True,
            channels=["console"],
            reason=f"default route for incident {incident.id}",
        )


def _matches(match: dict[str, Any], alert: Alert, incident: Incident) -> bool:
    if not match:
        return True

    for key, expected in match.items():
        actual = _value_for_key(key, alert, incident)
        if isinstance(expected, list):
            if actual not in expected:
                return False
        elif actual != expected:
            return False
    return True


def _value_for_key(key: str, alert: Alert, incident: Incident) -> Any:
    if key == "source":
        return alert.source
    if key == "severity":
        return alert.severity
    if key == "status":
        return alert.status
    if key == "incident.status":
        return incident.status
    if key == "incident.owner_team":
        return incident.owner_team
    if key.startswith("labels."):
        return alert.labels.get(key.removeprefix("labels."))
    if key.startswith("annotations."):
        return alert.annotations.get(key.removeprefix("annotations."))
    return alert.labels.get(key) or alert.annotations.get(key)
