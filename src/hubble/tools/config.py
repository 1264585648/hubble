from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

from hubble.tools.base import Tool, ToolRegistry
from hubble.tools.http import HttpTool
from hubble.tools.prometheus import PrometheusQueryTool


def load_tool_registry_from_file(path: str | Path) -> ToolRegistry:
    registry = ToolRegistry()
    config_path = Path(path)
    if not config_path.exists():
        return registry

    with config_path.open("r", encoding="utf-8") as file:
        raw = yaml.safe_load(file) or {}

    if not _get_nested(raw, ["tools", "enabled"], default=True):
        return registry

    tool_configs = _get_nested(raw, ["tools", "registry"], default=[])
    if not isinstance(tool_configs, list):
        return registry

    for tool_config in tool_configs:
        if not isinstance(tool_config, dict) or not tool_config.get("enabled"):
            continue
        tool: Tool | None = None
        if tool_config.get("type") == "http":
            tool = _build_http_tool(tool_config)
        elif tool_config.get("type") == "prometheus":
            tool = _build_prometheus_tool(tool_config)
        if tool:
            _safe_register(registry, tool)

    return registry


def _build_http_tool(config: dict[str, Any]) -> HttpTool | None:
    url = str(config.get("url") or "")
    url_env = config.get("url_env")
    if not url and url_env:
        url = os.getenv(str(url_env), "")
    if not url:
        return None

    headers = _headers_from_config(config)
    return HttpTool(
        name=str(config.get("name") or "http_tool"),
        description=str(config.get("description") or ""),
        method=str(config.get("method") or "GET"),
        url=url,
        headers=headers,
        body_template=config.get("body_template"),
        timeout_seconds=float(config.get("timeout_seconds") or 10.0),
        dangerous=None if "dangerous" not in config else bool(config.get("dangerous")),
        sensitive_fields=_string_list(config.get("sensitive_fields")),
    )


def _build_prometheus_tool(config: dict[str, Any]) -> PrometheusQueryTool | None:
    base_url = str(config.get("base_url") or "")
    base_url_env = config.get("base_url_env")
    if not base_url and base_url_env:
        base_url = os.getenv(str(base_url_env), "")
    if not base_url:
        return None

    return PrometheusQueryTool(
        name=str(config.get("name") or "query_prometheus"),
        description=str(config.get("description") or "Query Prometheus metrics."),
        base_url=base_url,
        headers=_headers_from_config(config),
        timeout_seconds=float(config.get("timeout_seconds") or 10.0),
    )


def _headers_from_config(config: dict[str, Any]) -> dict[str, str]:
    headers: dict[str, str] = {}
    raw_headers = config.get("headers")
    if isinstance(raw_headers, dict):
        headers.update({str(key): str(value) for key, value in raw_headers.items()})

    headers_env = config.get("headers_env")
    if isinstance(headers_env, dict):
        for header_name, env_name in headers_env.items():
            value = os.getenv(str(env_name), "")
            if value:
                headers[str(header_name)] = value

    bearer_token_env = config.get("bearer_token_env")
    if bearer_token_env:
        token = os.getenv(str(bearer_token_env), "")
        if token:
            headers["Authorization"] = f"Bearer {token}"

    return headers


def _safe_register(registry: ToolRegistry, tool: Tool) -> None:
    if registry.get(tool.name):
        return
    registry.register(tool)


def _get_nested(data: dict[str, Any], keys: list[str], *, default: Any) -> Any:
    current: Any = data
    for key in keys:
        if not isinstance(current, dict):
            return default
        current = current.get(key)
    return default if current is None else current


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]
