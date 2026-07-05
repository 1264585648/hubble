from __future__ import annotations

from typing import Any

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from hubble.alerts.models import Alert
from hubble.events.models import EventEnvelope
from hubble.incidents.models import Incident
from hubble.intake.models import IntakeDecision, IntakeRule
from hubble.reasoning.models import Analysis
from hubble.runtime import HubbleRuntime

app = FastAPI(
    title="Hubble Alert Bot",
    description="A pluggable AI-native AlertOps runtime.",
    version="0.1.0",
)

runtime = HubbleRuntime()


class WebhookResponse(BaseModel):
    event: EventEnvelope
    intake: IntakeDecision
    alert: Alert | None = None
    incident: Incident | None = None
    analysis: Analysis | None = None
    duplicate: bool = False
    filtered: bool = False


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/webhook/{source}", response_model=WebhookResponse)
async def receive_webhook(source: str, payload: dict[str, Any]) -> WebhookResponse:
    result = await runtime.ingest_webhook(source, payload)
    return WebhookResponse(
        event=result.event,
        intake=result.intake,
        alert=result.alert,
        incident=result.incident,
        analysis=result.analysis,
        duplicate=result.duplicate,
        filtered=result.filtered,
    )


@app.get("/alerts", response_model=list[Alert])
async def list_alerts() -> list[Alert]:
    return runtime.alert_lifecycle.list_alerts()


@app.get("/incidents", response_model=list[Incident])
async def list_incidents() -> list[Incident]:
    return runtime.incident_lifecycle.list_incidents()


@app.get("/intake-rules", response_model=list[IntakeRule])
async def list_intake_rules() -> list[IntakeRule]:
    return runtime.list_intake_rules()


@app.post("/intake-rules", response_model=IntakeRule)
async def upsert_intake_rule(rule: IntakeRule) -> IntakeRule:
    return runtime.upsert_intake_rule(rule)


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
    textarea { width: 100%; min-height: 240px; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; border: 1px solid #d0d7e2; border-radius: 12px; padding: 16px; box-sizing: border-box; }
    button { background: #155eef; color: white; border: 0; padding: 10px 16px; border-radius: 10px; margin-top: 12px; cursor: pointer; }
    pre { background: white; border: 1px solid #e4e7ec; border-radius: 12px; padding: 16px; overflow: auto; }
    .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 24px; }
    code { background: #eef4ff; padding: 2px 6px; border-radius: 6px; }
  </style>
</head>
<body>
  <h1>Hubble 前置规则 / 过滤配置</h1>
  <div class="hint">规则会在告警进入 Alert Core 之前执行，适合做 drop、tag、rewrite 和低价值告警过滤。</div>
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
      <h2>规则说明</h2>
      <pre>支持 action: allow / drop / tag / rewrite
支持 match: source, type, subject_contains, data.xxx, labels.xxx, annotations.xxx
rewrite 可用 set_fields 修改 data 字段
tag 可用 add_labels 添加标签</pre>
    </section>
    <section>
      <h2>当前规则</h2>
      <button onclick="loadRules()">刷新</button>
      <pre id="rules">Loading...</pre>
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
loadRules();
</script>
</body>
</html>
"""


def main() -> None:
    uvicorn.run("hubble.server:app", host="0.0.0.0", port=8000, reload=True)


if __name__ == "__main__":
    main()
