from __future__ import annotations

import re
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import httpx

from hubble.core.models import ToolResult
from hubble.tools.base import Tool, ToolContext

READONLY_METHODS = {"GET", "HEAD", "OPTIONS"}
REDACTED = "[REDACTED]"
DEFAULT_SENSITIVE_FIELDS = {
    "authorization",
    "cookie",
    "set-cookie",
    "token",
    "access_token",
    "api_key",
    "apikey",
    "password",
    "passwd",
    "secret",
    "webhook",
    "signature",
}
_PLACEHOLDER_RE = re.compile(r"\{([a-zA-Z0-9_.-]+)\}")


class HttpTool(Tool):
    """Configurable HTTP tool for querying internal read-only APIs."""

    input_schema = {
        "type": "object",
        "properties": {
            "query": {"type": "object", "description": "Optional query parameters."},
            "body": {"description": "Optional request body when no body_template is configured."},
            "timeout_seconds": {"type": "number"},
        },
        "additionalProperties": True,
    }

    def __init__(
        self,
        *,
        name: str,
        url: str,
        method: str = "GET",
        description: str = "",
        headers: dict[str, str] | None = None,
        body_template: Any | None = None,
        timeout_seconds: float = 10.0,
        dangerous: bool | None = None,
        sensitive_fields: list[str] | None = None,
        http_client: httpx.AsyncClient | None = None,
        max_response_chars: int = 20000,
    ) -> None:
        self.name = name
        self.description = description or f"HTTP {method.upper()} {url}"
        self.url = url
        self.method = method.upper()
        self.headers = headers or {}
        self.body_template = body_template
        self.timeout_seconds = float(timeout_seconds)
        self.dangerous = self.method not in READONLY_METHODS if dangerous is None else dangerous
        self.sensitive_fields = {
            *DEFAULT_SENSITIVE_FIELDS,
            *(field.lower() for field in (sensitive_fields or [])),
        }
        self.http_client = http_client
        self.max_response_chars = max_response_chars

    async def run(self, params: dict[str, Any], context: ToolContext) -> ToolResult:
        render_context = _build_render_context(params, context)
        url = _render_string(self.url, render_context)
        headers = {
            key: _render_string(str(value), render_context) for key, value in self.headers.items()
        }
        timeout_seconds = float(params.get("timeout_seconds") or self.timeout_seconds)
        request_kwargs: dict[str, Any] = {
            "headers": headers,
            "timeout": httpx.Timeout(timeout_seconds),
        }

        query = params.get("query")
        if isinstance(query, dict):
            request_kwargs["params"] = query

        body = _render_value(self.body_template, render_context)
        if body is None:
            body = params.get("body")
        if body is not None and self.method not in {"GET", "HEAD"}:
            if isinstance(body, str):
                request_kwargs["content"] = body
            else:
                request_kwargs["json"] = body

        try:
            response = await self._request(url, request_kwargs)
        except httpx.TimeoutException:
            return ToolResult(
                ok=False,
                error=f"HTTP tool timed out after {timeout_seconds:.2f}s",
                metadata={
                    "error_type": "timeout",
                    "method": self.method,
                    "url": _redact_url(url, self.sensitive_fields),
                },
            )
        except httpx.HTTPError as exc:
            return ToolResult(
                ok=False,
                error=_redact_value(str(exc), self.sensitive_fields),
                metadata={
                    "error_type": type(exc).__name__,
                    "method": self.method,
                    "url": _redact_url(url, self.sensitive_fields),
                },
            )

        response_body = _response_body(response, self.max_response_chars)
        data = {
            "status_code": response.status_code,
            "headers": _redact_value(dict(response.headers), self.sensitive_fields),
            "body": _redact_value(response_body, self.sensitive_fields),
        }
        ok = response.status_code < 400
        return ToolResult(
            ok=ok,
            data=data,
            error=None if ok else f"HTTP {response.status_code}",
            metadata={
                "method": self.method,
                "url": _redact_url(str(response.request.url), self.sensitive_fields),
                "status_code": response.status_code,
            },
        )

    async def _request(self, url: str, request_kwargs: dict[str, Any]) -> httpx.Response:
        if self.http_client:
            return await self.http_client.request(self.method, url, **request_kwargs)

        async with httpx.AsyncClient() as client:
            return await client.request(self.method, url, **request_kwargs)


def _build_render_context(params: dict[str, Any], context: ToolContext) -> dict[str, Any]:
    return {
        "params": params,
        "context": context.model_dump(),
        "alert": params.get("alert") or {},
        "incident": params.get("incident") or {},
        "labels": params.get("labels") or {},
        "annotations": params.get("annotations") or {},
        "source": params.get("source"),
        **params,
    }


def _render_value(value: Any, data: dict[str, Any]) -> Any:
    if value is None:
        return None
    if isinstance(value, str):
        return _render_string(value, data)
    if isinstance(value, list):
        return [_render_value(item, data) for item in value]
    if isinstance(value, dict):
        return {key: _render_value(item, data) for key, item in value.items()}
    return value


def _render_string(value: str, data: dict[str, Any]) -> str:
    def replace(match: re.Match[str]) -> str:
        resolved = _lookup(data, match.group(1))
        return "" if resolved is None else str(resolved)

    return _PLACEHOLDER_RE.sub(replace, value)


def _lookup(data: dict[str, Any], path: str) -> Any:
    current: Any = data
    for part in path.split("."):
        if isinstance(current, dict):
            current = current.get(part)
        else:
            current = getattr(current, part, None)
        if current is None:
            return None
    return current


def _response_body(response: httpx.Response, max_chars: int) -> Any:
    content_type = response.headers.get("content-type", "")
    if "application/json" in content_type:
        try:
            return response.json()
        except ValueError:
            pass
    return response.text[:max_chars]


def _is_sensitive_key(key: str, sensitive_fields: set[str]) -> bool:
    lowered = key.lower()
    return lowered in sensitive_fields or any(field in lowered for field in sensitive_fields)


def _redact_value(value: Any, sensitive_fields: set[str]) -> Any:
    if isinstance(value, dict):
        redacted: dict[Any, Any] = {}
        for key, item in value.items():
            if _is_sensitive_key(str(key), sensitive_fields):
                redacted[key] = REDACTED
            else:
                redacted[key] = _redact_value(item, sensitive_fields)
        return redacted
    if isinstance(value, list):
        return [_redact_value(item, sensitive_fields) for item in value]
    if isinstance(value, str):
        redacted = value
        for key in sensitive_fields:
            redacted = re.sub(
                rf"({re.escape(key)}=)[^&\s]+",
                rf"\1{REDACTED}",
                redacted,
                flags=re.IGNORECASE,
            )
        return redacted
    return value


def _redact_url(url: str, sensitive_fields: set[str]) -> str:
    try:
        parts = urlsplit(url)
        query = [
            (key, REDACTED if _is_sensitive_key(key, sensitive_fields) else value)
            for key, value in parse_qsl(parts.query, keep_blank_values=True)
        ]
        return urlunsplit(
            (parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment)
        )
    except ValueError:
        return _redact_value(url, sensitive_fields)
