# 层间 API 契约设计

Hubble V2 的解耦原则：

> 每一层只通过稳定契约交互，不直接依赖其他层的内部对象、实现类或隐式上下文。

层间交互只允许三类形式：

1. **Event**：主数据流，单向、不可变、可重放。
2. **API**：查询状态或下发命令，不承载主链路数据流。
3. **Capability Contract**：能力声明，如工具、动作、通道、模型 provider 的 schema。

## 1. EventEnvelope

所有外部输入必须先转成 `EventEnvelope`。

```text
Adapter / Collector → EventEnvelope → Event Bus
```

字段：

```text
EventEnvelope
├── id
├── type
├── source
├── subject
├── time
├── data
├── datacontenttype
├── trace_id
├── tenant_id
└── extensions
```

约束：

- Adapter 只产出 EventEnvelope。
- Adapter 不允许调用模型、工具、通道。
- EventEnvelope 发布后不可变。
- 未来可以替换为 Redis Streams / NATS / Kafka，而不影响上层。

## 2. Alert Lifecycle Contract

输入：

```text
EventEnvelope(type="alert.ingested")
```

输出：

```text
AlertLifecycleResult
├── alert
├── is_duplicate
└── deduped_alert_id
```

Alert Core 只负责：

- normalize
- fingerprint
- dedup
- status transition

Alert Core 不允许：

- 调模型
- 调工具
- 发通知
- 读群聊消息

## 3. Incident Lifecycle Contract

输入：

```text
Alert
```

输出：

```text
Incident
```

Incident Core 只负责：

- group_by
- alert attach
- incident timeline
- incident status
- affected services
- thread binding

Incident Core 不做策略判断，也不直接推送。

## 4. Policy Decision Contract

输入：

```text
Alert + Incident
```

输出：

```text
PolicyDecision
├── should_notify
├── should_analyze
├── channels
├── enrich_tools
├── escalation_channels
├── require_approval
└── reason
```

Policy Engine 只决定：

- 是否通知
- 是否分析
- 发到哪里
- 是否需要 enrichment
- 是否需要审批
- 是否升级

Policy Engine 不负责：

- 具体怎么查日志
- 具体怎么调用模型
- 具体怎么发飞书卡片

## 5. Reasoning Contract

输入：

```text
Alert + Incident + PolicyDecision + ToolResults(optional)
```

输出：

```text
Analysis
├── id
├── alert_id
├── incident_id
├── summary
├── severity
├── possible_causes
├── impact
├── recommended_actions
├── tool_requests
├── confidence
├── model_provider
├── prompt_version
└── raw_response
```

约束：

- Reasoning 可以建议工具调用。
- Reasoning 不能直接执行工具。
- Reasoning 可以建议 Action。
- Reasoning 不能直接执行危险 Action。
- 模型失败时必须 fallback。

## 6. Tool / Action Contract

Tool 是只读查询；Action 是有副作用动作。

```text
Tool.run(params, context) -> ToolResult
Action.request(params, context) -> ActionExecution
```

执行链路：

```text
ToolExecutionRequested → ToolExecutionFinished
ActionRequested → ActionApprovalRequired → ActionApproved → ActionExecuted
```

约束：

- Tool 默认可自动执行。
- Action 默认需要人工确认。
- 所有执行必须审计。
- 所有结果必须脱敏。
- 工具不能知道调用它的是模型、策略还是用户。

## 7. Channel Contract

推送和会话统一为 ChannelAdapter。

```text
ChannelAdapter
├── send(ChannelMessage)
├── reply(IncomingChannelMessage, text)
└── listen(handler)
```

只推送的渠道可以只实现 `send`。

支持会话的渠道，例如飞书、企微、Slack，需要实现：

- send
- listen
- reply
- command parse
- thread binding

## 8. Runtime Orchestration Contract

Runtime 是薄编排层，只负责把稳定契约串起来：

```text
EventEnvelope
→ AlertLifecycleResult
→ Incident
→ PolicyDecision
→ Analysis
→ ChannelMessage
```

Runtime 不应该包含复杂业务规则。复杂规则应该沉入 Policy Engine，复杂推理应该沉入 Reasoning Layer，外部系统差异应该沉入 Adapter / Channel / Tool。

## 9. 当前代码落地状态

已落地模块：

```text
src/hubble/events       EventEnvelope + InMemoryEventBus
src/hubble/alerts       Alert + AlertLifecycleService
src/hubble/incidents    Incident + IncidentLifecycleService
src/hubble/policies     PolicyDecision + PolicyEngine
src/hubble/reasoning    Analysis + ReasoningService
src/hubble/channels     ChannelAdapter + ConsoleChannelAdapter
src/hubble/runtime.py   Event-driven HubbleRuntime
```

当前 API：

```text
GET  /healthz
POST /webhook/{source}
GET  /alerts
GET  /incidents
```

下一步建议：

```text
1. Alertmanager webhook parser
2. YAML Policy DSL
3. OpenAI-compatible ReasoningProvider
4. Feishu ChannelAdapter
5. Prometheus / Log Tool
6. Incident thread binding
```
