# ruff: noqa: E501
from __future__ import annotations

import os
from typing import Any

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from hubble.alerts.models import Alert
from hubble.channels.config import load_channel_registry_from_file
from hubble.core.models import ToolResult
from hubble.events.models import EventEnvelope
from hubble.incidents.models import Incident
from hubble.intake.models import IntakeDecision, IntakeDryRunRequest, IntakeDryRunResponse, IntakeRule
from hubble.policies.config import load_policy_rules_from_file
from hubble.policies.service import PolicyEngine
from hubble.reasoning.config import load_reasoning_service_from_file
from hubble.reasoning.models import Analysis
from hubble.runtime import HubbleRuntime
from hubble.tools.base import ToolContext, ToolSpec
from hubble.tools.config import load_tool_registry_from_file

app = FastAPI(
    title="Hubble Alert Bot",
    description="A pluggable AI-native AlertOps runtime.",
    version="0.1.0",
)

CONFIG_PATH = os.getenv("HUBBLE_CONFIG", "configs/hubble.example.yaml")
runtime = HubbleRuntime(
    policy_engine=PolicyEngine(load_policy_rules_from_file(CONFIG_PATH)),
    reasoning_service=load_reasoning_service_from_file(CONFIG_PATH),
    tool_registry=load_tool_registry_from_file(CONFIG_PATH),
    channel_registry=load_channel_registry_from_file(CONFIG_PATH),
)


class WebhookResponse(BaseModel):
    event: EventEnvelope
    intake: IntakeDecision
    alert: Alert | None = None
    incident: Incident | None = None
    analysis: Analysis | None = None
    tool_results: list[ToolResult] = []
    duplicate: bool = False
    filtered: bool = False


class IncidentTransitionRequest(BaseModel):
    actor: str | None = None


class ToolRunRequest(BaseModel):
    params: dict[str, Any] = {}
    context: ToolContext | None = None
    allow_dangerous: bool = False


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/webhook/alertmanager/{source}", response_model=list[WebhookResponse])
async def receive_alertmanager_webhook(
    source: str,
    payload: dict[str, Any],
) -> list[WebhookResponse]:
    results = await runtime.ingest_alertmanager_webhook(source, payload)
    return [
        WebhookResponse(
            event=result.event,
            intake=result.intake,
            alert=result.alert,
            incident=result.incident,
            analysis=result.analysis,
            tool_results=result.tool_results,
            duplicate=result.duplicate,
            filtered=result.filtered,
        )
        for result in results
    ]


@app.post("/webhook/{source}", response_model=WebhookResponse)
async def receive_webhook(source: str, payload: dict[str, Any]) -> WebhookResponse:
    result = await runtime.ingest_webhook(source, payload)
    return WebhookResponse(
        event=result.event,
        intake=result.intake,
        alert=result.alert,
        incident=result.incident,
        analysis=result.analysis,
        tool_results=result.tool_results,
        duplicate=result.duplicate,
        filtered=result.filtered,
    )


@app.get("/alerts", response_model=list[Alert])
async def list_alerts() -> list[Alert]:
    return runtime.alert_lifecycle.list_alerts()


@app.get("/incidents", response_model=list[Incident])
async def list_incidents() -> list[Incident]:
    return runtime.incident_lifecycle.list_incidents()


@app.post("/incidents/{incident_id}/ack", response_model=Incident)
async def ack_incident(
    incident_id: str,
    request: IncidentTransitionRequest | None = None,
) -> Incident:
    incident = runtime.incident_lifecycle.ack(
        incident_id,
        actor=request.actor if request else None,
    )
    if not incident:
        raise HTTPException(status_code=404, detail="incident not found")
    return incident


@app.post("/incidents/{incident_id}/resolve", response_model=Incident)
async def resolve_incident(
    incident_id: str,
    request: IncidentTransitionRequest | None = None,
) -> Incident:
    incident = runtime.incident_lifecycle.resolve(
        incident_id,
        actor=request.actor if request else None,
    )
    if not incident:
        raise HTTPException(status_code=404, detail="incident not found")
    return incident


@app.post("/incidents/{incident_id}/reopen", response_model=Incident)
async def reopen_incident(
    incident_id: str,
    request: IncidentTransitionRequest | None = None,
) -> Incident:
    incident = runtime.incident_lifecycle.reopen(
        incident_id,
        actor=request.actor if request else None,
    )
    if not incident:
        raise HTTPException(status_code=404, detail="incident not found")
    return incident


@app.get("/tools", response_model=list[ToolSpec])
async def list_tools() -> list[ToolSpec]:
    return runtime.list_tools()


@app.post("/tools/{tool_name}/run", response_model=ToolResult)
async def run_tool(tool_name: str, request: ToolRunRequest | None = None) -> ToolResult:
    request = request or ToolRunRequest()
    return await runtime.run_tool(
        tool_name,
        params=request.params,
        context=request.context,
        allow_dangerous=request.allow_dangerous,
    )


@app.get("/intake-rules", response_model=list[IntakeRule])
async def list_intake_rules() -> list[IntakeRule]:
    return runtime.list_intake_rules()


@app.post("/intake-rules", response_model=IntakeRule)
async def upsert_intake_rule(rule: IntakeRule) -> IntakeRule:
    return runtime.upsert_intake_rule(rule)


@app.post("/intake-rules/dry-run", response_model=IntakeDryRunResponse)
async def dry_run_intake_rule(request: IntakeDryRunRequest) -> IntakeDryRunResponse:
    return runtime.dry_run_intake_rule(request)


@app.delete("/intake-rules/{rule_id}")
async def delete_intake_rule(rule_id: str) -> dict[str, bool]:
    deleted = runtime.delete_intake_rule(rule_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="intake rule not found")
    return {"deleted": True}


@app.get("/admin/intake-rules", response_class=HTMLResponse)
async def intake_rules_page() -> str:
    return """
<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <title>Hubble Intake Rules</title>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; margin: 40px; background: #f7f9fc; color: #172033; }
    h1 { margin-bottom: 8px; }
    .hint { color: #667085; margin-bottom: 24px; }
    textarea { width: 100%; min-height: 220px; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; border: 1px solid #d0d7e2; border-radius: 12px; padding: 16px; box-sizing: border-box; }
    button { background: #155eef; color: white; border: 0; padding: 10px 16px; border-radius: 10px; margin: 12px 8px 12px 0; cursor: pointer; }
    button.secondary { background: #475467; }
    pre { background: white; border: 1px solid #e4e7ec; border-radius: 12px; padding: 16px; overflow: auto; }
    .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 24px; }
    code { background: #eef4ff; padding: 2px 6px; border-radius: 6px; }
  </style>
</head>
<body>
  <h1>Hubble 前置规则 / 过滤配置</h1>
  <div class="hint">规则会在告警进入 Alert Core 之前执行，适合做 drop、tag、rewrite 和低价值告警过滤。Dry-run 不会创建 Alert / Incident。</div>
  <div class="grid">
    <section>
      <h2>新增 / 更新规则</h2>
      <textarea id="rule">{
  "name": "drop dev low alerts",
  "enabled": true,
  "priority": 10,
  "match": {
    "labels.env": "dev",
    "data.severity": "low"
  },
  "action": "drop",
  "reason": "开发环境 low 告警不进入主链路"
}</textarea>
      <button onclick="saveRule()">保存规则</button>
      <button class="secondary" onclick="dryRunTempRule()">测试当前规则</button>
      <h2>样例事件</h2>
      <textarea id="event">{
  "source": "demo",
  "payload": {
    "title": "dev low alert",
    "description": "noise",
    "severity": "low",
    "labels": {"service": "demo", "env": "dev"}
  }
}</textarea>
      <button class="secondary" onclick="dryRunSavedRules()">使用已保存规则测试事件</button>
      <h2>规则说明</h2>
      <pre>支持 action: allow / drop / tag / rewrite
支持 match: source, type, subject_contains, data.xxx, labels.xxx, annotations.xxx
rewrite 可用 set_fields 修改 data 字段
tag 可用 add_labels 添加标签
列表中会显示 matched_count / filtered_count / last_matched_at 等统计</pre>
    </section>
    <section>
      <h2>当前规则</h2>
      <button onclick="loadRules()">刷新</button>
      <pre id="rules">Loading...</pre>
      <h2>Dry-run 结果</h2>
      <pre id="dryrun">暂无</pre>
    </section>
  </div>
<script>
async function loadRules() {
  const res = await fetch('/intake-rules');
  document.getElementById('rules').textContent = JSON.stringify(await res.json(), null, 2);
}
async function saveRule() {
  const payload = JSON.parse(document.getElementById('rule').value);
  const res = await fetch('/intake-rules', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(payload)
  });
  if (!res.ok) alert(await res.text());
  await loadRules();
}
async function dryRunTempRule() {
  const event = JSON.parse(document.getElementById('event').value);
  const rule = JSON.parse(document.getElementById('rule').value);
  const res = await fetch('/intake-rules/dry-run', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({source: event.source || 'dry-run', payload: event.payload || {}, rule})
  });
  document.getElementById('dryrun').textContent = JSON.stringify(await res.json(), null, 2);
}
async function dryRunSavedRules() {
  const event = JSON.parse(document.getElementById('event').value);
  const res = await fetch('/intake-rules/dry-run', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({source: event.source || 'dry-run', payload: event.payload || {}})
  });
  document.getElementById('dryrun').textContent = JSON.stringify(await res.json(), null, 2);
}
loadRules();
</script>
</body>
</html>
"""


def main() -> None:
    uvicorn.run("hubble.server:app", host="0.0.0.0", port=8000, reload=True)


if __name__ == "__main__":
    main()
