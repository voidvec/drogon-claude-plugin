# drogon-claude-plugin 升级扩展方案 v0.2.0

> 基于 drogon v1.9.13 源码与官方文档（https://drogonframework.github.io/drogon-docs/）的深度分析，提出本插件的升级扩展方案。
> 所有接口签名均已与 `drogon` 仓库当前源码核对（源码为准）；官方文档章节结构作为"功能域覆盖度"的对标基准。
> 编写日期：2026-07-02。

## 0. 背景与方法

### 0.1 现状（v0.1.0）
- **规则层**：CLAUDE.md 已覆盖 12 组（A–L），聚焦异步回调、事件循环、控制器路由、配置、CMake、ORM、Redis、CSP、Plugin/Filter/Middleware、测试。
- **技能层**：10 个代码生成技能（controller / cmake / csp-view / db-config / filter / middleware / orm-crud / redis-config / test / setup-config）。
- **钩子层**：PostToolUse + SessionStart，扫描 4 类文件的高频违规。

### 0.2 方法
1. 枚举 drogon `lib/inc/drogon/*.h` 全部公开头文件，与 CLAUDE.md 覆盖域做差集。
2. 用官方文档章节（CHN/ENG/VI 三语的 `_Sidebar.md`，共 19 章 + FAQ）对标功能域覆盖度。
3. 阅读 `examples/` 下 14 个真实示例（file_upload / login_session / prometheus_example / client_example / websocket_client / redis_cache / cors / async_stream / simple_reverse_proxy 等），提取 v1.9.x 实际推荐用法。
4. 每个新增规则点的接口签名、行号均回查 `HttpAppFramework.h` / `Session.h` / `HttpMiddleware.h` / `MultiPart.h` / `HttpClient.h` / `RateLimiter.h` / `PubSubService.h` / `IOThreadStorage.h` / `Cookie.h` / `RequestStream.h` 源码。

### 0.3 核心发现：现有插件的覆盖盲区

将官方文档 19 章与现有 12 组规则对照，**以下功能域在 v0.1.0 中完全缺失或仅一笔带过**：

| 官方文档章节 | 现有规则组 | 缺口 |
|---|---|---|
| 07-会话（Session） | 无 | **完全缺失** |
| 09-1-文件处理程序（File Upload） | 无 | **完全缺失** |
| 13-AOP 面向切面编程（Advices） | 无 | **完全缺失**（drogon 独有强项） |
| 16-Brotli 压缩 | 无 | **完全缺失** |
| 17-协程（Coroutine handler/中间件/客户端） | A.6 局部提及 | **协程中间件、协程客户端、Task vs AsyncTask 细节缺失** |
| FAQ-1-线程模型 | B 组 | 缺 `IOThreadStorage`、`getIOLoop`、`getCurrentThreadIndex` |
| —（官方文档未单列但源码存在） | 无 | **HttpClient 出站请求、Cookie、RequestStream 流式上传、RateLimiter、PubSubService、Monitoring/Prometheus、registerHandler lambda 路由、HTTPS/SSL 配置、reverse proxy forward()、内置插件族（AccessLogger/Hodor/PromExporter/SecureSSLRedirector/SlashRemover/RealIpResolver/Redirector）** |

此外，现有插件规则中 **所有示例都基于"宏注册 + 控制器类"的经典写法**，而 v1.9.x 官方示例与文档主推的 **`app().registerHandler(path, lambda, {verbs})` lambda 内联路由**（含 `{N}` 位置参数捕获、`registerHandlerViaRegex` 正则路由）在 CLAUDE.md 中**只字未提**——这是 v0.1.0 与官方推荐用法之间最大的偏差。

---

## 1. 规则层扩展（CLAUDE.md 新增 M–T 组）

> 命名沿用现有 A–L 的字母序，新增 8 组。每组保持现有风格：规则条目 + 正/反代码示意 + 源码位置断言。

### M. 会话（Session）管理

**对标**：官方文档 CHN-07；源码 `lib/inc/drogon/Session.h`、`lib/src/SessionManager.cc`。

1. **默认关闭，显式开启**：会话需在启动链上 `app().enableSession(timeout)` 开启；`enableSession()` 不带参数时使用默认超时。AI 不得在未开启会话时调用 `req->session()`（会返回空指针/无效对象）。证据：`HttpAppFramework.h` `enableSession`。
2. **会话是 `std::shared_ptr<Session>`**：通过 `req->session()` 获取 `SessionPtr`；AI 不得假设其为指针解引用之外的语义。会话数据底层为 **`std::map<std::string, std::any>`**（`Session.h:34`，`using SessionMap = std::map<...>`——**不是** `unordered_map`，评审 §2.2 已核对修正），多线程安全（内部 `std::mutex`）。在调用重载的 `session->modify([](Session::SessionMap &m){...})` 时，迭代器/接口须按 `std::map`（有序）使用。
3. **取值优先 `getOptional<T>` / 类型安全 `modify<T>`**：`session->getOptional<T>(key)` 返回 `std::optional<T>`；写值用 `insert(key, value)`（key 已存在则**不**覆盖，见 `Session.h:155` 注释）或 `modify<T>(key, callable)`。AI 不得用 `session->operator[]` 直接取值（返回 `std::any&`，需再 `any_cast`，易错）。`modify<T>` 中类型不匹配会打 `LOG_ERROR<<"Bad type"`（`Session.h:120`）——AI 不得忽略类型一致性。
4. **登录后换号防 fixation**：认证成功后调用 `session->changeSessionIdToClient()`（`Session.h:220`），框架在响应时下发新 session ID cookie，防 session fixation 攻击。
5. **会话写操作在响应前完成**：会话 cookie 在响应发出时落盘；AI 不得在已 `callback(resp)` 之后再异步写会话（写不入当前请求的 cookie）。
6. **禁把会话当缓存做大对象存储**：会话驻留内存（`CacheMap`，`SessionManager.cc:50`），AI 不得往 session 塞大对象（如文件字节、大 JSON），应只放用户标识等小数据。

```cpp
// ✅ 正确：取值用 getOptional，登录换号
app().registerHandler("/login",
    [](const HttpRequestPtr &req,
       std::function<void(const HttpResponsePtr &)> &&callback) {
        if (check(req->getParameter("user"), req->getParameter("passwd"))) {
            req->session()->insert("userId", userId);
            req->session()->changeSessionIdToClient();   // M.4 防 fixation
            callback(...);
        } else { callback(k401); }
    }, {Post});

// ❌ 错误：未开启 enableSession 就用 session；或用 any_cast 裸取值
auto &v = req->session()->operator[]("userId");   // 返回 any&，未处理
```

### N. 文件上传（MultiPart / HttpFile）

**对标**：官方文档 CHN-09-1；源码 `lib/inc/drogon/MultiPart.h`、`examples/file_upload/file_upload.cc`。

1. **`MultiPartParser` 是入口**：解析 multipart/form-data 请求需构造 `MultiPartParser parser;` 并调用 `parser.parse(req)`；返回 **0 表示成功，非 0 表示失败**（`MultiPart.h:175`）。AI 不得假设 `parse` 返回 bool 或抛异常。
2. **必须先校验再 save**：`parse` 后应先校验 `getFiles().size()` 与文件类型/大小，再决定是否 `save()`；`HttpFile::save()` 默认写 `app().getUploadPath()`（`MultiPart.h:64`）。
3. **路径前缀语义**：`file.save(path)` 中，path 以 `/`、`./`、`../` 开头或为 `.`/`..` 时为**绝对/相对根路径**，否则拼接在 `getUploadPath()` 之下（`MultiPart.h:68-72`）。AI 不得假设 `save("uploads")` 等价于 `save("./uploads")`——前者会变成 `getUploadPath()/uploads/`，后者是当前工作目录的 `uploads/`。
4. **`saveAs` 同理**：`saveAs(fileName)` 中 fileName 不以 `/`、`./`、`../` 开头时，会拼到 `getUploadPath()` 之下（`MultiPart.h:77-80`）。AI 不得用用户可控字符串直接拼 `saveAs`，避免路径穿越（path traversal）。
5. **必须配置 `setClientMaxBodySize`**：上传前必须在启动链设 `app().setClientMaxBodySize(bytes)`，否则默认上限会拒绝大文件。`file_upload.cc:42` 示例设为 `20*2000*2000`。
6. **文件名/扩展名不可信**：`getFileName()` 来自客户端，AI 不得直接用它拼落盘路径或做信任判断；应用 `getMd5()` 或服务端重命名（`saveAs(服务端生成的名字)`）。
7. **流式上传大文件用 `RequestStream`**：超大文件（GB 级）避免一次性 `parse`（占内存），改用 `RequestStreamReader`（见 R 组）。普通上传用 `MultiPartParser`。

### O. AOP 面向切面编程（Advices）

**对标**：官方文档 CHN-13；源码 `lib/inc/drogon/HttpAppFramework.h:273-441, 920-928`。这是 drogon 区别于其他 C++ 框架的独有能力，**当前插件完全未覆盖**。

> ⚠️ **切面数量修正（评审 §2.3，已核对源码）**：原方案统计为 8 个，实际 drogon v1.9.13 提供 **11 个**内建切面。官方文档 CHN-13 正文只列了较常用的若干个，未覆盖全部；本方案以源码为准，给出完整 11 个及分类。

1. **11 个内建切面**（按生命周期分类，全部已回查 `HttpAppFramework.h`）：

   **(a) 请求/响应生命周期（7 个）**

| 切面 | 注册接口 | 调用签名 | 能否拦截 | 行号 |
|---|---|---|---|---|
| Sync | `registerSyncAdvice` | `HttpRequestPtr(const HttpRequestPtr&)` | 是（返非空 resp 短路，最早） | 306-313 |
| Pre-Routing | `registerPreRoutingAdvice` | 拦截型 / 观察型（两种重载） | 路由前 | 367/379 |
| Post-Routing | `registerPostRoutingAdvice` | 拦截型 / 观察型 | 路由后、过滤器前 | 389/401 |
| Pre-Handling | `registerPreHandlingAdvice` | 拦截型 / 观察型 | 过滤器后、handler 前 | 410 区域 |
| Post-Handling | `registerPostHandlingAdvice` | `void(req, resp)` | 否（不含静态文件响应） | — |
| Pre-Sending | `registerPreSendingAdvice` | `void(req, resp)` | 否（**含**静态文件响应，发往客户端前） | 439-441 |
| HttpResponseCreation | `registerHttpResponseCreationAdvice` | `void(const HttpResponsePtr&)` | 否（所有 resp 创建时，含 404） | 303-304 |

   **(b) 系统/连接生命周期（2 个）**

| 切面 | 注册接口 | 调用签名 | 说明 | 行号 |
|---|---|---|---|---|
| Beginning | `registerBeginningAdvice` | `void()` | `run()` 后触发一次；此时 controller/filter/plugin/DB client 均已就绪 | 277-278 |
| NewConnection | `registerNewConnectionAdvice` | `bool(const InetAddress&, const InetAddress&)` | 返 false 断连 | 288-290 |

   **(c) 会话生命周期（2 个）**

| 切面 | 注册接口 | 调用签名 | 说明 | 行号 |
|---|---|---|---|---|
| SessionStart | `registerSessionStartAdvice` | `AdviceStartSessionCallback`（`void(const std::string&)`） | 新 session 创建时 | 920-921 |
| SessionDestroy | `registerSessionDestroyAdvice` | `AdviceDestroySessionCallback` | session 超时销毁时 | 927-928 |

2. **拦截型 vs 观察型重载**：`Pre-Routing / Post-Routing / Pre-Handling` 各有**两个重载**——三参数拦截型 `void(req, AdviceCallback&&, AdviceChainCallback&&)`（与 Filter 的 `doFilter` 语义一致）和单参数观察型 `void(const HttpRequestPtr&)`（无拦截能力、开销更低）。**不打算拦截就用观察型**（`HttpAppFramework.h:379`）。AI 不得误用：单参数版没有回调参数，无法发响应。
3. **SyncAdvice 返回非空即短路**：`registerSyncAdvice` 返回**非空** `HttpResponsePtr` 时直接发响应、跳过所有后续（路由/过滤/handler），是最早的拦截点（`HttpAppFramework.h:306-313`）。AI 不得在 SyncAdvice 里做重活（它在请求最前端、同步执行）。
4. **HttpResponseCreation 影响所有响应**：含 404、drogon 内部错误响应。AI 不得在此做条件性 break 逻辑假设只影响业务响应。
5. **Post-Handling vs Pre-Sending 的区别**：Post-Handling **不含**静态文件响应；Pre-Sending **包含**静态文件响应，是修改响应头/统一日志的最后机会（评审 §2.3 补充，源码 `HttpAppFramework.h:439-441`）。
6. **拦截型 Advice 的恰好一次纪律**（评审 §3.2）：`Pre-Routing / Post-Routing / Pre-Handling` 拦截型必须**恰好调用一次** `AdviceCallback`（返回自定义响应）或 `AdviceChainCallback`（继续链）。漏调→连接挂起；重调→内存崩溃。与 A.1 回调纪律同源。
7. **advice 注册时机**：在 `app().run()` 之前注册；AI 不得在 handler 内动态注册 advice。

### P. 协程（Coroutine）完整规范

**对标**：官方文档 CHN-17；源码 `lib/inc/drogon/utils/coroutine.h`、`HttpMiddleware.h:87-147`、`HttpClient.h:147-165`。现有 A.6 仅一笔带过，本组给出完整纪律。

1. **编译开关**：协程依赖 `__cpp_impl_coroutine` 宏 + CMake `USE_COROUTINE=ON`。AI 不得在未确认编译开关时使用 `co_await`/`Task<>`。
2. **三种协程返回类型语义**（关键区分，v0.1.0 未讲清）：

| 返回类型 | 用途 | 异常行为 | 响应交付 |
|---|---|---|---|
| `Task<HttpResponsePtr>` | handler 返回响应 | 向上传播、可被 `co_await` | 框架负责 |
| `Task<>` | 通用异步任务 | 向上传播 | 调用方负责 |
| `AsyncTask` | fire-and-forget | **未处理异常 → `std::terminate`** | 调用方负责 |

   用 `AsyncTask` 必须 try/catch 兜底（A.7 已述）；优先 `Task<HttpResponsePtr>`。

3. **协程中间件**：基类是 **`HttpCoroMiddleware<T, false>`**（`HttpMiddleware.h:111`），不是回调式 `HttpMiddleware`。签名 `Task<HttpResponsePtr> invoke(const HttpRequestPtr&, MiddlewareNextAwaiter&& next)`，用 `co_await next` 取得下游响应。框架的 `async_run` 包装器**自动** catch `std::exception` 并经 `internal::handleException` 处理（`HttpMiddleware.h:126-134`）——协程中间件内异常**不会** `std::terminate`（与裸 `AsyncTask` 不同）。
4. **`MiddlewareNextAwaiter`**：`co_await next` 返回 `HttpResponsePtr`（`HttpMiddleware.h:89-108`）。AI 不得对 `next` 调用回调语法（那是回调式中间件 `nextCb(callback)` 的用法）。
5. **协程 ORM/Redis/HttpClient**：`execSqlCoro`、`sendRequestCoro`、redis 协程方法可 `co_await`。`sendRequestCoro` 超时抛 `HttpException(ReqResult::Timeout)`（`HttpClient.h:155`），必须 try/catch。
6. **`forwardCoro`**：反向代理的协程版 `co_await app().forwardCoro(req, hostString, timeout)`（`HttpAppFramework.h:770`）。
7. **⚠️ 参数生命周期纪律（评审 §3.1，高危 Use-After-Free，已用官方示例核对）**：**裸协程 handler（返回 `Task<>` / `Task<HttpResponsePtr>` / `AsyncTask`）的请求/回调参数必须按值传递**，禁止引用传递。原因：协程在 `co_await` 处挂起后，原始栈帧（含 handler 调用方传入的临时对象）可能已销毁，恢复时引用即悬空。官方示例 `examples/redis_cache/controllers/SlowCtrl.cc` 刻意区分了两种写法：

   ```cpp
   // 回调式 handler —— 引用安全（不会挂起）
   void SlowCtrl::hello(const HttpRequestPtr &req,
                         std::function<void(const HttpResponsePtr &&)> &&callback,
                         std::string &&userid);

   // 协程 AsyncTask handler —— 必须按值（对比官方 SlowCtrl::observe）
   drogon::AsyncTask SlowCtrl::observe(
       HttpRequestPtr req,                                        // 按值，非 const &
       std::function<void(const HttpResponsePtr &)> callback,     // 按值，非 &&
       std::string userid);                                        // 按值，非 &&
   ```

   | 场景 | `req` / `callback` 传参 | 理由 |
   |---|---|---|
   | 裸协程 handler（`Task*` / `AsyncTask`） | **按值** | 协程挂起恢复后引用悬空 |
   | 回调式 handler（`void`） | 引用 / `&&` | 不挂起，框架保证生命周期 |
   | 协程中间件 `HttpCoroMiddleware::invoke` | **可引用** | 框架 `async_run` 外层 lambda 已按值捕获 req/nextCb/mcb（`HttpMiddleware.h:121-124`），引用指向该副本，生命周期与协程同步 |

   > 例外说明：`prometheus_example/filters/PromStat.cc` 的协程中间件用 `const HttpRequestPtr &req` 是安全的，正是因为它是 `HttpCoroMiddleware`（框架已拷贝）。AI 不得把该例外外推到裸协程 handler。

### Q. HTTP 客户端（出站请求）

**对标**：源码 `lib/inc/drogon/HttpClient.h`、`examples/client_example/main.cc`。当前插件只讲入站，未讲出站。

1. **客户端用 `app()` 的事件循环**：`HttpClient::newHttpClient(host)` 默认绑 `app()` 的循环，**必须 `app().run()` 才工作**（`HttpClient.h:62-69`）。AI 不得在未 run 的程序里发请求。
2. **同步 `sendRequest` 死锁保护**：三参数同步重载有 `assert(!getLoop()->isInLoopThread())`（`HttpClient.h:133`）——**禁止在事件循环线程/异步回调里调用同步 `sendRequest`**，否则断言失败或死锁。handler 内必须用异步 `sendRequest(req, callback)` 或协程 `sendRequestCoro`。
3. **同一个 req 对象不可跨线程复用发送**：`sendRequest` 会**修改** req 对象（加 header），多线程用同一 req 危险（`HttpClient.h:87-88, 108-109`）。
4. **timeout 语义**：单位秒，0 = 不超时；超时回调以 `ReqResult::Timeout` + 空 resp 触发。AI 不得忘记检查 `ReqResult`（`client_example/main.cc:52`：`if (result != ReqResult::Ok)`）。
5. **反向代理用 `app().forward`**：内部转发用 `app().forward(req, callback, hostString, timeout)` 而非自建 client + 转发 header（`HttpAppFramework.h:760`）。

### R. 流式请求 / 大文件上传（RequestStream）

**对标**：源码 `lib/inc/drogon/RequestStream.h`（v1.9.x 新增）；`async_stream` 示例。

> ⚠️ **API 修正（评审 §2.1，已核对源码）**：`HttpRequest` **没有** `setStreamReader` 方法（`HttpRequest.h` 不含该方法）。流式上传必须通过 `drogon::internal::createRequestStream(req)` 把请求转换成 `RequestStreamPtr` 后再设置 reader（`RequestStream.h:47`）。

1. **handler 标记为流式**：先用 `internal::createRequestStream(req)` 取得 `RequestStreamPtr`（可能为空，需判空），再 `stream->setStreamReader(reader)`。普通 multipart 解析会把整个 body 读进内存，**超大文件必须用流式**。
   ```cpp
   // ✅ 正确：经 createRequestStream 封装
   auto stream = drogon::internal::createRequestStream(req);
   if (stream) {
       auto reader = RequestStreamReader::newReader(dataCb, finishCb);
       stream->setStreamReader(reader);
   }
   // ❌ 错误：HttpRequestPtr 上直接调 setStreamReader —— 编译错误
   // req->setStreamReader(reader);
   ```
2. **三回调模型**：`RequestStreamReader::newReader(dataCb, finishCb)`——`onStreamData(const char*, size_t)` 分块、`onStreamFinish(std::exception_ptr)` 结束（`RequestStream.h:95-103`）。AI 不得在 dataCb 里阻塞事件循环。
3. **multipart 流式**：`newMultipartReader(req, headerCb, dataCb, finishCb)` 提供 `MultipartHeader` 回调（`RequestStream.h:110-114`）。
4. **finish 必须发响应**：`onStreamFinish` 触发时（含 `exception_ptr` 非空表示出错）必须 `callback(resp)`，遵守 A.1。`StreamError` 有 `kBadRequest`/`kConnectionBroken` 两种码（`RequestStream.h:50-55`）。

### S. Cookie 安全

**对标**：源码 `lib/inc/drogon/Cookie.h`。

1. **`Cookie(key, value)` 构造**；通过 `resp->addCookie(cookie)` 或 `resp->addCookie("k","v")` 设置。
2. **会话 cookie 必须 `setHttpOnly(true)`**：默认 `httpOnly_=true`（`Cookie.h:418`），AI 不得显式设 false 除非有明确 JS 读取需求。
3. **敏感 cookie 检查 `setSecure` / `setSameSite`**：HTTPS 站点应 `setSecure(true)`；跨站防 CSRF 用 `setSameSite(SameSite::kLax)` 或 `kStrict`（`Cookie.h:45-51`）。`SameSite::kNone` 必须 `setSecure(true)`（浏览器强制）。
4. **`setPartitioned(true)` 自动连带 `setSecure(true)`**（`Cookie.h:165-168`），用于 CHIPS 第三方 cookie 分区。
5. **AI 不得手工拼 `Set-Cookie` 字符串**：用 `Cookie::cookieString()` 或 `resp->addCookie`，避免转义/格式错误。

### T. 线程模型进阶 / 共享状态

**对标**：官方文档 FAQ-1；源码 `lib/inc/drogon/IOThreadStorage.h`、`HttpAppFramework.h`。补充 B 组未尽的实战点。

1. **`IOThreadStorage<T>` 做无锁循环局部状态**：跨请求复用的对象（如每循环一个 DB 连接、一个计数器）用 `IOThreadStorage<MyData> storage_;`，`storage_->...` 自动取当前循环的副本（`IOThreadStorage.h:97-102`，靠 `app().getCurrentThreadIndex()` 寻址）。**构造时 `assert(app().getThreadNum()>0)`**——AI 不得在 `app().setThreadNum()` 之前构造 `IOThreadStorage`。
2. **`getThreadData/setThreadData` 只能在 handler 内调**：依赖 `getCurrentThreadIndex()`，handler 之外（如 main 里）调用是未定义（`IOThreadStorage.h:95-96` 注释）。
3. **跨循环派发用 `runInLoop` / `queueInLoop`**：`app().getIOLoop(i)->runInLoop(cb)` 或 `getLoop()->queueInLoop(cb)`（B.2 已述，本条强调取 loop 的正确入口：`app().getIOLoop(index)` 与 `app().getLoop()`）。
4. **`number_of_threads=0` = 自动按 CPU 并发**（B 组已述，此处补 `getCurrentThreadIndex()` 范围为 `[0, getThreadNum()]`，最后一个 index 是主循环）。
5. **`getIOThreadStorageLoop(index)` 越界抛 `std::out_of_range`**（`IOThreadStorage.h:158-167`），AI 不得用未校验的 index 调用。

### U. 内置工具与可观测性

**对标**：源码 `lib/inc/drogon/utils/monitoring/*.h`、`lib/inc/drogon/plugins/PromExporter.h`、`examples/prometheus_example`。

1. **Prometheus 监控**：通过 `drogon::plugin::PromExporter` 插件（配置 `plugins` 数组），暴露 `/metrics`；业务侧 `app().getPlugin<PromExporter>()->getCollector<monitoring::Counter>(name)->metric({labels})->increment()`（见 `examples/prometheus_example/filters/PromStat.cc`）。AI 不得手写 `/metrics` handler。
2. **`Counter / Gauge / Histogram`**：`utils/monitoring/` 下三种指标类型。`Histogram` 需传 `boundaries`/`ttl`/`bucketCount`（`PromStat.cc:47`：`metric({labels}, boundaries, 1h, 6)`）。
3. **内置插件族**（配置 `plugins` 即用，AI 不得重造）：
   - `AccessLogger`：访问日志
   - `SecureSSLRedirector`：HTTP→HTTPS 重定向
   - `SlashRemover`：去除末尾斜杠
   - `RealIpResolver`：从 `X-Forwarded-For` 解析真实 IP
   - `Redirector`：重定向
   - `Hodor`：基础限流防护
   - `PromExporter`：Prometheus 导出
4. **`RateLimiter`**：`RateLimiter::newRateLimiter(type, capacity, timeUnit)`，类型 `kFixedWindow/kSlidingWindow/kTokenBucket`（`RateLimiter.h:42-45`）。多线程用 `SafeRateLimiter` 包装（`RateLimiter.h:56-74`）。AI 不得在事件循环线程裸用非线程安全的 limiter 跨请求共享而不加 `SafeRateLimiter`。
5. **`PubSubService<T>`**：进程内发布订阅，`subscribe(topic, handler)` 返回 `SubscriberID`，`publish(topic, msg)` 广播（`PubSubService.h:144,166`）。AI 不得忘记 `unsubscribe(topic, id)`，否则回调悬挂（与 I.4 Redis 订阅同纪律）。

### V. 现代 lambda 路由与路径参数

**对标**：`examples/*/main.cc`（几乎所有现代示例）、`HttpAppFramework.h:534-595`。这是 **v0.1.0 与官方推荐写法最大的偏差**。

1. **首选 `app().registerHandler(pathPattern, lambda, {verbs}, handlerName)`**：无需定义控制器类，handler 直接写 lambda。签名 `template<typename FUNCTION> HttpAppFramework& registerHandler(...)`（`HttpAppFramework.h:534`）。
2. **路径参数自动绑定**：pathPattern 支持 `{N}` 位置捕获，且能映射到 query——`registerHandler("/hello?username={1}", [](req, cb, const std::string &name){...}, {Get})`（`HttpAppFramework.h:517-528`）。handler 的额外参数由框架按捕获顺序注入。
3. **正则路由 `registerHandlerViaRegex(regExp, lambda, {verbs})`**（`HttpAppFramework.h:586`）。
4. **constraints 同时收 verbs 与 middleware 名**：第三个参数 `std::vector<internal::HttpConstraint>` 可混传 `{Get, Post, "AuthMiddleware", "LogFilter"}`（`HttpAppFramework.h:549-558`）。AI 不得混淆 filter 与 middleware 在此处的传名方式（注意：filter 在约束里传名生效需已 `registerFilter`）。
5. **经典宏写法仍有效**：`HttpController` + `METHOD_ADD`（D.2）与 lambda 写法**二选一，不要混用**。AI 不得在同一项目里对同类路由混用两种风格（CLAUDE.md §11 约定）。

---

## 2. 技能层扩展（新增 8 个技能）

> 沿用现有 `skills/drogon-*` 目录结构：`SKILL.md`（含 frontmatter）+ `references/code-guide.md`。

| 新技能 | 用途 | 主要规则来源 |
|---|---|---|
| `drogon-gen-session-auth` | 生成基于 Session 的登录/登出/鉴权 handler + filter | M 组 |
| `drogon-gen-file-upload` | 生成文件上传 handler（MultiPartParser + 落盘 + 大小校验 + setClientMaxBodySize 配置） | N 组 |
| `drogon-gen-advice` | 生成 11 个内建切面中的指定 Advice（含 SyncAdvice 拦截器、Pre-Sending/Session 切面、观察型 vs 拦截型重载选择） | O 组 |
| `drogon-gen-coroutine-handler` | 生成协程 handler / 协程 middleware（HttpCoroMiddleware） / 协程 ORM 调用，正确区分 Task/AsyncTask，**强制裸协程 handler 参数按值传递**（P.7） | P 组 |
| `drogon-gen-http-client` | 生成出站 HttpClient 调用（异步回调 / 协程 / 反向代理 forward），含 ReqResult 检查与 timeout | Q 组 |
| `drogon-gen-rate-limiter` | 生成限流 filter，按类型生成 FixedWindow/SlidingWindow/TokenBucket + SafeRateLimiter | U.4 |
| `drogon-gen-monitoring` | 生成 Prometheus 指标采集（Counter/Gauge/Histogram） + PromExporter 插件配置 | U.1–U.2 |
| `drogon-gen-lambda-handler` | 生成 `registerHandler` lambda 路由（含 `{N}` 参数绑定、constraints 混传 verbs/middleware） | V 组 |

每个技能的 `code-guide.md` 须包含：参数验证、代码模板（正例）、禁止模式清单（反例 + 对应规则号）、源码位置断言。

---

## 3. 钩子层扩展（PostToolUse 违规库扩充）

在 `hooks/posttooluse.py` 的各 `*_VIOLATIONS` 列表追加检测项：

### 3.1 CPP_VIOLATIONS 新增
```python
# 协程误用
(r'\bTask<\s*void\s*>\s+\w+.*co_await', 'Task<void> 返回但未处理异常 — 用 AsyncTask 必须兜 try/catch，或改用 Task<HttpResponsePtr>（P.2）。'),
# 协程中间件基类错用
(r'class\s+\w+\s*:\s*public\s+HttpMiddleware<\w+,\s*false>\s*\{[^}]*co_await',
 '回调式 HttpMiddleware 不得用 co_await；协程中间件基类是 HttpCoroMiddleware<T,false>（P.3）。'),
# 同步 HttpClient 死锁
(r'client->sendRequest\s*\(\s*[^,]+,\s*[^,]*\)\s*(?!.*callback)',  # 三参数同步式在循环线程
 'HttpClient 同步 sendRequest 有死锁 assert，禁止在事件循环线程/handler 内调用，用异步或 sendRequestCoro（Q.2）。'),
# Session 裸取值
(r'session(?:Ptr)?\s*->\s*operator\[\]',
 'session->operator[] 返回 any&，需 any_cast 易错；用 getOptional<T>() 或 modify<T>()（M.3）。'),
# 未开启 session 直接用
# (启发式，弱信号，可选)
# Advice 在 handler 内注册（补齐 PreSending / Session 两个切面，共 11 个）
(r'register(SyncAdvice|PreRoutingAdvice|PostRoutingAdvice|PreHandlingAdvice|PostHandlingAdvice|PreSendingAdvice|BeginningAdvice|NewConnectionAdvice|HttpResponseCreationAdvice|SessionStartAdvice|SessionDestroyAdvice)\s*\(',
 'Advice 应在 app().run() 之前注册，不得在 handler 内动态注册（O.7）。'),
```

### 3.1.1 协程 handler 参数悬空检测（评审 §3.1，新增）

裸协程 handler（返回 `Task*` / `AsyncTask`）参数须按值。启发式正则（信号弱，建议作为**提示级**而非违规级，避免误报跨行签名）：

```python
# 仅在能确认是裸协程 handler 且同行声明了引用参数时提示
(r'(Task<[^>]*>|AsyncTask)\s+\w+\s*\([^)]*?(const\s+HttpRequestPtr\s*&|std::function[^)]*&&)[^)]*\)\s*\{[^}]*co_await',
 '裸协程 handler 参数应按值传递，co_await 挂起恢复后引用可能悬空（P.7）。协程中间件 HttpCoroMiddleware 不受此限。'),
```

> 启发式局限：跨行函数签名无法在单次 `re.search` 内可靠匹配；建议在技能层（`drogon-gen-coroutine-handler`）做强约束，钩子层仅做单行提示。

### 3.2 CSP_VIOLATIONS
（无新增——J 组已较完整；可选追加 `<%c++` 拼接 HTML 的弱提示，但 J.5 已有规则，避免噪声。）

### 3.3 CONFIG_VIOLATIONS 新增
```python
# 监听器缺失 https 字段时使用 ssl 相关
(r'"ssl":\s*"true"', '"ssl" 必须是布尔值 true/false，不是字符串（E.4）。'),
# PromExporter 缺 collectors
# (跨字段检查，复杂，建议放技能层而非钩子)
# 上传未设 body size
# (启发式：config.json 有 upload 相关但无 client_max_body_size，弱信号，可选)
```

### 3.4 TEST_VIOLATIONS 新增
（原草案 `co_await.*(?!try)` 模式噪声过大且 `None` 消息非法，**不启用**。协程测试的 try/catch 纪律由技能层 `drogon-gen-coroutine-handler` / `drogon-gen-test` 强约束，不在钩子层启发式检测。）

### 3.5 v0.1.0 钩子既有缺陷修复（评审 §4.1 / §4.2，必做）

**§4.1 回调变量名误报 + 折行误报**

现有 `posttooluse.py:29` 正则强制回调变量名为 `callback` 且单行内出现：

```python
# 现状（v0.1.0）—— 与 CLAUDE.md 自身示例冲突（C 组 good 示例用 cb / cbPtr）
(r'std::function\s*<\s*void\s*\(\s*const\s+HttpResponsePtr\s*[&*]\s*\)\s*>\s*(?!.*\bcallback\b)', ...)
```

问题：CLAUDE.md A 组推荐用 `cbPtr`、C 组 good 示例用 `cb`，导致 AI 遵循插件规范生成的代码反被插件判定违规；且负向先行断言 `(?!...)` 在单行内工作，折行签名会漏判或误判。

**修复**：放宽变量名到 `callback|cb|cbPtr`，并移除对"变量名必须出现"的硬约束（改为只在能确认 `co_await`/`return`/`;` 收尾且无任何调用时才提示，作为弱提示级）。或更稳妥——**删除该启发式规则**，把"每条路径恰好回调一次"的检测交给技能层与 A 组规则文本（这种数据流分析超出正则能力，钩子层强检只会带来误报）。

```python
# 建议方案 A：删除该条（推荐，数据流分析非正则所长）
# 建议方案 B：若保留，仅匹配"handler 体明确以 return; / return 数字; 收尾且无 callback/cb 调用"的强信号
(r'return\s*;', 'handler 内出现裸 return; —— 确认该路径已调用 callback/cb，否则违反 A.1（提示级）。'),
```

**§4.2 全局 `re.IGNORECASE` 导致 C++ 标识符误报**

`posttooluse.py:116` 对所有模式无差别应用 `re.IGNORECASE`。对 `done()`、`ASSERT_EQ` 等大小写敏感的 C++ 标识符，会把 `isDone()`、`task.done()`、`asset_eq` 误判为违规。

**修复**：把 `scan_text` 改为接受 per-pattern flags。对每条 `(pattern, message)` 升级为 `(pattern, message, flags)` 三元组（缺省 `0`），C++ 标识符类规则显式不带 `re.IGNORECASE`。

```python
# 改造 scan_text 签名
def scan_text(text, violations):
    matches = []
    for entry in violations:
        pattern, message = entry[0], entry[1]
        flags = entry[2] if len(entry) > 2 else 0   # 缺省大小写敏感
        if re.search(pattern, text, flags):
            matches.append(message)
    return matches

# 大小写敏感的规则（移除隐式 IGNORECASE）
TEST_VIOLATIONS = [
    (r'\bdone\(\)', 'done() callback does not exist ...', 0),       # 不再误伤 isDone()
    (r'\bASSERT_(EQ|NE|TRUE|FALSE|...)\b', 'ASSERT_* ...', 0),
    (r'\bcreateDbClient\b', 'createDbClient deprecated ...', 0),
]
# 真正需要忽略大小写的（如 CSP 的 {{ }} 与大小写无关）保留 re.IGNORECASE
```

---

## 4. 规则层对现有 A–L 组的修订点

> 不改变结构，仅补正与源码核对中发现的不一致或缺口。

| 现有条目 | 修订 |
|---|---|
| A.6 协程 | 补一句"详见 P 组"，避免在 A 组展开协程细节造成重复 |
| B 组 | 末尾补"详见 T 组 IOThreadStorage 进阶" |
| C.2 drogon_ctl 控制器 | 补注：现代项目可完全不用 `drogon_ctl create controller`，改用 `registerHandler` lambda 路由（V 组），二者择一 |
| D.1 类型选择表 | 补一行"lambda 内联路由 → `registerHandler`，无需控制器类" |
| K.3 Middleware | 标注"回调式；协程式见 P.3 `HttpCoroMiddleware`"。当前 K.3 的"正确（标准模式）"应注明是回调式 |
| E.4 配置项语义 | 补 `ssl` 布尔字段、`client_max_body_size`、`max_connection_num`、`plugins` 数组等 |

---

## 5. 与官方文档的一致性核对结论

- 官方文档 19 章中，v0.1.0 已深度覆盖：01–06、08–12、14、17（部分）、18、19。
- **本方案补齐**：07（Session→M）、09-1（File→N）、13（AOP→O）、16（Brotli，并入 U 或单列）、17 剩余（→P）、FAQ-1 剩余（→T）。
- 官方文档未单列但源码具备、本方案补入的：HttpClient（Q）、RequestStream（R）、Cookie 安全（S）、Monitoring/内置插件/RateLimiter/PubSub（U）、registerHandler（V）。
- **文档与源码的已知出入**：官方文档 CHN-13 称"7 个插入点"，源码实际为 **8 个**（多了 HttpResponseCreation 与 Sync 各算其一）；本方案以源码 8 个为准。官方文档部分 API 仍用旧式回调示例，而源码头文件与 examples 已主推协程/lambda——本方案一律以源码 + 现行 examples 为准。

---

## 6. 落地优先级建议

| 优先级 | 内容 | 理由 |
|---|---|---|
| P0（立即） | V 组 + `drogon-gen-lambda-handler` 技能 | v0.1.0 与官方推荐写法最大偏差，影响所有新项目 |
| P0 | O 组 AOP 规则 + `drogon-gen-advice` 技能（11 个切面） | drogon 独有强项，完全缺失 |
| P1 | M/N/P/Q 组及对应技能 | 高频功能域（登录/上传/协程/出站请求）完全缺失 |
| P1 | 钩子扩充 3.1 的协程/HttpClient 死锁检测 | 高危 bug 早期拦截 |
| P1 | §3.5 钩子既有缺陷修复（评审 §4.1/§4.2，cb 误报 + IGNORECASE 误报） | v0.1.0 既有 bug，且与自身规则冲突 |
| P2 | R/S/T/U 组及技能 | 进阶/可观测性，按需补齐 |
| P2 | §4 规则修订点 | 质量打磨 |

---

## 6.5 评审响应纪要（v0.2.0 → 评审意见处理）

> 对 `PRD/upgrade_review.md` 各条意见的逐条响应。所有源码主张均已二次回查 drogon v1.9.13 源码确认。

### 已接受并修订正文（5 条，全部源码核对通过）

| 评审条目 | 结论 | 证据 | 正文已修订处 |
|---|---|---|---|
| §2.1 RequestStream 无 `setStreamReader` | ✅ 接受 | `HttpRequest.h` 不含该方法；`RequestStream.h:47` 提供 `internal::createRequestStream` | R 组规则 1 已改 |
| §2.2 SessionMap 是 `std::map` 非 `unordered_map` | ✅ 接受（原方案 bug） | `Session.h:34` `using SessionMap = std::map<std::string, std::any>` | M 组规则 2 已改 |
| §2.3 AOP 是 11 个切面非 8 个 | ✅ 接受 | 补 `PreSendingAdvice`(h:439)、`SessionStartAdvice`(h:920)、`SessionDestroyAdvice`(h:927) | O 组规则 1 已扩为 11 个并分类 |
| §3.2 拦截型 Advice 恰好一次回调 | ✅ 接受 | 与 A.1 同源 | O 组新增规则 6 |
| §4.1 cb 误报 + 折行 / §4.2 全局 IGNORECASE 误报 | ✅ 接受 | 与 CLAUDE.md C 组 `cb`/`cbPtr` 示例冲突 | §3.5 给出 per-pattern flags 改造与方案 A/B |

### 接受但带重要细化（1 条）

**§3.1 协程 handler 参数按值传递**：✅ 接受核心主张，但补充关键边界条件——

- 主张成立范围：**裸协程 handler**（`Task<>` / `Task<HttpResponsePtr>` / `AsyncTask`）。已用官方示例 `examples/redis_cache/controllers/SlowCtrl.cc` 印证：其回调式 `hello` 用 `const HttpRequestPtr &req`，而协程 `observe` 刻意改为 `HttpRequestPtr req`（按值）。
- **例外（评审未提及，本方案补充）**：协程**中间件** `HttpCoroMiddleware::invoke` 用 `const HttpRequestPtr &req` 是安全的——框架的 `async_run` 外层 lambda 已按值捕获 `req`/`nextCb`/`mcb`（`HttpMiddleware.h:121-124`），引用指向该副本。官方 `prometheus_example/filters/PromStat.cc` 正是此用法。AI 不得把该例外外推到裸协程 handler。
- 已写入 P 组规则 7（含三种场景对照表）。

### 钩子层附加说明

- §3.1.1 协程参数悬空检测：受限于"跨行签名无法单次正则匹配"，钩子层仅做单行提示级，强约束下沉到 `drogon-gen-coroutine-handler` 技能。
- §3.4 原草案 `co_await.*(?!try)`（含非法 `None` 消息）已废弃。

### 未采纳（无）

评审意见全部合理，无驳回项。

---

## 7. 版本与兼容性

- 目标版本：插件 `0.2.0`；`plugin.json` 的 `version` 同步升级。
- 规则层扩充为纯新增（M–T 组），不破坏现有 A–L；§4 修订点为补充说明，无删改。
- 技能层为新增，不影响现有 10 个技能。
- 钩子层新增检测项为告警（PostToolUse 不阻断），无破坏性；`re.IGNORECASE` 调整需回归测试现有误报率。
- README.md 的"功能组件"表与"应显示 N 个技能和 M 个钩子"描述需同步更新。

---

## 附录 A：本方案核对过的源码文件清单

- `lib/inc/drogon/Session.h`、`lib/src/SessionManager.cc`
- `lib/inc/drogon/MultiPart.h`、`examples/file_upload/file_upload.cc`
- `lib/inc/drogon/HttpAppFramework.h`（registerHandler:534, registerHandlerViaRegex:586, forward:760, forwardCoro:770, setSSLFiles:809, advice 系列 11 个: 273-441 + 920-928）
- `lib/inc/drogon/HttpMiddleware.h`（HttpCoroMiddleware:111, MiddlewareNextAwaiter:89）
- `lib/inc/drogon/HttpClient.h`（sendRequest 同步 assert:133, sendRequestCoro:160）
- `lib/inc/drogon/RequestStream.h`
- `lib/inc/drogon/Cookie.h`
- `lib/inc/drogon/RateLimiter.h`
- `lib/inc/drogon/PubSubService.h`
- `lib/inc/drogon/IOThreadStorage.h`
- `lib/inc/drogon/utils/monitoring/*.h`
- `lib/inc/drogon/plugins/PromExporter.h`、`AccessLogger.h`、`Hodor.h`、`RealIpResolver.h`、`Redirector.h`、`SecureSSLRedirector.h`、`SlashRemover.h`
- `examples/prometheus_example/{main.cc,config.json,filters/PromStat.cc}`
- `examples/login_session/main.cc`、`examples/client_example/main.cc`

## 附录 B：官方文档章节对标矩阵

| 官方章节 | 现有规则 | 本方案新增规则 | 状态 |
|---|---|---|---|
| 01 概述 | — | — | 无需 |
| 02 安装 | F | — | 已覆盖 |
| 03 快速开始 | A–D | V | V 补 lambda 写法 |
| 04 控制器 | C,D | V | V 补现代写法 |
| 05 中间件过滤器 | K | P | P 补协程中间件 |
| 06 视图 | J | — | 已覆盖 |
| 07 会话 | — | **M** | **补齐** |
| 08 数据库 | G,H | — | 已覆盖 |
| 09 请求/文件 | — | **N,R** | **补齐** |
| 10 插件 | K | **U** | U 补内置插件族 |
| 11 配置 | E | §4 修订 | 补强 |
| 12 drogon_ctl | C | — | 已覆盖 |
| 13 AOP | — | **O** | **补齐** |
| 14 性能测试 | — | — | 文档测试工具，非编码规则 |
| 15 Coz | — | — | 分析工具，非编码规则 |
| 16 Brotli | — | U（并入） | 可选并入 U |
| 17 协程 | A.6 | **P** | **补齐** |
| 18 Redis | I | — | 已覆盖 |
| 19 测试 | L | — | 已覆盖 |
| FAQ-1 线程模型 | B | **T** | T 补 IOThreadStorage |
| —（源码有、文档未单列） | — | **Q,S**（HttpClient/Cookie 安全） | **补齐** |
