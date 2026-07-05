# Roadmap

Hubble V2 的实现路线不再围绕“Webhook → 模型 → 推送”单链路展开，而是围绕 **事件进入、告警生命周期、事件组、策略、AI 分析、工具增强、ChatOps 处置** 七个阶段推进。

## Phase 0：项目骨架

目标：让仓库具备清晰架构、可运行入口和可扩展接口。

- [x] README 项目定位。
- [x] 架构文档。
- [x] 插件契约文档。
- [x] Python 项目元数据。
- [x] FastAPI Webhook MVP。
- [x] 核心数据模型。
- [x] 模型、工具、推送、会话接口。
- [x] 开源参考项目分析。

## Phase 1：事件与告警核心

目标：先让 Hubble 成为一个可靠的告警运行时，即使没有大模型也能工作。

- [ ] `EventEnvelope`：参考 CloudEvents 的内部事件信封。
- [ ] `Alert`：统一告警对象。
- [ ] Alert fingerprint。
- [ ] 简单 dedup window。
- [ ] Alert status：firing / resolved / acknowledged / suppressed。
- [ ] Alert timeline。
- [ ] SQLite / PostgreSQL 存储接口。

## Phase 2：告警接入适配器

目标：让真实告警可以进来。

- [ ] 通用 Webhook 鉴权。
- [ ] Prometheus Alertmanager payload parser。
- [ ] Grafana webhook parser。
- [ ] Sentry webhook parser。
- [ ] 自定义 JSON mapping。
- [ ] 轮询任务调度器。
- [ ] 接入失败重试和死信记录。

## Phase 3：Incident Core

目标：把大量 Alert 聚合成可处置的 Incident。

- [ ] `Incident` 模型。
- [ ] group_by 配置。
- [ ] Alert → Incident 绑定。
- [ ] Incident timeline。
- [ ] affected_services。
- [ ] owner_team。
- [ ] incident status：open / investigating / mitigated / resolved。
- [ ] thread_id 绑定，用于群聊追问。

## Phase 4：Policy & Workflow Engine

目标：补齐告警系统真正需要的规则和处置策略。

- [ ] Routing rule。
- [ ] Silence。
- [ ] Inhibition。
- [ ] Maintenance window。
- [ ] Escalation rule。
- [ ] Approval gate。
- [ ] Workflow YAML。
- [ ] Execution audit。

## Phase 5：ChannelAdapter：推送 + 会话统一

目标：把推送层和会话层合并为统一交互层。

- [ ] Console channel。
- [ ] 通用 Webhook channel。
- [ ] 飞书机器人推送。
- [ ] 飞书事件订阅 / 群消息监听。
- [ ] 企业微信机器人推送。
- [ ] 企业微信回调。
- [ ] thread reply。
- [ ] command parser：`/ack`、`/resolve`、`/silence 30m`、`/explain`。

## Phase 6：Reasoning & Agent Layer

目标：让模型输出稳定、可控、可审计，不让模型接管主链路。

- [ ] OpenAI-compatible provider。
- [ ] 私有模型网关 provider。
- [ ] Prompt 模板目录。
- [ ] Prompt versioning。
- [ ] Structured Analysis schema。
- [ ] JSON schema 校验。
- [ ] 模型调用审计日志。
- [ ] 模型失败 fallback。
- [ ] 基于 severity / cost / privacy 的模型路由策略。

## Phase 7：Tool & Action Runtime

目标：让机器人能查上下文，也能在人工确认后执行动作。

- [ ] HTTP API Tool。
- [ ] Prometheus Query Tool。
- [ ] Loki / Elasticsearch Log Tool。
- [ ] SQL readonly Tool。
- [ ] Runbook / Markdown KB Tool。
- [ ] GitHub / GitLab deployment Tool。
- [ ] Tool result redaction。
- [ ] Dangerous Action model。
- [ ] Human approval for actions。
- [ ] Action execution audit。

## Phase 8：开源工程化

目标：降低使用门槛，适合开源传播。

- [ ] Dockerfile。
- [ ] docker-compose.yml。
- [ ] Helm Chart。
- [x] GitHub Actions CI。
- [ ] 单元测试覆盖核心模型和引擎。
- [ ] 插件开发教程。
- [ ] 示例截图和 Demo 视频。
- [ ] License 确认。

## 推荐主线

第一条可演示闭环建议按这个顺序做：

```text
EventEnvelope
→ Alert fingerprint / dedup
→ Alertmanager webhook parser
→ Console + Feishu ChannelAdapter
→ OpenAI-compatible structured analysis
→ Prometheus / Log query tools
→ 飞书群聊 /explain 与 /logs
→ Incident timeline 与 thread binding
```

这样既不会过早陷入平台化，又能保留长期架构的正确方向。
