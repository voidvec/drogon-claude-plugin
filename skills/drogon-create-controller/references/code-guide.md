# drogon-create-controller Implementation

## 输入解析

从用户输入中提取：
- `controller_type`: 控制器类型（必需）
- `class_name`: 控制器类名（必需）
- `namespace`: 命名空间（可选）
- `resource`: 资源名（可选，仅 restful 有效）

## 参数验证

1. `class_name` 不能为空
2. `controller_type` 必须是 `simple`、`http`、`restful`、`websocket` 之一
3. 若 `controller_type=restful` 且提供 `resource`，检查 `resource` 不为空

## 命令构建

```python
def build_command(controller_type, class_name, namespace=None, resource=None):
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

    cmd.append(class_name)

    if namespace:
        cmd.extend(["--namespace", namespace])

    return " ".join(cmd)
```

## 命令执行

```bash
cd <项目根目录>
<生成的命令>
```

## 输出生成

1. 执行成功后，检查 `controllers/<类名>.h` 和 `controllers/<类名>.cc` 是否存在
2. 若文件不存在，说明命令执行失败，返回错误消息
3. 若文件存在，返回成功消息，包含文件路径和使用说明
4. **重要**：`drogon_ctl create controller -s` 生成的代码中 `PATH_ADD` 可能错误包含第二个参数（如 `PATH_ADD("/path", Get)`）。若 `controller_type=simple`，打开生成的 `.h` 和 `.cc` 文件检查 `PATH_ADD` 调用：`HttpSimpleController` 的 `PATH_ADD` **只接受一个字符串参数**。如果生成代码有多余参数，必须删除。同时检查 `.cc` 文件中是否有不存在的 `asyncHandleHttpRequest(Get, Post, ...)` 重载——`HttpSimpleController` 只有一个 handler。

## 宏速查

| 控制器类型 | 路径注册宏 | 参数个数 | handler 签名 |
|-----------|-----------|---------|-------------|
| `HttpSimpleController` | `PATH_ADD(path)` | **1** 个 | `asyncHandleHttpRequest(req, callback)` |
| `HttpController` | `METHOD_ADD(method, path, verb)` | 3 个 | 每方法一个 handler |
| `WebSocketController` | `WS_PATH_ADD(path, ...)` | ≥1 个 | `handleNewMessage` / `handleNewConnection` / `handleConnectionClosed` |

AI 不得混淆——`PATH_ADD` 只有 1 参数，`METHOD_ADD` 有 3 参数。`HttpSimpleController` 不存在 `METHOD_ADD`。

## 类型选择规则

| 需求 | 控制器类型 |
|------|-----------|
| 单一 path 单一 handler | `HttpSimpleController` |
| RESTful API（多 HTTP 方法 + 路径参数） | `HttpController` |
| WebSocket 连接 | `WebSocketController` |
| 无需控制器类（v1.9.x 主推） | lambda 内联路由（用 `drogon-gen-lambda-handler`，不混用经典宏） |

- 不得在 RESTful API 里用 `HttpSimpleController`（无法区分 HTTP 方法），也不得在单一 path handler 里用 `HttpController`（过度设计）。
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

- 路径支持 `:param` 语法（如 `/users/:id`）。
- **禁止**用 `{id}` / `{param}` 模板引擎语法（drogon 不支持），也**禁止**省略 `:` 前缀（参数无法捕获）。
- 取值用 `req->getParameter("param")`（返回 `std::string`），**禁止**用 `req->path()` 手动解析路径参数。
- 注意：`{N}` 位置捕获是 lambda 内联路由（`drogon-gen-lambda-handler`）的语法，与经典 `:param` 是两套机制，不通用。

## 注册与生命周期纪律

- **自动注册**：所有控制器通过静态初始化宏自动注册（宏内部调用 `DrClassMap::getSingleInstance<Ctrl>()->registerPathAdvice()`）。**禁止**在 `main()` 手动注册控制器，**禁止**手动调用 `DrClassMap` 方法。
- **单例生命周期**：控制器是单例（`DrObject` + `DrClassMap`），框架启动时创建、关闭时销毁。**禁止**在 handler 里 `new Ctrl()` 或手动管理生命周期；**禁止**在控制器构造函数里做阻塞操作（会阻塞框架启动）。

## 错误处理

- 命令执行失败：返回 stderr 内容
- 文件未生成：返回"文件未生成，请检查 drogon_ctl 安装"
- 参数错误：返回具体的参数错误消息