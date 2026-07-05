import asyncio

from hubble.policies.config import load_policy_rules_from_file
from hubble.policies.models import PolicyRule
from hubble.policies.service import PolicyEngine
from hubble.runtime import HubbleRuntime


def test_policy_engine_matches_labels_and_severity() -> None:
    engine = PolicyEngine(
        [
            PolicyRule(
                name="payment critical",
                priority=1,
                match={
                    "labels.service": "payment-api",
                    "labels.env": "prod",
                    "severity": "critical",
                },
                channels=["console"],
                enrich_tools=["query_logs"],
                escalation_channels=["console"],
                require_approval=True,
            )
        ]
    )

    result = asyncio.run(
        HubbleRuntime(policy_engine=engine).ingest_webhook(
            "demo",
            {
                "title": "payment-api error rate is high",
                "description": "HTTP 5xx error rate exceeded 5% for 5 minutes.",
                "severity": "critical",
                "labels": {"service": "payment-api", "env": "prod"},
            },
        )
    )

    assert result.policy is not None
    assert result.policy.reason == "matched policy rule: payment critical"
    assert result.policy.enrich_tools == ["query_logs"]
    assert result.policy.escalation_channels == ["console"]
    assert result.policy.require_approval is True
    assert result.analysis is not None


def test_policy_can_disable_notification_and_analysis() -> None:
    engine = PolicyEngine(
        [
            PolicyRule(
                name="dev info ignored",
                priority=1,
                match={"labels.env": "dev", "severity": "info"},
                should_notify=False,
                should_analyze=False,
                channels=[],
            )
        ]
    )

    runtime = HubbleRuntime(policy_engine=engine)
    result = asyncio.run(
        runtime.ingest_webhook(
            "demo",
            {
                "title": "dev info alert",
                "description": "low value noise",
                "severity": "info",
                "labels": {"service": "demo", "env": "dev"},
            },
        )
    )

    assert result.policy is not None
    assert result.policy.reason == "matched policy rule: dev info ignored"
    assert result.analysis is None
    assert result.alert is not None
    assert result.incident is not None


def test_policy_rules_load_from_yaml(tmp_path) -> None:
    config_file = tmp_path / "hubble.yaml"
    config_file.write_text(
        """
policies:
  rules:
    - name: payment-critical-route
      enabled: true
      priority: 10
      match:
        labels.service: payment-api
        severity: critical
      should_notify: true
      should_analyze: true
      channels: [console]
      enrich_tools: [query_logs, query_prometheus]
      escalation_channels: [console]
      require_approval: false
""",
        encoding="utf-8",
    )

    rules = load_policy_rules_from_file(config_file)

    assert len(rules) == 1
    assert rules[0].name == "payment-critical-route"
    assert rules[0].match["labels.service"] == "payment-api"
    assert rules[0].enrich_tools == ["query_logs", "query_prometheus"]
