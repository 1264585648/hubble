from __future__ import annotations

from hubble.alerts.models import Alert
from hubble.incidents.models import Incident
from hubble.policies.models import PolicyDecision
from hubble.reasoning.models import Analysis


class ReasoningService:
    """Model-independent reasoning boundary.

    The MVP implementation is deterministic. A future OpenAI-compatible provider should be
    plugged in behind this service without changing alert, policy, tool or channel layers.
    """

    provider_name = "echo"
    prompt_version = "builtin.echo.v1"

    async def analyze(
        self,
        *,
        alert: Alert,
        incident: Incident,
        policy: PolicyDecision,
    ) -> Analysis:
        return Analysis(
            alert_id=alert.id,
            incident_id=incident.id,
            summary=f"{alert.title}: {alert.description or 'No description provided.'}",
            severity=alert.severity,
            possible_causes=[
                "当前使用内置 Echo reasoning，仅返回基础分析。",
                "后续可接入 OpenAI-compatible provider 和工具增强上下文。",
            ],
            impact=(
                f"关联 Incident: {incident.id}; "
                f"受影响服务: {', '.join(incident.affected_services) or '待确认'}"
            ),
            recommended_actions=[
                "确认告警是否仍在触发。",
                "检查最近发布、配置变更和依赖服务状态。",
                "根据 runbook 执行下一步排查。",
            ],
            confidence=0.2,
            model_provider=self.provider_name,
            prompt_version=self.prompt_version,
            raw_response=f"policy={policy.reason}",
        )
