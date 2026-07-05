from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from hubble.core.models import AlertAnalysis, AlertEvent


class ModelProvider(ABC):
    """Base interface for model providers."""

    name: str

    @abstractmethod
    async def analyze_alert(self, alert: AlertEvent, context: dict[str, Any]) -> AlertAnalysis:
        """Analyze an alert and return structured analysis."""


class EchoModelProvider(ModelProvider):
    """Development provider that does not call an LLM."""

    name = "echo"

    async def analyze_alert(self, alert: AlertEvent, context: dict[str, Any]) -> AlertAnalysis:
        return AlertAnalysis(
            summary=f"{alert.title}: {alert.description or 'No description provided.'}",
            severity=alert.severity,
            possible_causes=["模型未启用：当前使用 EchoModelProvider，仅返回基础摘要。"],
            impact="需要接入真实模型和工具后进一步判断。",
            recommended_actions=[
                "检查告警来源系统中的原始事件。",
                "确认是否存在近期发布、配置变更或依赖服务异常。",
                "根据 runbook 或值班手册执行下一步排查。",
            ],
            confidence=0.2,
            raw_response=str({"provider": self.name, "context_keys": list(context.keys())}),
        )


class ModelRouter:
    """Route alerts to model providers."""

    def __init__(self, default_provider: ModelProvider) -> None:
        self.default_provider = default_provider
        self.providers: dict[str, ModelProvider] = {default_provider.name: default_provider}

    def register(self, provider: ModelProvider) -> None:
        self.providers[provider.name] = provider

    async def analyze_alert(self, alert: AlertEvent, context: dict[str, Any] | None = None) -> AlertAnalysis:
        context = context or {}
        provider = self._select_provider(alert)
        return await provider.analyze_alert(alert, context)

    def _select_provider(self, alert: AlertEvent) -> ModelProvider:
        # Placeholder for future routing policies based on severity, cost, privacy and context length.
        return self.default_provider
