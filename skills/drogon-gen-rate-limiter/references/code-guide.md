# drogon-gen-rate-limiter 实现指南
所有 API/字段均对照 drogon v1.9.13 源码核对（RateLimiter.h、plugins/Hodor.h、lib/src/Hodor.cc），生产实践取自 authforge 与 pay-plugin。

## 1. 参数验证与方案选型
- `capacity` 缺省或为 0 → 报错（0 在 Hodor 里表示"不限制"，Hodor.cc:9）；`time_unit` 须为正整数秒（Hodor.cc:71）。`scope=user` 且以会话为键 → 必须先 `app().enableSession(...)`（HttpAppFramework.h:887）；Hodor 无内建会话限流，用户维度靠 `setUserIdGetter` 取 id（Hodor.h:99-103）。
- `multi_instance=true` → 直接走方案C：内存限流在多实例下各算各的。选型：**方案A Hodor**——配置即可用、全局生效、分层配额（默认推荐）；**方案B 编程式**——局部限流、自定义键、与 Filter 串联；**方案C Redis**——多实例全局限数。

## 2. 方案A：Hodor 插件（推荐默认）
何时选我：全站或按路由前缀限流，不想写代码（authforge/pay-plugin 均此用法）。config.json 的 `plugins` 数组完整写法（字段逐个对照 Hodor.cc）：

```json
{
    "name": "drogon::plugin::Hodor", "dependencies": [],
    "config": {
        "algorithm": "token_bucket",
        "urls": ["^/api/.*"],
        "time_unit": 60,
        "capacity": 5000,
        "ip_capacity": 30,
        "user_capacity": 10,
        "use_real_ip_resolver": false,
        "multi_threads": true,
        "rejection_message": "Too Many Requests",
        "limiter_expire_time": 600,
        "trust_ips": ["127.0.0.1"],
        "sub_limits": [{ "urls": ["^/api/pay/create$"], "ip_capacity": 20 }]
    }
}
```

| 字段 | 含义/取值 | 默认 | 源码 |
|---|---|---|---|
| algorithm | "token_bucket"/"fixed_window"/"sliding_window" | "token_bucket" | Hodor.cc:69-70 |
| urls | 路径正则数组；空=全部 URL | 空 | Hodor.cc:10-24 |
| time_unit | 时间单元（秒） | 60 | Hodor.cc:71 |
| capacity | 全局容量；0=不限 | 0 | Hodor.cc:9 |
| ip_capacity | 单 IP 容量；0=不限 | 0 | Hodor.cc:43 |
| user_capacity | 单用户容量；需 setUserIdGetter | 0 | Hodor.cc:54 |
| use_real_ip_resolver | true 时 dependencies 须加 RealIpResolver | false | Hodor.cc:75 |
| multi_threads | true 时内部自动包 SafeRateLimiter | true | Hodor.cc:73、28-41 |
| rejection_message | 默认 429 纯文本响应体 | "Too many requests" | Hodor.cc:78-79 |
| limiter_expire_time | IP/用户限流器过期秒数 | 600（下限 time_unit×3） | Hodor.cc:81-84 |
| sub_limits | 子策略{urls,capacity,ip_capacity,user_capacity} | 空 | Hodor.cc:86-107 |
| trust_ips | IP/CIDR 白名单，命中直接放行 | 空 | Hodor.cc:109-117、136-139 |

**路径正则（源码核对）**：`urls` 各项用 `|` 拼成交替正则 `(a)|(b)`，对 `req->path()` 做 `std::regex_match` **全串匹配**（Hodor.cc:16-21、142）——故 `^/api` 不命中 `/api/x`，要写 `^/api/.*`，结尾 `$` 可省。`sub_limits` 每项 `urls` 须非空且至少一个容量>0，否则整项被 LOG_ERROR 跳过（Hodor.cc:91-104）；主策略先查、sub_limits 按序查，任一层超限即 429（Hodor.cc:233-247）。

**自定义 429 响应（authforge 模式）**：默认拒绝响应是纯文本 + k429、无 CORS 头（Hodor.cc:76-80），浏览器只能看到跨域报错。生产做法（authforge main.cc:249-271）：插件就绪后挂 `setRejectResponseFactory`，统一错误 envelope + 补 CORS 头：

```cpp
drogon::app().registerBeginningAdvice([]() {  // 插件构造完成后执行
    try {
        drogon::app().getPlugin<drogon::plugin::Hodor>()->setRejectResponseFactory(
            [](const drogon::HttpRequestPtr &req) -> drogon::HttpResponsePtr {
                Json::Value body;  // 统一错误 envelope
                body["code"] = "VALIDATION_RATE_LIMITED";
                body["request_id"] = req->getHeader("X-Request-Id");
                auto resp = drogon::HttpResponse::newHttpJsonResponse(body);
                resp->setStatusCode(drogon::k429TooManyRequests);
                resp->addHeader("Retry-After", "60");
                const auto &origin = req->getHeader("Origin");  // CORS 头保留
                if (!origin.empty()) resp->addHeader("Access-Control-Allow-Origin", origin);
                return resp;
            });
    } catch (const std::exception &) { LOG_INFO << "Hodor not loaded by this config"; }
});
```

注意：`user_capacity` 生效前提是启动后调过 `setUserIdGetter`，userId 为空该维度直接放行（Hodor.cc:184-189）——authforge 配了 user_capacity 却没设 getter，此维度实际不生效（真实踩坑）。

## 3. 方案B：编程式 RateLimiter
何时选我：局部路由限流、用业务键（会话/租户）计数、或与其他 Filter 串联。枚举 `RateLimiterType::kFixedWindow / kSlidingWindow / kTokenBucket`（RateLimiter.h:10-15）；`newRateLimiter(type, capacity, timeUnit)` 默认 60 秒（RateLimiter.h:42-45）；判定 `isAllowed()`（RateLimiter.h:52）。

**必须 SafeRateLimiter**：多 IO 线程下同一 limiter 会被多个事件循环线程并发调用，裸实现非线程安全；SafeRateLimiter 用 mutex 串行化（RateLimiter.h:56-74），Hodor 在 multi_threads=true 时同样这么包（Hodor.cc:28-41）。Filter 模板（按 IP 令牌桶，30 次/60 秒）：

```cpp
class RateLimitFilter : public drogon::HttpFilter<RateLimitFilter> {
  public:
    void doFilter(const drogon::HttpRequestPtr &req, drogon::FilterCallback &&fcb,
                  drogon::FilterChainCallback &&fccb) override {
        const std::string ip = req->peerAddr().toIp();
        drogon::RateLimiterPtr limiter;
        {
            std::lock_guard<std::mutex> lock(mutex_);
            auto &slot = limiters_[ip];  // 生产需过期清理（Hodor 用 CacheMap，Hodor.cc:46-52）
            if (!slot)                   // 必须 Safe 包装：跨事件循环线程共享
                slot = std::make_shared<drogon::SafeRateLimiter>(
                    drogon::RateLimiter::newRateLimiter(
                        drogon::RateLimiterType::kTokenBucket, 30,
                        std::chrono::seconds(60)));
            limiter = slot; }
        if (limiter->isAllowed()) { fccb(); return; }  // 放行：继续过滤链
        Json::Value body;  body["code"] = "RATE_LIMITED";
        auto resp = drogon::HttpResponse::newHttpJsonResponse(body);  // 超限：429
        resp->setStatusCode(drogon::k429TooManyRequests);
        const auto &origin = req->getHeader("Origin");  // 429 也带 CORS 头
        if (!origin.empty()) resp->addHeader("Access-Control-Allow-Origin", origin);
        fcb(resp);                                      // 拒绝：恰好一次回调
    }
  private:
    std::map<std::string, drogon::RateLimiterPtr> limiters_;
    std::mutex mutex_;
};
```

per-loop 无锁模式（简述）：`IOThreadStorage<RateLimiterPtr>` 给每个 IO 线程一槽（按 `getThreadNum()+1` 分槽，须在 `setThreadNum` 后构造，IOThreadStorage.h:66-82），`init()` 为各槽建裸 limiter，doFilter 里 `getThreadData()->isAllowed()` 仅被本事件循环线程访问（IOThreadStorage.h:97-102）→ 无需 SafeRateLimiter、无锁；代价是总配额按线程数放大，容量要除以线程数。

## 4. 方案C：Redis 分布式限流（多实例部署）
何时选我：多实例/多进程部署需要全局限数（INCR+EXPIRE 固定窗口）。回调签名：RedisClient.h:128、RedisResult.h:127、RedisException.h:67。

```cpp
auto cb = std::make_shared<drogon::FilterCallback>(std::move(fcb));
auto ccb = std::make_shared<drogon::FilterChainCallback>(std::move(fccb));
const std::string key = "rl:" + req->peerAddr().toIp();
drogon::app().getRedisClient()->execCommandAsync(
    [cb, ccb, key](const drogon::nosql::RedisResult &r) {
        if (r.asInteger() == 1)  // 窗口首个请求：补 EXPIRE 防键永存
            drogon::app().getRedisClient()->execCommandAsync(
                [key](const drogon::nosql::RedisResult &) {},
                [](const std::exception &e) { LOG_ERROR << e.what(); },
                "expire %s %d", key.c_str(), 60);
        if (r.asInteger() <= 100) { (*ccb)(); return; }  // 分支一：放行
        auto resp = drogon::HttpResponse::newHttpResponse();
        resp->setStatusCode(drogon::k429TooManyRequests); (*cb)(resp);  // 分支二：拒绝
    },
    [ccb](const std::exception &e) {
        LOG_ERROR << "redis limiter: " << e.what();
        (*ccb)();  // 异常分支：显式 fail-open，不吞回调
    },
    "incr %s", key.c_str());
```

双回调纪律：fcb/fccb 移交异步回调后，成功与异常**每个路径都恰好调用一次**二者之一——早返回后不得再调，异常分支必须显式降级（fail-open 或 429 fail-close），禁止吞掉不调。

## 禁止模式清单
1. 多个事件循环线程共享**非 SafeRateLimiter** 的 RateLimiterPtr——数据竞争；必须 Safe 包装（RateLimiter.h:56-74）或 per-loop 独享。
2. Hodor 字段拼错（本版本真实字段仅上表 12 个）：实际键是 `trust_ips`（Hodor.cc:109），Hodor.cc:112 的报错文案误写成 trusted_ips、勿被误导；`per_ip_traffics`/`use_token_bucket`/`session_limit`/`remap_address` 不存在，属旧版或臆造；`algorithm` 拼错（如 "tokenBucket"）不报错、静默回落令牌桶（RateLimiter.h:17-24）；`time_unit` 是秒数整数，不是 "60s" 字符串。
3. 限流 429 响应丢 CORS 头——浏览器把 429 报成跨域失败，前端读不到 body；在 setRejectResponseFactory/Filter 拒绝分支补 `Access-Control-Allow-Origin`（若全站已用 registerPreSendingAdvice 加 CORS，429 也会过该链，HttpServer.cc:801）。
4. 会话维度限流忘 `app().enableSession(...)`（HttpAppFramework.h:887）——session 不生效，按 sessionId 的限流键全部退化。
5. 静默失效两例：`user_capacity` 配了但没调 `setUserIdGetter`——该维度直接放行（Hodor.cc:184-189）；urls 正则未覆盖全路径（如 `^/api`）——regex_match 全串匹配不命中，限流不生效（Hodor.cc:142）。
