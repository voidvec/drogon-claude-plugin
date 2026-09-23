# drogon-gen-monitoring 实现指南

所有 API 与行为均已对照 drogon v1.9.13 源码核对（lib/inc/drogon/utils/monitoring/*.h、lib/inc/drogon/plugins/PromExporter.h、lib/src/PromExporter.cc、examples/prometheus_example）。引用格式为 文件:行号。

## 1. 参数验证：指标选型

| 类型 | 语义 | 更新方法（源码核对） | 典型用途 |
|------|------|----------------------|----------|
| counter | 只增不减 | `increment()`、`increment(double)`（Counter.h:51,60） | 请求/错误总数 |
| gauge | 可设任意值 | `set(double)`（Gauge.h:86）、`increment()`/`decrement()`（Gauge.h:53,59）、`setToCurrentTime()`（Gauge.h:97） | 连接数、队列深度 |
| histogram | 值分布 | `observe(double)`（Histogram.h:83） | 延迟分布 |

- 单调累加的量禁止用 gauge（Prometheus `rate()` 只对 counter 有意义）；counter 名建议 `_total` 后缀。
- 延迟一律 histogram 且以秒为单位（名带 `_seconds` 后缀）。
- boundaries 必须严格递增，否则构造抛异常（Histogram.h:72-80）；官方取 `{0.0001, 0.001, 0.01, 0.1, 0.5, 1, 2, 3}`（PromStat.cc:42-43）；`+Inf` 桶由框架自动生成，勿手写。

## 2. PromExporter 插件配置

```json
{
    "name": "drogon::plugin::PromExporter",
    "dependencies": [],
    "config": {
        "path": "/metrics",
        "collectors": [
            { "name": "http_requests_total", "help": "The total number of http requests", "type": "counter", "labels": ["method", "path"] },
            { "name": "http_request_duration_seconds", "help": "The processing time of http requests, in seconds", "type": "histogram", "labels": ["method", "path"] }
        ]
    }
}
```

- 字段核对：`path` 默认 `/metrics`（PromExporter.h:94）；`collectors[].name/help/type/labels`，type 取 counter/gauge/histogram（PromExporter.cc:37-110 解析，未知 type 打 LOG_ERROR）。
- 暴露原理：initAndStart 在 `path` 注册 `{Get, Options}` handler，输出 text/plain 的 Prometheus 文本格式并 setExpiredTime(5)（PromExporter.cc:18-36）。
- `collectors` 可省略：authforge 只配 `"path": "/metrics"`（apps/server/config/config.json:127-134），指标全在代码内注册。
- histogram 的 boundaries 无法在 config 声明，必须在代码首次 `metric()` 调用时传入（见下节）。

## 3. 三种指标的采集代码

完整调用链（官方 PromStat.cc:22-48 模式）：

```cpp
#include <drogon/plugins/PromExporter.h>
#include <drogon/utils/monitoring/Counter.h>
#include <drogon/utils/monitoring/Gauge.h>
#include <drogon/utils/monitoring/Histogram.h>
using namespace std::literals::chrono_literals;

auto prom = app().getPlugin<drogon::plugin::PromExporter>();
if (prom)
{
    try
    {   // getCollector：名字未注册抛 runtime_error（PromExporter.cc:206）；类型不符返回 nullptr
        auto c = prom->getCollector<drogon::monitoring::Counter>("http_requests_total");
        if (c)
            c->metric({method, path})->increment();   // 标签值个数必须等于 labels 数（Collector.h:68-73）
        auto g = prom->getCollector<drogon::monitoring::Gauge>("queue_size");  // 需在 config 声明同名 gauge
        if (g)
            g->metric({})->set(42);                   // 无标签时传 {}
        static const std::vector<double> boundaries{0.0001, 0.001, 0.01, 0.1, 0.5, 1, 2, 3};
        auto h = prom->getCollector<drogon::monitoring::Histogram>("http_request_duration_seconds");
        if (h)
            h->metric({method, path}, boundaries, 1h, 6)->observe(sec);  // 1h 滑窗/6 个时间桶（Histogram.h:40-46）
    }
    catch (const std::exception &)
    {
        // 指标未在 config/代码注册——记日志降级，不影响业务请求
    }
}
```

- `metric(labelValues, args...)`：按标签值组合取/建实例并缓存（Collector.h:63-84）；args 仅首次创建时生效，后续调用忽略。
- maxAge/timeBucketsCount：每 maxAge/timeBucketsCount 轮转一个时间桶，最多保留 timeBucketsCount 个，构成滑动窗口（Histogram.cc observe() 内 runEvery；Histogram.h:109-120）；maxAge>0 时 timeBucketsCount 必须>0（Histogram.h:62-69）。官方取 1h/6。

延迟采集的官方模式是 HttpCoroMiddleware（官方 PromStat.cc:17-52，头文件 `class PromStat : public HttpCoroMiddleware<PromStat>`，PromStat.h:13）：

```cpp
Task<HttpResponsePtr> PromStat::invoke(const HttpRequestPtr &req, MiddlewareNextAwaiter &&next)
{
    std::string path{req->matchedPathPattern()};
    auto method = req->methodString();
    auto prom = app().getPlugin<drogon::plugin::PromExporter>();
    if (prom) { /* 前置 Counter：getCollector<Counter>(...)->metric({method,path})->increment()，同上 */ }
    auto start = trantor::Date::date();
    auto resp = co_await next;
    if (prom) { /* 后置 Histogram：observe((end-start 微秒)/1e6)，boundaries/1h/6 同上 */ }
    co_return resp;
}
```

挂载靠 METHOD_LIST 第三个参数写中间件名（PromTestCtrl.h:12-13）：`ADD_METHOD_TO(PromTestCtrl::fast, "/fast", "PromStat");`

替代：`app().registerPostHandlingAdvice(回调(req, resp))`（HttpAppFramework.h:429-431，handler 生成响应后触发，不含静态文件响应）；起点用 `req->creationDate()`（HttpRequest.h:371）。适合无中间件的存量工程。

## 4. 补充模式：std::atomic 计数器（pay-plugin PayAuthMetrics 模式）

静态 `std::atomic<uint64_t>` 成员 + `++` 自增 + `snapshot()`/`toPrometheus()` 汇总导出（PayAuthMetrics.h:20-23、PayAuthMetrics.cc:9-56），由独立的低频 handler 输出 Prometheus 文本。

何时用：Prometheus 采集开销敏感的高频路径。monitoring::Counter 每次 increment 拿内部 mutex（Counter.h:53），`Collector::metric()` 查找再拿一层 mutex（Collector.h:74）——一次采集两次加锁；atomic `++` 无锁。pay-plugin 在每请求鉴权中调 `PayAuthMetrics::incXxx()`（AuthCheck.cc:164-246），PromExporter 只挂 `/metrics/base`（examples/pay-server/config.json:127-132），业务计数走自有路径，两者路径错开互不冲突。

## 禁止模式清单

1. 手写 `path`（默认 /metrics）上的自有 handler：与 PromExporter 已注册的 `{Get, Options}` handler 冲突（PromExporter.cc:18-36）。自有指标要么进 collectors，要么像 pay-plugin 把 PromExporter 挪到 `/metrics/base`、自有 handler 用其他路径。
2. 线程安全如实说明：Counter/Gauge/Histogram 的全部更新方法都由内部 `std::mutex` 保护（Counter.h:78、Gauge.h:104、Histogram.h:103 及 Histogram.cc 的 observe/collect），跨线程直接共享同一 Metric 对象是安全的，不构成数据竞争。真正禁止：(a) 把 `metric()` 返回的 `const std::shared_ptr<T>&`（指向 Collector 内部 map 元素，Collector.h:64）保存为长期全局句柄——应每次调用 `metric()` 或立即拷贝 shared_ptr；(b) 在已持业务锁的临界区内再调 `metric()->increment()` 造成锁嵌套。
3. 指标名含非法字符：Prometheus 命名规范 `[a-zA-Z_:][a-zA-Z0-9_:]*`，禁止连字符、点号、中文、数字开头；drogon 不校验名字（Metric.h 构造只查 label 数量），非法名会静默产出被 Prometheus 服务端拒绝的文本。
4. 在同步 Advice/热路径做高开销采集：registerPostHandlingAdvice 等同步回调里不要逐请求 new 对象或遍历全量 collector；boundaries 等 vector 必须 `static const`（PromStat.cc:42 模式）；更高频路径改用第 4 节 atomic 模式。

## 最小可运行示例（一个 Counter + 一个 Histogram）

1. config.json：第 2 节片段原样放入 plugins 数组，listeners 按需（官方 config.json:3-9 端口 5555）。
2. main.cc：`drogon::app().loadConfigFile("../config.json").run();`（官方 main.cc:5）。
3. 代码：实现第 3 节中间件（PromStat 模式），在目标路由用 `ADD_METHOD_TO(..., "PromStat")` 挂载。
4. 验证：`curl http://127.0.0.1:5555/metrics` 应输出 `# HELP http_requests_total ...`、`http_request_duration_seconds_bucket{...,le="0.1"}`、`..._sum`、`..._count`（exportCollector 拼装，PromExporter.cc:113-170）。
