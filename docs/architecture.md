# Hubble 架构设计 V2

Hubble 的目标不是做一个“Webhook + LLM + 飞书推送”的简单串联工具，而是做一个面向告警生命周期的 **AI-native AlertOps Runtime**。

第一版架构里的五个部分——接入层、模型调度层、工具层、推送层、会话层——方向是对的，但还不够完整。优化后的核心判断是：

> **告警系统的主干应该是事件、告警和事件组生命周期；大模型是增强分析与处置能力，不应该成为唯一主链路。**

进一步调整后，Hubble 在告警事件进入 Alert Core 之前增加一层 **Intake Rule & Filter Engine（前置规则与过滤层）**。它用于过滤低价值告警、测试环境告警、已知噪音告警，也可以对事件做轻量打标和字段重写。

## 1. 参考项目与借鉴点

| 项目 / 标准 | 可借鉴点 | Hubble 的取舍 |
| --- | --- | --- |
| Prometheus Alertmanager | 去重、分组、路由、silence、inhibition、高可用 | 作为告警核心的基础能力，不重复造复杂监控系统 |
| Grafana OnCall OSS | 值班、路由、升级链、ChatOps、通知偏好 | 参考产品模型；注意其 OSS 仓库已归档，不作为依赖 |
| Keep | AIOps、去重、抽取、映射、维护窗口、服务拓扑、工作流、Provider | 重点参考 AIOps 结构；Hubble 差异化走 ChatOps-first + Agentic 工具调用 |
| StackStorm | sensors、triggers、actions、rules、workflows、packs、audit trail | 工具与自动化层重点参考，尤其是“触发器 → 规则 → 动作/工作流” |
| CloudEvents | 通用事件信封 | 作为内部 EventEnvelope 设计参考，降低接入源差异 |
| OpenTelemetry | 日志、指标、链路追踪的统一相关性 | 工具层查询日志/指标/trace 时参考其语义和关联方式 |
| LangGraph | 长运行、有状态、human-in-the-loop agent | 后期可作为会话处置和多步推理的可选 Agent Runtime |

## 2. 优化后的总体架构

```text
┌──────────────────────────────────────────────────────────────────────┐
│                           Interface Layer                            │
│     Web UI / CLI / REST API / Feishu / WeCom / Slack / Web Chat       │
│     Rule Config Page: 前置规则配置、过滤测试、规则启停                  │
└───────────────────────────────▲──────────────────────────────────────┘
                                │
┌───────────────────────────────┴──────────────────────────────────────┐
│                Notification & Conversation Layer                      │
│       推送、线程回复、群聊监听、命令、人工确认、通知偏好                  │
└───────────────────────────────▲──────────────────────────────────────┘
                                │
┌───────────────────────────────┴──────────────────────────────────────┐
│                    Reasoning & Agent Layer                            │
│       LLM 分析、RAG、工具规划、多轮上下文、结构化输出、置信度             │
└───────────────────────────────▲──────────────────────────────────────┘
                                │
┌───────────────────────────────┴──────────────────────────────────────┐
│                    Tool & Action Runtime                              │
│       查日志、查指标、查 Trace、查 DB、查发布、查知识库、执行动作          │
└───────────────────────────────▲──────────────────────────────────────┘
                                │
┌───────────────────────────────┴──────────────────────────────────────┐
│                    Workflow & Policy Engine                           │
│       路由、升级、抑制、静默、审批、自动化编排、危险动作拦截               │
└───────────────────────────────▲──────────────────────────────────────┘
                                │
┌───────────────────────────────┴──────────────────────────────────────┐
│                 Alert / Incident Lifecycle Core                       │
│       归一化、指纹、去重、分组、关联、状态机、事件组、生命周期             │
└───────────────────────────────▲──────────────────────────────────────┘
                                │
┌───────────────────────────────┴──────────────────────────────────────┐
│                 Intake Rule & Filter Engine                           │
│       allow、drop、tag、rewrite、采样、噪音过滤、规则配置                 │
└───────────────────────────────▲──────────────────────────────────────┘
                                │
┌───────────────────────────────┴──────────────────────────────────────┐
│                    Event Bus & Job Runtime                            │
│       队列、定时任务、重试、限流、幂等、死信队列、异步 Worker              │
└───────────────────────────────▲──────────────────────────────────────┘
                                │
┌───────────────────────────────┴──────────────────────────────────────┐
│                    Adapter / Collector Layer                          │
│       Webhook、Polling、Prometheus、Grafana、Sentry、云厂商、自定义源      │
└──────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────┐
│                    Storage / Audit / Observability                    │
│       PostgreSQL、Redis、对象存储、审计日志、Metrics、Trace、回放          │
└──────────────────────────────────────────────────────────────────────┘
```

## 3. 新增 Intake Rule & Filter Engine

这层位于 `Event Bus` 和 `Alert / Incident Lifecycle Core` 之间。

它的职责是：

```text
EventEnvelope(alert.received)
→ IntakeDecision
→ EventEnvelope(alert.ingested) 或 EventEnvelope(alert.filtered)
```

### 3.1 为什么不能放进 Policy Engine

前置规则和 Policy Engine 的边界不同：

| 层 | 处理时机 | 处理对象 | 核心问题 |
| --- | --- | --- | --- |
| Intake Rule & Filter | Alert 创建前 | EventEnvelope | 这个事件要不要进入告警生命周期？ |
| Policy & Workflow | Alert / Incident 创建后 | Alert + Incident | 这个事件组应该怎么路由、升级、处置？ |

如果把过滤逻辑放进 Policy 层，会导致大量低价值事件仍然进入 Alert Core、Incident Core、模型分析和推送链路，增加噪音和成本。

### 3.2 支持动作

第一版支持：

```text
allow    允许进入 Alert Core
drop     丢弃，不进入 Alert Core
tag      给事件添加 labels
rewrite  修改事件字段，例如 severity、labels、annotations
```

后续可扩展：

```text
sample        按比例采样
rate_limit    频率限制
merge_hint    给后续 group_by 提供聚合提示
route_hint    给 Policy Engine 提供路由提示
```

### 3.3 规则配置页面

Hubble 会提供独立页面：

```text
/admin/intake-rules
```

它用于：

- 查看规则列表。
- 新增 / 修改 / 删除规则。
- 启用 / 禁用规则。
- 配置 match 条件。
- 选择 action：allow / drop / tag / rewrite。
- 后续扩展：规则命中统计、规则 dry-run、样例事件测试。

## 4. 核心事件链路

```text
Adapter.to_event(raw)
→ EventEnvelope(type="alert.received")
→ Event Bus
→ IntakeRuleEngine.evaluate(event)
→ allowed: EventEnvelope(type="alert.ingested")
→ dropped: EventEnvelope(type="alert.filtered")
→ AlertLifecycleService
→ IncidentLifecycleService
→ PolicyEngine
→ ReasoningService
→ ChannelAdapter
```

## 5. 核心数据模型补充

### 5.1 IntakeRule

```text
IntakeRule
├── id
├── name
├── enabled
├── priority
├── match
├── action              # allow / drop / tag / rewrite
├── reason
├── add_labels
├── set_fields
└── stop_processing
```

### 5.2 IntakeDecision

```text
IntakeDecision
├── allowed
├── action
├── matched_rule_id
├── matched_rule_name
├── reason
└── event
```

## 6. 模块拆分建议

```text
src/hubble/
├── adapters/              # 外部系统适配器：Webhook、飞书、企微、Slack、Sentry 等
├── events/                # EventEnvelope、事件总线、重试、死信队列
├── intake/                # 前置规则、过滤、打标、重写、规则配置 API
├── alerts/                # Alert 归一化、指纹、去重、状态机
├── incidents/             # Incident 聚合、时间线、生命周期
├── policies/              # 路由、静默、抑制、升级、审批策略
├── workflows/             # 多步编排，参考 StackStorm rules/workflows
├── reasoning/             # LLM、Prompt、RAG、结构化输出、Agent Runtime
├── tools/                 # 只读工具
├── actions/               # 有副作用动作
├── channels/              # 推送 + 会话统一适配器
├── storage/               # PostgreSQL、Redis、内存实现
├── audit/                 # 模型调用、工具调用、动作执行审计
└── server.py
```

## 7. MVP 应该怎么收敛

不要一开始就做完整平台。建议 Hubble MVP 只做 5 条闭环：

### MVP-1：稳定告警入口

- 通用 Webhook。
- Prometheus Alertmanager parser。
- Alert fingerprint。
- 简单 dedup。
- Console / Feishu 推送。

### MVP-2：前置规则过滤闭环

- IntakeRule 模型。
- InMemory IntakeRuleEngine。
- `/intake-rules` API。
- `/admin/intake-rules` 规则配置页面。
- drop / tag / rewrite。

### MVP-3：AI 分析闭环

- OpenAI-compatible model provider。
- Prompt versioning。
- Structured Analysis。
- 模型失败 fallback。

### MVP-4：工具增强闭环

- HTTP tool。
- Prometheus query tool。
- Loki / Elasticsearch log query tool。
- 工具结果脱敏。
- 工具调用审计。

### MVP-5：ChatOps 闭环

- 飞书群消息监听。
- thread ↔ incident 绑定。
- `/explain`、`/logs 10m`、`/ack`、`/silence 30m`。
- 危险动作只提出建议，不自动执行。

## 8. Hubble 的定位差异

Hubble 不建议直接做成 Keep 的复制品，也不建议做成 Alertmanager 的 Python 版。

更好的定位是：

> **面向中文团队和 ChatOps 场景的 AI 告警分析与处置助手。**

核心差异：

- 比 Alertmanager 更懂上下文和会话。
- 比传统 OnCall 工具更轻量。
- 比通用 Agent 框架更聚焦告警场景。
- 比 AIOps 大平台更容易本地部署和二次开发。
- 比简单 LLM 转发器更能控制告警噪音和生命周期。

## 9. 后续实现优先级

```text
P0: IntakeRuleEngine + EventEnvelope + Alert fingerprint + Webhook parser
P1: Intake Rule Config Page + Alertmanager-compatible grouping / silence / inhibition 简化版
P2: Feishu ChannelAdapter：推送 + 回复 + 命令
P3: OpenAI-compatible ReasoningProvider + Structured Analysis
P4: Tool Runtime：Prometheus / Logs / HTTP / Runbook
P5: Incident Core：alert group、timeline、thread binding
P6: Policy Engine：routing、escalation、approval
P7: Workflow Engine：多步诊断和半自动处置
```
