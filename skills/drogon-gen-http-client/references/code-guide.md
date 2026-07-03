# drogon-gen-http-client Implementation

## Input parsing

Extract:
- `mode`: `async` / `coro` / `forward` (required)
- `target`: host string prefixed with `http://` or `https://` (required)
- `method`: HTTP method (default `Get`)
- `timeout`: seconds, 0 = no timeout (default `0`)

## Forbidden patterns

- Synchronous `sendRequest(req)` / `sendRequest(req, timeout)` **inside a handler or the event-loop thread** — has `assert(!getLoop()->isInLoopThread())`, deadlocks (HttpClient.h:133).
- Reusing the **same** `HttpRequestPtr` across threads — `sendRequest` mutates it (adds headers), concurrent reuse is a data race (HttpClient.h:87-88).
- Forgetting to check `ReqResult` — timeout yields `ReqResult::Timeout` + empty resp.
- `app().run()` not called — client uses the app event loop, won't work without run.

## Key APIs (source-checked, HttpClient.h)

| API | Signature | Notes | Source |
|-----|-----------|-------|--------|
| create client | `HttpClient::newHttpClient(hostString, loop=nullptr, useOldTLS=false, validateCert=true)` | hostString must start with http(s):// | 344 |
| async send | `client->sendRequest(req, callback, timeout=0)` | callback gets `(ReqResult, HttpResponsePtr)` | 91 |
| sync send | `client->sendRequest(req, timeout=0)` → `pair<ReqResult, HttpResponsePtr>` | **deadlock assert in loop thread** | 130 |
| coroutine send | `client->sendRequestCoro(req, timeout=0)` → awaiter | throws `HttpException(ReqResult)` on timeout | 160 |
| reverse proxy | `app().forward(req, callback, hostString="", timeout=0)` | use instead of hand-rolled client+header copy | HttpAppFramework.h:760 |

## Code templates

### async

```cpp
auto client = HttpClient::newHttpClient("http://api.example.com");
auto req = HttpRequest::newHttpRequest();
req->setMethod(Get);
req->setPath("/users/1");
client->sendRequest(req, [](ReqResult result, const HttpResponsePtr &resp) {
    if (result != ReqResult::Ok) {           // Q.4 always check
        LOG_ERROR << "request failed: " << result;
        return;
    }
    LOG_INFO << "body: " << resp->getBody();
}, 5.0);                                      // 5s timeout
```

### coro

```cpp
drogon::Task<HttpResponsePtr> fetchUser(int id) {
    auto client = HttpClient::newHttpClient("http://api.example.com");
    auto req = HttpRequest::newHttpRequest();
    req->setPath("/users/" + std::to_string(id));
    try {
        auto resp = co_await client->sendRequestCoro(req, 5.0);   // throws on timeout
        co_return resp;
    } catch (const drogon::HttpException &e) {
        LOG_ERROR << "http error: " << e.what();
        co_return HttpResponse::newHttpResponse();
    }
}
```

### forward (reverse proxy)

```cpp
app().registerHandler("/api/{1}",
    [](const HttpRequestPtr &req,
       std::function<void(const HttpResponsePtr &)> &&callback,
       const std::string &path) {
        req->setPath("/" + path);             // rewrite path before forwarding
        app().forward(req, callback, "http://backend:8080", 5.0);
    }, {Get, Post});
```

## Key rules

1. In a handler/loop thread: use **async** or **coro**, never the sync overload.
2. Always check `ReqResult` (async) or catch `HttpException` (coro).
3. One `HttpRequestPtr` per send; don't share across threads.
4. Reverse proxy → use `app().forward`, not a hand-rolled client.

## Error handling

- `mode` invalid: list valid modes.
- `target` not starting with http(s)://: return error.
