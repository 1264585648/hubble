# 插件接口约定

Hubble 的核心扩展点包括五类：

1. `Ingress`：接入层插件。
2. `ModelProvider / ModelRouter`：模型调度插件。
3. `Tool`：工具插件。
4. `Notifier`：推送插件。
5. `SessionAdapter`：会话监听插件。

所有插件都应该遵循以下原则：

- 输入输出结构化。
- 不直接依赖具体推送渠道。
- 不在插件里写死密钥。
- 支持超时和错误返回。
- 可被配置文件启用或关闭。

## 1. Ingress 接入插件

```python
class Ingress(Protocol):
    name: str

    async def start(self, handler: AlertHandler) -> None:
        ...
```

`Ingress` 负责把外部数据转为 `AlertEvent`，然后调用 handler。

### 示例场景

- `WebhookIngress`：接收 HTTP 请求。
- `PollingIngress`：定时调用 HTTP API。
- `PrometheusIngress`：解析 Alertmanager payload。
- `SentryIngress`：解析 Sentry issue event。

## 2. ModelProvider / ModelRouter

```python
class ModelProvider(Protocol):
    name: str

    async def analyze_alert(self, alert: AlertEvent, context: dict) -> AlertAnalysis:
        ...
```

`ModelProvider` 负责调用某个具体模型。`ModelRouter` 负责根据场景选择 provider。

### 路由策略

- `severity >= critical`：使用高可靠模型。
- `low severity`：使用低成本模型或规则引擎。
- `large context`：使用长上下文模型。
- `privacy sensitive`：使用私有模型。

## 3. Tool 工具插件

```python
class Tool(Protocol):
    name: str
    description: str
    dangerous: bool

    async def run(self, params: dict, context: ToolContext) -> ToolResult:
        ...
```

工具层是告警机器人真正有价值的部分。模型只负责提出工具调用意图，Hubble 负责校验、执行、审计和返回结果。

### 工具元信息

每个工具都应该声明：

- `name`：唯一名称。
- `description`：给模型看的能力描述。
- `input_schema`：参数结构。
- `dangerous`：是否可能产生副作用。
- `timeout_seconds`：超时时间。
- `required_scopes`：权限范围。

### 工具调用安全

- 只读工具可以自动执行。
- 危险工具必须人工确认。
- 所有工具调用都要记录参数、执行人、结果和耗时。
- 工具返回应做脱敏，避免把密钥、手机号、Token 等敏感信息发到群里。

## 4. Notifier 推送插件

```python
class Notifier(Protocol):
    name: str

    async def send(self, notification: Notification) -> SendResult:
        ...
```

推送插件只负责发送，不负责生成告警文案。文案由核心层统一生成，避免每个渠道风格不一致。

### 推荐支持

- `FeishuNotifier`
- `WeComNotifier`
- `DingTalkNotifier`
- `SlackNotifier`
- `WebhookNotifier`

## 5. SessionAdapter 会话插件

```python
class SessionAdapter(Protocol):
    name: str

    async def start(self, handler: SessionHandler) -> None:
        ...

    async def reply(self, message: SessionMessage, text: str) -> None:
        ...
```

会话层用于处理群聊追问、命令式操作和人工确认。

### 命令建议

```text
/explain              解释当前告警
/logs 10m service=a   查询最近 10 分钟日志
/ack                  标记已确认
/resolve              标记已恢复
/runbook              查找相关处理手册
/silence 30m          静默 30 分钟
```

## 6. 插件加载方式

初期可使用配置文件显式加载：

```yaml
plugins:
  ingress:
    - type: webhook
      name: prometheus
  notifiers:
    - type: feishu
      name: sre-feishu
```

后续可支持 Python entry points：

```toml
[project.entry-points."hubble.tools"]
query_logs = "hubble_tools_loki:QueryLogsTool"
```

## 7. 错误处理约定

插件不应该随意抛出未处理异常，应该返回结构化错误：

```text
ToolResult
├── ok
├── data
├── error
├── elapsed_ms
└── metadata
```

这样模型可以根据错误继续推理，例如“日志平台暂时不可用，建议先检查监控指标”。
