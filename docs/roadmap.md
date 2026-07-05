# Roadmap

## Phase 0：项目骨架

目标：让仓库具备清晰架构、可运行入口和可扩展接口。

- [x] README 项目定位。
- [x] 架构文档。
- [x] 插件契约文档。
- [x] Python 项目元数据。
- [x] FastAPI Webhook MVP。
- [x] 核心数据模型。
- [x] 模型、工具、推送、会话接口。

## Phase 1：可用的告警入口

目标：让真实告警可以进来。

- [ ] 通用 Webhook 鉴权。
- [ ] Prometheus Alertmanager payload parser。
- [ ] Grafana webhook parser。
- [ ] Sentry webhook parser。
- [ ] 轮询任务调度器。
- [ ] 告警指纹、去重、聚合。
- [ ] SQLite/PostgreSQL 持久化。

## Phase 2：模型调度层

目标：让模型输出稳定、可控、可审计。

- [ ] OpenAI-compatible provider。
- [ ] 私有模型网关 provider。
- [ ] Prompt 模板目录。
- [ ] 结构化输出校验。
- [ ] 模型调用审计日志。
- [ ] 基于 severity / cost / privacy 的模型路由策略。
- [ ] 失败降级：模型不可用时回退为规则摘要。

## Phase 3：工具层

目标：让机器人能查上下文，而不是只根据告警文本猜。

- [ ] HTTP API 工具。
- [ ] Loki / Elasticsearch 日志查询工具。
- [ ] Prometheus query 工具。
- [ ] SQL 只读查询工具。
- [ ] Runbook / Markdown 知识库查询工具。
- [ ] 工具调用审计。
- [ ] 危险工具二次确认。
- [ ] 敏感信息脱敏。

## Phase 4：推送层

目标：让告警能稳定发到团队工作流里。

- [ ] 飞书机器人推送。
- [ ] 企业微信机器人推送。
- [ ] 钉钉机器人推送。
- [ ] Slack 推送。
- [ ] 通用 Webhook 推送。
- [ ] 卡片消息模板。
- [ ] 告警升级策略。
- [ ] 静默 / 抑制策略。

## Phase 5：会话层

目标：让用户可以在群里继续追问和处置。

- [ ] CLI 会话 Demo。
- [ ] 飞书事件订阅。
- [ ] 企业微信回调。
- [ ] 会话上下文绑定 alert / incident。
- [ ] `/ack`、`/resolve`、`/silence` 命令。
- [ ] 多轮追问。
- [ ] 工具调用确认流程。

## Phase 6：部署和开源工程化

目标：降低使用门槛，适合开源传播。

- [ ] Dockerfile。
- [ ] docker-compose.yml。
- [ ] Helm Chart。
- [ ] GitHub Actions CI。
- [ ] 单元测试。
- [ ] 插件开发教程。
- [ ] 示例截图和 Demo 视频。
- [ ] License 确认。

## 推荐优先级

第一条主线建议先做：

```text
Webhook 接入 → Echo 模型 → Console 推送 → 飞书推送 → OpenAI-compatible 模型 → 日志查询工具 → 飞书会话追问
```

这样最快能形成一个可演示闭环。
