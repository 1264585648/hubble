from __future__ import annotations

from typing import Any

from hubble.core.models import AlertAnalysis, AlertEvent, Notification, SessionMessage
from hubble.model.base import ModelRouter
from hubble.notifiers.base import NotifierRegistry
from hubble.tools.base import ToolRegistry


class AlertEngine:
    """Main orchestration engine for alert processing."""

    def __init__(
        self,
        *,
        model_router: ModelRouter,
        tool_registry: ToolRegistry,
        notifier_registry: NotifierRegistry,
        default_channels: list[str] | None = None,
    ) -> None:
        self.model_router = model_router
        self.tool_registry = tool_registry
        self.notifier_registry = notifier_registry
        self.default_channels = default_channels or []

    async def handle_alert(self, alert: AlertEvent) -> AlertAnalysis:
        """Process one alert from ingress to model analysis and notification."""
        alert.fingerprint = alert.stable_fingerprint()
        context = self._build_context(alert)
        analysis = await self.model_router.analyze_alert(alert, context)
        notification = self._build_notification(alert, analysis)
        await self.notifier_registry.send(notification, channels=self.default_channels or None)
        return analysis

    async def handle_session_message(self, message: SessionMessage) -> str:
        """Handle a user follow-up message from a chat session.

        This is intentionally simple for the MVP. Later it should load alert/incident context,
        route to a conversation-aware model prompt, optionally execute tools and reply in thread.
        """
        known_tools = ", ".join(tool.name for tool in self.tool_registry.list_tools()) or "none"
        return (
            "已收到你的追问。当前会话能力仍是 MVP 骨架。\n"
            f"问题：{message.text}\n"
            f"可用工具：{known_tools}\n"
            "下一步会接入告警上下文、工具调用和多轮记忆。"
        )

    def _build_context(self, alert: AlertEvent) -> dict[str, Any]:
        return {
            "fingerprint": alert.fingerprint,
            "available_tools": [
                {
                    "name": tool.name,
                    "description": tool.description,
                    "dangerous": tool.dangerous,
                }
                for tool in self.tool_registry.list_tools()
            ],
        }

    def _build_notification(self, alert: AlertEvent, analysis: AlertAnalysis) -> Notification:
        causes = "\n".join(f"- {item}" for item in analysis.possible_causes) or "- 暂无"
        actions = "\n".join(f"- {item}" for item in analysis.recommended_actions) or "- 暂无"

        body = (
            f"## 发生了什么\n{analysis.summary}\n\n"
            f"## 严重程度\n来源级别：{alert.severity}\n模型判断：{analysis.severity}\n\n"
            f"## 可能原因\n{causes}\n\n"
            f"## 影响范围\n{analysis.impact or '待确认'}\n\n"
            f"## 建议动作\n{actions}\n\n"
            f"## 元信息\n"
            f"source={alert.source}\n"
            f"fingerprint={alert.fingerprint}\n"
            f"confidence={analysis.confidence:.2f}"
        )
        return Notification(
            title=f"[{analysis.severity.upper()}] {alert.title}",
            body=body,
            severity=analysis.severity,
            alert_id=alert.id,
            metadata={"source": alert.source, "fingerprint": alert.fingerprint},
        )
