---
name: drogon-gen-middleware
description: 生成 drogon Middleware（全局请求处理链）类及注册代码，支持日志、CORS、性能计时等类型。
version: 0.1.0
---

# drogon-gen-middleware

生成 drogon Middleware（全局请求处理链）类及注册代码。

## 使用场景

当需要全局请求处理（日志、CORS、性能计时）时，使用此技能生成符合 drogon 约定的 Middleware 代码。

## 输入参数

- `middleware_name`: Middleware class name
- `middleware_type`: Type (`logging`, `cors`, `timing`)
- `modify_response`: Whether to modify the response (`true`/`false`, default `false`)

## 输出

1. Middleware 类头文件（继承 `HttpMiddleware<ClassName, false>`）
2. `invoke()` 实现（正确链式调用 `nextCb(callback)`）
3. `registerMiddleware()` 注册代码

## 示例

```
/drogon-gen-middleware middleware_name=LogMiddleware middleware_type=logging
```

生成请求日志 Middleware。

## 参考文件
详细实现指南见 `references/code-guide.md`（含参数验证、代码模板、禁止模式清单）。生成代码前先读取该文件。
