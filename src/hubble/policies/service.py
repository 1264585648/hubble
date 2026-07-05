from __future__ import annotations

from hubble.alerts.models import Alert
from hubble.incidents.models import Incident
from hubble.policies.models import PolicyDecision


class PolicyEngine:
    """Thin rule boundary between lifecycle state and downstream actions.

    The MVP returns a deterministic default decision. Later this should load YAML rules and
    produce decisions for routing, silence, inhibition, escalation and approval gates.
    """

    def evaluate(self, alert: Alert, incident: Incident) -> PolicyDecision:
        if alert.status == "suppressed":
            return PolicyDecision(
                should_notify=False,
                should_analyze=False,
                channels=[],
                reason="alert is suppressed",
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
