---
name: drogon-gen-monitoring
description: 需要接入 Prometheus 指标/Counter/Gauge/Histogram/自定义业务监控时，生成 PromExporter 配置与指标采集代码。
version: 0.2.0
---

# drogon-gen-monitoring

生成 drogon 的 Prometheus 监控接入代码（PromExporter 插件配置 + Counter/Gauge/Histogram 采集 + 热路径 atomic 补充）。

## 使用场景

当需要为服务暴露 Prometheus 指标（请求计数、延迟分布、业务状态值），或为高频热路径增加轻量业务计数时，使用此技能生成已对照 drogon v1.9.13 源码核对的配置与代码。

## 输入参数

- `metrics`：指标定义，格式 `名称:类型`，多项逗号分隔（类型 counter/gauge/histogram）
- `labels`：标签名列表（如 `method,path`，可选；延迟类建议 method,path）
- `collect_point`：采集点，`middleware`（全局请求统计）/ `handler`（业务代码内）/ `advice`（PostHandling 钩子），默认 `handler`
- `path`：指标暴露路径（默认 `/metrics`）
- `hot_path`：高频热路径标记（`true` 时改用 atomic 计数器补充模式，可选）

## 输出

1. config.json 的 PromExporter 插件段（path + collectors 数组：name/help/type/labels）
2. 采集代码：`getCollector<T>(名)->metric({标签值})->increment/set/observe` 完整调用链（含异常捕获与判空）
3. 延迟采集中间件模板（官方 prometheus_example 的 PromStat 模式，含路由挂载）
4. 高频路径 std::atomic 计数器 + Prometheus 文本导出的补充方案（pay-plugin 模式）

## 示例

```
/drogon-gen-monitoring metrics=http_requests_total:counter,http_request_duration_seconds:histogram labels=method,path collect_point=middleware
```

## 参考文件
详细实现指南见 `references/code-guide.md`（含指标选型、PromExporter 配置、采集模板、禁止模式清单、最小可运行示例）。生成代码前先读取该文件。
