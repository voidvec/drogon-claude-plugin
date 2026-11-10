# 基线内事实错误清单（drogon v1.9.13）

本文件是 `hooks/posttooluse.py` 与 `tests/test_posttooluse.py` 里 `B1`/`B2`/`B3`/`B45` 编号注释的证据源，也是 `tests/test_skills_facts.py` 每条 FORBIDDEN/REQUIRED 断言的取证出处。

## 0. 范围纪律

- **只处理在 v1.9.13 就已不成立的陈述**：不存在的 API 名、不存在的配置键、方向反了的禁令、张冠李戴的行号。
- **不借本轮升到 1.9.14**：基线声明、技能正文、示例都留在 v1.9.13；任何只有 1.9.14 才成立的写法（例如 `registerPostHandlingAdvice` 的新签名、带 `bool` 参数的 `loadSSL` 重载）一律不写入。
- 修复形态一律**给出可用结论**，不接受"把错的删掉"——删掉错的而不留对的，正是这类错误能长期存活的机制。

## 1. 取证基准

| 项 | 值 |
|----|----|
| drogon 源码 | 本地 tag clone `C:\Users\vilas\tmp-audit\drogon1913`，`git describe --tags` = `v1.9.13` |
| trantor | drogon v1.9.13 记录的子模块指针 `63a4e5e164e219dc3bf30cdbfa1462ae5602fa97`（仓库 `an-tao/trantor`，本地子模块未 checkout，经 `gh api .../contents/trantor/net/EventLoop.h?ref=<sha>` 取原文） |
| jsoncpp | **不是** drogon 的 submodule（v1.9.13 的 `.gitmodules` 只有 trantor，`third_party/` 只有 `mman-win32`），由 `CMakeLists.txt:192-193`（`:191` 是 `# jsoncpp` 注释行）`find_package(Jsoncpp REQUIRED)` + `Jsoncpp_lib` 从外部提供，因此没有"随基线锁定"的版本。取证用 `open-source-parsers/jsoncpp` tag `1.9.5` 的 `src/lib_json/json_value.cpp`（留档 `C:\Users\vilas\tmp-audit\jsoncpp_1_9_5_json_value.cpp`，与 `gh api?ref=1.9.5` 拉下的原文 md5 一致：`90a9ed3e1981c0c497d6ba741b7ae288`）；涉及"某构造不存在"的否定主张另在 `1.9.5/1.9.6/1.9.7/master` 四个 ref 的 `include/json/value.h` 上各查一次。**强度弱于 tag 内文件**：结论对得上任何 drogon 实际链接的 jsoncpp 版本才成立，取证时按 ref 逐个核对，不写"jsoncpp 一直是这样"。 |
| C++ 语义主张 | 只读源码不足以定"能否编译"时，用本地工具链实测：`clang++ -std=c++17 -fsyntax-only` 判可否编译，`-Xclang -ast-dump` 读重载决议实际选中哪个构造（B45 即用这条把 `Json::Value({{...}})` 的真身定死） |
| 全文检索 | 存在性主张一律整树 `grep`（`--include=*.{h,cc,cmake,in,csp}` + `CMakeLists.txt`），0 命中才允许写"不存在" |
| 行号容差 | ±3 行内算命中；区间必须覆盖被点名的那一行 |

## 2. 事实错误逐项（B1–B45）

每条格式：**原陈述**（被删掉的原话）→ **v1.9.13 实证** → **修复形态** → **守卫**。

### A 组：防错钩子自身的规则错误

**B1 — `username` 一刀切判 error**
- 原陈述：`CFG.002` 见 `username` 即 error，提示"drogon 用 `user`，改成 `user`"。
- 实证：`lib/src/ConfigLoader.cc:551` 数据库段读 `user`；但 `:614` Redis 段读 `username`（Redis 6.0 ACL 用户名），且 `:615-619` 才有 `passwd`→`password` 回退。照旧告警会把**唯一正确的 Redis 键名**改坏并静默丢弃 ACL 用户。
- 修复：规则改为**按段判定**——只在 `db_clients` 段报 error，消息里明写"`redis_clients` 段的 `username` 是对的，别改"。JSON 分支用 `[^\]]` 天然止于数组边界；YAML 分支逐行只吃缩进行，遇到顶格段头即终止；两个分支都有步数上界（第四轮 F1 的 ReDoS 教训）。
- 守卫：`tests/test_posttooluse.py` 的 CFG.002 正例（db_clients 报错）+ 反例（redis_clients 不报），以及"YAML 段外不误报"用例。

**B2 — `password` 被当成错误键**
- 原陈述：`CFG.001` 见 `password` 即 error。
- 实证：`ConfigLoader.cc:552-556`（db）与 `:615-619`（redis）都在 `passwd` 为空时回退读 `password`——它是**合法回退键**，只是非首选。
- 修复：降为 warning，措辞改"首选 `passwd`；`password` 仅在 `passwd` 为空时被读取"。
- 守卫：`tests/test_posttooluse.py` B2 用例锁 severity=warning 与消息口径。

**B3 — `session->operator[]` 被描述成"存在但易错"**
- 原陈述：`CPP.008` 消息称其"returns `std::any&` and needs `any_cast` — error-prone"。
- 实证：`lib/inc/drogon/Session.h` 全文无 `operator[]`（只有 `get<T>`、`getOptional<T>` :74、`modify<T>` :108/:141、`insert`/`erase`/`find`）——该形态**编译不过**，不是"可用但危险"。
- 修复：消息改为"Session 无 `operator[]`，此写法不编译；读用 `getOptional<T>()`/`get<T>()`，写用 `modify<T>()`"。
- 守卫：`tests/test_posttooluse.py` B3 用例；`tests/test_skills_facts.py` REQUIRED 锁 session 文档表述。

### B 组：配置与文档事实

**B4 — 假配置键 `logfile_size`**
- 原陈述：JSON/YAML 模板里 `"logfile_size": 104857600`。
- 实证：整树 0 命中。真实键 `log_size_limit`（`ConfigLoader.cc:164`，默认 100000000）与 `max_files`（`:165`，默认 0）。
- 守卫：FORBIDDEN `logfile_size` + REQUIRED `log_size_limit`/`max_files`。

**B5 — `log_level` 取值集合与默认值**
- 原陈述：`log_level`: 日志级别（`DEBUG`/`INFO`/`WARN`/`ERROR`，默认 `INFO`）。
- 实证：`:168` 源码默认 `"DEBUG"`；`:169-184` 只匹配 `TRACE`/`DEBUG`/`INFO`/`WARN` 四个串，**没有 `ERROR`/`FATAL` 分支**——写 `ERROR` 时 `setLogLevel` 根本不被调用，级别停在 trantor 编译期内建默认（`RELEASE` 宏下 `kInfo`，否则 `kDebug`，`trantor/utils/Logger.h:282-288`），且不报错。
- 修复：文档列全四档、标出 `ERROR` 的静默行为，并显式要求生成时写出该键。
- 守卫：REQUIRED `ConfigLoader.cc:168-184`。

**B6 — `enable_session` 默认值**
- 原陈述：默认 `true`。
- 实证：`ConfigLoader.cc:266` `app.get("enable_session", false)` → drogon 默认 **false**。
- 修复：保留"本技能按 Web 服务场景抬高为 true"的意图，但把 drogon 真实默认写清并强制显式出键。
- 守卫：REQUIRED `ConfigLoader.cc:266`。

**B7 — `client_max_body_size` 的数字取值**
- 原陈述：只说"值为字符串如 `1M`"，未说明纯数字形态的边界。
- 实证：`:467` 默认 `"1M"` 交 `bytesSize()`（`:43-106`）解析；后缀 `K/M/G/T`（`:55-77`）之外走"纯字节数"分支，而该分支的数字白名单 `:78-86` 逐个列 `0-5`、`7-9`——**漏了 `'6'`**。于是 `"1048576"`（=1M）落到 `default: return false`（`:88-90`），调用方 `:473-476` 抛 `std::runtime_error("Error format of client_max_body_size")`，整个配置加载失败。写成 JSON 数字 `1048576` 同样中招（jsoncpp `Value::asString()` 对整型返回十进制字符串，并非空串）；只有空串/`null` 才是"不限"（`:45-48` 置 `size_t(-1)`）。
- 修复：文档统一要求带 `K`/`M`/`G` 后缀，并说明这是上游缺陷而非用法偏好。
- 守卫：REQUIRED `bytesSize`、`ConfigLoader.cc:43-106`（setup-config）与 `数字白名单`（websocket）——交付前评审指出原写法的"两处落点"只有 `bytesSize` 真有 needle，其余靠正文措辞碰巧；现已补齐。四条 needle 对本轮改动前的文本（`git show HEAD:`）实测均 0 命中，改动后转绿。

**B8 — "WebSocket 无消息大小上限配置"（反向禁令）**
- 原陈述：大消息条目写"且无消息大小上限配置（核对不存在 `setWebSocketMaxMessageSize` 类 API）"。
- 实证：上限**可配**——`app().setClientMaxWebSocketMessageSize()`（`lib/inc/drogon/HttpAppFramework.h:1301`，注释 :1297 明写默认 128K；成员默认 `128 * 1024`，`lib/src/HttpAppFrameworkImpl.h:742`），配置键 `client_max_websocket_message_size` 默认 `"128K"`（`ConfigLoader.cc:487-491`，解析失败 `:495-496` 抛异常）。被点名的 `setWebSocketMaxMessageSize` 确实不存在（整树 0 命中），但那不等于"无上限配置"。
- 补漏：该上限**只卡入站**——检查在 `if (isMasked != 0)` 分支内（`lib/src/WebSocketConnectionImpl.cc:371-379`），服务端 `send()` 的大帧不受约束，不能当内存护栏。
- 守卫：FORBIDDEN `无消息大小上限配置`、`setWebSocketMaxMessageSize`；REQUIRED `setClientMaxWebSocketMessageSize`、`client_max_websocket_message_size`、`ConfigLoader.cc:487-491`。

**B9 — CSP `{% key %}` 被写成 `[[ key ]]` 的别名**
- 原陈述：语法表 `| {% key %} | Anywhere | Alias for [[ key ]] |`，并补注"单值 `{% key %}` 合法，仅用于变量插值"。
- 实证：`drogon_ctl/create_view.cc:537-538` 把 `{% X %}` 无条件下推为 `<%c++ $$<<X;%>`——`X` 是 **C++ 表达式**，不是键名。上游模板自己的用法都是表达式（`drogon_ctl/templates/model_cc.csp:79` 的 `{%col.colName_%}`、`:197` 的 `{%i%}`）。在视图里写 `{% title %}` 得到 `error: 'title' was not declared in this scope`。
- 守卫：FORBIDDEN `Alias for \`[[ key ]]\``、`is valid for variable interpolation only`；REQUIRED `create_view.cc:537-538`。

**B10 — CSP `[[ ]]` "必须恰好一个空格"**
- 原陈述：Critical 注："方括号间必须是单个空格，`[[##]]`/`[[content]]` 永不匹配"。
- 实证：`create_view.cc:155-164` 是"跳过前导空格、再截到下一个空格"——`[[ content ]]`、`[[content]]`、`[[  content  ]]` 都取到键 `content`；`[[##]]` 取到的是键 `##`；只有 `[[ ]]` 解析成空键 `""`（布局子内容插槽，插入点 `:551`）。两个真实副作用是 `[[ a b ]]` 静默丢掉 `b`、拼错键名不报错只渲染空。
- 守卫：FORBIDDEN `must be exactly a single space`；REQUIRED `create_view.cc:155-164`。

**B11 — CSP `[[ ]]` 未说明类型限制**（B10 的同族漏项）
- 实证：生成的 `outputVal()`（`create_view.cc:71-88`）只有 `const char*` 与 `std::string`/`const std::string` 两个分支且**无 else**——`insert("age", 30)` 后写 `[[ age ]]` 不报错也不输出。
- 修复：新增"数字/布尔别用 `[[ ]]`"条目，给出 `std::to_string` 或 `<%c++ $$ << data.get<int>("age"); %>` 两条出路。

**B12 — sync advice 的返回类型写成 `HttpRequestPtr`**
- 原陈述：Advice 表 sync 行 callable 签名 `HttpRequestPtr(const HttpRequestPtr&)`，模板亦 `-> HttpRequestPtr`。
- 实证：`HttpAppFramework.h:356-358` 是 `std::function<HttpResponsePtr(const HttpRequestPtr &)>`——返回**响应**指针，非空即短路。照原签名写出来的 advice 类型就不对。
- 守卫：FORBIDDEN `HttpRequestPtr(const HttpRequestPtr&)`；REQUIRED `HttpResponsePtr(const HttpRequestPtr&)`。

**B13 — Advice 表三行行号空缺**
- 原陈述：`pre_handling (intercept)`、`pre_handling (observe)`、`post_handling` 的 Lines 列是 `—`。
- 实证：`HttpAppFramework.h:410-413`（3 参 `AdviceCallback&&`/`AdviceChainCallback&&`）、`:422-423`（1 参观察者）、`:430-432`（`void(req, resp)` 两参）。顺带核对：v1.9.13 的 post_handling **没有**第三个 `std::function<void()>` 参数（那是更新版本才有的形态，本轮不引入）。
- 守卫：**只有证据，没有自动化守卫**——表内行号与签名落在 §5 的复核记录里，`tests/test_skills_facts.py` 既无对应 FORBIDDEN token 也无对应 REQUIRED needle（行号是 `HttpAppFramework.h:NNN` 这种随版本漂移的坐标，写成子串 needle 会让下一次整体核对必须同步改测试，收益不抵维护成本）。这是已登记的缺口：填法是给 Advice 表加一条"签名参数个数"型 needle，而不是行号 needle。

**B14 — 事务"抛异常进 catch 即触发回滚"（方向反了）**
- 原陈述：ORM 事务纪律写"需要回滚时用异常或显式 rollback：抛异常进 catch 即触发回滚"。
- 实证：`orm_lib/src/TransactionImpl.cc:37-88` 析构里 `:41` 判 `!isCommitedOrRolledback_`，为真就在 `:51-52` **无条件 `conn->execSql("commit", ...)`**——异常出作用域只会让半截失败的批量写被提交。`Transaction::commit()` 在 `orm_lib/inc/drogon/orm/DbClient.h:423` 是注释掉的，只有 `:422` 的 `rollback()` 是纯虚可用接口。
- 修复：结论改为"回滚只认显式 `trans->rollback()`；异常路径必须在 catch 里显式回滚"。
- 守卫：FORBIDDEN `抛异常进 catch 即触发回滚`；REQUIRED `trans->rollback()`、`TransactionImpl.cc:37-88`。

**B15 — `newTransaction()` 的阻塞与异常形态**（B14 同族漏项）
- 实证：`orm_lib/src/DbClientImpl.cc:326-343` 以 promise/future 等待连接，超时 `throw TimeoutError`——它是**同步阻塞**调用，不能出现在事件循环线程上。

**B16 — Mapper 方法表里的假方法 `findByCriteria`**
- 原陈述：SQL 注入防护条目与操作映射表都写 `findBy` / `findByCriteria`。
- 实证：整树 0 命中。`Mapper<T>` 的查询入口是 `findByPrimaryKey`/`findAll`/`findOne`/`findBy`。
- 守卫：FORBIDDEN `findByCriteria`（豁免行除外）；REQUIRED `updateBy`。

**B17 — `req->getLoop()` 当可用 API**
- 原陈述：线程池派发模板里 `loop = req->getLoop()`。
- 实证：`lib/inc/drogon/HttpRequest.h` 全文 0 次出现 `getLoop`；只有框架内部 `lib/src/HttpRequestImpl.h:107` 有。公开可用的是 `app().getLoop()`（`HttpAppFramework.h:158`）与 `app().getIOLoop(id)`（`:168`）。
- 守卫：FORBIDDEN `req->getLoop`；`tests/test_skills_facts.py` 的正反对照测试覆盖豁免机制。

**B18 — 路径参数冒号语法 `:param`**
- 原陈述：多处写"路径支持 `:param`（如 `/users/:id`）""禁止 `{id}`/`{param}` 模板引擎语法（drogon 不支持）""禁止省略 `:` 前缀"。
- 实证：`HttpControllersRouter::addHttpPath` 用正则 `\{([^/]*)\}` 解析占位符（`lib/src/HttpControllersRouter.cc:346`），三种形态 `{}`（`:416-433` 自动编号）、`{N}`（`:367-385`，越界/为 0/重复即 `exit(1)`）、`{N:name}`（`:389-414`，名字不参与匹配）；随后统一 `regex_replace(originPath, regex, "([^/]*)")`（`:563-564`）编译成位置捕获——**名字被丢弃**，冒号只是普通路径字符。即 `{id}` 是合法写法，而 `:id` 从来不存在。
- 修复：给出真实三形态 + 取值方式（handler 形参按位、或 `req->getRoutingParameters()`，`HttpRequest.h:259`；`getParameter` 只读 query/body，`:319`）。
- 守卫：FORBIDDEN `:param`、`` `{param}` 模板引擎语法 ``。

**B19 — `HttpSimpleController` 的 `PATH_ADD` "只接受一个字符串参数"（反向禁令）**
- 原陈述：命令执行第 4 步称 `drogon_ctl` 生成的 `PATH_ADD` "可能错误包含第二个参数"，要求"多余参数必须删除"；宏速查表写 `PATH_ADD(path)`、参数个数 **1**。
- 实证：`PATH_ADD` 是变参宏 `PATH_ADD(path, ...)`（`lib/inc/drogon/HttpSimpleController.h:27`，展开为 `registerSelf__(path, {__VA_ARGS__})`），变参位全部是 `internal::HttpConstraint`（HTTP 方法、filter 名、中间件名）。生成器写出的只是一行**注释掉的示例**（`drogon_ctl/create_controller.cc:127-129`）。照旧"删掉第二个参数"会静默丢掉方法约束。
- 另核对：基类只有 `asyncHandleHttpRequest(req, callback)` 一个纯虚（`HttpSimpleController.h:46-48`），不存在带方法参数的重载——要按方法分流请用 `HttpController`。
- 守卫：FORBIDDEN `只接受一个字符串参数`；REQUIRED `PATH_ADD(path, ...)`、`HttpSimpleController.h:27`。

**B20 — simple 控制器"无法区分 HTTP 方法"（反向禁令）**
- 原陈述：选型纪律写"不得在 RESTful API 里用 `HttpSimpleController`（无法区分 HTTP 方法）"。
- 实证：`processSimpleControllerParams`（`HttpControllersRouter.cc:193-225`）把变参里的 `HttpConstraint` 按类型分流成 `validMethods`，simple 控制器完全可以限定方法。它真正的限制是**不支持路径占位符**（见 B21）。
- 守卫：FORBIDDEN `无法区分 HTTP 方法`。

**B21 — simple 控制器路径匹配的真实约束（B20 的正确替代结论）**
- 实证：simple 路径经 `tolower` 归一后存进 `simpleCtrlMap_`（`HttpControllersRouter.cc:236-239`），请求期 `find(loweredPath)` 精确查表（`:609-610`）→ 占位符会被原样当路径字符。要路径参数只能用 `HttpController` 或 lambda 内联路由（都走 `addHttpPath`）。
- 守卫：REQUIRED `simpleCtrlMap_`、`getRoutingParameters`。

**B22 — 假 API `registerPathAdvice()`**
- 原陈述：自动注册条目称"宏内部调用 `DrClassMap::getSingleInstance<Ctrl>()->registerPathAdvice()`"。
- 实证：整树 0 命中。真实链是嵌套私有类 `pathRegistrator` 的静态成员 `registrator_` 在静态初始化期调 `T::initPathRouting()`（`HttpSimpleController.h:91-104`，类外定义 `:112-114`）。
- 守卫：FORBIDDEN `registerPathAdvice`。

**B23 — 假链接目标 `drogon::orm_lib` / `drogon::redis_client`**
- 原陈述：CMake 模板与纪律条目要求 `target_link_libraries(... drogon::drogon drogon::orm_lib)`，并留了条"待验证"的 `drogon::redis_client`。
- 实证：`drogon::orm_lib` 整树 0 命中；ORM 源文件直接累加进 `DROGON_SOURCES`（`CMakeLists.txt:374` pg / `:429` mysql / `:456` sqlite3），由 `:767` `target_sources(... PRIVATE ...)` 编进主 target；Redis 源 `:474-481` 同理。前提开关在 drogon 自己的构建上：`BUILD_ORM`（`:9`）、`BUILD_REDIS`（`:23`，`CMAKE_DEPENDENT_OPTION` 依赖 `BUILD_ORM`）+ `find_package(Hiredis)`（`:468`）+ 各后端 `find_package`（pg `:367`、mysql `:406-407`、sqlite3 `:442-443`）。
- 附带实证（原描述只说"可能未导出"）：Hiredis 没找到时 drogon **照常构建**，改用 `lib/src/RedisClientSkipped.cc` 桩件——运行期 `newRedisClient` 打 `LOG_FATAL` 后 **`abort()`**（`:28-30`），不是异常，catch 不住。故 Redis 依赖必须配置期验证。
- 守卫：FORBIDDEN `drogon::orm_lib`、`drogon::redis_client`。

**B24 — "只导出唯一 imported target"口径过头**
- 原陈述：目标名条目写"Drogon 只导出 `Drogon::Drogon` 一个 imported target"。
- 实证：`Drogon::Drogon` 确是 `DrogonTargets` 导出集里唯一目标（`CMakeLists.txt:137` ALIAS、`:695-696` install(TARGETS ... EXPORT)、`:825-827` install(EXPORT ... NAMESPACE Drogon::)，`cmake/templates/DrogonConfig.cmake.in:7-8` 也这么写），但 `DrogonConfig.cmake.in:14-20` 的 `find_dependency(...)` 会把 `Trantor::Trantor` 等依赖目标一并带进来。"唯一"只成立于 Drogon 自己的导出集。
- 守卫：REQUIRED `DrogonConfig.cmake.in:14-20`。

**B25 — 下游写 `USE_COROUTINE` 编译定义**
- 原陈述：CMake 模板与 SKILL 示例输出都含 `target_compile_definitions(${project_name} PRIVATE USE_COROUTINE)`。
- 实证：`USE_COROUTINE` 是 drogon **自己的** option（`CMakeLists.txt:519-523`，判据 `DROGON_CXX_STANDARD EQUAL 20`；该标准由 `:108-113` 推导）。对已安装的 `Drogon::Drogon` 在下游再定义它不产生任何效果。消费者该做的是保证 C++20 并确认 drogon 构建时开了开关。
- 修复：模板改为 `if(CMAKE_CXX_STANDARD LESS 20) FATAL_ERROR`；SKILL 示例条目同步改写（消除与 code-guide 的自相矛盾）。

**B26 — `drogon_create_views` 的 include 前置条件**
- 原陈述：写"`find_package(drogon)` 后即可用唯一导出函数"，且模板直接调用。
- 实证：`DrogonConfig.cmake.in:53-58` 把 `include(DrogonUtilities)`/`ParseAndAddDrogonTests` 包在 `if(NOT TARGET Drogon::Drogon)` 里——同一进程里已定义过 `Drogon::Drogon`（如二级 `find_package` 或先手动 include）时这些模块不会被引入，函数就"凭空消失"。文档改为显式说明该陷阱。

**B27 — `ParseAndAddDrogonTests` "递归扫描 tests/ 并注册为独立测试目标"**
- 原陈述：CMake 扫描条目。
- 实证：`cmake/ParseAndAddDrogonTests.cmake:74-79` 入口只读 `get_target_property(SourceFiles ${TestTarget} SOURCES)`，再对每个源文件拼 `${CMAKE_CURRENT_SOURCE_DIR}/${SourceFile}`（`:39-40`）后用正则 `[ \t]*DROGON_TEST[ \t]*\([a-zA-Z0-9_]+\)`（`:50`）取宏名，逐条 `add_test(NAME <case> COMMAND <target> -r <case>)`（`:68`）——不扫目录、不建可执行目标，且**没写进 `add_executable` 的 `.cc` 一条都不会注册**（症状：ctest 显示 0 用例，无报错）。另需 `enable_testing()`。
- 守卫：FORBIDDEN `递归扫描`、`自动注册为单独的测试目标`；REQUIRED `ParseAndAddDrogonTests.cmake:74-79`、`enable_testing()`。

**B28 — RedisClient 的假命令方法 / 假模板重载**
- 原陈述："所有操作（`set`/`get`/`lpush` 等）都是异步的""**禁止**用 `execCommand<T>` 同步重载（无法获取结果）"。
- 实证：`nosql_lib/redis/inc/drogon/nosql/RedisClient.h` 公开面只有 `execCommandAsync`(:128)、`execCommandSync`(:163、:176 两个模板重载，**同步版就是给返回值用的**，内部 `:200` `prom.get_future().get()` 阻塞)、`newSubscriber`(:210)、`newTransaction`(:219)、`newTransactionAsync`(:229)、`setTimeout`(:242)、`closeAll`(:250)、`execCommandCoro`(:275)、`newTransactionCoro`(:308)。没有任何按命令命名的方法，也没有裸 `execCommand<T>`。命令名只能作为字符串参数传入，格式化委托 hiredis `redisvFormatCommand`（`RedisConnection.h:74-78`），`%s`/`%b` 之外退回 printf 语义，所以 `%d` 是合法用法。
- 修复：接口清单按行号列全（补 `newTransactionCoro`），删除"同步重载拿不到结果"的反向禁令，改成"同步版阻塞，禁止在事件循环线程用"。
- 守卫：FORBIDDEN `client->get(`、`client->set(`、`execCommand<`；REQUIRED `execCommandSync`、`newTransactionCoro`。

**B29 — `drogon_ctl create controller --namespace` 假选项**
- 原陈述：参数表把 `namespace` 当可选项，命令构造里 `cmd.extend(["--namespace", namespace])`，并声称生成到 `controllers/<类名>.h`。
- 实证：`drogon_ctl/create_controller.cc:28-59` 是白名单解析（`-s/--simple`、`-a`、`-h/--http`、`-w/--websocket`、`-r/--restful`），任何其它 `-` 开头 token 直接回 `ARGS_ERROR_STR` 并 return——**什么都不生成**。命名空间要并入类名写成 `myapp::MyCtrl`，生成器自己展开嵌套 `namespace`（`:103-115`），文件名把 `::` 换成 `_` 且写在**当前工作目录**（`:349-354`），没有 `controllers/` 子目录。restful 分支同理（`:405-407`）。
- 守卫：FORBIDDEN 无（`--namespace` 与文档正文形态冲突）；REQUIRED `create_controller.cc:28-59`。

**B30 — 把私有仓库的文件写成 drogon 自己的 `examples/pay-server/...`**
- 原陈述：`drogon-setup-config` 写"pay-plugin（`examples/pay-server/main.cc`）验证过的完整模式"；`drogon-gen-monitoring` 写"PromExporter 只挂 `/metrics/base`（examples/pay-server/config.json:127-132）"。
- 实证：v1.9.13 tag 的 `examples/` 只有 15 个示例子目录（`async_stream`、`benchmark`、`client_example`、`cors`、`file_upload`、`helloworld`、`jsonstore`、`login_session`、`prometheus_example`、`redis`、`redis_cache`、`redis_chat`、`simple_reverse_proxy`、`websocket_client`、`websocket_server`，另两个条目是 `CMakeLists.txt` 与 `README.md`），**没有 `pay-server`**。这类坐标的危害比"行号漂了"更大：用户照路径去翻官方仓库，翻不到就会连整段结论一起弃用。
- 修复：去掉伪装成 drogon 路径的坐标，明确标注"私有仓库，无行号坐标"；可自证的部分交给紧跟的最小代码样例与真实存在的 drogon 示例路径。
- 守卫：FORBIDDEN `examples/pay-server`；对 HEAD 前文本实测命中（setup-config:227、monitoring:99），修复后转绿。
- 顺带核对：正文其余 6 处 `examples/...` 引用（`async_stream/main.cc`、`prometheus_example`、`redis_cache/controllers/SlowCtrl.cc`、`redis_cache/test/test_main.cc`、`websocket_client`、`websocket_server/WebSocketServer.cc`）在 tag 里全部存在，无需改动。

### C 组：补审发现的错误（B31–B42，覆盖首轮漏掉的 11 个技能）

首轮 4 个对撞组只覆盖 22 个技能里的 11 个；交付前用 3 个新组（E 协程/lambda/http-client、F db-config/上传/流/限流、G filter/middleware/监控/会话）把余下 11 个补齐，合计再对撞 172 处引用（E 22 / F 83 / G 67，其中非 OK 为 E 2 / F 9 / G 9；每组的四类计数相加即该组总数，见 §5）。以下 12 条已逐条本地复核后才落笔。

**B31 — `connection_number` "默认 10"**
- 实证：`ConfigLoader.cc:557` `client.get("connection_number", 1)`；`:558-561` 仅当解析结果恰为 1 时才回落读 `number_of_connections`（默认同样 1）。
- 影响：不写该键的用户以为有 10 条连接，实际 1 条——压测瓶颈会被归因错方向。
- 守卫：FORBIDDEN `连接数（默认 10）`；REQUIRED `ConfigLoader.cc:557`。

**B32 — db-config 把 `password` 列进"禁止键"**
- 原陈述：键名纪律与禁止清单各一条"`password`（正确 `passwd`）"。
- 实证：`ConfigLoader.cc:552-556` 先读 `passwd`，为空时**回落读 `password`**——它是合法回落键，不是错误键（与 B2 同一条源码，首轮只改了钩子，文档这半漏了，补审抓到）。
- 修复：明确"生成时统一写 `passwd`；用户已有的 `password` 不要当错误改掉"；真正不存在的只有 `db_name` 与 db 段的 `username`（后者是 redis 键，`:614`）。
- 守卫：REQUIRED `合法回落键`。

**B33 — "SQLite 的 `connection_number` 必须为 1"**
- 实证：`DbClientImpl.cc:87-96` 对 Sqlite3 同样按 `numberOfConnections_` 建 N 条连接；`:62-67` 只把 SQLite 的 loop 数压成 1，配合 `SharedMutex` 串行。无任何 assert/throw 禁止 >1。
- 影响：把合法配置判成非法，agent 会去"修"一个没问题的文件。
- 守卫：FORBIDDEN 的 token 是带反引号的短语 `connection_number\` 必须为 1`——正文改成"可以大于 1（合法）"后不再命中，而"别说成'必须为 1'"这种反面表述也不命中。

**B34 — "禁止给 SQLite 配 `host`/`port`"的危害方向**
- 实证：`HttpAppFrameworkImpl.cc:999-1002` `addDbClient(orm::Sqlite3Config{connectionNum, filename, name, timeout})` 只取这四项，`host`/`port`/`is_fast` 被**静默丢弃**，既不报错也不生效。
- 修复：从"禁止（会出错）"改成"配了不报错、也不生效"。
- 守卫：REQUIRED `静默丢弃`。

**B35 — "`loadConfigFile` 连接失败时抛 `std::runtime_error`"**
- 实证：被点名的 `:113/117/124/139/301` 五处全是配置文件层面错误（不存在/无权限/无扩展名/解析失败/`static_file_headers` 不是数组）；与 db 相关的只有 `:545-549`（`dbname` 为空）。数据库连不上不在这里抛：SQLite 打开失败只 `LOG_FATAL` + `closeCallback_`（`orm_lib/src/sqlite3_impl/Sqlite3Connection.cc:116-127`），PG/MySQL 走运行期 `DrogonDbException`/失败回调。
- 影响：用户以为 try/catch 覆盖了"连不上"，于是没配 try/catch 之外的连接失败处理。
- 守卫：FORBIDDEN `连接失败时抛`；REQUIRED `配置文件层面`。

**B36 — `forwardCoro(req, "host:port")` 少了 scheme**
- 实证：`HttpClientImpl.cc:171-184` 只有开头匹配 `https://` / `http://` 才继续解析域名与端口，`else { return; }`——裸 `"host:port"` 造出一个什么都没设置的客户端，请求必败且无任何报错。同仓库 `drogon-gen-http-client` 的 `newHttpClient` 一行早就写了"must start with http(s)://"，协程这条自相矛盾。
- 守卫：FORBIDDEN `forwardCoro(req, "backend.example.com:8080")`；REQUIRED 带 `http://` 的正确示例。

**B37 — 反向代理模板用 `const HttpRequestPtr &req` 的裸协程**
- 实证：与同文档 Key rules 第 2 条"裸协程 handler 参数必须按值"直接冲突；官方 `examples/redis_cache/controllers/SlowCtrl.cc:16-17` 的协程 handler 也是按值收 `HttpRequestPtr req`。挂起恢复后引用悬垂正是该技能要防的 UAF。
- 守卫：REQUIRED `HttpRequestPtr req)`（示例参数按值）。

**B38 — `trantor::EventLoop::TimerId`**
- 实证：trantor（pinned SHA）`trantor/net/EventLoop.h:40` 是命名空间级 `using TimerId = uint64_t;`，`EventLoop` 类内**没有**嵌套 `TimerId`；照抄示例 B 即编译失败。同文件顺带补证 `runEvery` 在 `:194`、`invalidateTimer` 在 `:222`（文档原引用正确）。
- 守卫：FORBIDDEN `trantor::EventLoop::TimerId`；REQUIRED `trantor::TimerId`。

**B39 — session 门禁模板读一个从没写过的键**
- 实证：login 只 `insert("userId", …)`、logout 只 `erase("userId")`，check 模板却读 `getOptional<bool>("loggedIn")`；`Session.h:78-92` 键不存在时返回 `std::nullopt`，`.value_or(false)` 静默兜底 → `/profile` **永远 401**。
- 修复：check 改读 `getOptional<std::string>("userId")` + `if (!userId)`，并把"读写必须同 key 同静态类型、类型不符只打 `LOG_ERROR << "Bad type"` 后返回 nullopt（不抛）"写进 Key rules。
- 守卫：FORBIDDEN `getOptional<bool>("loggedIn")`；REQUIRED `getOptional<std::string>("userId")`。

**B40 — `HttpResponse::addCookie` 漏写 `= 0`**
- 实证：`HttpResponse.h:272-273` 是 `virtual void addCookie(const std::string &key, const std::string &value) = 0;`，另两个重载（`:276`/`:277`）也全是纯虚；文档独独第一个写成有实现体的形态，会让人以为继承时可跳过。
- 守卫：REQUIRED `const std::string &value) = 0;`（session-auth）——交付前评审指出原来只写"随 B39 的 REQUIRED 一并覆盖该文件"，而同文件 needle 盖不住这行签名；补 needle 后对改动前文本实测 0 命中。

**B41 — `MultiPartParser::getFiles()` 缺尾部 const**
- 实证：`MultiPart.h:131` `const std::vector<HttpFile> &getFiles() const;`（`:129-130` 是它的两行 `///` 注释——交付前评审把首轮登记的 `:130` 纠为 `:131`，正文与 FORBIDDEN 的理由串一并跟上）。
- 守卫：FORBIDDEN `std::vector<HttpFile>& getFiles()`；REQUIRED `&getFiles() const`。

**B42 — 监控文档自称"所有 API 与行为均已对照 v1.9.13 源码核对"，正文却给私有仓库坐标**
- 实证：`drogon-gen-monitoring` 头部一句话把 `pay-plugin`/`authforge` 段落也纳入"已源码核对"，而这些内容在 drogon 全树 0 命中（`grep -rni "PayAuthMetrics|pay-plugin|authforge"`）。结论本身与源码兼容（`collectors` 确为可选，`PromExporter.cc:37-110`），错的是**证据范围的自我声明**。
- 修复：头部改为"drogon 侧 API 与行为已对照 v1.9.13 核对；`pay-plugin`/`authforge` 段落是私有仓库经验，其行号坐标不在源码核对范围内"。
- 守卫：REQUIRED `不在源码核对范围内`。

### 交付前评审补漏（B43–B45，首轮扫描面之外的活声明）

> 命名说明：§2 的 A/B/C 组是**错误来源分组**，§5 的 A–G 是**对撞代理分组**，两者不对应；本节是交付前评审代理的补漏，为避免与代理 D 组混淆，不再用字母命名。B45 的来源略有不同——它首轮登记为"取证环境限制"的 UNVERIFIED（见 §5），本轮补到证据后升级为事实错误。

交付前的 3 个评审代理复核的是**本批次的整改本身**。B43/B44 不是新读源码读出来的，而是首轮扫描面（`skills/**` + `CLAUDE.md`）之外的文件里仍在生效的假能力声明——同一条错误在盲区又活了一份。

**B43 — README 双语版仍在推销 `:param`**
- 原陈述：`README.md:107` / `README.zh-CN.md:107` 的技能矩阵把 `drogon-create-controller` 写成"路径前缀差异、`:param`、自动注册"。
- 实证：drogon 没有冒号占位符——`HttpControllersRouter.cc:346` 的 `\{([^/]*)\}` 只认 `{}` / `{N}` / `{N:name}`（见 §2 的 B18），冒号被当成普通路径字符。CLAUDE.md 路由表首轮已改对，README 是同一条错误的另一处落点。
- 影响：README 是用户读到的第一份能力清单，比技能正文更容易被当成事实照抄。
- 修复：两行都改为 `{}` / `{N}` 路径参数。
- 守卫：`SCAN_GLOBS` 追加 `README*.md` 后该 token 立刻转红（命中 `README.md:107`、`README.zh-CN.md:107`），改完转绿——红与绿都实测过。

**B44 — `log_level` 的"默认 `INFO`"混淆技能默认与源码默认**
- 原陈述：`drogon-setup-config/SKILL.md:23` 写"只认 `TRACE`/`DEBUG`/`INFO`/`WARN`，默认 `INFO`"；同技能 code-guide 的「错误处理」段又列"`log_level` 不是有效的日志级别：返回错误消息"。
- 实证：`ConfigLoader.cc:168` 源码默认是 `"DEBUG"`；`:169-184` 只匹配四个串、**没有 `else` 分支**，非法值既不报错也不返回错误消息，`setLogLevel` 压根不会被调用（停在 trantor 内建默认档）。"返回错误消息"描述的其实是**本技能**对入参的校验（`format` / `listen_port` / `log_level` 是技能参数，不是 drogon 的键名），但读者会当成 drogon 的行为。
- 修复：SKILL.md 按同表 `enable_session` 行的既有口径写清"本技能默认 / drogon 自身默认"；code-guide 的「错误处理」段补上主语，并把 drogon 侧"不校验"的源码事实写在同一段。
- 守卫：REQUIRED 新增 `drogon 自身默认 \`DEBUG\``（SKILL.md）与 `不是 drogon 的键名`（code-guide，取正文那半句做 needle），两条对本轮改动前的文本实测 0 命中、改动后转绿；`ConfigLoader.cc:168-184` 首轮已在 needle 表内。

**B45 — `Json::Value({{"k", "v"}})` 不是 JSON 对象，而是能编译通过的未定义行为**
- 原陈述：`skills/drogon-gen-filter/references/code-guide.md:36` 的 auth filter 模板用 `drogon::HttpResponse::newHttpJsonResponse(Json::Value({{"error", "unauthorized"}}))` 造 401 的错误体——读者会以为它构造出 `{"error":"unauthorized"}`。
- 实证（三层，全部本地可复现）：
  1. jsoncpp `Value` **没有** `initializer_list` 构造：`include/json/value.h` 在 tag `1.9.5`/`1.9.6`/`1.9.7` 与 `master` 上 `grep -c initializer_list` 均为 **0**，构造只有 `Value(Int)`、`Value(const char*)`、`Value(const char*, const char*)`、`Value(const String&)` 等。
  2. 那它为什么能编译？`clang++ -std=c++17 -fsyntax-only` 退出码 0——外层花括号列表把内层 `{"error", "unauthorized"}` 当成**两个实参**喂给了 `Value(const String &)`，先构造 `std::string(begin, end)`。
  3. 重载决议的实际选中项由 `-Xclang -ast-dump` 定死：`CXXConstructExpr 'const String' 'void (const char *, const char *, const allocator &) '`，两个操作数分别是字面量 `"error"` 与 `"unauthorized"` 的**数组首元素指针**。这两个指针来自互不相干的两个字面量，`[begin, end)` 不是合法区间——长度取决于两块内存的相对布局，是未定义行为；即使侥幸跑通也得到一个乱码字符串而不是对象。
  4. 顺带收紧的一条同族事实：jsoncpp `Value::asString()`（`json_value.cpp:628-651`）只对 `nullValue` 返回 `""`，`intValue`/`uintValue`/`realValue` 走 `valueToString()` 得到十进制串，`booleanValue` 得 `"true"`/`"false"`，array/object 落 `JSON_FAIL_MESSAGE`。所以"写成 JSON 数字时 `asString()` 会返回空串"这种担心不成立，`client_max_body_size: 1048576`（§2 的 B7）与字符串写法同样中招。
- 影响：这是本批次里唯一**写法本身即未定义行为**的一条——同族的 B14（异常路径静默提交）、B36（裸 `host:port` 造出空客户端）、B39（读一个从没写过的 session 键）同样能编译且静默出错，但那三处调的都是合法接口、只是走错分支；B45 是构造实参的那个 `[begin, end)` 区间本身非法。技能模板是被照抄的对象，用户拿到的是"能编、能跑、错误体是垃圾或随机崩溃"的代码——比编译失败更难发现。drogon 自己的示例与其它技能的 JSON 响应写法都是显式赋值（`drogon-gen-lambda-handler` :39-41、`drogon-gen-rate-limiter` :58/:94），只有 filter 模板这一处用了花括号列表。
- 修复：模板改为 `Json::Value body; body["error"] = "unauthorized";` 后把 `body` 传给 `newHttpJsonResponse`（`HttpResponse.h:418` 收 `const Json::Value &`）；同技能「禁止模式清单」新增一条，把"没有 initializer_list 构造 / 实际匹配 `Value(const String &)` / 无关字面量首尾指针"三点写成可自证的结论与替代写法。
- 守卫：三层各设一道。① `FORBIDDEN` 新增 `Json::Value({{`（全扫描面命中即红，模板行本身改为反面示例并点名豁免）；② `REQUIRED` 新增 2 条锁死正确写法（`no \`initializer_list\` constructor` 与 `Json::Value body; body["k"] = "v";`）；③ 钩子新增 `CPP.010`（`error`，正则 `\bJson::Value\s*[({]\s*\{`）。正则取 `[({]\s*\{` 而不是 `\(\s*\{\{`：交付前评审实测出换写法就绕过（`Json::Value({ { … })`、`Json::Value{{ … }}`），加宽后由 `tests/test_posttooluse.py` 的 `JSON_UB_SPELLINGS` 6 种拼写参数化钉住覆盖面，另配 `test_CPP010_does_not_fire_on_explicit_object_build` 作正向对照（逐键赋值不得被顺手打死）。**这两条测试都先见 RED 再改正则**，`RULE_FIXTURES` 那条则先红在 `unknown rule CPP.010`。ReDoS 沿用第四轮 F1 教训：无嵌套量词，实测输入 300KB→2.4ms、600KB→4.9ms、1.2MB→10.0ms、2.4MB→20.2ms（长度翻倍耗时翻倍，与同长度无锚点文本 600KB→3.0ms 同阶，即线性扫描代价）。转绿后 `python -m pytest tests/test_posttooluse.py -q` = **104 passed, 2 skipped**。
- 守卫的残余缺口（登记，不修）：文档侧是子串 token、钩子侧是正则，两套口径不等价——`Json::Value{{`（无圆括号）在文档扫描面不红，只被钩子拦；钩子仍漏变量名插在中间的 `Json::Value body{{…}}`（加宽要引入 `\w+` 回溯，代价不值）。实测至少还漏 3 类：`Json::Value v{{…}}`（短变量名）、`Json::Value x = {{"k","v"}};`（等号赋值）、`Json::Value a( { {…} } )`（括号内多层空格）。合规代码由钩子兜底即可，文档 token 的职责只是防同一段错误 prose 回流。

## 3. 坐标漂移（结论对、行号错）

| 编号 | 落点 | 原引用 | v1.9.13 实际 |
|------|------|--------|--------------|
| C1 | drogon-gen-cmake | mysql `find_package` 在 `CMakeLists.txt:410-414` | `:406-407`（`:410-414` 是 `set(DROGON_FOUND_MYSQL ...)` 结果处理） |
| C2 | drogon-gen-orm-model | 不支持的 `db_type` 报错在 `create_model.cc:964-968` | 读键并转小写在 `:964-968`，`"Does not support "` + `exit(1)` 在 `:1308-1312` |
| C3 | drogon-create-controller | restful 空参数越界读 `parameters[0]`（`:87`） | `:88`（`:83-86` 是 `size() > 1` 的 `Too many parameters`；判定用 `> 1` 而非"恰好 1"，一个类名都不给时读空 vector——生成命令必须始终带类名） |
| C4 | drogon-create-controller | `{}` 自动编号 `:414-431` | `:416-433`（`:414` 是 `{N:name}` 分支的 `push_back`，`++placeIndex` 在 `:433`） |
| C5 | drogon-gen-orm-crud | `TransactionImpl.cc:37-78` | `TransactionImpl.cc:37-88` |
| C6 | drogon-gen-orm-crud | `HttpControllersRouter.cc:181-215` | `:193-225`（`processSimpleControllerParams` 全体） |
| C7 | drogon-gen-plugin | `HttpAppFrameworkImpl.cc:636-637`（称顺序始于 `createDbClients`）、`:636-686` | `:631-632`、`:631-686`（`:636` 已进 `createRedisClients` 之后的段落，起点前移 5 行；结论"插件 initAndStart 在 IO 线程池启动前同步执行"不变） |
| C8 | drogon-gen-csp-view | `model_cc.csp:197` 的 `{%i%}` | `:223`（`index = offset + {%i%};`，另见 `:314`/`:316`/`:480`；`:197` 实际是 `{%col.colValName_%}` / `{%col.colType_%}`） |

## 4. 连带产物

- `CLAUDE.md` 技能路由表两行随正文改写：创建控制器行去掉 `:param` 改为 `{}`/`{N}` 路径参数；测试行由"CMake 扫描"改为"CMake 注册（`ParseAndAddDrogonTests` 只认 target 的 SOURCES）"。
- `AGENTS.md` / `GEMINI.md` 等宿主产物由 `scripts/gen-host-artifacts.py` 重新生成，`npm/assets` 与 `drogon_plugin_assets` 由 `sync-assets` 双向对拍。

### 守卫自身的加固（交付前评审提出，非文档事实错误）

本轮的教训是"改对了正文，但守卫的覆盖面与放行粒度不够，导致同一错误在盲区继续活着"，因此新建的 `tests/test_skills_facts.py` 按交付前评审指出的盲区做了五处加固。交付时的实测规模：**86 用例 / FORBIDDEN 33 个假 token / REQUIRED 46 条 needle / FILE_SCOPE 3 条 / 扫描面 49 文件**（`python -m pytest tests/test_skills_facts.py -q` 与直接 import 该模块读登记表长度，两条都跑过；全仓 `python -m pytest tests/ -q` = **339 passed, 2 skipped**；本文件与守卫都是本批次新增，未进 HEAD，所以这里只给当场实测的绝对数字，不给无法复验的增量）：

- **扫描面**：`SCAN_GLOBS` 由 `skills/**/*.md` + `CLAUDE.md`（45 文件）扩到再含 `README*.md`、`AGENTS.md`、`GEMINI.md`（49 文件）。README 直接抓出了 B43；生成产物进扫描面只多拦一种情况——假 token 已在 CLAUDE.md 改掉但产物没重生成时这里会再红一次（"产物整体不同步"本来已由 `tests/test_hosts.py::test_generator_check_passes_on_repo` 拦住，不夸大成本用例的作用）。
- **扫描面 canary**：`test_scan_surface_still_covers_every_fact_source` 钉住五个根文件在面内、`skills/**/*.md` 全量在面内、技能数仍为 22、总数不低于 49。四条分工要写清，别读成"任何改名都会红"：① 把 `SCAN_GLOBS` 改小 → 根文件那条断言红；② 被 REQUIRED 点名的文件改名 → 该 needle 红（needle 找不到宿主文件）；③ **没被任何 needle 点名的 `references/*.md` 改名 → 不会红**，这是本 canary 的已知盲区，只能靠下一条的总数下限和评审 diff 兜；但改扩展名（`.md`→`.txt`）会让 `>=49` 红，改无 needle 的 `SKILL.md` 会让 `==22` 红——这两类不是盲区；④ 技能数不再是 22 → 红，但它同时是"口径变更"信号，新增技能时必须同步改 22 与报告与 README 矩阵，否则就会红。
- **登记表数量 canary**：`test_fact_registries_have_declared_sizes` 写明 33/46/3 三个数字，并校验 `FILE_SCOPE` 只能指向 `skills/` 下以 `/` 结尾的目录前缀。因为 FORBIDDEN/REQUIRED 是用 `parametrize` 展开的，删一条就少一条用例且**不会变红**；把数量写死是为了让"削弱守卫"必须是一次显式改动，而不是顺手清理。数量对得上不代表内容还在：同一条用例另校验每个 token 与其理由非空白（空白 token 子串匹配等于永不命中、清空理由让红灯变成没有结论的噪音）、每条 needle 非空白、`REQUIRED` 无重复条目（重复会把 canary 的数字撑虚）。
- **豁免标记点名 token**：`<!-- fact-guard-waived -->` 改为 `<!-- fact-guard-waived:TOKEN -->`。行级裸标记会把同一行上的其它假 token 一起放掉（redis-config:189 一行里就有 `client->get(` / `client->set(` / `execCommand<` 三个），现在逐 token 各写一个标记（交付时实测 7 行共 10 个标记）。合法性判定抽成纯函数 `_waiver_problems()`，`test_no_zombie_waiver_marker` 用它扫**全扫描面 49 文件**（本文件与 `docs/`、`npm/assets`、`drogon_plugin_assets` 不在面内，别把这条读成"扫全仓"），`test_waiver_decoration_is_always_a_problem` 用合成文本做正反对照，抓四种装饰：裸标记、未闭合标记、未知 token 名、以及**在不扫描该 token 的文件里豁免它**（`FILE_SCOPE` 之外的文件根本不会被检查，那种标记只骗得过读 diff 的人）。另有 `test_waiver_for_one_token_does_not_lift_another_on_the_same_line` 证明豁免不跨 token 传染。
  - 交付前第二轮评审在这条里实测出一个**死分支**：判定"该行确实写了这个 token"时没先把标记文本剥掉，而标记名本身就含 token，所以这条腿永远成立——豁免一个正文里根本不存在的词也会被判合法。已抽 `_strip_markers()` 修掉（未闭合的标记连同其后内容一起丢掉，宁可少放行也不留死分支），并用合成文本 `phantom` 正反对照锁死；改动前后各跑一次，改前那条断言确实红。
- **散文型 token 按目录限定**：`FILE_SCOPE` 把 `只接受一个字符串参数`、`递归扫描`、`连接失败时抛` 三个中文措辞 token 限定在它们真正说过错话的技能目录里——这类词换到别的文件（尤其新纳入的 README）很可能是另一句正确的话，不限定就把守卫变成"仓库里不许出现这个词"。`test_file_scope_narrows_without_emptying` 保证限定真的生效、又没被 scope 成 0 个文件（那等于删守卫）。

**这套机制仍然拦不住什么**（写清楚，免得把加固当成完备）：

- 豁免按行放行，所以把一句真回归**追加到已豁免行的末尾**照样被放掉。要拦就得限制"一行只允许一个假 token"，代价是把教学句式逼成断行，本轮不做。
- 子串匹配对写法敏感：`client->get("k")` 写成 `client->get ("k")`、`req->getLoop` 写成 `req -> getLoop()` 都是绿的。补变体 token 只能覆盖想得到的写法，覆盖不了写法空间。
- 文档守卫是**子串**口径，钩子是**正则**口径，两者不等价：`Json::Value{{` 只在钩子里红，文档扫描面看不见（B45 末尾已登记）。把 token 换成正则能对齐，但代价是每条禁止项都要维护一条正则和一张写法覆盖表，本轮只对"能编译的 UB"这一条付这个代价。
- `docs/` 下的报告本身不在扫描面内，所以报告里复述错误写法不会被拦——这是刻意的（报告必须以原文引用被删掉的错误），也意味着报告的准确性只能靠评审对撞，没有自动化兜底。
- `FILE_SCOPE` 是双向的：它避免了误红，也意味着这三个措辞在各自 scope 之外的 **47 个文件**里完全失明（每条 scope 只命中 2 个文件——该目录下的 `SKILL.md` 与 `references/code-guide.md`——扫描面共 49 个），包括 README。取舍依据是"这三条的错误只存在于那一个文件的上下文"，新增同类错误时应优先登记为 API/键名型 token。

## 5. 复核方法与结论

- 七个只读对撞子代理分组覆盖全部 22 个技能的文档，共 442 处引用（首轮 270 + 补审 172），逐条在 tag 原文读取区间上下文；首轮四组（270 处，A/B/C/D）汇总（OK / DRIFT / WRONG-CLAIM / UNVERIFIED）：
  - A（create-controller）29 / 0 / 0 / 0——其中 2 条按 ±3 容差判 OK，本轮仍收紧为精确行号（§3 的 C3、C4）。
  - B（cmake + test）44 / 1 / 0 / 0——DRIFT 即 C1。
  - C（orm + model + redis）59 / 0 / 1 / 1——WRONG-CLAIM 即 C2；1 条 UNVERIFIED 未取证，因此**没有**据此改任何文档。
  - D（config + ws + plugin + advice + csp）128 / 2 / 1 / 4——首次运行因 SSE 60s 无数据中断，重跑后完成；DRIFT 两条即 C7，WRONG-CLAIM 一条即 C8。
- 交付前补跑 3 组（覆盖首轮漏掉的 11 个技能，结果按 §2 的 C 组处理）：E（coroutine + lambda + http-client）20 / 0 / 2 / 0；F（db-config + file-upload + stream + rate-limiter）74 / 1 / 5 / 3；G（filter + middleware + monitoring + session-auth）58 / 1 / 6 / 2。
- 补审组里 3 条 UNVERIFIED 由本地补证转为 OK，未改文档：trantor `AsyncStream::send` 的"@return false if the connection is closed"注释、`EventLoop::runEvery`(:194)/`invalidateTimer`(:222) 行号、`InetAddress::toIp()`(:106) 存在性——均经 `gh api` 取 pinned SHA 原文核实。
- 补审组里另有 2 条**不成立或不成立到可以改的程度**，按纪律不落到文档：① "login 模板里 `checkCredentials(user, passwd)` / `userId` 未声明，不可编译"——模板里的占位函数与占位变量不是事实主张，文档也没有声称它是完整程序，与 B39（读了一个从没写过的 session 键，属真实逻辑错误）区别对待；② ~~`Json::Value({{"error", "unauthorized"}})` 能否编译~~ 首轮以"jsoncpp 不在本地 clone"记为无法取证，**本轮已补证并推翻原代理结论的方向**：它能编译，但构造的不是对象而是 UB，因此升级为 §2 的 B45 事实错误处理，不再留在"不落到文档"这一档。
- 组 D 的 4 条 UNVERIFIED 是取证环境限制而非文档缺陷：① trantor `net/inner/TcpConnectionImpl.cc` 里 `send()` 的跨线程派发（代理报 460-473，已按 pinned SHA 经 API 实读 460-474 补证）② jsoncpp `asString()` 的两项行为——本轮已补证（见 §1 的 jsoncpp 行与 `json_value.cpp:628-651`），结论是"整型不会变成空串"，§2 的 B7 表述原本就写对了，无需改文档 ③ `examples/pay-server/main.cc`（该路径不存在，升级为 §2 的 B30 事实错误处理）④ `pay-plugin` / `authforge` 的全部外部行号（见 §6）。
- 组 D 另给出"其余重点主张均被源码支持"的清单（`enable_session` 默认 false、`threads_num`→`number_of_threads` 优先级、`log_level` 取值与默认 DEBUG、bytesSize 白名单缺 `'6'`、listener cert/key 与全局 ssl 块回落、Advice 各注册声明的签名与 intercept/observe 划分、插件 initAndStart 在 IO 线程池启动前同步执行 + shutdown 逆序且晚于 DB/Redis reset、CSP outputVal 分支与键名解析规则），与本轮改动无冲突；`HttpAppFramework.h` 的 `register*Advice` 声明经本地 grep 为 14 处（对应 11 类切面，PreRouting/PostRouting/PreHandling 各有 2 个重载），文档"11 个内建切面"口径成立。
- 代理上报的坐标漂移按 §3 处理；**其中 4 条被当场推翻**（不得按代理结论改文档）：
  1. "`setClientMaxWebSocketMessageSize` 在 `@deprecated` 块内"——`HttpAppFramework.h` 全文 0 处 `@deprecated`，`:1295-1302` 是正常声明，默认 128K 写在 `:1297`。
  2. "`registerPostHandlingAdvice` 是 3 参（末参 `std::function<void()>`）"——`:430-432` 在 v1.9.13 就是 2 参；3 参是更新版本形态，本轮不引入。
  3. "顶层 `ssl` 块非可选、无条件 `loadSSL(..., true)`"——实际调用是 `ConfigLoader.cc:705` `loadSSL(configJsonRoot_["ssl"])`，函数体 `:678-679` `if (!sslConf) return;`，键名正是 `key`/`cert`/`conf`（`:680-684`），文档口径成立。
  4. "`<%view %>` 必须行首"——`create_view.cc:180` 用 `line.find(sub_view_start)` 在整行任意位置匹配，"Anywhere"属实。
- 本地无法直接取证的两处外部依赖：① trantor 子模块未 checkout，已按 `an-tao/trantor` 的 pinned SHA 经 `gh api` 取原文核实三处——`trantor/net/EventLoop.h:116`（文档用它作 `getEventLoopOfCurrentThread()` "无循环线程返回 nullptr" 的坐标，落点 `skills/drogon-gen-orm-crud/references/code-guide.md:91-92`；实测该行正是该声明，且头文件在 `net/` 不在 `utils/`）、`trantor/utils/Logger.h:282-288`（B5 的 `LOG_LEVEL` 编译期默认档）、`trantor/net/inner/TcpConnectionImpl.cc:460-474`（`send(const char*, size_t)` 的跨线程派发）。**路径注意**：`trantor/net/TcpConnectionImpl.cc` 在 pinned SHA 上不存在（`gh api` 返回 404），实际在 `net/inner/` 下，早期记录漏了 `inner/`；② jsoncpp 不在 clone 内——首轮据此把三条相关主张记为 UNVERIFIED，本轮改为按 `open-source-parsers/jsoncpp` 的 tag 原文 + 本地 `clang++` 实测取证（方法见 §1），其中 `asString()` 的行为证实了 B7 原文，`Value` 无 `initializer_list` 构造则把"无法取证"升级为 B45 这条真错误。**教训写下来**：依赖库不在 clone 不等于主张无法取证，`find_package` 的外部库同样有公开 tag 可读，编译器也在本机可用。
- 交付前另有 3 个评审代理复核**本批次的整改本身**（不是再读源码），逐条对撞后处理如下：
  1. **成立并已改**：README 双语版的 `:param`（B43）、`MultiPart.h:130` → `:131`（B41）、SKILL.md 的 `log_level` 默认值口径（B44）。
  2. **成立并已改（本文件自身的假陈述）**：§2 B7 的"守卫"行原先声称覆盖了两个落点，实际只有 `bytesSize` 真有 needle；B40 的"随 B39 的 REQUIRED 一并覆盖"实际盖不住那行签名；本文件开头把 `B1`/`B2`/`B3` 编号注释的落点写成 `tests/test_skills_facts.py`，实测在 `hooks/posttooluse.py` 与 `tests/test_posttooluse.py`；§2 C 组引言与 §5 的加总把 G 组记成 68（其四类相加是 58+1+6+2=67），连带 173→172、443→442。以上均已按实测重写，并给前两条补了真 needle。
  3. **成立并已加固**：豁免标记跨 token 传染、散文 token 的全仓误伤、扫描面盲区——见 §4 的五处加固。
  4. **未采纳并说明理由**："`req->getLoop` 应补 `request->getLoop` 之类变体 token"。本仓库文档一律用 `req` 指代请求（全扫描面 `request->getLoop` 0 命中），而守卫是子串匹配，要覆盖任意变量名就得引入"同行多 token 相与且排除正确写法"的机制；为没出现过的写法付这个复杂度属于凭空设计，不做。
  5. **另需澄清**：首轮统计外部私有仓库坐标用的 55/65/29 与本轮重测不同，§6 已改用交付前重测口径并注明方法。
- 上述整改落地后**又跑了一轮同标准的交付前评审**（3 个代理：守卫方向、文档声明对撞、钩子规则覆盖）。这一轮抓到的全是**本文件与 CHANGELOG 自己的假陈述/过头陈述**，逐条处置如下（全部按实测改）：
  1. **成立并已加固（守卫真缺陷）**：`_waiver_problems()` 的"该行确实写了这个 token"是死分支——豁免标记的文本本身就含 token 名，判存在前必须剥掉标记。已抽 `_strip_markers()` 修掉，并给 `test_waiver_decoration_is_always_a_problem` 补第 ④ 条合成正反对照（改前该断言确实红）。
  2. **成立并已加固（规则漏写法）**：`CPP.010` 原正则 `\bJson::Value\s*\(\s*\{\{` 被 `Json::Value({ { … })` 与 `Json::Value{{ … }}` 绕过。先补 6 条 `JSON_UB_SPELLINGS` 参数化用例见到 2 条红，再加宽成 `\bJson::Value\s*[({]\s*\{`，同时补逐键赋值的正向对照防误报；仍漏的 `Json::Value body{{…}}` 与"文档 token 与钩子口径不等价"已在 B45 末尾登记为残余缺口。
  3. **成立并已改（数字说谎）**：`test_posttooluse.py` 的"97 passed"实为**104 passed, 2 skipped**；`<1ms` 的 ReDoS 表述换成可复现的分段计时（见 B45）；§6 的"27 行"复现不出来已撤（见 §6 的更正记录）；"新增项一律先见 RED"有 2 条例外，已改成 31/33 并列名那两条。
  4. **成立并已改（口径与主语错位）**：§5 的 trantor 路径漏 `inner/`（`net/TcpConnectionImpl.cc` 在 pinned SHA 上 404）；`EventLoop.h:116` 未写用途与落点；B44 的 needle 名照抄了整句而实际登记的是半句；§4 把 `test_no_zombie_waiver_marker` 的范围写成"扫全仓"（实为扫描面 49 文件）；§1 的 `CMakeLists.txt:191-193` 收紧为 `:192-193`（`:191` 是 `# jsoncpp` 注释）；§4 的扫描面 canary 原写"改名才会红"过宽，已按三条分工重写并如实登记"无 needle 的文件改名不会红"；B13 的"守卫"原本只有复核记录、没有任何自动化断言，已改成明写缺口。
  5. **成立并已收窄**：B45 原称"本批次唯一编译器不报错的一条"过头——B14/B36/B39 同样能编译且静默出错，区别在写法本身是否非法；措辞已收窄为"唯一写法本身即未定义行为的一条"并列出那三条同族。
  6. **不成立，未采纳**："`EventLoop.h:116` 的用途无法取证"——该坐标确实被 `skills/drogon-gen-orm-crud/references/code-guide.md:91-92` 用作 `getEventLoopOfCurrentThread()` 返回 nullptr 的依据，且 pinned SHA 原文 `:116` 正是这条声明（`:111-112` 的注释写着 "Return nullptr if there is no event loop in the current thread"），故保留该坐标并按第 4 条补写用途与落点。另有一条代理建议（"`CMakeLists.txt` 该写成 `:192-193`）本身成立，已并入第 4 条，不重复计数。

## 6. 本轮明确不处理

- **1.9.14-only 内容**：任何需要更高版本才成立的 API 形态（含上面第 2 条）不进正文；若要支持需先整体抬基线声明，另开轮次。
- **指向外部私有仓库的坐标**：按交付前重测（对 §5 的 49 个扫描文件正则匹配 `pay-plugin|authforge`）共 **56 行命中 / 67 词次**，且这 56 行全部落在 `skills/` 下（按 9 个技能文件分布：plugin 15、test 11、cmake 8、orm-model 6、monitoring 6（`SKILL.md` 1 + code-guide 5）、setup-config 5、rate-limiter 4、redis-config 1）。"带行号坐标"这一档按**同行出现 `:<数字>`** 计为 **32 行**；改按更严格的"同行还要有一个带扩展名的文件名"（`\.\w+:\d`、`[\w./-]+\.\w+:\d`）同样是 **32 行**，两种口径在这批数据上一致。插件用户拿不到这两个仓库，等于不可复核的证据。应改为内联最小样例或随包 `examples/`，登记为 0.6.0 待办。**例外**：`examples/pay-server/...` 伪装成 drogon 官方路径的那两处已在本轮处理（§2 的 B30）——它们的错不在于"私有"，而在于冒领了公开仓库的坐标。
  - 更正记录：本条曾写"更严格口径为 27 行"。交付前第二轮评审复核时按上述几种文件名词形正则各跑一次都得到 32，那个 27 复现不出来，因此撤掉"两种口径相差 5 行"的说法，只保留可复现的 32。
- `docs/ROUND4-INCREMENTAL-CORRECTNESS-REVIEW.md` 里的宿主/流水线项与本批次无关，不在本文件范围。
