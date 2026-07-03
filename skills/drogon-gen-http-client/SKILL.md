---
name: drogon-gen-http-client
description: 生成 drogon 出站 HTTP 请求代码（异步回调 / 协程 / 反向代理 forward），含 ReqResult 检查与 timeout。
version: 0.1.0
---

# drogon-gen-http-client

生成 drogon `HttpClient` 出站请求代码。

## 使用场景

当需要从 drogon 应用向外部服务发 HTTP 请求（调用第三方 API、微服务间调用、反向代理）时使用。

## 输入参数

- `mode`: `async` / `coro` / `forward`（反向代理）
- `target`: 目标地址（如 `http://api.example.com`）
- `method`: HTTP 方法（默认 `Get`）
- `timeout`: 超时秒数（可选，默认 `0`=不超时）

## 输出

1. `HttpClient::newHttpClient(...)` 创建 + 请求构造
2. 异步回调（含 `ReqResult` 检查）或协程 `sendRequestCoro`（含超时异常处理）或 `app().forward`
3. 同步 `sendRequest` 死锁禁用提醒

## 示例

```
/drogon-gen-http-client mode=async target=http://api.example.com method=Get
/drogon-gen-http-client mode=forward target=http://backend:8080
```

## 参考文件
详细实现指南见 `references/code-guide.md`（含 API 签名、代码模板、禁止模式）。生成代码前先读取该文件。
