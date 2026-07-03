---
name: drogon-gen-coroutine-handler
description: 生成 drogon 协程 handler / 协程中间件 / 协程 ORM 调用，正确区分 Task/AsyncTask，强制裸 handler 参数按值传递。
version: 0.1.0
---

# drogon-gen-coroutine-handler

生成 drogon 协程代码：handler、协程中间件（`HttpCoroMiddleware`）、协程 ORM/Redis/HttpClient 调用。

## 使用场景

当项目已启用协程（`USE_COROUTINE=ON`）且需编写异步 handler / 中间件时使用。

## 输入参数

- `kind`: `handler` / `middleware` / `orm_call` / `http_call`
- `return_type`: handler 的返回类型（`Task<HttpResponsePtr>` / `AsyncTask`），仅 `kind=handler` 时有效
- `class_name`: 类名（仅 `kind=middleware`）

## 输出

1. 协程代码（正确的返回类型、`co_await`、try/catch 兜底）
2. **参数按值传递**（裸 handler）或可引用（协程中间件，框架已拷贝）
3. AsyncTask 的 try/catch 提醒（否则未处理异常 `std::terminate`）

## 示例

```
/drogon-gen-coroutine-handler kind=handler return_type=Task<HttpResponsePtr>
/drogon-gen-coroutine-handler kind=middleware class_name=AuthMiddleware
```

## 参考文件
详细实现指南见 `references/code-guide.md`（含返回类型对照、参数生命周期对照、代码模板、禁止模式）。生成代码前先读取该文件。
