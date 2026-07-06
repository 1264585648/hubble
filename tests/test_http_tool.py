from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from hubble.core.models import ToolResult
from hubble.policies.models import PolicyRule
from hubble.policies.service import PolicyEngine
from hubble.runtime import HubbleRuntime
from hubble.tools.base import Tool, ToolContext, ToolRegistry
from hubble.tools.http import HttpTool


@pytest.mark.asyncio
async def test_http_tool_renders_template_and_redacts_sensitive_fields() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode("utf-8"))
        assert body["service"] == "payment-api"
        assert body["env"] == "prod"
        assert request.headers["authorization"] == "Bearer super-secret"
        return httpx.Response(
            200,
            json={"service": body["service"], "token": "response-token"},
            headers={"set-cookie": "session=secret"},
            request=request,
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    tool = HttpTool(
        name="query_logs",
        method="POST",
        url="https://logs.internal/query?token=request-token",
        headers={"Authorization": "Bearer super-secret"},
        body_template={"service": "{service}", "env": "{labels.env}"},
        http_client=client,
    )

    try:
        result = await tool.run(
            {"service": "payment-api", "labels": {"env": "prod"}},
            ToolContext(alert_id="a1", incident_id="i1"),
        )
    finally:
        await client.aclose()

    assert result.ok is True
    assert result.data["body"]["service"] == "payment-api"
    assert result.data["body"]["token"] == "[REDACTED]"
    assert result.data["headers"]["set-cookie"] == "[REDACTED]"
    assert "request-token" not in result.metadata["url"]


@pytest.mark.asyncio
async def test_http_tool_timeout_returns_structured_error() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("upstream timeout", request=request)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    tool = HttpTool(
        name="query_logs",
        method="GET",
        url="https://logs.internal/query",
        timeout_seconds=0.01,
        http_client=client,
    )

    try:
        result = await tool.run({}, ToolContext())
    finally:
        await client.aclose()

    assert result.ok is False
    assert result.metadata["error_type"] == "timeout"
    assert "timed out" in result.error


@pytest.mark.asyncio
async def test_tool_registry_blocks_dangerous_tool_by_default() -> None:
    registry = ToolRegistry()
    registry.register(
        HttpTool(name="delete_service", method="DELETE", url="https://internal/delete")
    )

    result = await registry.run("delete_service", {})

    assert result.ok is False
    assert result.metadata["error_type"] == "confirmation_required"


class StaticContextTool(Tool):
    name = "context"
    description = "Return static context."

    async def run(self, params: dict[str, Any], context: ToolContext) -> ToolResult:
        return ToolResult(
            ok=True,
            data={
                "service": params["service"],
                "incident_id": context.incident_id,
            },
        )


@pytest.mark.asyncio
async def test_runtime_enrichment_tool_results_are_used_by_reasoning() -> None:
    registry = ToolRegistry()
    registry.register(StaticContextTool())
    runtime = HubbleRuntime(
        tool_registry=registry,
        policy_engine=PolicyEngine(
            [
                PolicyRule(
                    name="payment",
                    match={"labels.service": "payment-api"},
                    should_notify=False,
                    should_analyze=True,
                    enrich_tools=["context"],
                    channels=[],
                )
            ]
        ),
    )

    result = await runtime.ingest_webhook(
        "demo",
        {
            "title": "payment error rate high",
            "severity": "critical",
            "labels": {"service": "payment-api", "env": "prod"},
        },
    )

    assert len(result.tool_results) == 1
    assert result.tool_results[0].ok is True
    assert result.analysis is not None
    assert result.analysis.tool_results[0].data["service"] == "payment-api"
