# drogon-create-controller

生成 drogon 控制器代码（`.h` + `.cc`），支持 `HttpSimpleController`、`HttpController`、`WebSocketController` 三种类型。

## 使用场景

当需要创建一个新的 drogon 控制器时，使用此技能快速生成符合 drogon 约定的代码文件。

## 输入参数

- `controller_type`: 控制器类型（`simple`、`http`、`restful`、`websocket`）
- `class_name`: 控制器类名（PascalCase）
- `namespace`: 命名空间（可选，如 `myapp`）
- `resource`: 资源名（可选，仅当 `controller_type=restful` 时有效）

## 输出

1. 执行 `drogon_ctl create controller` 命令
2. 生成控制器代码文件（`controllers/<类名>.h` + `controllers/<类名>.cc`）
3. 说明生成的文件位置和使用方法

## 示例

```
/drogon-create-controller controller_type=simple class_name=MyCtrl namespace=myapp
```

生成文件：
- `controllers/MyCtrl.h`
- `controllers/MyCtrl.cc`