# drogon-claude-plugin v0.2.0 升级方案详细评审意见

> 基于对项目现有结构、[UPGRADE-PLAN-v0.2.0.md](../docs/UPGRADE-PLAN-v0.2.0.md) 以及 `drogon` (v1.9.13) 官方库源码与实际示例的深度对比，特制定本评审意见报告。

---

## 1. 整体可行性评估

本升级方案（v0.2.0）的整体设计非常详尽且切中要害，成功找出了 v0.1.0 在**会话管理 (Session)**、**文件上传 (MultiPart)**、**面向切面编程 (AOP/Advices)**、**协程扩展 (Coroutine)**、**HTTP出站请求 (HttpClient)** 以及**现代 Lambda 路由注册**等高频使用场景下的规则盲区。

*   **规则层 (CLAUDE.md 新增 M–V 组)**：与 `drogon` 当前版本的头文件定义基本吻合，提出的各项规则极具实战意义（例如 Session 中 `insert` 与 `modify` 的语义差异、路径前缀的解析逻辑等）。
*   **技能层 (新增 8 个技能)**：设计逻辑紧贴新增规则，能极大提升 AI 协助开发时的代码生成质量。
*   **钩子层 (PostToolUse 检测项)**：扩展了 C++ 协程、中间件、同步 HttpClient 死锁以及配置/测试文件的检测，有助于在开发早期拦截高危 Bug。

---

## 2. 核心 API 签名与设计修正（基于 Drogon 源码）

经过直接对 `drogon` 框架库源码的走读，本评审意见对 [UPGRADE-PLAN-v0.2.0.md](../docs/UPGRADE-PLAN-v0.2.0.md) 的原有接口表述进行了修正，以避免编译错误和运行时隐患：

### 2.1 R 组：流式上传 (RequestStream) —— 修正编译期 API 错误

*   **原方案断言**：在 handler 里通过 `req->setStreamReader(reader)` 注册读取器。
*   **源码核对结论**：核对 [RequestStream.h](https://github.com/drogonframework/drogon/blob/v1.9.13/lib/inc/drogon/RequestStream.h#L36-L47) 发现，`HttpRequest` 类没有继承 `RequestStream` 接口，本身**不具备** `setStreamReader` 方法。直接在 `HttpRequestPtr` 上调用该方法会导致**编译错误**。
*   **修正规范**：流式上传必须使用底层提供的接口转换函数 `drogon::internal::createRequestStream` 进行包装后调用：
    ```cpp
    // ✅ 正确：通过内部 createRequestStream 封装后再设置 Reader
    auto stream = drogon::internal::createRequestStream(req);
    if (stream)
    {
        auto reader = RequestStreamReader::newReader(dataCb, finishCb);
        stream->setStreamReader(reader);
    }
    ```

### 2.2 M 组：会话 (Session) —— 修正底层数据结构定义

*   **原方案断言**：会话底层数据结构为 `std::unordered_map<std::string, std::any>`。
*   **源码核对结论**：核对 [Session.h](https://github.com/drogonframework/drogon/blob/v1.9.13/lib/inc/drogon/Session.h#L34) 发现，会话底层使用的类型实际上是 `std::map<std::string, std::any>`，并非 `unordered_map`：
    ```cpp
    using SessionMap = std::map<std::string, std::any>;
    ```
*   **修正规范**：AI 在编写与 SessionMap 直接交互的 Lambda（例如调用重载的 `session->modify([](Session::SessionMap &map){...})`）时，**必须**使用 `std::map` 类型的迭代器 and 接口，不得误用 `std::unordered_map`。

### 2.3 O 组：AOP 面向切面编程 (Advices) —— 完善 11 个内建切面体系

*   **原方案断言**：方案仅指出了 8 个内建插入点，且未作分类。
*   **源码核对结论**：核对 [HttpAppFramework.h](https://github.com/drogonframework/drogon/blob/v1.9.13/lib/inc/drogon/HttpAppFramework.h#L273-L441) 以及 [Session 相关 Advice](https://github.com/drogonframework/drogon/blob/v1.9.13/lib/inc/drogon/HttpAppFramework.h#L920-L928) 发现，Drogon 实际上提供了 **11 个内建的 AOP 切面**，具体分类如下：
    1.  **请求/响应生命周期切面 (7个)**：
        *   `SyncAdvice`：同步拦截，返回非空响应即直接短路（不执行后续路由与过滤器）。
        *   `Pre-Routing`：路由匹配前（拦截型/观察型）。
        *   `Post-Routing`：路由匹配后、过滤器与中间件执行前（拦截型/观察型）。
        *   `Pre-Handling`：过滤器与中间件执行后、进入 Handler 前（拦截型/观察型）。
        *   `Post-Handling`：Handler 执行并生成业务 Response 后（观察型，不包含静态文件响应）。
        *   `Pre-Sending`：响应真正发送给客户端前（观察型，**包含静态文件响应**，用于修改响应头或日志）。
        *   `HttpResponseCreation`：每当 `HttpResponse` 实例被创建时触发。
    2.  **系统/连接生命周期切面 (2个)**：
        *   `BeginningAdvice`：主事件循环启动后立即触发一次。
        *   `NewConnectionAdvice`：新连接建立时触发，返回 `false` 可强行拒绝并关闭连接。
    3.  **会话生命周期切面 (2个)**：
        *   `SessionStartAdvice`：当新 Session 创建并开始时触发。
        *   `SessionDestroyAdvice`：当旧 Session 超时销毁时触发。

---

## 3. 补充安全编码规范（防范运行崩溃）

### 3.1 P 组：协程 (Coroutine) —— 防止参数生命周期悬空 (Dangling Reference)

> [!CAUTION]
> **高危内存越界崩溃**：在普通回调式 handler 中，参数通常定义为 `const HttpRequestPtr &req`（引用传递）。然而在协程 handler 中，因为协程执行到 `co_await` 挂起时，当前栈帧的临时请求对象可能已被销毁，待协程恢复时，`req` 引用将指向已被释放的内存，导致**崩溃 (Use-After-Free)**。
> 
> **硬性纪律**：**所有协程 handler 的请求参数必须按值传递**（例如 `const HttpRequestPtr req`），坚决禁止使用引用传递。

*   **错误示例**（引用传递，挂起恢复后 req 悬空）：
    ```cpp
    // ❌ 错误：使用引用传递 HttpRequestPtr
    drogon::Task<HttpResponsePtr> getUser(const HttpRequestPtr &req, int id) {
        auto db = app().getDbClient();
        auto r = co_await db->execSqlCoro("SELECT * FROM users WHERE id=$1", id);
        auto name = req->getParameter("name"); // ❌ 崩溃：访问悬空引用 req
        co_return HttpResponse::newHttpResponse();
    }
    ```
*   **正确示例**（值传递，安全）：
    ```cpp
    // ✅ 正确：按值传递 HttpRequestPtr
    drogon::Task<HttpResponsePtr> getUser(const HttpRequestPtr req, int id) {
        auto db = app().getDbClient();
        auto r = co_await db->execSqlCoro("SELECT * FROM users WHERE id=$1", id);
        auto name = req->getParameter("name"); // ✅ 安全
        co_return HttpResponse::newHttpResponse();
    }
    ```

### 3.2 O 组：拦截型 Advice —— 严格执行恰好一次回调纪律

*   **硬性纪律**：在 `Pre-Routing / Post-Routing / Pre-Handling` 这三个拦截型 Advice 中，**必须且仅能调用一次回调函数**（调用 `AdviceCallback` 返回自定义响应，或调用 `AdviceChainCallback` 继续链式执行）。漏调将导致连接挂起，重复调用会导致内存崩溃。

### 3.3 V 组：现代 Lambda 路由 —— 捕获列表生命周期安全

*   **硬性纪律**：在 lambda 路由闭包中，**严禁捕获任何局部变量的引用或指针**。所有需要长期复用的组件应当通过 `std::shared_ptr` 按值捕获，或者直接调用 `app().getDbClient()` 等全局单例接口获取。

---

## 4. v0.1.0 插件实现遗留缺陷与 Bug 分析

在深入审阅插件当前版本（v0.1.0）的代码时，本评审发现了以下必须在 v0.2.0 中进行修正的实现缺陷：

### 4.1 异步回调检测钩子误报与自身规则冲突（高危）
*   **缺陷现象**：[posttooluse.py:L29](../hooks/posttooluse.py#L29) 处的正则 `r'std::function\s*<\s*void\s*\(\s*const\s+HttpResponsePtr\s*[&*]\s*\)\s*>\s*(?!.*\bcallback\b)'` 强行规定回调变量名必须为 `callback`，并且限制在单行。
*   **危害后果**：
    1.  如果回调变量折行定义，会误报“未调用 callback”警告。
    2.  与 [CLAUDE.md](../CLAUDE.md) 的推荐示例相冲突（`CLAUDE.md` 在 good 示例中大量将回调简写为 `cb`），导致 AI 严格遵循插件规范生成代码时，却被插件自身的检测钩子判定为违规。
*   **改进方案**：更新正则以兼容 `callback` 或 `cb`，并支持多行折行检测。

### 4.2 全局大小写不敏感匹配导致高误报率
*   **缺陷现象**：[posttooluse.py:L116](../hooks/posttooluse.py#L116) 对所有规则文件都应用了 `re.IGNORECASE` 匹配，其中包括针对 `done()` 的检测规则。
*   **危害后果**：在 C++ 中，`bool isDone()`、`task.done()` 是极为普通的函数与变量名。因为大小写不敏感与单词边界判定，哪怕是正常的业务逻辑调用，也会被错误拦截为“测试 done() 回调误用违规”。
*   **改进方案**：针对大小写敏感的 C++ 标识符匹配项（例如 `done()`、`createDbClient`），在正则级别中去除全局 `IGNORECASE` 约束，改用精确大小写检测。
