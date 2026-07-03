# drogon-gen-coroutine-handler Implementation

## Input parsing

Extract:
- `kind`: `handler` / `middleware` / `orm_call` / `http_call` (required)
- `return_type`: `Task<HttpResponsePtr>` / `AsyncTask` (only for `kind=handler`)
- `class_name`: (only for `kind=middleware`)

## Forbidden patterns

- Using coroutine APIs without confirming `__cpp_impl_coroutine` defined AND CMake `USE_COROUTINE=ON`.
- Bare coroutine handler (`Task*`/`AsyncTask`) with **reference** params — Use-After-Free after suspend/resume.
- `AsyncTask` without try/catch — uncaught exception calls `std::terminate`.
- Deriving coroutine middleware from `HttpMiddleware<T,false>` — must be `HttpCoroMiddleware<T,false>`.
- Calling `nextCb(callback)` syntax on `MiddlewareNextAwaiter` — coroutine uses `co_await next`.

## Return type semantics

| Return | Use | Exception behavior | Response delivery |
|--------|-----|--------------------|-------------------|
| `Task<HttpResponsePtr>` | handler returning response | propagates, awaitable | framework |
| `Task<>` | general async task | propagates | caller |
| `AsyncTask` | fire-and-forget | **uncaught → std::terminate** | caller |

Prefer `Task<HttpResponsePtr>`.

## Parameter lifetime — critical

| Scenario | `req` / `callback` passing | Reason |
|----------|---------------------------|--------|
| Bare coroutine handler (`Task*` / `AsyncTask`) | **by value** | reference dangles after resume |
| Callback handler (`void`) | reference / `&&` | never suspends |
| Coroutine middleware `HttpCoroMiddleware::invoke` | **reference ok** | framework `async_run` lambda captures req/nextCb/mcb by value (HttpMiddleware.h:121-124) |

Evidence: official `examples/redis_cache/controllers/SlowCtrl.cc` — callback `hello` uses `const HttpRequestPtr &req`; coroutine `observe` uses `HttpRequestPtr req` (by value).

## Code templates

### handler (Task<HttpResponsePtr>, params by value)

```cpp
drogon::Task<HttpResponsePtr> getUser(int id) {
    try {
        auto client = app().getDbClient();
        auto r = co_await client->execSqlCoro("SELECT name FROM users WHERE id=$1", id);
        auto resp = HttpResponse::newHttpResponse();
        resp->setBody(r.empty() ? "none" : r[0]["name"].as<std::string>());
        co_return resp;
    } catch (const std::exception &e) {
        LOG_ERROR << e.what();
        co_return HttpResponse::newHttpResponse();
    }
}
```

### handler (AsyncTask — must catch, params by value)

```cpp
drogon::AsyncTask observe(
    HttpRequestPtr req,                                        // by value
    std::function<void(const HttpResponsePtr &)> callback,     // by value
    std::string userid) {                                      // by value
    try {
        // ... co_await ...
        callback(resp);
    } catch (const std::exception &e) {
        LOG_ERROR << e.what();
        callback(HttpResponse::newNotFoundResponse());
    }
    co_return;
}
```

### middleware (HttpCoroMiddleware — reference ok, framework catches)

```cpp
class ${class_name} : public drogon::HttpCoroMiddleware<${class_name}, false> {
  public:
    drogon::Task<drogon::HttpResponsePtr> invoke(
        const drogon::HttpRequestPtr &req,
        drogon::MiddlewareNextAwaiter &&next) override {
        LOG_INFO << "before: " << req->path();
        auto resp = co_await next;        // awaits downstream response
        resp->addHeader("X-Tag", "ok");
        co_return resp;
    }
};

// Register in main():
// app().registerMiddleware(std::make_shared<${class_name}>());
```

### http_call (coroutine client — must catch timeout)

```cpp
auto resp = co_await client->sendRequestCoro(req, 5.0);  // throws HttpException on timeout
```

### forward (coroutine reverse proxy)

协程版反向代理用 `app().forwardCoro(req, host, port)`，避免自建 client + 手动复制 header：

```cpp
drogon::Task<HttpResponsePtr> proxy(const HttpRequestPtr &req) {
    try {
        auto resp = co_await app().forwardCoro(req, "backend.example.com", 8080);
        co_return resp;
    } catch (const std::exception &e) {
        LOG_ERROR << "forward failed: " << e.what();
        co_return HttpResponse::newHttpResponse();
    }
}
```

## Key rules

1. Confirm `USE_COROUTINE=ON` before generating coroutine code.
2. Bare coroutine handler: pass `req`/`callback` by value; coroutine middleware: reference is fine.
3. `AsyncTask` body must be wrapped in try/catch.
4. Coroutine middleware derives from `HttpCoroMiddleware<T,false>`, await `next`.

## Error handling

- `kind` invalid: list valid kinds.
- `kind=handler` without `return_type`: default to `Task<HttpResponsePtr>`.
