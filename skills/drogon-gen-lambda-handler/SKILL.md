---
name: drogon-gen-lambda-handler
description: 生成 drogon 现代 lambda 路由代码（app().registerHandler），含 {N} 路径参数绑定与 constraints 混传。
version: 0.1.0
---

# drogon-gen-lambda-handler

生成基于 `app().registerHandler` 的现代 lambda 路由代码（无需控制器类）。

## 使用场景

当需要快速注册一个路由（无需定义 `HttpController` 子类）时使用。这是 v1.9.x 主推写法。与经典宏写法（`HttpController`+`METHOD_ADD`，用 `drogon-create-controller`）二选一，不混用。

## 输入参数

- `path`: 路由路径（如 `/hello?username={1}`，支持 `{N}` 位置参数）
- `methods`: HTTP 方法列表（如 `Get,Post`）
- `middlewares`: 中间件/过滤器名列表（可选，如 `AuthMiddleware,LogFilter`）
- `regex`: 是否正则路由（`true`/`false`，默认 `false`）

## 输出

1. `registerHandler` / `registerHandlerViaRegex` 注册代码
2. 正确的 lambda 签名（含路径参数按顺序注入）
3. constraints 混传 verbs + middleware 名

## 示例

```
/drogon-gen-lambda-handler path=/hello?username={1} methods=Get
/drogon-gen-lambda-handler path=/api/data methods=Post middlewares=AuthMiddleware
```

## 参考文件
详细实现指南见 `references/code-guide.md`（含路径参数语义、代码模板、禁止模式）。生成代码前先读取该文件。
