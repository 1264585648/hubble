from __future__ import annotations

import json
from typing import Any

import httpx

from hubble.alerts.models import Alert
from hubble.incidents.models import Incident
from hubble.policies.models import PolicyDecision
from hubble.reasoning.models import Analysis


class ReasoningService:
    """Deterministic fallback reasoning service.

    This service is intentionally dependency-free. It is used when no model provider is
    configured or when a model provider fails.
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


class OpenAICompatibleReasoningService:
    """Reasoning service backed by an OpenAI-compatible chat completions API."""

    provider_name = "openai-compatible"
    prompt_version = "builtin.openai_compatible.v1"

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        timeout_seconds: float = 20.0,
        fallback: ReasoningService | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.fallback = fallback or ReasoningService()
        self.http_client = http_client

    async def analyze(
        self,
        *,
        alert: Alert,
        incident: Incident,
        policy: PolicyDecision,
    ) -> Analysis:
        try:
            payload = _build_chat_completion_payload(
                model=self.model,
                alert=alert,
                incident=incident,
                policy=policy,
            )
            response_json = await self._post_chat_completion(payload)
            content = _extract_message_content(response_json)
            analysis = _analysis_from_json_content(
                content,
                alert=alert,
                incident=incident,
                raw_response=content,
            )
            analysis.model_provider = self.provider_name
            analysis.prompt_version = self.prompt_version
            return analysis
        except Exception as exc:  # noqa: BLE001 - provider boundary must fallback safely
            fallback_analysis = await self.fallback.analyze(
                alert=alert,
                incident=incident,
                policy=policy,
            )
            fallback_analysis.raw_response = f"fallback_from={self.provider_name}; error={type(exc).__name__}"
            return fallback_analysis

    async def _post_chat_completion(self, payload: dict[str, Any]) -> dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        url = f"{self.base_url}/chat/completions"

        if self.http_client:
            response = await self.http_client.post(url, headers=headers, json=payload)
        else:
            timeout = httpx.Timeout(self.timeout_seconds)
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(url, headers=headers, json=payload)

        response.raise_for_status()
        data = response.json()
        if not isinstance(data, dict):
            raise ValueError("OpenAI-compatible response must be a JSON object")
        return data


def _build_chat_completion_payload(
    *,
    model: str,
    alert: Alert,
    incident: Incident,
    policy: PolicyDecision,
) -> dict[str, Any]:
    return {
        "model": model,
        "temperature": 0,
        "response_format": {"type": "json_object"},
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are Hubble, an AI alert analysis assistant. "
                    "Return only valid JSON matching this schema: "
                    "summary:string, severity:string, possible_causes:string[], "
                    "impact:string, recommended_actions:string[], confidence:number."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "alert": alert.model_dump(mode="json"),
                        "incident": incident.model_dump(mode="json"),
                        "policy": policy.model_dump(mode="json"),
                    },
                    ensure_ascii=False,
                ),
            },
        ],
    }


def _extract_message_content(response_json: dict[str, Any]) -> str:
    choices = response_json.get("choices")
    if not isinstance(choices, list) or not choices:
        raise ValueError("missing choices")
    message = choices[0].get("message") if isinstance(choices[0], dict) else None
    if not isinstance(message, dict):
        raise ValueError("missing message")
    content = message.get("content")
    if not isinstance(content, str) or not content.strip():
        raise ValueError("missing message content")
    return content


def _analysis_from_json_content(
    content: str,
    *,
    alert: Alert,
    incident: Incident,
    raw_response: str,
) -> Analysis:
    payload = json.loads(content)
    if not isinstance(payload, dict):
        raise ValueError("analysis content must be a JSON object")

    return Analysis(
        alert_id=alert.id,
        incident_id=incident.id,
        summary=str(payload.get("summary") or alert.title),
        severity=str(payload.get("severity") or alert.severity),
        possible_causes=_string_list(payload.get("possible_causes")),
        impact=str(payload.get("impact") or ""),
        recommended_actions=_string_list(payload.get("recommended_actions")),
        confidence=float(payload.get("confidence") or 0.0),
        raw_response=raw_response,
    )


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]
