import json

import httpx
import pytest

from hubble.policies.models import PolicyDecision
from hubble.reasoning.config import load_reasoning_service_from_file
from hubble.reasoning.service import OpenAICompatibleReasoningService, ReasoningService
from hubble.runtime import HubbleRuntime


@pytest.mark.asyncio
async def test_openai_compatible_provider_returns_structured_analysis() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/chat/completions"
        assert request.headers["authorization"] == "Bearer test-key"
        body = json.loads(request.content.decode("utf-8"))
        assert body["model"] == "test-model"
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "summary": "Payment API error rate is elevated.",
                                    "severity": "critical",
                                    "possible_causes": ["recent deployment", "database latency"],
                                    "impact": "Checkout may fail for some users.",
                                    "recommended_actions": ["check deployment", "query logs"],
                                    "confidence": 0.86,
                                }
                            )
                        }
                    }
                ]
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    service = OpenAICompatibleReasoningService(
        base_url="https://model.example.com/v1",
        api_key="test-key",
        model="test-model",
        http_client=client,
    )
    runtime = HubbleRuntime(reasoning_service=service)

    result = await runtime.ingest_webhook(
        "demo",
        {
            "title": "payment-api error rate is high",
            "description": "HTTP 5xx error rate exceeded 5% for 5 minutes.",
            "severity": "critical",
            "labels": {"service": "payment-api", "env": "prod"},
        },
    )

    await client.aclose()

    assert result.analysis is not None
    assert result.analysis.model_provider == "openai-compatible"
    assert result.analysis.summary == "Payment API error rate is elevated."
    assert result.analysis.confidence == 0.86
    assert result.analysis.possible_causes == ["recent deployment", "database latency"]


@pytest.mark.asyncio
async def test_openai_compatible_provider_falls_back_to_echo_on_bad_response() -> None:
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"choices": []})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    service = OpenAICompatibleReasoningService(
        base_url="https://model.example.com/v1",
        api_key="test-key",
        model="test-model",
        http_client=client,
    )
    runtime = HubbleRuntime(reasoning_service=service)

    result = await runtime.ingest_webhook(
        "demo",
        {
            "title": "fallback alert",
            "description": "bad model response should fallback",
            "severity": "high",
            "labels": {"service": "demo", "env": "prod"},
        },
    )

    await client.aclose()

    assert result.analysis is not None
    assert result.analysis.model_provider == "echo"
    assert "fallback_from=openai-compatible" in (result.analysis.raw_response or "")


def test_reasoning_config_falls_back_without_env(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("HUBBLE_MODEL_BASE_URL", raising=False)
    monkeypatch.delenv("HUBBLE_MODEL_API_KEY", raising=False)
    monkeypatch.delenv("HUBBLE_MODEL_NAME", raising=False)

    config_file = tmp_path / "hubble.yaml"
    config_file.write_text(
        """
model:
  providers:
    - name: openai-compatible
      type: openai_compatible
      enabled: true
      base_url_env: HUBBLE_MODEL_BASE_URL
      api_key_env: HUBBLE_MODEL_API_KEY
      model_env: HUBBLE_MODEL_NAME
""",
        encoding="utf-8",
    )

    service = load_reasoning_service_from_file(config_file)

    assert isinstance(service, ReasoningService)


def test_reasoning_config_loads_openai_provider_with_env(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("HUBBLE_MODEL_BASE_URL", "https://model.example.com/v1")
    monkeypatch.setenv("HUBBLE_MODEL_API_KEY", "secret-key")
    monkeypatch.setenv("HUBBLE_MODEL_NAME", "test-model")

    config_file = tmp_path / "hubble.yaml"
    config_file.write_text(
        """
model:
  providers:
    - name: openai-compatible
      type: openai_compatible
      enabled: true
      base_url_env: HUBBLE_MODEL_BASE_URL
      api_key_env: HUBBLE_MODEL_API_KEY
      model_env: HUBBLE_MODEL_NAME
      timeout_seconds: 7
""",
        encoding="utf-8",
    )

    service = load_reasoning_service_from_file(config_file)

    assert isinstance(service, OpenAICompatibleReasoningService)
    assert service.base_url == "https://model.example.com/v1"
    assert service.model == "test-model"
    assert service.timeout_seconds == 7
