---
name: drogon-create-controller
description: 需要为路由 / 接口创建 drogon 控制器时，生成 .h + .cc（HttpSimpleController / HttpController / WebSocketController 三选一），含路径前缀、`{N}` 路径参数与自动注册纪律。
license: MIT
---

# drogon-create-controller

生成 drogon 控制器代码（`.h` + `.cc`），支持 `HttpSimpleController`、`HttpController`、`WebSocketController` 三种类型。

## 使用场景

当需要创建一个新的 drogon 控制器时，使用此技能快速生成符合 drogon 约定的代码文件。

## 输入参数

- `controller_type`: 控制器类型（`simple`、`http`、`restful`、`websocket`）
- `class_name`: 控制器类名（PascalCase）
- `namespace`: 命名空间（可选，如 `myapp`）。`drogon_ctl create controller` **没有** `--namespace` 选项，任何 `-` 开头的多余参数会让命令直接报参数错误且**不生成文件**（源码 `create_controller.cc:28-59` 的参数白名单）；命名空间只能并入类名写成 `myapp::MyCtrl`（`::` 前缀会生成真正的嵌套 `namespace`，源码 `create_controller.cc:103-115`）
- `resource`: 资源名（可选，仅当 `controller_type=restful` 时有效）

## 输出

1. 执行 `drogon_ctl create controller` 命令
2. 生成控制器代码文件——文件名是类名里 `::` 替换为 `_`，写在**当前工作目录**（`myapp::MyCtrl` → `myapp_MyCtrl.h` / `myapp_MyCtrl.cc`），**没有 `controllers/` 子目录**（源码 `create_controller.cc:349-354`）
3. 说明生成的文件位置和使用方法

## 示例

```
/drogon-create-controller controller_type=simple class_name=myapp::MyCtrl
```

生成文件：
- `myapp_MyCtrl.h`
- `myapp_MyCtrl.cc`
## 参考文件
详细实现指南见 `references/code-guide.md`（含参数验证、代码模板、禁止模式清单）。生成代码前先读取该文件。
