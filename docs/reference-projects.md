# 开源项目参考分析

本文记录 Hubble 架构设计中可以参考的开源项目、标准和取舍。

## 1. Prometheus Alertmanager

项目地址：

- https://github.com/prometheus/alertmanager
- https://prometheus.io/docs/alerting/latest/alertmanager/

### 可借鉴点

Alertmanager 是告警处理链路里最值得参考的基础模型，尤其是：

- Deduplication：同类告警去重。
- Grouping：把相似告警合并成一次通知。
- Routing：通过路由树把告警发送到不同 receiver。
- Silence：基于 matcher 的临时静默。
- Inhibition：当主告警存在时，抑制从属告警。
- HA：高可用部署。
- Alert limits：限制异常告警风暴。

### Hubble 的取舍

Hubble 不应该重新实现完整 Alertmanager，但应该兼容它的输入和借鉴它的核心概念。

建议实现：

```text
Alertmanager Webhook Parser
Alert fingerprint
group_by
silence
inhibition
routing
```

暂不做：

```text
完整 HA gossip 集群
完整 Prometheus Alertmanager API 兼容
复杂 receiver 模板系统
```

## 2. Grafana OnCall OSS

项目地址：

- https://github.com/grafana/oncall
- https://grafana.com/docs/oncall/latest/

### 可借鉴点

Grafana OnCall 的价值在于事件响应流程，而不是底层告警计算：

- on-call schedule。
- escalation chain。
- alert routing。
- ChatOps channel。
- 用户通知偏好。
- resolution notes。
- alert group API。

### 注意

Grafana 文档显示：截至 2026-03-24，Grafana OnCall OSS 项目已归档，仓库为 read-only，后续活跃开发转向 Grafana Cloud IRM。因此 Hubble 可以参考它的产品概念，但不应把它作为长期依赖。

### Hubble 的取舍

建议参考：

```text
route
schedule
escalation
alert group
chatops thread
resolution note
```

暂不做：

```text
完整值班排班系统
复杂个人通知偏好
移动端推送
电话 / SMS 通知
```

## 3. Keep

项目地址：

- https://github.com/keephq/keep
- https://docs.keephq.dev/

### 可借鉴点

Keep 是目前最接近 Hubble 方向的开源 AIOps / alert management 项目。

值得重点研究：

- Providers：接入不同告警源和外部系统。
- Deduplication：降噪。
- Extraction：从告警文本里抽取字段。
- Mapping：字段映射和标准化。
- Maintenance Windows：维护窗口。
- Service Topology：服务拓扑。
- Workflows：告警自动化。
- Alert Evaluation Engine：告警规则评估。

### Hubble 的取舍

Hubble 不建议做成 Keep 的复制品。

Hubble 可以差异化为：

```text
ChatOps-first
中文团队友好
轻量部署
Agentic troubleshooting
飞书 / 企微优先
更强调群聊追问和半自动处置
```

Keep 更像 AIOps 管理平台，Hubble 更适合定位为 AI 告警机器人运行时。

## 4. StackStorm

项目地址：

- https://github.com/StackStorm/st2
- https://docs.stackstorm.com/overview.html

### 可借鉴点

StackStorm 是事件驱动自动化平台，它的抽象非常适合 Hubble 的工具和自动化层。

核心概念：

```text
Sensor  -> 监听外部事件
Trigger -> 系统内部事件表示
Rule    -> 把 Trigger 映射到 Action / Workflow
Action  -> 原子操作
Workflow -> 多步自动化编排
Pack    -> 插件分发单元
Audit   -> 执行审计
```

### Hubble 的取舍

建议重点参考：

```text
Trigger / Rule / Action / Workflow / Pack
```

但 Hubble 不需要一开始就做完整通用自动化平台。第一版只需要：

```text
AlertRule
ReadonlyTool
DangerousAction
Workflow as YAML
Execution audit
```

## 5. CloudEvents

项目地址：

- https://cloudevents.io/
- https://github.com/cloudevents/spec

### 可借鉴点

CloudEvents 解决的是事件格式不统一的问题。

Hubble 的接入源会很多：Webhook、Prometheus、Grafana、Sentry、CI/CD、云厂商、自研系统。如果每个源直接进入业务逻辑，后续会很乱。

建议引入内部统一信封：

```text
EventEnvelope
├── id
├── source
├── type
├── subject
├── time
├── data
├── datacontenttype
├── trace_id
├── tenant_id
└── extensions
```

### Hubble 的取舍

不强制用户按 CloudEvents 发数据，但内部事件模型参考 CloudEvents。

## 6. OpenTelemetry

项目地址：

- https://github.com/open-telemetry/opentelemetry-collector
- https://opentelemetry.io/docs/

### 可借鉴点

Hubble 的工具层会查日志、指标、Trace。OpenTelemetry 的价值在于相关性：

- trace_id。
- span_id。
- resource attributes。
- service.name。
- deployment.environment。
- structured logs。

### Hubble 的取舍

建议在 AlertEvent / Incident / ToolContext 里预留这些字段：

```text
trace_id
span_id
service.name
deployment.environment
k8s.namespace.name
k8s.pod.name
cloud.region
```

这样后续查日志、查 trace、查指标可以更自然地串起来。

## 7. LangGraph

项目地址：

- https://github.com/langchain-ai/langgraph

### 可借鉴点

LangGraph 适合做长运行、有状态、可中断、可恢复、human-in-the-loop 的 Agent 工作流。

Hubble 后续如果要做：

```text
多步诊断
工具调用计划
人工确认
会话记忆
失败恢复
```

可以参考 LangGraph 的状态图思路，甚至作为可选后端。

### Hubble 的取舍

第一版不建议强依赖 LangGraph，否则项目复杂度会上升。

建议先自研轻量接口：

```text
ReasoningProvider
ConversationState
ToolCallPlanner
HumanApprovalGate
```

等场景复杂后，再决定是否引入 LangGraph。

## 8. 最终取舍总结

Hubble 应该吸收这些项目的优点，但保持边界清晰：

```text
Alertmanager: 告警去重、分组、路由、静默、抑制
Grafana OnCall: 升级链、ChatOps、值班响应模型
Keep: AIOps、Provider、降噪、维护窗口、服务拓扑、工作流
StackStorm: Trigger / Rule / Action / Workflow / Pack / Audit
CloudEvents: 事件信封
OpenTelemetry: 日志、指标、Trace 相关性
LangGraph: 有状态 Agent 和 human-in-the-loop 思路
```

Hubble 的核心定位：

> 一个轻量、可插拔、ChatOps-first 的 AI 告警分析与处置机器人运行时。
