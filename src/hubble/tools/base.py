from __future__ import annotations

import asyncio
import time
from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, Field

from hubble.core.models import ToolResult


class ToolSpec(BaseModel):
    """Stable public description of a tool capability."""

    name: str
    description: str = ""
    input_schema: dict[str, Any] = Field(
        default_factory=lambda: {"type": "object", "additionalProperties": True}
    )
    dangerous: bool = False
    timeout_seconds: float = 10.0
    metadata: dict[str, Any] = Field(default_factory=dict)


class ToolContext(BaseModel):
    """Runtime context passed to tools without coupling them to alert internals."""

    alert_id: str | None = None
    incident_id: str | None = None
    operator_id: str | None = None
    trace_id: str | None = None
    tenant_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class Tool(ABC):
    """Base interface for tools such as log query, database query or API check."""

    name: str
    description: str = ""
    input_schema: dict[str, Any] = {"type": "object", "additionalProperties": True}
    dangerous: bool = False
    timeout_seconds: float = 10.0

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name=self.name,
            description=self.description,
            input_schema=self.input_schema,
            dangerous=self.dangerous,
            timeout_seconds=self.timeout_seconds,
        )

    @abstractmethod
    async def run(self, params: dict[str, Any], context: ToolContext) -> ToolResult:
        """Run the tool with validated params."""


class ToolRegistry:
    """In-memory tool registry and execution guard."""

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        if tool.name in self._tools:
            raise ValueError(f"Tool already registered: {tool.name}")
        self._tools[tool.name] = tool

    def get(self, tool_name: str) -> Tool | None:
        return self._tools.get(tool_name)

    def list_tools(self) -> list[Tool]:
        return list(self._tools.values())

    def list_specs(self) -> list[ToolSpec]:
        return [tool.spec for tool in self.list_tools()]

    async def run(
        self,
        tool_name: str,
        params: dict[str, Any] | None = None,
        context: ToolContext | None = None,
        *,
        allow_dangerous: bool = False,
    ) -> ToolResult:
        tool = self._tools.get(tool_name)
        if not tool:
            return ToolResult(
                ok=False,
                error=f"Unknown tool: {tool_name}",
                metadata={"error_type": "unknown_tool", "tool_name": tool_name},
            )

        if tool.dangerous and not allow_dangerous:
            return ToolResult(
                ok=False,
                error=f"Tool requires confirmation: {tool_name}",
                metadata={"error_type": "confirmation_required", "tool_name": tool_name},
            )

        started = time.perf_counter()
        try:
            result = await asyncio.wait_for(
                tool.run(params or {}, context or ToolContext()),
                timeout=tool.timeout_seconds,
            )
        except TimeoutError:
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            return ToolResult(
                ok=False,
                error=f"Tool timed out after {tool.timeout_seconds:.2f}s: {tool_name}",
                elapsed_ms=elapsed_ms,
                metadata={"error_type": "timeout", "tool_name": tool_name},
            )
        except Exception as exc:  # noqa: BLE001 - plugin boundary should never crash runtime
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            return ToolResult(
                ok=False,
                error=str(exc),
                elapsed_ms=elapsed_ms,
                metadata={"error_type": type(exc).__name__, "tool_name": tool_name},
            )

        if result.elapsed_ms is None:
            result.elapsed_ms = int((time.perf_counter() - started) * 1000)
        result.metadata.setdefault("tool_name", tool_name)
        return result
