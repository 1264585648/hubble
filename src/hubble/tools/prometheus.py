from __future__ import annotations

from typing import Any

import httpx

from hubble.core.models import ToolResult
from hubble.tools.base import Tool, ToolContext


class PrometheusQueryTool(Tool):
    """Read-only Prometheus query tool.

    Supports instant queries via /api/v1/query and range queries via /api/v1/query_range.
    """

    input_schema = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "PromQL expression."},
            "time": {"type": "string", "description": "Optional instant query time."},
            "start": {"type": "string", "description": "Range query start time."},
            "end": {"type": "string", "description": "Range query end time."},
            "step": {"type": "string", "description": "Range query step, e.g. 30s."},
            "timeout": {"type": "string", "description": "Prometheus query timeout, e.g. 10s."},
            "limit": {"type": "integer"},
            "range": {"type": "boolean", "description": "Force range query."},
        },
        "required": ["query"],
        "additionalProperties": True,
    }

    dangerous = False

    def __init__(
        self,
        *,
        name: str = "query_prometheus",
        base_url: str,
        description: str = "Query Prometheus metrics.",
        headers: dict[str, str] | None = None,
        timeout_seconds: float = 10.0,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self.name = name
        self.description = description
        self.base_url = base_url.rstrip("/")
        self.headers = headers or {}
        self.timeout_seconds = timeout_seconds
        self.http_client = http_client

    async def run(self, params: dict[str, Any], context: ToolContext) -> ToolResult:
        query = params.get("query")
        if not isinstance(query, str) or not query.strip():
            return ToolResult(
                ok=False,
                error="Prometheus query is required",
                metadata={"error_type": "validation_error", "tool_name": self.name},
            )

        endpoint = "/api/v1/query_range" if _is_range_query(params) else "/api/v1/query"
        request_params = _build_request_params(params, query=query, range_query=endpoint.endswith("query_range"))

        try:
            response = await self._get(endpoint, request_params)
        except httpx.TimeoutException:
            return ToolResult(
                ok=False,
                error=f"Prometheus query timed out after {self.timeout_seconds:.2f}s",
                metadata={"error_type": "timeout", "tool_name": self.name},
            )
        except httpx.HTTPError as exc:
            return ToolResult(
                ok=False,
                error=str(exc),
                metadata={"error_type": type(exc).__name__, "tool_name": self.name},
            )

        try:
            payload = response.json()
        except ValueError:
            return ToolResult(
                ok=False,
                error="Prometheus response is not JSON",
                metadata={"status_code": response.status_code, "tool_name": self.name},
            )

        if not isinstance(payload, dict):
            return ToolResult(ok=False, error="Prometheus response must be an object")

        ok = response.status_code < 400 and payload.get("status") == "success"
        error = None if ok else str(payload.get("error") or f"HTTP {response.status_code}")
        return ToolResult(
            ok=ok,
            data=payload.get("data"),
            error=error,
            metadata={
                "tool_name": self.name,
                "status_code": response.status_code,
                "prometheus_status": payload.get("status"),
                "endpoint": endpoint,
                "warnings": payload.get("warnings") or [],
                "infos": payload.get("infos") or [],
                "context": {
                    "alert_id": context.alert_id,
                    "incident_id": context.incident_id,
                },
            },
        )

    async def _get(self, endpoint: str, params: dict[str, Any]) -> httpx.Response:
        url = f"{self.base_url}{endpoint}"
        request_kwargs = {
            "headers": self.headers,
            "params": params,
            "timeout": httpx.Timeout(self.timeout_seconds),
        }
        if self.http_client:
            return await self.http_client.get(url, **request_kwargs)
        async with httpx.AsyncClient() as client:
            return await client.get(url, **request_kwargs)


def _is_range_query(params: dict[str, Any]) -> bool:
    if params.get("range") is True:
        return True
    return bool(params.get("start") and params.get("end") and params.get("step"))


def _build_request_params(
    params: dict[str, Any],
    *,
    query: str,
    range_query: bool,
) -> dict[str, Any]:
    request_params: dict[str, Any] = {"query": query}
    optional_keys = ["timeout", "limit"]
    optional_keys.extend(["start", "end", "step"] if range_query else ["time"])
    for key in optional_keys:
        value = params.get(key)
        if value is not None:
            request_params[key] = value
    return request_params
