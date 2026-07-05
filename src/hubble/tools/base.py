from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from hubble.core.models import ToolResult


@dataclass(slots=True)
class ToolContext:
    alert_id: str | None = None
    incident_id: str | None = None
    operator_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class Tool(ABC):
    """Base interface for tools such as log query, database query or API check."""

    name: str
    description: str
    dangerous: bool = False
    timeout_seconds: int = 10

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

    def list_tools(self) -> list[Tool]:
        return list(self._tools.values())

    async def run(
        self,
        tool_name: str,
        params: dict[str, Any],
        context: ToolContext | None = None,
        *,
        allow_dangerous: bool = False,
    ) -> ToolResult:
        tool = self._tools.get(tool_name)
        if not tool:
            return ToolResult(ok=False, error=f"Unknown tool: {tool_name}")

        if tool.dangerous and not allow_dangerous:
            return ToolResult(ok=False, error=f"Tool requires confirmation: {tool_name}")

        started = time.perf_counter()
        try:
            result = await tool.run(params, context or ToolContext())
        except Exception as exc:  # noqa: BLE001 - plugin boundary should never crash the runtime
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            return ToolResult(ok=False, error=str(exc), elapsed_ms=elapsed_ms)

        if result.elapsed_ms is None:
            result.elapsed_ms = int((time.perf_counter() - started) * 1000)
        return result
