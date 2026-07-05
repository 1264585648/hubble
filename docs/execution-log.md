# Execution Log

本文记录每一轮实际执行的任务，避免 Task Plan 和代码演进脱节。

## 2026-07-05：第一批任务执行

### 已完成任务

```text
T1.8 Intake Rule Dry-run
T1.9 Intake Rule 命中统计
T2.3 Alertmanager Webhook Parser
```

## T1.8 Intake Rule Dry-run

### 完成内容

- 新增 `IntakeDryRunRequest`。
- 新增 `IntakeDryRunResponse`。
- 新增 Runtime 方法：`dry_run_intake_rule()`。
- 新增 API：`POST /intake-rules/dry-run`。
- 前置规则配置页新增：
  - “测试当前规则”按钮。
  - “使用已保存规则测试事件”按钮。
  - Dry-run 结果展示区。

### 验收结果

- 提交样例事件可以看到命中规则。
- 可以提交临时规则测试但不保存。
- dry-run 不会创建 Alert / Incident。
- dry-run 不会发布正式 `alert.ingested` 事件。
- 测试覆盖 dry-run 不创建 Alert。

## T1.9 Intake Rule 命中统计

### 完成内容

`IntakeRule` 新增统计字段：

```text
matched_count
allowed_count
filtered_count
tag_count
rewrite_count
last_matched_at
```

`IntakeRuleEngine.evaluate()` 新增参数：

```text
record_stats: bool = True
```

dry-run 调用时使用：

```text
record_stats=False
```

### 验收结果

- `GET /intake-rules` 会返回统计字段。
- 正式告警命中规则后计数增加。
- drop 规则命中后 `filtered_count` 增加。
- tag / rewrite 规则会分别增加对应计数。
- 页面展示规则 JSON，因此可以看到统计字段。
- 测试覆盖命中统计。

## T2.3 Alertmanager Webhook Parser

### 完成内容

- 新增 `AlertmanagerWebhookAdapter`。
- 新增 Runtime 方法：`ingest_alertmanager_webhook()`。
- 新增 API：`POST /webhook/alertmanager/{source}`。
- 新增示例：`examples/alertmanager_payload.json`。
- Alertmanager `alerts[]` 会被拆成多条 `EventEnvelope(type="alert.received")`。
- 每条 alert 都继续走：

```text
Intake Rule
→ Alert Lifecycle
→ Incident Lifecycle
→ Policy
→ Reasoning
→ Channel
```

### 字段映射

```text
labels.alertname        → Alert.title
annotations.description → Alert.description
labels.severity         → Alert.severity
alert.status            → Alert.status
alert.fingerprint       → Alert.fingerprint
```

### 验收结果

- Alertmanager batch payload 可以通过 `/webhook/alertmanager/{source}` 接入。
- firing alert 能映射为 `status=firing`。
- resolved alert 能映射为 `status=resolved`。
- severity 能从 labels 中映射。
- summary / description 能从 annotations 中映射。
- 有示例 payload。
- 有接口测试覆盖 firing 和 resolved。

## 本轮新增 / 修改文件

```text
src/hubble/intake/models.py
src/hubble/intake/service.py
src/hubble/adapters/alertmanager.py
src/hubble/runtime.py
src/hubble/server.py
src/hubble/alerts/service.py
examples/alertmanager_payload.json
tests/test_server.py
configs/hubble.example.yaml
README.md
```

## 当前最近下一批任务

建议继续按以下顺序执行：

```text
1. T2.6 Incident 状态流转 API
2. T3.3 YAML Policy DSL
3. T4.3 OpenAI-compatible Provider
4. T6.2 Feishu ChannelAdapter
5. T5.2 HTTP Tool
6. T5.3 Prometheus Query Tool
7. T7.1 Storage Interface
```
