# Drogon 后端开发规则

> 本文件由 drogon-claude-plugin v0.3.0 自动生成,请勿手改(源:CLAUDE.md;重新生成:python scripts/gen-host-artifacts.py)。适用于任何读取 AGENTS.md 的 coding agent。
>
> 下文的 Skill 路由表指向随插件分发的 22 个技能(Claude Code / ZCode / Codex / Cursor / VS Code / Gemini CLI 经各自机制安装后可用)。若当前环境只落了规则文件,路由表仍可作为 drogon 领域地图使用。

## A. 异步回调模型（所有 handler 的最高纪律）

Drogon 的每个 handler 接收一个 `std::function<void(const HttpResponsePtr &)>` 回调。**响应的发出只与回调是否被调用有关，与 handler 是否 return 无关**。

1. **恰好一次**：每个 handler 必须在**所有代码路径**（含错误/异常/提前返回）上**恰好调用一次** `callback`。
2. **绝不重复**：禁止第二次调用 `callback`（未定义行为，可能重复响应或连接污染）。
3. **禁止 handler 内同步阻塞**：不得在 handler 内做阻塞式同步 I/O（同步读 DB、`sleep`、长计算、阻塞文件读写）后再 `callback`。改用 drogon 异步 API，或丢到线程池，完成处就近 `callback`。
4. **按值捕获回调**：异步/延迟场景下 `callback` 必须**按值捕获**进闭包，确保生命周期超出 handler 栈帧；悬空回调会崩溃。
5. **异常不得逃逸 handler**：用 try/catch 包裹业务逻辑，每个 catch 路径都调 `callback(错误响应)`。框架默认异常处理器只是兜底，**不能替代**你对 callback 的保证。全局兜底用 `app().setExceptionHandler`（不替代各 handler 自身的纪律）。
6. **优先协程**：`__cpp_impl_coroutine` 已定义且 CMake `USE_COROUTINE=ON` 时，优先用协程 handler（`Task<HttpResponsePtr>`，框架负责异常与响应交付）。`AsyncTask` 抛未处理异常会 `std::terminate`，用时必须 try/catch。**裸协程 handler 的 req/callback 参数必须按值传递**（挂起恢复后引用悬空）。协程细节用 `drogon-gen-coroutine-handler` skill。

## B. 事件循环模型（Trantor IO）

Drogon 跑在 trantor 的事件循环上；配置项 `number_of_threads` 决定循环数（**值为 0 表示按 CPU 硬件并发数自动设置**），每条连接钉在某个循环上。

1. **事件循环线程不可阻塞**：禁止在事件循环线程做任何阻塞工作（同步 DB 调用、`sleep`、长计算、阻塞文件 I/O）——会拖死同一循环上所有其他连接。
2. **重/阻塞活儿走线程池**：把重活儿交给独立线程池；完成后用 `runInLoop` 派回连接所属的事件循环，再在那里 `callback`。长周期任务可建专属 `trantor::EventLoopThread`（见 `drogon-gen-plugin` skill）。
3. **跨循环共享状态加锁**：跨循环共享的状态必须加锁；更优是保持状态"循环局部"（`IOThreadStorage<T>`），或用 `runInLoop` 派发到归属循环访问。跨线程操作连接对象（如 WebSocketConnection）必须先派发回其所属循环。

## Skill 路由表

遇到下列任务时，**主动调用对应 Skill**——详细模板、API 签名、禁止模式清单都在 skill 的 `references/code-guide.md` 里，按需加载以节省上下文。

| 任务 | Skill | 说明 |
|------|-------|------|
| 创建控制器（.h+.cc） | `drogon-create-controller` | simple/http/websocket；含路径前缀差异、`:param`、WebSocket 宏、自动注册、生命周期纪律 |
| 现代 lambda 内联路由 | `drogon-gen-lambda-handler` | `app().registerHandler` + `{N}` 参数绑定；与经典宏二选一不混用 |
| ORM CRUD 代码 | `drogon-gen-orm-crud` | 回调式 + 协程式；含禁 `execSqlSync`、双回调、事务纪律 |
| 从数据库生成 ORM 模型 | `drogon-gen-orm-model` | `drogon_ctl create model` 全参数；生成物约定、CMake 接入、MSVC/C++20 codecvt shim、禁止手改生成文件 |
| 数据库配置 | `drogon-gen-db-config` | PG/MySQL/SQLite；含键名黑名单、`loadConfigFile` 异常、运行期 `DrogonDbException`、SQL 注入防护 |
| Redis 配置 + 用法 | `drogon-gen-redis-config` | 配置 + 单例/异步/异常/订阅防泄漏；`execCommandAsync` 双回调、格式化参数、协程 |
| 通用配置文件 | `drogon-setup-config` | listeners/app/SSL/静态文件/会话；含 `custom_config`+`getCustomConfig`、`loadConfigJson`、多环境 |
| CMake 构建 | `drogon-gen-cmake` | find_package/ORM/协程；含 Conan 2、`drogon_create_views`、drogon_ctl 模型接入、MSVC 专项 |
| 协程 handler/中间件 | `drogon-gen-coroutine-handler` | Task/AsyncTask 语义、参数按值生命周期、`forwardCoro` |
| HTTP 出站请求 | `drogon-gen-http-client` | 异步/协程/反向代理 forward；含同步 `sendRequest` 死锁保护、timeout |
| CSP 视图模板 | `drogon-gen-csp-view` | 语法速查、布局、HttpViewData；含 `drogon_ctl create view` 管线、禁拼 HTML |
| Filter（请求拦截） | `drogon-gen-filter` | 认证/限流/输入校验；含 `doFilter(fcb,fccb)`、`AutoCreation=false` |
| Middleware（全局处理链） | `drogon-gen-middleware` | 日志/CORS/性能计时；含 `invoke(nextCb,mcb)` |
| Plugin（系统级扩展） | `drogon-gen-plugin` | 连接池/第三方 SDK 初始化；含生命周期与 `shutdown()` 排水、专属 EventLoopThread、静态库注册丢失对策 |
| Advice（AOP 切面） | `drogon-gen-advice` | 11 个内建切面；含拦截型 vs 观察型、注册时机 |
| 文件上传 | `drogon-gen-file-upload` | MultiPart 解析+校验+落盘；含 `setClientMaxBodySize`、路径穿越 |
| 流式上传/下载 | `drogon-gen-stream` | RequestStream 三回调流式上传；chunked 流式响应；大文件不占内存 |
| Session 登录鉴权 | `drogon-gen-session-auth` | 登录/登出/鉴权；含 `changeSessionIdToClient` 防 fixation、Cookie 安全（HttpOnly/Secure/SameSite） |
| WebSocket 长连接 | `drogon-gen-websocket` | WS 控制器宏、连接管理/广播、跨线程 send 安全、心跳 |
| 限流 | `drogon-gen-rate-limiter` | Hodor 插件配置 + 自定义 429；编程式 RateLimiter/SafeRateLimiter；Redis 分布式限流 |
| 监控指标 | `drogon-gen-monitoring` | PromExporter 插件 + Counter/Gauge/Histogram 采集；禁手写 /metrics |
| 测试 | `drogon-gen-test` | DROGON_TEST；含断言宏、异步测试、CMake 扫描、自定义 main 与端口隔离 |

## 通用纪律（跨 Skill）

- **所有 I/O 必须异步**：DB、Redis、HTTP 出站、文件操作均不得在事件循环线程同步阻塞（见 B.1）。详见各 skill。
- **所有异步操作必须双回调**：成功 + 失败回调都要处理；失败回调必须 `callback(错误响应)`（见 A.1）。
- **异常不得逃逸**：handler 内所有可能抛异常的代码都要 try/catch，catch 路径调 `callback`（见 A.5）。
- **配置加载必须 try/catch**：`app().loadConfigFile()` 失败抛 `std::runtime_error`，不得忽略。
- **键名严格**：DB 用 `passwd`/`user`/`dbname`，Redis 用 `passwd`/`db`，通用配置用 `enable_session`/`number_of_threads`——禁止错误变体（详见 db-config / redis-config / setup-config skill）。
- **优先内建能力**：限流优先 Hodor、指标优先 PromExporter、访问日志优先 AccessLogger——配置即用，禁止重造轮子（详见 rate-limiter / monitoring skill）。
- **生成代码不手改**：`drogon_ctl` 生成的 ORM 模型 / restful 控制器是重生成产物，定制走继承或包装（见 orm-model skill）。

## 防错兜底

本插件另配 **PostToolUse hook**（`hooks/posttooluse.py`），在每次 Edit/Write 后自动扫描 C++/CSP/config 文件，检测高频 API 误用（不存在的宏、弃用 API、同步阻塞死锁、`operator[]` 误用等）并告警。即使规则一时遗漏，hook 会兜底提示。
