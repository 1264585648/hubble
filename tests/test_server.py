from fastapi.testclient import TestClient

from hubble.server import app


client = TestClient(app)


def test_healthz() -> None:
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_webhook_demo() -> None:
    response = client.post(
        "/webhook/demo",
        json={
            "title": "payment-api error rate is high",
            "description": "HTTP 5xx error rate exceeded 5% for 5 minutes.",
            "severity": "high",
            "labels": {"service": "payment-api", "env": "prod"},
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["event"]["type"] == "alert.ingested"
    assert body["intake"]["allowed"] is True
    assert body["filtered"] is False
    assert body["alert"]["severity"] == "high"
    assert body["incident"]["status"] == "open"
    assert body["analysis"]["severity"] == "high"
    assert "payment-api error rate is high" in body["analysis"]["summary"]


def test_alerts_and_incidents_are_queryable() -> None:
    alerts_response = client.get("/alerts")
    incidents_response = client.get("/incidents")

    assert alerts_response.status_code == 200
    assert incidents_response.status_code == 200
    assert isinstance(alerts_response.json(), list)
    assert isinstance(incidents_response.json(), list)


def test_intake_rule_can_filter_alerts() -> None:
    rule_response = client.post(
        "/intake-rules",
        json={
            "name": "drop dev low alerts",
            "enabled": True,
            "priority": 1,
            "match": {"labels.env": "dev", "data.severity": "low"},
            "action": "drop",
            "reason": "drop noisy dev alerts",
        },
    )
    assert rule_response.status_code == 200
    rule = rule_response.json()

    response = client.post(
        "/webhook/demo",
        json={
            "title": "dev low alert",
            "description": "noise",
            "severity": "low",
            "labels": {"service": "demo", "env": "dev"},
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["filtered"] is True
    assert body["intake"]["allowed"] is False
    assert body["alert"] is None
    assert body["incident"] is None
    assert body["analysis"] is None

    delete_response = client.delete(f"/intake-rules/{rule['id']}")
    assert delete_response.status_code == 200


def test_intake_rules_page_is_available() -> None:
    response = client.get("/admin/intake-rules")
    assert response.status_code == 200
    assert "Hubble 前置规则" in response.text
