# Hubble Task Plan 与验收标准

本文把 Hubble 的开发拆成可执行任务。每个任务都包含目标、范围、依赖和验收标准，方便后续直接转成 GitHub Issues / Project Board。

## 任务状态约定

```text
TODO        未开始
IN_PROGRESS 进行中
DONE        已完成
BLOCKED     被依赖阻塞
```

## 优先级约定

```text
P0  当前最小可用闭环必须完成
P1  MVP 演示闭环必须完成
P2  进入可用开源项目阶段
P3  企业化 / 高级能力
```

## 全局 Definition of Done

所有代码任务默认满足以下条件才算完成：

- 代码进入 `main` 分支。
- CI 通过：ruff + pytest。
- 有必要的单元测试或接口测试。
- README 或 docs 中有对应说明。
- 新增 API 有请求 / 响应示例。
- 新增配置项进入 `configs/hubble.example.yaml`。
- 不破坏现有 `/healthz`、`/webhook/{source}`、`/alerts`、`/incidents`。

---

# Phase 0：项目基础与契约冻结

目标：先把架构边界固定住，避免后续功能越写越耦合。

## T0.1 架构文档与 README 同步

优先级：P0  
状态：DONE

### 目标

让 README、架构图、层间契约文档保持一致。

### 范围

- README 架构说明。
- Mermaid 架构图。
- `docs/architecture.md`。
- `docs/layer-contracts.md`。

### 验收标准

- README 中包含 V2 架构图。
- README 中出现 `Intake Rule & Filter Engine`。
- `docs/architecture.md` 中解释 Intake Rule 和 Policy Engine 的边界。
- `docs/layer-contracts.md` 中记录 `Adapter → EventEnvelope → IntakeDecision → AlertLifecycleResult` 契约。

## T0.2 CI 基础检查

优先级：P0  
状态：DONE

### 目标

保证后续每次提交都有基本质量检查。

### 范围

- GitHub Actions。
- ruff。
- pytest。

### 验收标准

- `.github/workflows/ci.yml` 存在。
- push / pull_request 会运行安装、lint、test。
- 本地或 CI 执行 `pytest` 不应失败。

---

# Phase 1：事件接入与前置过滤闭环

目标：让告警事件先进入统一信封，再经过前置规则过滤，最后才进入告警生命周期。

## T1.1 EventEnvelope 标准化

优先级：P0  
状态：DONE

### 目标

所有外部输入都先变成统一事件信封。

### 范围

- `src/hubble/events/models.py`
- `EventEnvelope`
- `EventRecord`

### 验收标准

- `EventEnvelope` 至少包含：`id`、`type`、`source`、`subject`、`time`、`data`、`trace_id`、`tenant_id`、`extensions`。
- Webhook 输入不会直接进入 Alert Core。
- 测试中 `/webhook/{source}` 返回值包含 `event` 字段。

## T1.2 InMemoryEventBus

优先级：P0  
状态：DONE

### 目标

提供 MVP 事件总线，后续可替换为 Redis Streams / NATS / Kafka。

### 范围

- `src/hubble/events/bus.py`
- `publish`
- `subscribe`
- `replay`
- `records`

### 验收标准

- 可以发布事件。
- 可以订阅指定事件类型。
- 可以订阅 `*` 通配事件。
- 可以回放已发布事件。
- handler 抛异常时，`EventRecord.error` 有记录。

## T1.3 Adapter Contract

优先级：P0  
状态：DONE

### 目标

所有接入源通过统一 Adapter 契约进入系统。

### 范围

- `src/hubble/adapters/base.py`
- `Adapter.to_event(raw) -> EventEnvelope`
- `GenericWebhookAdapter`

### 验收标准

- `GenericWebhookAdapter` 输出 `EventEnvelope(type="alert.received")`。
- Adapter 不依赖 Alert / Incident / Reasoning / Channel 模块。
- README 或契约文档中写明 Adapter 只做协议解析和格式转换。

## T1.4 IntakeRule 数据模型

优先级：P0  
状态：DONE

### 目标

定义前置过滤规则的稳定数据结构。

### 范围

- `src/hubble/intake/models.py`
- `IntakeRule`
- `IntakeDecision`

### 验收标准

- `IntakeRule` 支持：`name`、`enabled`、`priority`、`match`、`action`、`reason`、`add_labels`、`set_fields`。
- `action` 支持：`allow`、`drop`、`tag`、`rewrite`。
- `IntakeDecision` 能表达 allowed / filtered 结果。

## T1.5 IntakeRuleEngine

优先级：P0  
状态：DONE

### 目标

在 Alert 创建之前执行前置规则。

### 范围

- `src/hubble/intake/service.py`
- `evaluate(event)`
- `list_rules()`
- `upsert_rule()`
- `delete_rule()`

### 验收标准

- 没有规则时默认 allow。
- `drop` 规则命中后不创建 Alert。
- `tag` 规则可以给 `data.labels` 增加字段。
- `rewrite` 规则可以修改 `data` 字段。
- 支持按 `source`、`type`、`subject_contains`、`data.xxx`、`labels.xxx`、`annotations.xxx` 匹配。
- 测试覆盖 drop 规则。

## T1.6 Intake Rule API

优先级：P0  
状态：DONE

### 目标

提供前置规则的配置 API。

### 范围

- `GET /intake-rules`
- `POST /intake-rules`
- `DELETE /intake-rules/{rule_id}`

### 验收标准

- `GET /intake-rules` 返回规则列表。
- `POST /intake-rules` 可以创建或更新规则。
- `DELETE /intake-rules/{rule_id}` 可以删除规则。
- 删除不存在规则返回 404。
- README 中列出这些 API。

## T1.7 Intake Rule Admin Page

优先级：P1  
状态：DONE

### 目标

提供一个单独页面配置前置规则。

### 范围

- `GET /admin/intake-rules`
- 内置轻量 HTML 页面。

### 验收标准

- 浏览器打开 `/admin/intake-rules` 可看到配置页面。
- 页面可以展示当前规则。
- 页面可以提交 JSON 规则。
- 页面提示支持 `allow / drop / tag / rewrite`。
- README 中写明页面地址。

## T1.8 Intake Rule Dry-run

优先级：P1  
状态：TODO

### 目标

允许用户在保存规则前用样例事件测试命中结果。

### 范围

- `POST /intake-rules/dry-run`
- 请求体包含：`event` 或 `raw_payload`、可选 `rule`。
- 返回命中规则、动作、改写后的 event。

### 验收标准

- 提交样例事件可以看到会命中哪个规则。
- 提交临时规则可以测试但不保存。
- dry-run 不会创建 Alert / Incident。
- dry-run 不会发布正式 `alert.ingested` 事件。
- 前端页面有“测试规则”按钮。

## T1.9 Intake Rule 命中统计

优先级：P2  
状态：TODO

### 目标

知道每条规则过滤了多少告警，避免规则误杀。

### 范围

- rule hit count。
- last matched time。
- filtered count。
- allowed count。
- rewrite/tag count。

### 验收标准

- `GET /intake-rules` 返回统计信息或有单独 stats API。
- 每次规则命中后计数增加。
- 页面展示命中次数和最后命中时间。
- 测试覆盖命中计数。

---

# Phase 2：Alert / Incident 生命周期核心

目标：把单条事件变成可管理的告警，再聚合成 Incident。

## T2.1 Alert 数据模型

优先级：P0  
状态：DONE

### 目标

定义统一告警对象。

### 范围

- `src/hubble/alerts/models.py`
- `Alert`
- `AlertSeverity`
- `AlertStatus`

### 验收标准

- Alert 包含 source、title、description、severity、status、labels、annotations、fingerprint、raw_event_id。
- Alert 能生成稳定 fingerprint。
- 同样 source/title/labels 的 fingerprint 稳定一致。

## T2.2 AlertLifecycleService

优先级：P0  
状态：DONE

### 目标

负责 normalize、fingerprint、dedup。

### 范围

- `src/hubble/alerts/service.py`
- `handle_event(event)`
- `get(alert_id)`
- `list_alerts()`

### 验收标准

- `alert.ingested` 可以生成 Alert。
- severity 非法时变成 `unknown`。
- status 非法时变成 `firing`。
- fingerprint 相同且 status 相同的事件会标记 duplicate。
- `/alerts` 可以查询已创建 Alert。

## T2.3 Alertmanager Webhook Parser

优先级：P1  
状态：TODO

### 目标

兼容 Prometheus Alertmanager 标准 webhook payload。

### 范围

- `AlertmanagerWebhookAdapter`
- 支持 groupLabels、commonLabels、commonAnnotations、alerts[]。

### 验收标准

- Alertmanager payload 中每个 alert 都能转为独立 `EventEnvelope` 或 batch event。
- `status=firing/resolved` 能正确映射。
- `labels.severity` 能正确映射。
- `annotations.summary/description` 能正确映射。
- 有 `examples/alertmanager_payload.json`。
- 有接口测试覆盖 firing 和 resolved。

## T2.4 Incident 数据模型

优先级：P0  
状态：DONE

### 目标

定义事件组对象，承接告警聚合和会话上下文。

### 范围

- `src/hubble/incidents/models.py`
- `Incident`
- `IncidentTimelineItem`

### 验收标准

- Incident 包含 title、severity、status、alert_ids、alert_fingerprints、affected_services、timeline。
- Incident status 支持 open / investigating / mitigated / resolved。
- timeline 可以记录 incident.created / alert.attached。

## T2.5 IncidentLifecycleService

优先级：P0  
状态：DONE

### 目标

按 group_by 把相关告警合并成 Incident。

### 范围

- `src/hubble/incidents/service.py`
- `attach_alert(alert)`
- `get(incident_id)`
- `list_incidents()`

### 验收标准

- 相同 source + group_by labels 的 Alert 进入同一个 Incident。
- 新 Alert 进入已有 Incident 时 timeline 增加 `alert.attached`。
- Incident severity 会随更高等级 Alert 升级。
- `/incidents` 可以查询 Incident。

## T2.6 Incident 状态流转 API

优先级：P1  
状态：TODO

### 目标

允许人工或命令修改 Incident 状态。

### 范围

- `POST /incidents/{id}/ack`
- `POST /incidents/{id}/resolve`
- `POST /incidents/{id}/reopen`

### 验收标准

- ack 后状态变为 investigating。
- resolve 后状态变为 resolved，并写入 resolved_at。
- reopen 后状态变为 open。
- 每次状态变化写入 timeline。
- 不存在 incident 返回 404。

---

# Phase 3：Policy / Workflow 决策层

目标：Alert / Incident 创建后，由策略决定是否分析、推送、升级和执行工作流。

## T3.1 PolicyDecision 模型

优先级：P0  
状态：DONE

### 目标

定义策略层输出契约。

### 范围

- `src/hubble/policies/models.py`
- `PolicyDecision`

### 验收标准

- PolicyDecision 包含 should_notify、should_analyze、channels、enrich_tools、escalation_channels、require_approval、reason。
- Runtime 不直接硬编码渠道选择，读取 PolicyDecision.channels。

## T3.2 默认 PolicyEngine

优先级：P0  
状态：DONE

### 目标

提供 MVP 默认策略。

### 范围

- `src/hubble/policies/service.py`
- `evaluate(alert, incident)`

### 验收标准

- suppressed alert 不通知、不分析。
- high / critical alert 默认发 console。
- 其他 alert 默认发 console。
- PolicyEngine 不调用模型、工具和通道。

## T3.3 YAML Policy DSL

优先级：P1  
状态：TODO

### 目标

把路由、分析、工具增强等策略从代码中移到配置。

### 范围

- `configs/hubble.example.yaml` 中的 policies。
- 支持 match labels / severity / source。
- 支持 channels / enrich_tools / require_approval。

### 验收标准

- 可以通过 YAML 定义 payment-api 的路由规则。
- 配置变更后重启服务生效。
- 命中规则后 PolicyDecision.reason 包含规则名。
- 测试覆盖至少 2 条策略规则。

## T3.4 Silence / Maintenance Window

优先级：P2  
状态：TODO

### 目标

支持维护窗口和临时静默。

### 范围

- Silence model。
- MaintenanceWindow model。
- API 创建 / 删除 / 查询 silence。
- PolicyEngine 识别 silence。

### 验收标准

- 命中 silence 的 Incident 不通知。
- silence 有开始 / 结束时间。
- 过期 silence 不再生效。
- timeline 记录 silence 命中原因。

## T3.5 Escalation Rule

优先级：P2  
状态：TODO

### 目标

未确认或长时间未恢复时升级。

### 范围

- escalation rule。
- 定时扫描 open incident。
- escalation_channels。

### 验收标准

- Incident 超过配置时间未 ack，会生成 escalation event。
- escalation event 会发送到升级渠道。
- 已 resolved 的 incident 不升级。
- 已 ack 的 incident 按配置决定是否升级。

---

# Phase 4：Reasoning / AI 分析层

目标：让模型分析成为可插拔能力，而不是主链路强依赖。

## T4.1 Analysis 数据模型

优先级：P0  
状态：DONE

### 目标

定义结构化模型分析结果。

### 范围

- `src/hubble/reasoning/models.py`
- `Analysis`
- `ToolCallRequest`

### 验收标准

- Analysis 包含 summary、severity、possible_causes、impact、recommended_actions、confidence、model_provider、prompt_version。
- Webhook 响应中包含 `analysis`。

## T4.2 Echo ReasoningService

优先级：P0  
状态：DONE

### 目标

无模型也能完成基础分析闭环。

### 范围

- `src/hubble/reasoning/service.py`

### 验收标准

- 不配置模型时 `/webhook/{source}` 仍返回 Analysis。
- Analysis 中能看到 provider_name = echo。
- Echo 不访问外部服务。

## T4.3 OpenAI-compatible Provider

优先级：P1  
状态：TODO

### 目标

接入任意 OpenAI-compatible API。

### 范围

- base_url。
- api_key。
- model。
- timeout。
- structured output prompt。

### 验收标准

- 环境变量配置后可调用模型。
- 模型返回可以解析成 Analysis。
- 模型失败时 fallback 到 Echo。
- 请求超时不阻塞主链路。
- 不在日志中输出 API Key。

## T4.4 Prompt Versioning

优先级：P1  
状态：TODO

### 目标

每次模型分析可以追踪 prompt 版本。

### 范围

- `prompts/` 目录。
- prompt_version。
- Analysis 记录 prompt_version。

### 验收标准

- prompt 模板从文件加载。
- Analysis 中包含 prompt_version。
- 修改 prompt 可以更新版本号。
- 文档说明如何新增 prompt。

## T4.5 Tool Request Planning

优先级：P2  
状态：TODO

### 目标

模型可以提出工具调用建议，但不能直接执行。

### 范围

- Analysis.tool_requests。
- Tool call planner。
- Tool request event。

### 验收标准

- 模型输出的 tool_requests 会被校验。
- 未注册工具请求会被拒绝。
- Tool 请求不会自动执行危险动作。
- 测试覆盖合法 / 非法工具请求。

---

# Phase 5：Tool / Action Runtime

目标：让 Hubble 能查上下文，并在人工确认后执行动作。

## T5.1 Tool Registry 重构

优先级：P1  
状态：TODO

### 目标

把旧 `tools/base.py` 迁移到新 Tool Runtime 契约。

### 范围

- `ToolSpec`
- `ToolContext`
- `ToolResult`
- `ToolRegistry`
- capability schema。

### 验收标准

- 工具有 name、description、input_schema、dangerous、timeout。
- 工具执行结果有 ok、data、error、elapsed_ms。
- 未注册工具返回结构化错误。
- dangerous tool 默认不执行。

## T5.2 HTTP Tool

优先级：P1  
状态：TODO

### 目标

支持调用内部 HTTP API 查询上下文。

### 范围

- method。
- url。
- headers。
- body template。
- timeout。

### 验收标准

- 可以配置一个只读 HTTP tool。
- 工具超时返回结构化错误。
- 返回结果可被 Reasoning 使用。
- 支持敏感字段脱敏。

## T5.3 Prometheus Query Tool

优先级：P1  
状态：TODO

### 目标

支持查询 Prometheus 指标。

### 范围

- instant query。
- range query。
- base_url / token。

### 验收标准

- 可以查询最近 N 分钟指标。
- 查询失败返回结构化错误。
- 支持 service/env 标签参数。
- 有测试或 mock 示例。

## T5.4 Log Query Tool

优先级：P1  
状态：TODO

### 目标

支持日志查询，优先 Loki / Elasticsearch 二选一。

### 范围

- query。
- time range。
- limit。
- service/env labels。

### 验收标准

- 可以按 service 查询最近日志。
- 返回日志条数可限制。
- 超时和失败可控。
- 脱敏 token / password / secret。

## T5.5 Action Approval Gate

优先级：P2  
状态：TODO

### 目标

危险动作必须人工确认。

### 范围

- ActionRequested。
- ActionApprovalRequired。
- ActionApproved / ActionRejected。
- Execution audit。

### 验收标准

- dangerous action 不会自动执行。
- 审批通过后才执行。
- 拒绝后写入审计记录。
- 所有动作有执行人 / 审批人 / 时间 / 参数 / 结果。

---

# Phase 6：Channel / ChatOps

目标：统一推送和会话，让用户能在告警线程中追问和处置。

## T6.1 ChannelAdapter 契约

优先级：P0  
状态：DONE

### 目标

合并 Notifier 和 Session 抽象。

### 范围

- `src/hubble/channels/base.py`
- `ChannelAdapter`
- `ChannelRegistry`
- `ConsoleChannelAdapter`

### 验收标准

- ChannelAdapter 支持 send。
- 可选支持 listen / reply。
- ConsoleChannelAdapter 可打印 ChannelMessage。
- Runtime 通过 ChannelRegistry 发送消息。

## T6.2 Feishu ChannelAdapter

优先级：P1  
状态：TODO

### 目标

支持飞书机器人推送。

### 范围

- webhook 推送。
- markdown 或 card 消息。
- channel config。

### 验收标准

- 配置 webhook 后可以发送告警消息到飞书。
- 发送失败返回结构化错误。
- 不泄露 webhook secret。
- README 有配置示例。

## T6.3 Feishu Conversation Listener

优先级：P2  
状态：TODO

### 目标

支持在飞书群线程中追问。

### 范围

- 事件订阅。
- thread_id。
- sender_id。
- command parser。

### 验收标准

- 收到飞书消息能转换为 IncomingChannelMessage。
- 能根据 thread_id 绑定 Incident。
- 支持 `/explain` 返回 Incident 摘要。
- 支持 `/ack` 修改 Incident 状态。

## T6.4 WeCom ChannelAdapter

优先级：P2  
状态：TODO

### 目标

支持企业微信机器人推送。

### 范围

- webhook 推送。
- markdown 消息。

### 验收标准

- 配置 webhook 后可以推送企业微信。
- 失败返回结构化错误。
- README 有配置示例。

---

# Phase 7：存储、审计与可观测性

目标：从内存 Demo 进入可用服务。

## T7.1 Storage Interface

优先级：P1  
状态：TODO

### 目标

抽象存储层，替换当前内存状态。

### 范围

- Alert repository。
- Incident repository。
- Intake rule repository。
- Event repository。

### 验收标准

- Runtime 不直接依赖内存 dict。
- 内存实现和数据库实现共享接口。
- 测试可以使用 memory repository。

## T7.2 SQLite Storage

优先级：P1  
状态：TODO

### 目标

本地部署可持久化。

### 范围

- SQLite schema。
- migrations 或初始化脚本。
- alerts / incidents / rules / events。

### 验收标准

- 重启后 intake rules 不丢失。
- 重启后 alerts/incidents 可查询。
- 有配置项选择 sqlite。
- 有基本迁移说明。

## T7.3 PostgreSQL Storage

优先级：P2  
状态：TODO

### 目标

支持企业部署。

### 范围

- PostgreSQL DSN。
- schema。
- 连接池。

### 验收标准

- 配置 PostgreSQL 后服务可启动。
- alerts/incidents/rules/events 持久化。
- 数据库不可用时启动或请求返回清晰错误。

## T7.4 Audit Log

优先级：P2  
状态：TODO

### 目标

记录关键决策和执行过程。

### 范围

- intake rule 命中。
- policy decision。
- reasoning request / response。
- tool / action execution。
- channel send result。

### 验收标准

- 每次告警处理有 trace_id 或 correlation id。
- 可以按 incident_id 查询审计日志。
- 敏感字段被脱敏。

## T7.5 Metrics

优先级：P2  
状态：TODO

### 目标

暴露服务健康和处理指标。

### 范围

- `/metrics`。
- alert received count。
- alert filtered count。
- notification sent count。
- reasoning latency。
- tool latency。

### 验收标准

- Prometheus 可以 scrape `/metrics`。
- 指标包含 label：source、severity、action。
- README 有指标说明。

---

# Phase 8：部署与开源体验

目标：让项目能被别人快速试用和贡献。

## T8.1 Dockerfile

优先级：P1  
状态：TODO

### 目标

一条命令构建镜像。

### 验收标准

- `docker build .` 成功。
- 容器启动后 `/healthz` 返回 ok。
- README 有 Docker 运行示例。

## T8.2 docker-compose.yml

优先级：P1  
状态：TODO

### 目标

本地一键运行 Hubble 和依赖。

### 验收标准

- `docker compose up` 可启动服务。
- 服务端口暴露 8000。
- 可选包含 PostgreSQL / Redis。
- README 有 compose 示例。

## T8.3 开源贡献文档

优先级：P2  
状态：TODO

### 目标

降低贡献门槛。

### 范围

- `CONTRIBUTING.md`
- development setup。
- testing。
- coding style。

### 验收标准

- 新贡献者可以按文档跑起测试。
- 文档说明如何新增 Adapter / Tool / Channel。
- 文档说明 PR 要求。

## T8.4 License

优先级：P1  
状态：TODO

### 目标

明确开源协议。

### 验收标准

- 仓库根目录存在 `LICENSE`。
- README 中 License 不再是 TBD。
- 选择 MIT / Apache-2.0 / AGPL 等之一。

---

# 推荐执行顺序

## 当前最近 10 个任务

```text
1. T1.8 Intake Rule Dry-run
2. T1.9 Intake Rule 命中统计
3. T2.3 Alertmanager Webhook Parser
4. T2.6 Incident 状态流转 API
5. T3.3 YAML Policy DSL
6. T4.3 OpenAI-compatible Provider
7. T6.2 Feishu ChannelAdapter
8. T5.2 HTTP Tool
9. T5.3 Prometheus Query Tool
10. T7.1 Storage Interface
```

## 最小演示闭环

```text
Webhook → Intake Rule → Alert → Incident → Policy → Echo Analysis → Console
```

验收标准：

- 可以用 curl 发送告警。
- 可以在页面配置一条 drop 规则。
- 命中 drop 后不创建 Alert。
- 未命中 drop 时创建 Alert / Incident。
- 返回 Analysis。
- Console 输出通知。

## 第一版可用闭环

```text
Alertmanager → Intake Rule → Incident → OpenAI-compatible Analysis → Feishu → /explain
```

验收标准：

- Alertmanager payload 能正常接入。
- 前置规则能过滤 dev / low 告警。
- 生产 critical 告警能推送到飞书。
- 飞书线程能追问 `/explain`。
- 所有关键过程可在审计日志中查询。
