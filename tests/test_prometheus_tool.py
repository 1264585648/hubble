import httpx
import pytest

from hubble.tools.base import ToolContext
from hubble.tools.config import load_tool_registry_from_file
from hubble.tools.prometheus import PrometheusQueryTool


@pytest.mark.asyncio
async def test_prometheus_instant_query() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/query"
        assert request.url.params["query"] == "up"
        return httpx.Response(
            200,
            json={
                "status": "success",
                "data": {
                    "resultType": "vector",
                    "result": [{"metric": {"job": "api"}, "value": [1, "1"]}],
                },
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    tool = PrometheusQueryTool(base_url="https://prometheus.example.com", http_client=client)

    result = await tool.run({"query": "up"}, ToolContext(alert_id="a1", incident_id="i1"))
    await client.aclose()

    assert result.ok is True
    assert result.data["resultType"] == "vector"
    assert result.metadata["endpoint"] == "/api/v1/query"
    assert result.metadata["context"]["incident_id"] == "i1"


@pytest.mark.asyncio
async def test_prometheus_range_query() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/query_range"
        assert request.url.params["query"] == "rate(http_requests_total[5m])"
        assert request.url.params["start"] == "100"
        assert request.url.params["end"] == "200"
        assert request.url.params["step"] == "30s"
        return httpx.Response(
            200,
            json={
                "status": "success",
                "data": {
                    "resultType": "matrix",
                    "result": [{"metric": {"job": "api"}, "values": [[100, "1"]]}],
                },
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    tool = PrometheusQueryTool(base_url="https://prometheus.example.com", http_client=client)

    result = await tool.run(
        {
            "query": "rate(http_requests_total[5m])",
            "start": "100",
            "end": "200",
            "step": "30s",
        },
        ToolContext(),
    )
    await client.aclose()

    assert result.ok is True
    assert result.data["resultType"] == "matrix"
    assert result.metadata["endpoint"] == "/api/v1/query_range"


@pytest.mark.asyncio
async def test_prometheus_query_validation() -> None:
    tool = PrometheusQueryTool(base_url="https://prometheus.example.com")

    result = await tool.run({}, ToolContext())

    assert result.ok is False
    assert result.metadata["error_type"] == "validation_error"


def test_prometheus_tool_loads_from_config(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("HUBBLE_PROMETHEUS_BASE_URL", "https://prometheus.example.com")
    monkeypatch.setenv("HUBBLE_PROMETHEUS_TOKEN", "secret-token")
    config_file = tmp_path / "hubble.yaml"
    config_file.write_text(
        """
tools:
  enabled: true
  registry:
    - name: query_prometheus
      type: prometheus
      enabled: true
      base_url_env: HUBBLE_PROMETHEUS_BASE_URL
      bearer_token_env: HUBBLE_PROMETHEUS_TOKEN
      timeout_seconds: 3
""",
        encoding="utf-8",
    )

    registry = load_tool_registry_from_file(config_file)
    tool = registry.get("query_prometheus")

    assert tool is not None
    assert tool.spec.name == "query_prometheus"
    assert tool.spec.dangerous is False
    assert tool.spec.timeout_seconds == 3
