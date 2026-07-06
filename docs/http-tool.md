# HTTP Tool 使用说明

HTTP Tool 用于在告警分析前查询内部系统，例如日志平台、服务健康接口、CMDB、发布系统或自研诊断 API。它属于 Tool / Action Runtime 的只读工具能力，默认通过 Policy DSL 的 `enrich_tools` 被主链路调用。

## 设计目标

- 工具通过 `ToolRegistry` 注册，不和 Runtime、Reasoning、Channel 直接耦合。
- 工具声明 `ToolSpec`，包含 `name`、`description`、`input_schema`、`dangerous` 和 `timeout_seconds`。
- `dangerous=true` 的工具默认不会执行，必须显式传入 `allow_dangerous=true`。
- 执行结果统一返回 `ToolResult`：`ok`、`data`、`error`、`elapsed_ms`、`metadata`。
- HTTP 超时、网络异常、上游非 2xx/3xx 都返回结构化错误，不让主链路崩溃。
- 响应头、响应体和 URL 查询参数会按敏感字段规则脱敏。

## 配置示例

```yaml
tools:
  enabled: true
  auto_execute_readonly: true
  require_confirmation_for_dangerous: true
  registry:
    - name: query_logs
      type: http
      enabled: true
      description: Query recent logs from an internal log service.
      method: POST
      url_env: HUBBLE_QUERY_LOGS_URL
      bearer_token_env: HUBBLE_QUERY_LOGS_TOKEN
      headers:
        Content-Type: application/json
      body_template:
        service: "{service}"
        env: "{env}"
        severity: "{severity}"
        incident_id: "{incident.id}"
        alert_id: "{alert.id}"
        query: "service={service} env={env}"
        limit: 20
      timeout_seconds: 10
      dangerous: false
      sensitive_fields: [authorization, token, password, secret]
```

## 模板变量

`body_template`、`url` 和 `headers` 支持简单占位符：

```text
{service}
{env}
{severity}
{status}
{source}
{labels.xxx}
{annotations.xxx}
{alert.id}
{incident.id}
{context.trace_id}
```

在主告警链路中，Runtime 会自动把当前 `Alert`、`Incident`、labels、annotations、source、severity 和 status 注入给工具。

## 在 Policy 中启用

```yaml
policies:
  rules:
    - name: payment-critical-route
      match:
        labels.service: payment-api
        labels.env: prod
        severity: critical
      should_analyze: true
      enrich_tools: [query_logs]
```

命中策略后，主链路会变成：

```text
Alert → Incident → PolicyDecision → ToolResult[] → Analysis → ChannelMessage
```

`ToolResult[]` 会写入 `Analysis.tool_results`，模型或 Echo fallback 可以把工具结果作为上下文。

## 手动调试

查看已注册工具：

```bash
curl http://127.0.0.1:8000/tools
```

手动执行工具：

```bash
curl -X POST http://127.0.0.1:8000/tools/query_logs/run \
  -H 'Content-Type: application/json' \
  -d '{"params":{"service":"payment-api","env":"prod"}}'
```

执行危险工具时必须显式确认：

```json
{
  "params": {},
  "allow_dangerous": true
}
```

## 返回结构

成功示例：

```json
{
  "ok": true,
  "data": {
    "status_code": 200,
    "headers": {},
    "body": {"items": []}
  },
  "error": null,
  "elapsed_ms": 32,
  "metadata": {
    "tool_name": "query_logs",
    "method": "POST",
    "url": "https://logs.example.internal/query",
    "status_code": 200
  }
}
```

超时示例：

```json
{
  "ok": false,
  "data": null,
  "error": "HTTP tool timed out after 10.00s",
  "elapsed_ms": 10001,
  "metadata": {
    "error_type": "timeout",
    "method": "POST",
    "url": "https://logs.example.internal/query"
  }
}
```

## 安全边界

- `Authorization`、`Cookie`、`token`、`password`、`secret` 等字段默认脱敏。
- `sensitive_fields` 可以追加业务自定义敏感字段。
- Tool 执行失败不会影响告警主链路，失败结果会进入 `Analysis.tool_results`。
- 只读查询工具可以自动执行；变更类动作后续应走 Action Approval Gate。
