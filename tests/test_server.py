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
