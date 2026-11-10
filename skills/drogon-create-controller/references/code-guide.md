# drogon-create-controller Implementation

## 输入解析

从用户输入中提取：
- `controller_type`: 控制器类型（必需）
- `class_name`: 控制器类名（必需）
- `namespace`: 命名空间（可选，会拼进类名的 `::` 前缀，如 `myapp::MyCtrl`）
- `resource`: 资源名（可选，仅 restful 有效）

## 参数验证

1. `class_name` 不能为空
2. `controller_type` 必须是 `simple`、`http`、`restful`、`websocket` 之一
3. 若 `controller_type=restful` 且提供 `resource`，检查 `resource` 不为空

## 命令构建

```python
def build_command(controller_type, class_name, namespace=None, resource=None):
    """命名空间走类名里的 `::`（如 `myapp::MyCtrl`），drogon_ctl 没有 `--namespace` 选项。

    `create_controller::handleCommand`（v1.9.13 `drogon_ctl/create_controller.cc:28-59`）
    对任何以 `-` 开头、且不在 {-s,--simple, -a, -h, --http, -w,--websocket, -r,--restful} 里的
    token 直接回 `ARGS_ERROR_STR` 并 return——`--namespace myapp` 会让命令什么都不生成。
    """
    cmd = ["drogon_ctl", "create", "controller"]

    type_map = {
        "simple": "-s",
        "http": "-h",
        "restful": "-r",
        "websocket": "-w",
    }

    cmd.append(type_map[controller_type])

    if controller_type == "restful" and resource:
        cmd.append(f"--resource={resource}")

    # 命名空间前缀拼进类名本身：myapp::MyCtrl -> namespace myapp { class MyCtrl }
    full_name = f"{namespace}::{class_name}" if namespace else class_name
    cmd.append(full_name)

    return " ".join(cmd)
```

`-r`（restful）走另一条分支（`create_controller.cc:66-90`）：先解析 `--resource=`（:70-72），再检查剩余参数个数——`> 1` 就打 `Too many parameters` 并 `exit(1)`（:83-86）。⚠️ 判定用的是 `> 1` 而不是"恰好 1"，一个类名都不给时会在空 vector 上读 `parameters[0]`（:88），属上游未防护的越界；生成命令时**必须**始终带上类名。restful 分支同样把 `::` 换成 `_` 当文件名（`createARestfulController`，:405-407）。

## 命令执行

```bash
cd <项目根目录>
<生成的命令>
```

## 输出生成

1. 执行成功后，检查 `controllers/<类名>.h` 和 `controllers/<类名>.cc` 是否存在
2. 若文件不存在，说明命令执行失败，返回错误消息
3. 若文件存在，返回成功消息，包含文件路径和使用说明
4. **`drogon_ctl` 生成的 `PATH_ADD` 只有一行注释掉的示例**（`create_controller.cc:127-129`）：`// PATH_ADD("/path", "filter1", "filter2", HttpMethod1, HttpMethod2...)`。`PATH_ADD` 是变参宏 `PATH_ADD(path, ...)`（`lib/inc/drogon/HttpSimpleController.h:27`），其余参数全部是 `internal::HttpConstraint`——HTTP 方法、filter 名、中间件名，都是合法输入。**禁止**把"删掉第二个参数"当成修复动作：那会静默丢掉方法与约束。要检查的是：注释行是否被取消注释、路径是否为目标路径、约束是否与需求一致。
5. **`HttpSimpleController` 只有一个 handler**：基类只有 `asyncHandleHttpRequest(req, callback)` 这一个纯虚函数（`HttpSimpleController.h:46-48`），不存在带方法参数的重载。**禁止**写出 `asyncHandleHttpRequest(req, callback, Get)` 之类签名——要按方法分流请用 `HttpController` 的 `METHOD_ADD`。

## 宏速查

| 控制器类型 | 路径注册宏 | 宏形态 | handler 签名 |
|-----------|-----------|---------|-------------|
| `HttpSimpleController` | `PATH_ADD(path, ...)` | 变参（约束为 `HttpConstraint`） | `asyncHandleHttpRequest(req, callback)` |
| `HttpController` | `METHOD_ADD(method, pattern, ...)` | 3+（方法、路径、约束变参） | 每方法一个 handler |
| `HttpController` | `ADD_METHOD_TO(method, path_pattern, ...)` | 同上，但**不加类名前缀** | 每方法一个 handler |
| `WebSocketController` | `WS_PATH_ADD(path, ...)` | 变参 | `handleNewMessage` / `handleNewConnection` / `handleConnectionClosed` |

来源：`HttpSimpleController.h:27`、`HttpController.h:28-36`、`WebSocketController.h:27-33`。

AI 不得混淆——`HttpSimpleController` 不存在 `METHOD_ADD`；`HttpController` 不存在 `PATH_ADD`。三个宏的尾参都是 `{__VA_ARGS__}` 收进 `std::vector<internal::HttpConstraint>`，**都不是固定元数**。

## 类型选择规则

| 需求 | 控制器类型 |
|------|-----------|
| 单一 path、整页/视图式 handler | `HttpSimpleController` |
| RESTful API（多资源方法 + 路径参数） | `HttpController` |
| WebSocket 连接 | `WebSocketController` |
| 无需控制器类（v1.9.x 主推） | lambda 内联路由（用 `drogon-gen-lambda-handler`，不混用经典宏） |

- `HttpSimpleController` **不支持路径占位符**（见下节），需要路径参数就必须用 `HttpController` 或 lambda 内联路由。
- 经典宏写法与 lambda 写法二选一，**不混用**。

## 路径前缀行为（高频陷阱）

两种控制器的路径前缀行为**相反**，极易踩坑：

- **`HttpSimpleController` 不自动加类名前缀**：`PATH_ADD("/view")` 注册的路径就是 `/view`，不是 `/MyCtrl/view`。
- **`HttpController` 自动加类名前缀**：`METHOD_ADD(Get::create, "/")` 的实际路径是 `/SayHello/`（类名作为前缀）。

WebSocketController 宏（源码 `lib/inc/drogon/WebSocketController.h:27-33`）：
- `WS_PATH_LIST_BEGIN` / `WS_PATH_ADD(path, ...)` / `WS_PATH_LIST_END`
- 高级：`WS_ADD_PATH_VIA_REGEX(regExp, ...)` 支持正则匹配路径（同上 31-32 行）。
- 需实现 `handleNewMessage()`、`handleNewConnection()`、`handleConnectionClosed()`。

## 路径参数（经典控制器）

drogon **没有冒号语法**——`/users/:id` 在 v1.9.13 的路径解析里不被识别，冒号会被当成普通路径字符。真实占位符由 `HttpControllersRouter::addHttpPath` 用正则 `\{([^/]*)\}` 解析（`lib/src/HttpControllersRouter.cc:346`），形态有三种：

| 形态 | 例 | 语义 |
|------|----|------|
| `{}` | `/users/{}-{}` | 按出现顺序自动编号为第 1、2 个 handler 形参（`:416-433`） |
| `{N}` | `/users/{1}` | 显式绑定到第 N 个 handler 形参（N 从 1 起；`place > binder->paramCount()` 或 `place == 0` 或重复编号直接 `exit(1)`，`:374`/`:383`） |
| `{N:name}` | `/users/{1:id}` | 同 `{N}`；**名字不参与匹配**，只为源码可读（数字由 `regNumberAndName("([0-9]+):.*")` 取出，`:389-394`） |

⚠️ 占位符最终统一被 `regex_replace(originPath, regex, "([^/]*)")` 编译成位置捕获（`:563-564`）——`{id}` 与 `{}` 生成的正则**完全相同**，框架**不保留名字**。所以"按名取路径参数"这条路不存在：值只能按 handler 形参顺序拿，或按索引从 `getRoutingParameters()` 拿。

**关键差异：`HttpSimpleController` 完全不支持占位符。** 它的路径被小写归一后存进 `simpleCtrlMap_`（`HttpControllersRouter.cc:239`），请求期用 `find(loweredPath)` 精确查表（`HttpControllersRouter.cc:609-610`）——占位符会原样当成路径字符。要路径参数，只能选 `HttpController`（`METHOD_ADD`/`ADD_METHOD_TO`）或 lambda 内联路由，二者都走 `addHttpPath`。

- 取值优先用 handler 形参（框架按占位符顺序注入 `const std::string &`）。
- 需要一次拿全量时用 `req->getRoutingParameters()`（`lib/inc/drogon/HttpRequest.h:259`，返回 `const std::vector<std::string> &`，按位置索引）。
- `req->getParameter("k")` 只读 **query string / body** 参数（`HttpRequest.h:319`），拿不到路径占位符；**禁止**用 `req->path()` 手工切分路径。

## 注册与生命周期纪律

- **自动注册**：宏展开出的 `initPathRouting()` 由模板内的私有嵌套类 `pathRegistrator` 的静态成员 `registrator_` 在静态初始化期调用（`HttpSimpleController.h:91-104`、类外定义 `112-114`），最终落到 `app().registerHttpSimpleController(...)` / `app().registerHandler(...)`。**没有** `registerPathAdvice()` 这个东西（全树 0 命中）。**禁止**在 `main()` 手动注册控制器，**禁止**手动调用 `DrClassMap` 方法。 <!-- fact-guard-waived:registerPathAdvice -->
- **单例生命周期**：控制器是单例（`DrObject` + `DrClassMap`），框架启动时创建、关闭时销毁。**禁止**在 handler 里 `new Ctrl()` 或手动管理生命周期；**禁止**在控制器构造函数里做阻塞操作（会阻塞框架启动）。

## 禁止模式清单

- **禁止**在 `main()` 手动注册控制器（`registerHandler` / `DrClassMap` 之类）——控制器经静态初始化宏自动注册。
- **禁止**在控制器构造函数里做阻塞操作（同步 DB、`sleep`、文件 I/O）——构造函数在框架启动期执行。
- **禁止**在 handler 里同步阻塞后再调用 callback（同步查 DB、长计算）；改用 drogon 异步 API 或线程池。
- **禁止**漏调或多调 `callback`：所有代码路径（含异常、提前返回）必须**恰好一次**。
- **禁止**在 handler 里 `new Ctrl()` 或手动管理控制器生命周期——控制器是 `DrObject` 单例。
- **禁止**用 `req->path()` 手工切分路径参数；用 handler 形参或 `req->getRoutingParameters()`。
- **禁止**在路径里写冒号占位符（`/users/:id`）——drogon 只认 `{}` / `{N}` / `{N:name}`，且 `HttpSimpleController` 一条都不认。
- **禁止**把 `drogon_ctl` 生成的 `PATH_ADD` 注释示例里的第二个参数当 bug 删掉——那是方法/filter/中间件约束的变参位。

## 错误处理

- 命令执行失败：返回 stderr 内容
- 文件未生成：返回"文件未生成，请检查 drogon_ctl 安装"
- 参数错误：返回具体的参数错误消息