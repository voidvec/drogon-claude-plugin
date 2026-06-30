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

AI 不得混淆——`PATH_ADD` 只有 1 参数，`METHOD_ADD` 有 3 参数。`HttpSimpleController` 不存在 `METHOD_ADD`。

## 错误处理

- 命令执行失败：返回 stderr 内容
- 文件未生成：返回"文件未生成，请检查 drogon_ctl 安装"
- 参数错误：返回具体的参数错误消息