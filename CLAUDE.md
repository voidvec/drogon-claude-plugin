# Drogon 后端开发规则

> 本文件由 `drogon` Claude Code 插件提供。基于 Drogon 框架做后端开发时,以下规则堵住最高频、最隐蔽的 bug,**必须遵守**。规则针对 drogon v1.9.13,关键断言附源码位置。

## A. 异步回调模型

Drogon 的每个 handler 接收一个 `std::function<void(const HttpResponsePtr &)>` 回调对象。**响应的发出只与回调是否被调用有关,与 handler 是否 return 无关**(见 `lib/src/HttpAppFrameworkImpl.cc`——响应仅在 `callback(...)` 执行时才发出)。

1. **恰好一次**:每个 handler 必须在**所有代码路径**(含所有错误/异常/提前返回路径)上**恰好调用一次** `callback`。绝不能"handler 返回了就算响应已发"。
2. **绝不重复**:禁止第二次调用 `callback`——二次调用是未定义行为,可能导致重复响应或连接状态污染。
3. **返回 ≠ 已响应**:response 仅在 `callback(resp)` 真正执行时才发出。
4. **按值捕获回调**:异步/延迟场景下,`callback` 必须**按值捕获**进闭包(`std::function` 可拷贝),确保其生命周期超出 handler 栈帧;悬空回调会导致崩溃。
5. **禁止 handler 内同步阻塞**:不得在 handler 内做阻塞式同步 I/O(同步读 DB、`sleep`、长计算、阻塞文件读写)然后再 `callback`——这会卡死事件循环线程。改用 drogon 异步 API,或丢到线程池,完成处就近 `callback`。
6. **优先协程**:`__cpp_impl_coroutine` 已定义且 CMake `USE_COROUTINE=ON` 时,优先用协程 handler。**注意区分**:`Task<>` / `Task<HttpResponsePtr>` 会向上传播异常、可被 `co_await`,框架负责异常与响应交付;而 `AsyncTask`(fire-and-forget)在抛出**未处理**异常时会 `std::terminate`——用 `AsyncTask` 时**必须** try/catch(见规则 7)。优先选 `Task<HttpResponsePtr>`;只有当你需要自行管理 callback 时才用 `AsyncTask`,且务必兜异常。
7. **异常不得逃逸 handler**:handler 体内禁止让异常逃逸;用 try/catch 包裹业务逻辑,在每个 catch 路径上都调用 `callback(错误响应)`。框架的默认异常处理器(`lib/src/HttpAppFrameworkImpl.cc` 中的 `defaultExceptionHandler`)只是兜底,**不能替代你自己对 callback 的保证**——异常一旦逃逸,callback 很可能永远不被调用,违反规则 1。

## B. Trantor IO / 事件循环模型

Drogon 跑在 trantor 的事件循环上;配置项 `number_of_threads` 决定循环数(**值为 0 表示按 CPU 硬件并发数自动设置**,见 `lib/src/HttpAppFrameworkImpl.cc` 中 `setThreadNum` 实现),每条连接被钉在某个循环上。

1. **事件循环线程不可阻塞**:禁止在事件循环线程做任何阻塞工作(同步 DB 调用、`sleep`、长计算、阻塞文件 I/O)。它会拖死**同一个循环上**的所有其他连接。
2. **重/阻塞活儿走线程池**:把重活儿交给独立线程池;完成后用 `runInLoop` 把回调派发回连接所属的事件循环,再在那里 `callback`。
3. **跨循环共享状态的纪律**:跨循环共享的状态必须加锁;更优做法是保持状态"循环局部",或用 `runInLoop` 派发到归属循环访问,避免竞态。

## C. 代码示意

下列示意聚焦"回调纪律 / 不阻塞 / 异常安全"三件事的**形状**;具体 ORM/异步 API 签名以 drogon v1.9.13 实际为准。

### ❌ DON'T:早返回路径没回调 + 同步阻塞事件循环

```cpp
void Ctrl::bad(const HttpRequestPtr &req,
               std::function<void(const HttpResponsePtr &)> &&cb) {
    if (req->getParameter("id").empty())
        return;                       // BUG: 直接返回,响应永远不会发出(违反 A.1)
    auto row = syncQueryFromDb();     // BUG: 阻塞事件循环线程(违反 B.1)
    auto resp = HttpResponse::newHttpResponse();
    resp->setBody(row);
    cb(resp);
}
```

### ✅ DO(回调式):每条路径恰好回调一次;异步结果用回调接收,不阻塞;异常路径也回调

```cpp
void Ctrl::good(const HttpRequestPtr &req,
                std::function<void(const HttpResponsePtr &)> &&cb, int id) {
    // 多个异步 lambda 都要用到 callback:包进 shared_ptr 再按值捕获进每个 lambda,
    // 既保证生命周期超出本栈帧,又避免把同一个 callback move 两次(A.4)。
    auto cbPtr = std::make_shared<std::function<void(const HttpResponsePtr &)>>(
        std::move(cb));
    try {
        app().getDbClient()->execSqlAsync(
            "SELECT name FROM users WHERE id=$1",
            [cbPtr](const orm::Result &r) {                     // 按值捕获 shared_ptr(A.4)
                auto resp = HttpResponse::newHttpResponse();
                resp->setBody(r.empty() ? "none" : r[0]["name"].as<std::string>());
                (*cbPtr)(resp);                                  // 成功路径回调(A.1)
            },
            [cbPtr](const orm::DrogonDbException &e) {
                (*cbPtr)(HttpResponse::newHttpResponse());       // 错误路径回调(A.1)
            },
            id);
    } catch (...) {
        (*cbPtr)(HttpResponse::newHttpResponse());               // 异常路径也回调(A.7)
    }
}
```

### ✅ DO(协程式,AsyncTask):仍接收 callback,每条路径都回调;异常用 try/catch 兜住(否则未处理异常会 std::terminate)

```cpp
drogon::AsyncTask Ctrl::goodCoro(
    const HttpRequestPtr req,
    std::function<void(const HttpResponsePtr &)> callback, int id) {
    try {
        auto loop = trantor::EventLoop::getEventLoopOfCurrentThread();
        auto r = co_await app().getDbClient()->execSqlCoro(            // 异步,不阻塞循环(B.1)
            "SELECT name FROM users WHERE id=$1", id);
        auto resp = HttpResponse::newHttpResponse();
        resp->setBody(r.empty() ? "none" : r[0]["name"].as<std::string>());
        callback(resp);                                               // 成功路径回调(A.1)
    } catch (...) {
        callback(HttpResponse::newHttpResponse());                    // 异常路径也回调(A.7)
    }
    co_return;
}
```
## C. drogon_ctl 使用规范

### C.1 生成文件的约定
`drogon_ctl create controller` 生成的文件遵循 `<类名>.h` + `<类名>.cc`，放置在 `controllers/` 子目录下（可通过 `--namespace` 指定命名空间，不影响目录结构）。文件名与类名严格对应，AI 不得手动创建 `controllers/` 外的控制器文件，否则 `drogon_ctl` 无法发现。

### C.2 控制器类型指定
`create controller` 支持选项（源码：`drogon_ctl/create.cc:30-38`）：
- `-s` 或 `--simple`：生成 `HttpSimpleController` 子类（单一 path，单一 handler）
- `-h`、`-a` 或 `--http`：生成 `HttpController` 子类（HTTP 方法控制器，需手动用 `METHOD_ADD` 注册方法）
- `-w` 或 `--websocket`：生成 `WebSocketController` 子类（WebSocket 连接）
- `-r` 或 `--restful`：生成 `HttpController` 子类（RESTful 风格，支持资源映射，含 `--resource=<resource>` 选项指定资源名）

AI 不得假设生成的控制器类型，必须根据命令参数判断。

### C.3 model 生成
`drogon_ctl create model` 需要指定：
- 数据库类型：`--pg`（PostgreSQL）、`--mysql`（MySQL）、`--sqlite3`（SQLite3）
- 表名：`-t <表名>`
- 命名空间：`--namespace <命名空间>`（可选）

生成的 model 类放在 `models/` 子目录下，包含 `Mapper<T>` 和 `CoroMapper<T>` 的 CRUD 方法。AI 不得在非 ORM 配置下建议使用 `create model`（Phase 3 将详细规范 ORM 使用）。

### C.4 view 生成
`drogon_ctl create view` 生成的是 CSP（C++ Server Pages）视图模板文件（`.csp`），放置在 `views/` 子目录下。AI 不得混淆"controller 的视图方法"（controller 返回 `HttpResponse::newFileResponse()` 渲染模板）和"CSP 视图模板"（模板文件本身）。

### C.5 plugin/filter/middleware 区分
- `create plugin`：生成 `Plugin` 子类，用于系统级扩展（如监控、日志记录），在配置文件的 `plugins` 数组中声明。
- `create filter`：生成 `HttpFilter` 子类，用于请求/响应拦截（如鉴权、限流），通过 `app().registerFilter(...)` 注册（注意：`FILTER_ADD` 宏不存在，详见 K.2）。
- `create middleware`：生成 `HttpMiddleware` 子类，用于全局请求处理链（如日志、CORS），通过 `app().registerMiddleware(...)` 注册（注意：`ADD_MIDDLEWARE` 宏不存在，详见 K.3）。

三者用途不同，AI 不得混用。详细规范见 K 组规则。

## D. 控制器注册与路由

### D.1 类型选择
| 需求 | 控制器类型 | 说明 |
|------|------------|------|
| 单一 path 单一 handler | `HttpSimpleController` | 用 `PATH_ADD` 注册 path，实现 `asyncHandleHttpRequest()` |
| RESTful API（多个 HTTP 方法 + 路径参数） | `HttpController` | 用 `METHOD_ADD` 注册方法（`Get`、`Post`、`Put`、`Delete` 等） |
| WebSocket 连接 | `WebSocketController` | 用 `WS_PATH_ADD` 注册连接消息 |

AI 不得在 RESTful API 里使用 `HttpSimpleController`（无法区分 HTTP 方法），也不得在单一 path 的 handler 里使用 `HttpController`（过度设计）。

### D.2 宏的使用
- `HttpSimpleController`：用 `PATH_LIST_BEGIN` / `PATH_ADD(path)` / `PATH_LIST_END` 注册 path，实现 `asyncHandleHttpRequest()`。**注意**：`HttpSimpleController` **不会自动添加类名前缀**到路径（如 `PATH_ADD("/view")` 注册的路径就是 `/view`，而非 `/HelloViewController/view`），这与 `HttpController` 不同。
- `HttpController`：用 `METHOD_LIST_BEGIN` / `METHOD_ADD(方法, path)` / `METHOD_LIST_END` 注册 HTTP 方法（如 `METHOD_ADD(Get::create, "/users/:id")`），实现对应方法（`void yourGet(...)`）。**注意**：`HttpController` **会自动添加类名前缀**到路径（如 `METHOD_ADD(Get::create, "/")` 注册的路径实际是 `/SayHello/`）。
- `WebSocketController`：用 `WS_PATH_LIST_BEGIN` / `WS_PATH_ADD(path, ...)` / `WS_PATH_LIST_END` 注册 WebSocket 连接，实现 `handleNewMessage()`、`handleNewConnection()`、`handleConnectionClosed()` 等方法（源码：`lib/inc/drogon/WebSocketController.h:27-33`）。**高级用法**：`WS_ADD_PATH_VIA_REGEX(regExp, ...)` 支持正则表达式匹配路径（源码：同上，第 31-32 行）。

**代码示例**：

```cpp
// HttpSimpleController 示例（不自动添加类名前缀）
class MySimpleCtrl : public HttpSimpleController<MySimpleCtrl> {
  public:
    PATH_LIST_BEGIN
    PATH_ADD("/view");  // 路径就是 "/view"，不是 "/MySimpleCtrl/view"
    PATH_LIST_END

    void asyncHandleHttpRequest(const HttpRequestPtr &req,
                                std::function<void(const HttpResponsePtr &)> &&callback) override {
        auto resp = HttpResponse::newHttpResponse();
        resp->setBody("Simple controller");
        callback(resp);
    }
};
```

```cpp
// HttpController 示例（自动添加类名前缀）
class MyHttpCtrl : public HttpController<MyHttpCtrl> {
  public:
    METHOD_LIST_BEGIN
    METHOD_ADD(MyHttpCtrl::getUsers, "/users", Get);      // 实际路径: /MyHttpCtrl/users
    METHOD_ADD(MyHttpCtrl::getUser, "/users/:id", Get);   // 实际路径: /MyHttpCtrl/users/:id
    METHOD_ADD(MyHttpCtrl::createUser, "/users", Post);
    METHOD_LIST_END

    void getUsers(const HttpRequestPtr &req,
                  std::function<void(const HttpResponsePtr &)> &&callback);
    void getUser(const HttpRequestPtr &req,
                 std::function<void(const HttpResponsePtr &)> &&callback);
    void createUser(const HttpRequestPtr &req,
                    std::function<void(const HttpResponsePtr &)> &&callback);
};
```

```cpp
// WebSocketController 示例
class MyWsCtrl : public WebSocketController<MyWsCtrl> {
  public:
    WS_PATH_LIST_BEGIN
    WS_PATH_ADD("/ws");  // WebSocket 连接路径
    WS_PATH_LIST_END

    void handleNewMessage(const WebSocketConnectionPtr &wsConnPtr,
                          std::string &&message,
                          const WebSocketMessageType &type) override;
    void handleNewConnection(const HttpRequestPtr &req,
                             const WebSocketConnectionPtr &wsConnPtr) override;
    void handleConnectionClosed(const WebSocketConnectionPtr &wsConnPtr) override;
};
```

### D.3 路径参数
`PATH_ADD` 或 `METHOD_ADD` 中的路径支持 `:param` 语法（如 `/users/:id`），AI 不得使用 `{id}` 或 `{param}` 模板引擎语法（drogon 不支持），也不得省略 `:` 前缀（参数无法捕获）。

参数捕获方法：在 handler 中用 `req->getParameter("param")` 获取参数值（返回 `std::string`）。AI 不得尝试用 `req->path()` 手动解析路径参数（`getParameter` 已封装此逻辑）。

### D.4 自动注册
所有控制器通过静态初始化的宏自动注册（宏内部调用 `DrClassMap::getSingleInstance<Ctrl>()->registerPathAdvice()`）。AI 不得在 `main()` 里手动注册控制器，也不得手动调用 `DrClassMap` 的方法（违反框架约定）。

### D.5 生命周期
控制器是单例（`DrObject` + `DrClassMap`），框架在启动时创建实例，在关闭时销毁。AI 不得在 handler 里 `new Ctrl()` 或手动管理控制器生命周期，也不得在控制器构造函数里做阻塞操作（会阻塞框架启动）。

## E. 配置文件规范

### E.1 配置文件位置与错误处理
`app().loadConfigFile("config.json")` 的路径解析规则：
1. 相对路径：相对于当前工作目录（CWD）解析
2. 绝对路径：直接使用
3. 路径分隔符：drogon 内部使用 `drogon::utils::toNativePath()` 自动转换为平台原生格式（Windows 用 `\`，Unix 用 `/`）

错误处理（源码：`lib/src/ConfigLoader.cc`）：
- 文件不存在：抛出 `std::runtime_error("Config file ... not found!")`
- 无读取权限：抛出 `std::runtime_error("No permission to read config file ...")`
- 解析失败：抛出 `std::runtime_error("Error reading config file ...: ...")`

AI 不得假设配置文件一定能加载成功，必须在 `app().loadConfigFile()` 外层加 try/catch。

### E.2 JSON vs YAML
`app().loadConfigFile()` 通过文件扩展名自动判断格式（`.json` 或 `.yaml`/`.yml`）。AI 不得在 YAML 文件中使用 JSON 语法（如双引号包裹键），也不得在 JSON 文件中使用 YAML 语法（如无引号的键、注释）。

### E.3 多环境配置
推荐通过环境变量覆盖配置项（`app().loadConfigFile()` 之前设置 `setenv()`），或使用多个配置文件（`config.dev.json`、`config.prod.json`）并在 `main()` 中选择。AI 不得建议手动修改配置文件（版本控制风险），也不得硬编码环境特定配置（如 IP、端口）。

### E.4 配置项语义
常见配置项（以 JSON 为例）：

```json
{
  "listeners": [
    {
      "address": "0.0.0.0",
      "port": 8080,
      "https": false
    }
  ],
  "app": {
    "number_of_threads": 0,
    "enable_session": true,
    "session_timeout": 1200,
    "log": {
      "log_path": "./logs",
      "logfile_size": 104857600,
      "log_level": "DEBUG"
    }
  }
}
```

AI 不得使用错误键名（如 `threads`、`num_threads`、`enable_sessions`），也不得省略必需键（如 `listeners`、`app`）。

## F. CMake 构建集成

### F.1 依赖发现
使用 `find_package(drogon REQUIRED)`，然后 `target_link_libraries(your_app PRIVATE drogon::drogon)`。AI 不得手动 `include_directories()`（drogon 的头文件路径通过 `drogon::drogon` 的 INTERFACE_INCLUDE_DIRECTORIES 自动传递），也不得链接 `libdrogon.a`（硬编码路径不可移植）。

### F.2 ORM 集成
若使用 ORM，需显式链接 `drogon::orm_lib`（`target_link_libraries(your_app PRIVATE drogon::drogon drogon::orm_lib)`）。AI 不得假设 `drogon::drogon` 已包含 ORM（drogon 可能编译时禁用 ORM），也不得链接 `libdrogon_orm.a`（硬编码路径不可移植）。

### F.3 特性检查
若 drogon 是通过 Conan 安装的，需使用 `conan_basic_setup()` 生成的 `drogon_CONAN_TARGETS`；若手动编译 drogon，需检查 `BUILD_ORM` 等选项的值。AI 不得硬编码 drogon 的安装路径（如 `/usr/local/include/drogon`），也不得假设 drogon 总是以特定方式安装（用户可能手动编译或使用包管理器）。

### F.4 插件/过滤器编译
用户写的 `HttpPlugin` 或 `HttpFilter` 需链接 `drogon::drogon`，并确保头文件路径正确（`#include <drogon/HttpController.h>`）。AI 不得遗漏 `drogon::drogon` 依赖（链接错误），也不得错误使用 `target_include_directories()`（drogon 的头文件已通过 `drogon::drogon` 传递）。

## G. ORM 异步使用规范

### G.1 优先使用异步 ORM
在 handler 中必须使用 `Mapper<T>` 或 `CoroMapper<T>` 的异步方法，不得使用同步方法（如 `client->execSqlSync()`）。同步方法会阻塞事件循环线程，拖死同一个循环上的所有其他连接（违反 B.1）。

**正确**：
```cpp
auto client = app().getDbClient();
client->execSqlAsync(
    "SELECT * FROM users WHERE id=$1",
    [](const orm::Result &r) { /* 成功回调 */ },
    [](const orm::DrogonDbException &e) { /* 失败回调 */ },
    id);
```

**错误**：
```cpp
auto client = app().getDbClient();
auto result = client->execSqlSync("SELECT * FROM users WHERE id=$1", id);  // 阻塞事件循环
```

### G.2 异步回调完整性
`execSqlAsync` 需要两个回调（成功和失败），AI 不得忘记失败回调或错误处理。失败回调必须调用 `callback(错误响应)`，确保响应被发送（遵守 A.1）。

**正确**：
```cpp
client->execSqlAsync(
    "SELECT * FROM users WHERE id=$1",
    [callback](const orm::Result &r) {
        auto resp = HttpResponse::newHttpResponse();
        resp->setBody("success");
        callback(resp);  // 成功路径回调
    },
    [callback](const orm::DrogonDbException &e) {
        LOG_ERROR << "DB error: " << e.base().what();
        auto resp = HttpResponse::newHttpResponse();
        resp->setStatusCode(k500InternalServerError);
        resp->setBody("DB error");
        callback(resp);  // 失败路径回调
    },
    id);
```

**错误**：
```cpp
client->execSqlAsync(
    "SELECT * FROM users WHERE id=$1",
    [callback](const orm::Result &r) {
        auto resp = HttpResponse::newHttpResponse();
        resp->setBody("success");
        callback(resp);
    },
    // 忘记失败回调！数据库错误时永远不会调用 callback
    id);
```

### G.3 协程优先
若编译时启用了协程（`USE_COROUTINE` 宏），优先使用 `CoroMapper<T>` 的协程方法（`co_await`），而非回调式异步。协程更简洁、易读、不易出错。

**正确（协程）**：
```cpp
drogon::Task<HttpResponsePtr> Ctrl::getUser(int id) {
    try {
        auto client = app().getDbClient();
        CoroMapper<Users> mapper(client);  // 需显式构造（源码：`orm_lib/inc/drogon/orm/Mapper.h:124`）
        auto user = co_await mapper.findByPrimaryKey(id);
        auto resp = HttpResponse::newHttpResponse();
        resp->setBody(user.getValueOfName());
        co_return resp;  // 协程自动处理回调
    } catch (const orm::DrogonDbException &e) {
        LOG_ERROR << "DB error: " << e.base().what();
        co_return HttpResponse::newHttpResponse();  // 返回空响应
    }
}
```

**可接受（回调式，若无协程支持）**：
```cpp
void Ctrl::getUser(int id,
                  std::function<void(const HttpResponsePtr &)> &&callback) {
    auto client = app().getDbClient();
    Mapper<Users> mapper(client);
    mapper.findByPrimaryKey(
        id,
        [callback](const Users &user) {
            auto resp = HttpResponse::newHttpResponse();
            resp->setBody(user.getValueOfName());
            callback(resp);
        },
        [callback](const orm::DrogonDbException &e) {
            LOG_ERROR << "DB error: " << e.base().what();
            auto resp = HttpResponse::newHttpResponse();
            resp->setStatusCode(k500InternalServerError);
            resp->setBody("DB error");
            callback(resp);
        });
}
```

### G.4 事务必须回滚
使用 `client->newTransaction()` 创建事务对象（源码：`orm_lib/inc/drogon/orm/DbClient.h:283-287`），事务对象析构时会自动提交（源码：`orm_lib/src/TransactionImpl.cc:41-79`）。AI 不得手动调用 `commit()` 方法（`Transaction::commit()` 被注释掉，见 `orm_lib/inc/drogon/orm/DbClient.h:423`）。

**正确（自动提交）**：
```cpp
auto client = app().getDbClient();
try {
    auto trans = client->newTransaction();
    trans->execSqlSync("INSERT INTO users (...) VALUES (...)");
    // 析构时自动提交（如果未回滚）
    callback(success_resp);
} catch (const orm::DrogonDbException &e) {
    // 异常时 Transaction 对象被销毁，不会自动提交
    LOG_ERROR << "Transaction error: " << e.base().what();
    callback(error_resp);
}
```

**正确（手动回滚）**：
```cpp
auto client = app().getDbClient();
try {
    auto trans = client->newTransaction();
    trans->execSqlSync("INSERT INTO users (...) VALUES (...)");
    
    if (some_error_condition) {
        trans->rollback();  // 手动回滚（源码：`orm_lib/inc/drogon/orm/DbClient.h:422`）
        // Transaction 对象仍会析构，但不会自动提交
        callback(error_resp);
        return;
    }
    
    // 析构时自动提交
    callback(success_resp);
} catch (const orm::DrogonDbException &e) {
    // 异常时 Transaction 对象被销毁，不会自动提交
    LOG_ERROR << "Transaction error: " << e.base().what();
    callback(error_resp);
}
```

**错误**：
```cpp
auto client = app().getDbClient();
client->beginTransaction();
// 执行多个数据库操作
client->commitTransaction();
// 忘记 catch 异常，数据库操作失败时不会回滚
```

### G.5 批量操作走线程池
大量插入/更新时（如 100+ 条记录），不得在事件循环线程中循环调用异步操作。应将批量操作丢到线程池，完成后用 `runInLoop` 派发回调。

**简化示例**：
```cpp
// 在独立线程中执行批量同步操作
std::thread([callback, items]() {
    try {
        auto client = app().getDbClient();
        auto trans = client->newTransaction();
        for (const auto &item : items) {
            trans->execSqlSync("INSERT INTO table (...) VALUES (...)", ...);
        }
        // 析构时自动提交
        
        // 用 runInLoop 派发回事件循环线程
        trantor::EventLoop::getEventLoopOfCurrentThread()->queueInLoop([callback]() {
            auto resp = HttpResponse::newHttpResponse();
            resp->setBody("batch insert success");
            callback(resp);
        });
    } catch (const orm::DrogonDbException &e) {
        // 异常自动回滚
        trantor::EventLoop::getEventLoopOfCurrentThread()->queueInLoop([callback]() {
            auto resp = HttpResponse::newHttpResponse();
            resp->setStatusCode(k500InternalServerError);
            resp->setBody("batch insert error");
            callback(resp);
        });
    }
}).detach();
// 提示：生产环境应使用更健壮的线程池库，确保线程池在应用退出时清理
```

**错误**：
```cpp
// 在事件循环线程中循环执行异步操作（阻塞事件循环）
for (const auto &item : items) {
    client->execSqlAsync(
        "INSERT INTO table (...) VALUES (...)",
        [](const orm::Result &r) { /* 成功回调 */ },
        [](const orm::DrogonDbException &e) { /* 失败回调 */ },
        ...);
}
```

## H. DB 连接与错误处理

### H.1 DB 连接配置格式
`config.json` 中的 `db_clients` 数组格式如下（源码：`lib/src/ConfigLoader.cc`）：

```json
{
  "db_clients": [
    {
      "name": "default",
      "rdbms": "postgresql",
      "host": "localhost",
      "port": 5432,
      "dbname": "mydb",
      "user": "postgres",
      "passwd": "password",
      "is_fast": false,
      "connection_number": 10
    }
  ]
}
```

AI 不得使用错误的键名（如 `db_name`、`username`、`password`）或值（如 `port` 为字符串）。键名和值必须与上述格式严格一致。

### H.2 SQLite 配置
SQLite 的 `db_clients` 配置不同，需使用 `filename` 而非 `host`/`port`：

```json
{
  "db_clients": [
    {
      "name": "default",
      "rdbms": "sqlite3",
      "filename": "./mydb.db",
      "is_fast": false,
      "connection_number": 1
    }
  ]
}
```

AI 不得在 SQLite 配置中使用 `host`/`port`，否则连接失败。SQLite 只支持单连接（`connection_number` 必须为 1），此字段虽然对所有数据库类型通用（源码：`lib/src/ConfigLoader.cc:557-560`），但 SQLite 下必须为 1。

### H.3 连接失败处理
`app().loadConfigFile()` 时若数据库连接失败，会抛出 `std::runtime_error`（源码：`lib/src/ConfigLoader.cc:113、117、124、139、301 行）。AI 必须在 `loadConfigFile()` 外层加 try/catch，捕获异常并退出程序或回退到无数据库模式。AI 不得忽略连接失败。

**正确**：
```cpp
int main() {
    try {
        app().loadConfigFile("./config.json");
    } catch (const std::runtime_error &e) {
        LOG_FATAL << "Failed to load config: " << e.what();
        return 1;
    }
    
    app().run();
    return 0;
}
```

**错误**：
```cpp
int main() {
    app().loadConfigFile("./config.json");  // 数据库连接失败时抛出异常，程序崩溃
    app().run();
    return 0;
}
```

### H.4 运行时连接错误
数据库运行时错误（如唯一键冲突）会抛出 `DrogonDbException`。AI 不得忽略异常，应在 catch 路径中调用 `callback(错误响应)` 并记录日志。

**正确**：
```cpp
try {
    auto mapper = app().getDbClient()->getMapper<Users>();
    mapper.insert(user,
        [](const size_t id) {
            auto resp = HttpResponse::newHttpResponse();
            resp->setBody("insert success");
            callback(resp);
        },
        [](const orm::DrogonDbException &e) {
            LOG_ERROR << "Insert error: " << e.base().what();
            auto resp = HttpResponse::newHttpResponse();
            resp->setStatusCode(k500InternalServerError);
            resp->setBody("insert error");
            callback(resp);
        });
} catch (...) {
    callback(HttpResponse::newHttpResponse());  // 捕获所有异常
}
```

**错误**：
```cpp
mapper.insert(user,
    [](const size_t id) {
        auto resp = HttpResponse::newHttpResponse();
        resp->setBody("insert success");
        callback(resp);
    });
// 忘记失败回调，插入失败时永远不会调用 callback
```

### H.5 SQL 注入防护
`Mapper<T>` 的方法（如 `findBy`、`findByCriteria`）会自动参数化查询，AI 不得手动拼接 SQL 字符串。若必须手动拼接 SQL，使用参数占位符（`$1`、`$2`）而非字符串拼接。

**正确**：
```cpp
// 使用参数占位符（自动防注入）
client->execSqlAsync(
    "SELECT * FROM users WHERE id=$1",
    [](const orm::Result &r) { /* 成功回调 */ },
    [](const orm::DrogonDbException &e) { /* 失败回调 */ },
    user_id);

// 使用 Mapper<T>（自动防注入）
auto mapper = app().getDbClient()->getMapper<Users>();
mapper.findByCriteria(
    Criteria(Users::Cols::_name, CompareOperator::EQ, user_name),
    [](const std::vector<Users> &users) { /* 成功回调 */ },
    [](const orm::DrogonDbException &e) { /* 失败回调 */ });
```

**错误**：
```cpp
// 手动拼接 SQL（SQL 注入风险）
std::string sql = "SELECT * FROM users WHERE id=" + user_id;
client->execSqlAsync(
    sql,
    [](const orm::Result &r) { /* 成功回调 */ },
    [](const orm::DrogonDbException &e) { /* 失败回调 */ });
```

## I. Redis 客户端使用规范

### I.1 单例 Redis 客户端
通过 `app().getRedisClient()` 获取 Redis 客户端，AI 不得手动创建 `RedisClient` 实例。框架在启动时创建单个客户端，手动创建浪费资源。

**正确**：
```cpp
auto redis = app().getRedisClient();
```

**错误**：
```cpp
auto redis = std::make_shared<RedisClient>(...);  // 手动创建，浪费资源
```

### I.2 Redis 操作是异步的
`RedisClient` 的所有操作（`set`、`get`、`lpush` 等）都是异步的，通过回调返回结果。AI 不得假设操作同步完成，必须在回调中处理结果。

**正确（异步回调）**：
```cpp
auto redis = app().getRedisClient();
redis->execCommandAsync(
    [](const drogon::nosql::RedisResult &r) {
        auto value = r.asString();
        auto resp = HttpResponse::newHttpResponse();
        resp->setBody(value);
        callback(resp);
    },
    [](const drogon::nosql::RedisException &e) {
        LOG_ERROR << "Redis error: " << e.what();
        auto resp = HttpResponse::newHttpResponse();
        resp->setStatusCode(k500InternalServerError);
        resp->setBody("Redis error");
        callback(resp);
    },
    "GET",
    "mykey");
```

**错误**：
```cpp
auto redis = app().getRedisClient();
redis->execCommand<int>("GET", "mykey");  // 忘记回调，无法获取结果
```

### I.3 Redis 错误处理
Redis 操作失败时，回调中的 `RedisException` 参数非空。AI 不得忽略异常，应在 catch 路径中处理错误或记录日志。

**正确**：
```cpp
redis->execCommandAsync(
    [](const drogon::nosql::RedisResult &r) {
        auto value = r.asString();
        auto resp = HttpResponse::newHttpResponse();
        resp->setBody(value);
        callback(resp);
    },
    [](const drogon::nosql::RedisException &e) {
        LOG_ERROR << "Redis error: " << e.what();
        auto resp = HttpResponse::newHttpResponse();
        resp->setStatusCode(k500InternalServerError);
        resp->setBody("Redis error");
        callback(resp);
    },
    "GET",
    "mykey");
```

**错误**：
```cpp
redis->execCommandAsync(
    [](const drogon::nosql::RedisResult &r) {
        auto value = r.asString();
        auto resp = HttpResponse::newHttpResponse();
        resp->setBody(value);
        callback(resp);
    },
    // 忘记错误处理，Redis 失败时永远不会调用 callback
    "GET",
    "mykey");
```

### I.4 Redis 订阅/发布
`RedisSubscriber` 的 `subscribe()` 方法用于订阅频道，`unsubscribe()` 用于取消订阅。AI 不得忘记取消订阅，否则资源泄漏（源码：`RedisSubscriber.h:26-28` 说明"until unsubscribe() is called ... or the subscriber or RedisClient who creates it no longer exists"）。

**正确（手动取消订阅）**：
```cpp
class MySubscriber : public RedisSubscriber {
  public:
    void subscribe(const std::string &channel) {
        auto redis = app().getRedisClient();
        channel_ = channel;
        redis->subscribe(channel,
            [this](const std::string &channel,
                   const std::string &message) {
                LOG_INFO << "Received message on " << channel << ": " << message;
            });
    }
    
    void unsubscribe() {
        if (!channel_.empty()) {
            auto redis = app().getRedisClient();
            redis->unsubscribe(channel_);
            channel_.clear();
        }
    }
    
    ~MySubscriber() override {
        unsubscribe();  // 析构时取消订阅
    }
    
  private:
    std::string channel_;
};
```

**错误**：
```cpp
// 忘记取消订阅，资源泄漏
void subscribe(const std::string &channel) {
    auto redis = app().getRedisClient();
    redis->subscribe(channel,
        [](const std::string &channel,
               const std::string &message) {
            LOG_INFO << "Received message on " << channel << ": " << message;
        });
}
```

### I.5 Redis 连接配置
`config.json` 中的 `redis_clients` 数组格式如下（源码：`lib/src/ConfigLoader.cc:606-638`）：

```json
{
  "redis_clients": [
    {
      "name": "default",
      "host": "127.0.0.1",
      "port": 6379,
      "username": "",
      "passwd": "",
      "db": 0,
      "is_fast": false,
      "connection_number": 1,
      "timeout": -1.0
    }
  ]
}
```

AI 不得使用错误的键名（如 `password`、`database`）或值（如 `port` 为字符串）。键名和值必须与上述格式严格一致。`username` 字段为 Redis 6.0+ ACL 支持，早期版本可留空。

## J. CSP 视图模板语法

### J.1 `drogon_ctl create view` 的输入输出
`drogon_ctl create view` 接受一个**已存在的手写 `.csp` 文件**作为输入，生成 2 个输出文件：`<类名>.h` 和 `<类名>.cc`。

**正确**（2 个输出文件）：
```bash
# 输入：手写的 HelloView.csp
drogon_ctl create view HelloView.csp
# 输出：HelloView.h  +  HelloView.cc  （2 个文件）
```

**错误**：
```bash
drogon_ctl create view <name>  # 不会自动生成 .csp 文件
```

`.csp` 文件是**输入**，由用户手写（或由 `drogon-gen-csp-view` 技能生成），不是 `drogon_ctl` 的输出产物。AI 不得暗示 `create view` 会生成 `.csp` 文件。

- `.csp` 文件无固定位置要求，示例中与 controller 同目录（如 `examples/helloworld/HelloView.csp`）
- 输出文件可通过 `-o` 指定输出目录，通过 `-n` 指定命名空间
- 证据：`drogon_ctl/create_view.cc:342-369`

### J.2 四大模板语法

在 `.csp` 文件中，有四种核心语法元素：

| 序号 | 语法 | 位置 | 含义 |
|------|------|------|------|
| 1 | `<%c++ ... %>` | 任何位置 | 嵌入 C++ 代码块 |
| 2 | `@@` | **只在** `<%c++ %>` 块内 | 引用整个 `HttpViewData` 对象 |
| 3 | `$$` | **只在** `<%c++ %>` 块内 | 输出流（`drogon::OStringStream`） |
| 4 | `[[ key ]]` | **在** `<%c++ %>` 块**外** | 内联输出 `viewData["key"]` 的值 |
| 5 | `{% key %}` | 任何位置 | 等价于 `<%c++ $$ << key; %>`，解析阶段直接替换 |

**`@@` 的两种用法**：

```html
<!-- 方式 1：取值 -->
<%c++
    auto name = @@.get<std::string>("name");
    if (name.empty())
        name = "anonymous";
%>
```

```html
<!-- 方式 2：下标访问 -->
<%c++
    auto &val = @@["name"];  // 返回 std::any&
%>
```

**`$$` 输出**：

```html
<%c++ $$ << "Hello, " << name; %>
```

**`[[ ]]` 内联输出**：

```html
<title>[[ name ]]</title>
<!-- 等价于 <%c++ $$ << name; %> -->
```

- ❌ `@@key@@` 包裹语法不存在，`@@` 是独立 token
- ❌ `{{ key }}` 模板引擎语法不存在（如 Jinja2 / Mustache）
- ❌ `{% if %}...{% endif %}` 块级控制流语法不存在（`{% key %}` 单值插值有效，但 `{% %}` 块语法无效）
- ✅ C++ 逻辑在 `<%c++ %>` 块内**完全允许**，这是 CSP 的核心设计
- 证据：`drogon_ctl/create_view.cc:24-32`

### J.3 控制器渲染视图

```cpp
HttpViewData data;
data["name"] = req->getParameter("name");
auto resp = HttpResponse::newHttpViewResponse("HelloView", data);
callback(resp);
```

- `viewName` **不带 `.csp` 后缀**（框架内部自动补全）
- 参数类型：`const HttpViewData &`（第二个参数，默认 `HttpViewData()`）
- 第三个可选参数：`req`，默认 `HttpRequestPtr()`
- 证据：`HttpResponse.h:429-432`，`examples/helloworld/HelloViewController.cc:24-26`

### J.4 HttpViewData API

```cpp
// 插入数据
data.insert("key", std::any(value));
data.insertAsString<int>("key", 42);     // 自动转字符串
data["key"] = value;                      // operator[]

// 模板中取值（在 <%c++ %> 内）
@@.get<std::string>("key")                // 类型安全取值
@@.get<int>("key")
@@["key"]                                 // 返回 std::any&

// HTML 转义（静态方法，需手动调用）
HttpViewData::htmlTranslate(userInput)    // 非自动！
```

- 键名**大小写敏感**（底层 `std::unordered_map<std::string, std::any>`，`HttpViewData.h:171`）
- 证据：`HttpViewData.h:35-54, 57-65, 69-75, 130-133, 145-150`

### J.5 禁止在 handler 中手工拼接 HTML 页面

handler 中不得手动构造完整 HTML 页面字符串（`std::string html = "<!DOCTYPE html><html>..."` 然后 `resp->setBody(html)`）。走 CSP 视图或 JSON 响应。`.csp` 文件内 `<%c++ %>` 块中用 `$$ << "<tag>"` 输出 HTML 片段是正常的 CSP 用法，不受此限制。

### J.6 布局与子视图

| 语法 | 用途 | 示例 |
|------|------|------|
| `<%layout name %>` | 指定父布局模板（无后缀、无引号） | `<%layout main %>` |
| `<%view name %>` | 嵌入子视图 | `<%view sidebar %>` |
| `<%inc ... %>` | 在生成的 C++ 源文件中插入代码（如 `#include`） | `<%inc #include "utils.h" %>` |

**layout 机制**：

```
子视图.csp:
  <%layout main %>         ← 声明使用 main 布局
  <h1>[[ title ]]</h1>
  <p>[[ content ]]</p>

父布局.csp:
  <html>
  <body>
    <div class="header">...</div>
    [[ ]]                  ← 空字符串 key = 子视图内容
    <div class="footer">...</div>
  </body>
  </html>
```

子视图内容存入 `data[""]`（空字符串键——`std::unordered_map::operator[]` 在 key 不存在时自动插入空的 `std::any`，这在布局机制下是预期行为，源码见 `create_view.cc:551`: `data[""] = std::move(str)`）。父布局通过 `[[ ]]` 获取子视图内容——**必须是 `[[ ]]`**（括号间恰有一个空格），CSP 解析器 trim 两端空格后得到空字符串 key（`create_view.cc:160-163`）。`[[##]]`、`[[content]]` 等写法查找的是不存在的 key，子视图内容永远渲染不出来。

> **⚠️ `[[ ]]` 只能在父布局中使用**。它查找的是布局引擎注入的 `data[""]`（子视图渲染内容）。在子模板或普通 `.csp` 文件中使用 `[[ ]]` 查找的是用户的 `HttpViewData[""]`，通常为空——请用 `[[ keyName ]]` 传入具体变量名。

- ❌ `<%viewpath layout="header.csp"%>` 不存在
- ❌ `<%extends "layout.csp"%>` 不存在
- 证据：`drogon_ctl/create_view.cc:24-32, 429, 542-553`

### J.7 无自动 HTML 转义

CSP **不会**自动对输出进行 HTML 转义。`HtmlViewData::htmlTranslate()` 是静态辅助函数，必须在 C++ 代码中**手动调用**。

**正确（手动转义）**：
```html
<%c++
    auto safeText = HttpViewData::htmlTranslate(userInput);
    $$ << safeText;
%>
```

**错误（假设自动转义）**：
```html
[[ userInput ]]  <!-- 不会自动转义，XSS 风险 -->
```

- ❌ `<%raw%>...<%/raw%>` 标签**不存在**
- 证据：`drogon_ctl/create_view.cc:71-89`（`outputVal()` 直接流输出，无 `htmlTranslate` 调用），`HttpViewData.h:145-150`

## K. Plugin / Filter / Middleware 机制

### K.1 Plugin

```cpp
class MyPlugin : public drogon::Plugin<MyPlugin> {
  public:
    void initAndStart(const Json::Value &config) override { /* 第三方库初始化 */ }
    void shutdown() override { /* 资源清理 */ }
};
```

- 框架托管，每类型单实例（`DrClassMap` + `PluginsManager` 管理）
- 在配置文件中声明的 `plugins` 数组中列出
- `initAndStart()` 在 `app().run()` **之前**被同步调用，禁止阻塞（与 B.1 一致），耗时初始化走 `std::async`
- 证据：`plugins/Plugin.h:67-71`

### K.2 Filter（请求级拦截）

❌ `FILTER_ADD` 宏**不存在**

✅ 注册方式：
```cpp
app().registerFilter(std::make_shared<AuthFilter>());
```

Filter API：
```cpp
class AuthFilter : public HttpFilter<AuthFilter, false> {
  public:
    void doFilter(const HttpRequestPtr &req,
                  FilterCallback &&fcb,          // 拦截路径
                  FilterChainCallback &&fccb)    // 放行路径
    override;
};
```

- `FilterCallback` = `std::function<void(const HttpResponsePtr &)>` ——调用此回调直接向客户端发送响应，跳过 handler
- `FilterChainCallback` = `std::function<void()>` ——无参数，调用即继续链
- **`AutoCreation = false`** ——第二个模板参数**必须为 `false`**，否则 `registerFilter()` 中的 `static_assert(!T::isAutoCreation)` 会导致编译失败（`HttpAppFramework.h:696-699`）

**正确（认证失败）**：
```cpp
void doFilter(const HttpRequestPtr &req,
              FilterCallback &&fcb,
              FilterChainCallback &&fccb) override {
    if (!checkAuth(req)) {
        auto resp = HttpResponse::newHttpJsonResponse({"error": "unauthorized"});
        resp->setStatusCode(k401Unauthorized);
        fcb(resp);  // 拦截，直接返回 401
        return;
    }
    fccb();  // 放行
}
```

**错误**：
```cpp
void doFilter(...) override {
    if (!checkAuth(req))
        return;  // BUG: 既不 fcb 也不 fccb，响应永远不会发出
}
```

- 证据：`HttpFilter.h:49-51`，`drogon_callbacks.h:31-32`，`HttpAppFramework.h:692`

### K.3 Middleware（全局请求处理链）

❌ `ADD_MIDDLEWARE` 宏**不存在**

✅ 注册方式：
```cpp
app().registerMiddleware(std::make_shared<LogMiddleware>());
```

Middleware API：
```cpp
class LogMiddleware : public HttpMiddleware<LogMiddleware, false> {
  public:
    void invoke(const HttpRequestPtr &req,
                MiddlewareNextCallback &&nextCb,  // 只接受一个参数！
                MiddlewareCallback &&mcb)          // 最终响应回调
    override;
};
```

- `MiddlewareNextCallback` = `std::function<void(std::function<void(const HttpResponsePtr &)> &&)>` ——**一个参数**（下游响应回调）
- `MiddlewareCallback` = `std::function<void(const HttpResponsePtr &)>` ——最终响应回调
- **`AutoCreation = false`** ——第二个模板参数**必须为 `false`**，否则 `registerMiddleware()` 中的 `static_assert(!T::isAutoCreation)` 会导致编译失败（`HttpAppFramework.h:714-717`）

**正确（标准模式）**：
```cpp
void invoke(const HttpRequestPtr &req,
            MiddlewareNextCallback &&nextCb,
            MiddlewareCallback &&mcb) override {
    LOG_INFO << "Before: " << req->path();
    nextCb([mcb = std::move(mcb)](const HttpResponsePtr &resp) {
        resp->addHeader("X-Powered-By", "drogon");
        mcb(resp);  // 必须调用 mcb 传递响应
    });
}
```

**错误**：
```cpp
void invoke(...) override {
    nextCb(req, [mcb = std::move(mcb)](...) { ... });
    // BUG: nextCb 只接受一个参数，不是 nextCb(req, callback)
}
```

- 证据：`HttpMiddleware.h:55-60`，`drogon_callbacks.h:35-37`，`HttpAppFramework.h:709`

### K.4 三者职责边界

| 类型 | 用途 | 注册方式 | 生命周期 |
|------|------|---------|---------|
| Plugin | 系统级扩展（连接池、第三方 SDK） | 配置文件 `plugins` 数组 | 应用级 |
| Filter | 请求拦截（鉴权、限流、输入校验） | `app().registerFilter(...)` | 请求级 |
| Middleware | 全局处理链（日志、CORS、性能计时） | `app().registerMiddleware(...)` | 请求级 |

三者不得混用——Plugin 不处理请求，Filter 不做全局逻辑，Middleware 不初始化资源。

## L. DROGON_TEST 测试框架

### L.1 Test 宏

```cpp
DROGON_TEST(MyTest) {
    // test body
}
```

- 测试文件建议放在 `tests/` 目录（`ParseAndAddDrogonTests.cmake` 递归扫描所有子目录）
- 通过 `DrObject` 模板自动注册（与 controller 同机制）
- 证据：`drogon_test.h:720-732`

### L.2 断言宏

| 宏 | 行为 | 失败时 |
|----|------|--------|
| `CHECK(expr)` | 断言为真 | 记录失败，继续执行 |
| `CHECK_THROWS(expr)` | 期望抛出异常 | 记录失败，继续执行 |
| `CHECK_NOTHROW(expr)` | 期望不抛异常 | 记录失败，继续执行 |
| `CHECK_THROWS_AS(expr, type)` | 期望抛出特定类型 | 记录失败，继续执行 |
| `REQUIRE(expr)` | 断言为真 | **终止**当前测试 |
| `REQUIRE_THROWS(expr)` | 期望抛出异常 | **终止**当前测试 |
| `REQUIRE_NOTHROW(expr)` | 期望不抛异常 | **终止**当前测试 |
| `REQUIRE_THROWS_AS(expr, type)` | 期望抛出特定类型 | **终止**当前测试 |
| `MANDATE(expr)` | 断言为真 | **die**（abort） |
| `MANDATE_THROWS(expr)` | 期望抛出异常 | **die**（abort） |
| `MANDATE_NOTHROW(expr)` | 期望不抛异常 | **die**（abort） |
| `MANDATE_THROWS_AS(expr, type)` | 期望抛出特定类型 | **die**（abort） |
| `STATIC_REQUIRE(expr)` | 编译期断言 | 编译失败 |
| `FAIL(msg)` / `FAULT(msg)` | 无条件失败 | |
| `SUCCESS()` | 显式成功标记 | |
| `SUBSECTION(name)` | 嵌套子测试（Catch2 风格） | |
| `SUBTEST(name)` | 测试树层级 | |

- `CHECK_*` 系列用于非致命断言，`REQUIRE_*` 用于致命断言，`MANDATE_*` 用于不可恢复错误
- AI 不得使用不存在的 `ASSERT_*`（如 `ASSERT_EQ`）——drogon 不使用 Google Test 断言宏
- 证据：`drogon_test.h:622-734`

### L.3 异步测试模式

❌ 没有 `done()` 回调机制

异步测试的实际模式：在事件循环上调度测试逻辑，在回调中直接断言。

```cpp
DROGON_TEST(AsyncDbTest) {
    auto loop = app().getLoop();
    loop->queueInLoop([]() {
        auto client = app().getDbClient();
        client->execSqlAsync(
            "SELECT 1",
            [](const orm::Result &r) {
                CHECK(r.size() > 0);
            },
            [](const orm::DrogonDbException &e) {
                FAIL("DB query failed: " + e.base().what());
            });
    });
}
```

测试的 `main()` 通过 `drogon::test::run(argc, argv)` 启动事件循环。AI 不得在异步测试中等待 `done()`——这个机制在 drogon 中不存在。
- 证据：`drogon_test.h:355-358, 383`

### L.4 测试 main()

```cpp
int main(int argc, char *argv[]) {
    drogon::app().setLogLevel(trantor::Logger::kDebug);
    return drogon::test::run(argc, argv);
}
```

- `setLogLevel()` API 正确（`HttpAppFramework.h:1104`）
- `drogon::test::run()` 启动事件循环并执行所有注册测试（`drogon_test.h:383`）

### L.5 DB 配置（测试中）

**正确**（使用 `addDbClient()`）：
```cpp
int main(int argc, char *argv[]) {
    drogon::app().addDbClient(
        orm::Sqlite3Config{.filename = ":memory:"});
    return drogon::test::run(argc, argv);
}
```

**错误**：
```cpp
app().createDbClient(...);  // deprecated! 使用 addDbClient 代替
```

- 必须在 `app().run()` 之前调用
- 不得在 DROGON_TEST 内部创建 DbClient（框架已在 main 中配置）
- 证据：`HttpAppFramework.h:1495-1510`