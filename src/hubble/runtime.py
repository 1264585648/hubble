from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from hubble.alerts.models import Alert
from hubble.alerts.service import AlertLifecycleService
from hubble.channels.base import ChannelRegistry, ConsoleChannelAdapter
from hubble.channels.models import ChannelMessage, IncomingChannelMessage
from hubble.events.bus import InMemoryEventBus
from hubble.events.models import EventEnvelope
from hubble.incidents.models import Incident
from hubble.incidents.service import IncidentLifecycleService
from hubble.policies.models import PolicyDecision
from hubble.policies.service import PolicyEngine
from hubble.reasoning.models import Analysis
from hubble.reasoning.service import ReasoningService


@dataclass(slots=True)
class AlertPipelineResult:
    event: EventEnvelope
    alert: Alert
    incident: Incident
    policy: PolicyDecision
    analysis: Analysis
    duplicate: bool = False


class HubbleRuntime:
    """Event-driven runtime that wires each layer through stable contracts."""

    def __init__(
        self,
        *,
        event_bus: InMemoryEventBus | None = None,
        alert_lifecycle: AlertLifecycleService | None = None,
        incident_lifecycle: IncidentLifecycleService | None = None,
        policy_engine: PolicyEngine | None = None,
        reasoning_service: ReasoningService | None = None,
        channel_registry: ChannelRegistry | None = None,
    ) -> None:
        self.event_bus = event_bus or InMemoryEventBus()
        self.alert_lifecycle = alert_lifecycle or AlertLifecycleService()
        self.incident_lifecycle = incident_lifecycle or IncidentLifecycleService()
        self.policy_engine = policy_engine or PolicyEngine()
        self.reasoning_service = reasoning_service or ReasoningService()
        self.channel_registry = channel_registry or ChannelRegistry()

        if "console" not in self.channel_registry.list_names():
            self.channel_registry.register(ConsoleChannelAdapter())

    async def ingest_webhook(self, source: str, payload: dict[str, Any]) -> AlertPipelineResult:
        event = EventEnvelope(
            type="alert.ingested",
            source=source,
            subject=_event_subject(payload),
            data=payload,
        )
        await self.event_bus.publish(event)
        return await self.process_alert_event(event)

    async def process_alert_event(self, event: EventEnvelope) -> AlertPipelineResult:
        lifecycle_result = self.alert_lifecycle.handle_event(event)
        alert = lifecycle_result.alert

        incident = self.incident_lifecycle.attach_alert(alert)
        policy = self.policy_engine.evaluate(alert, incident)
        analysis = await self.reasoning_service.analyze(
            alert=alert,
            incident=incident,
            policy=policy,
        )
        incident.current_summary = analysis.summary
        incident.last_analysis_id = analysis.id

        if policy.should_notify and not lifecycle_result.is_duplicate:
            await self.channel_registry.send(
                _build_channel_message(alert, incident, analysis),
                channels=policy.channels,
            )

        await self.event_bus.publish(
            EventEnvelope(
                type="analysis.finished",
                source="hubble.reasoning",
                subject=analysis.incident_id,
                data=analysis.model_dump(mode="json"),
                trace_id=event.trace_id,
                tenant_id=event.tenant_id,
            )
        )

        return AlertPipelineResult(
            event=event,
            alert=alert,
            incident=incident,
            policy=policy,
            analysis=analysis,
            duplicate=lifecycle_result.is_duplicate,
        )

    async def handle_channel_message(self, message: IncomingChannelMessage) -> str:
        incident = self.incident_lifecycle.get(message.incident_id or "")
        if not incident:
            return "没有找到绑定的 Incident。请在告警线程中追问，或提供 incident_id。"

        return (
            f"Incident: {incident.id}\n"
            f"状态: {incident.status}\n"
            f"摘要: {incident.current_summary or '暂无'}\n"
            f"你的问题: {message.text}\n"
            "当前版本已完成会话入口，下一步会接入工具调用和多轮上下文。"
        )


def _event_subject(payload: dict[str, Any]) -> str | None:
    labels = payload.get("labels") or {}
    return (
        payload.get("title")
        or payload.get("alertname")
        or labels.get("alertname")
        or payload.get("name")
    )


def _build_channel_message(alert: Alert, incident: Incident, analysis: Analysis) -> ChannelMessage:
    causes = "\n".join(f"- {item}" for item in analysis.possible_causes) or "- 暂无"
    actions = "\n".join(f"- {item}" for item in analysis.recommended_actions) or "- 暂无"

    body = (
        f"## 发生了什么\n{analysis.summary}\n\n"
        f"## Incident\n{incident.id}\n\n"
        f"## 严重程度\n来源级别：{alert.severity}\n分析级别：{analysis.severity}\n\n"
        f"## 可能原因\n{causes}\n\n"
        f"## 影响范围\n{analysis.impact or '待确认'}\n\n"
        f"## 建议动作\n{actions}\n\n"
        f"## 元信息\n"
        f"source={alert.source}\n"
        f"fingerprint={alert.fingerprint}\n"
        f"confidence={analysis.confidence:.2f}"
    )
    return ChannelMessage(
        title=f"[{analysis.severity.upper()}] {alert.title}",
        body=body,
        severity=analysis.severity,
        incident_id=incident.id,
        alert_id=alert.id,
        metadata={
            "source": alert.source,
            "fingerprint": alert.fingerprint,
            "analysis_id": analysis.id,
        },
    )
