# drogon-gen-advice Implementation

## Input parsing

Extract `advice_type` (required) from the 11 valid values listed in SKILL.md.

## Forbidden patterns

- Registering advice **inside a handler** — must be before `app().run()`.
- Intercepting advice missing the callback call — exactly-once discipline: must call `AdviceCallback` OR `AdviceChainCallback` once; omitting → connection hangs, double-call → crash.
- Using the 1-arg observer overload to send a response — it has no callback params, cannot intercept.
- Heavy work inside `SyncAdvice` — it runs synchronously at the very front of the request path.

## 11 built-in advices (source-checked, HttpAppFramework.h)

| Type | Register API | Callable signature | Intercepts | Lines |
|------|--------------|--------------------|-----------|-------|
| sync | `registerSyncAdvice` | `HttpRequestPtr(const HttpRequestPtr&)` | yes (non-empty short-circuits) | 306-313 |
| pre_routing (intercept) | `registerPreRoutingAdvice` | `void(req, AdviceCallback&&, AdviceChainCallback&&)` | yes | 367 |
| pre_routing (observe) | `registerPreRoutingAdvice` | `void(const HttpRequestPtr&)` | no | 379 |
| post_routing (intercept) | `registerPostRoutingAdvice` | 3-arg | yes | 389 |
| post_routing (observe) | `registerPostRoutingAdvice` | 1-arg | no | 401 |
| pre_handling (intercept) | `registerPreHandlingAdvice` | 3-arg | yes | — |
| pre_handling (observe) | `registerPreHandlingAdvice` | 1-arg | no | — |
| post_handling | `registerPostHandlingAdvice` | `void(req, resp)` (no static responses) | no | — |
| pre_sending | `registerPreSendingAdvice` | `void(req, resp)` (includes static) | no | 439-441 |
| http_response_creation | `registerHttpResponseCreationAdvice` | `void(const HttpResponsePtr&)` (all, incl 404) | no | 303-304 |
| beginning | `registerBeginningAdvice` | `void()` (once, after run) | no | 277-278 |
| new_connection | `registerNewConnectionAdvice` | `bool(InetAddress&, InetAddress&)` (false=drop) | yes | 288-290 |
| session_start | `registerSessionStartAdvice` | `AdviceStartSessionCallback` | no | 920-921 |
| session_destroy | `registerSessionDestroyAdvice` | `AdviceDestroySessionCallback` | no | 927-928 |

## Code templates

### pre_routing_obs (observer, cheapest)

```cpp
app().registerPreRoutingAdvice([](const HttpRequestPtr &req) {
    LOG_INFO << "incoming: " << req->path();
});
```

### pre_routing_int (interceptor — exactly-once callback)

```cpp
app().registerPreRoutingAdvice([](const HttpRequestPtr &req,
                                  AdviceCallback &&acb,
                                  AdviceChainCallback &&accb) {
    if (shouldBlock(req)) {
        auto resp = HttpResponse::newHttpResponse();
        resp->setStatusCode(k403Forbidden);
        acb(resp);      // intercept — call exactly once
        return;
    }
    accb();             // continue chain — call exactly once
});
```

### sync (short-circuit)

```cpp
app().registerSyncAdvice([](const HttpRequestPtr &req) -> HttpRequestPtr {
    // Return non-empty response pointer to short-circuit; return nullptr to proceed.
    return nullptr;
});
```

### pre_sending (add header to ALL responses incl. static)

```cpp
app().registerPreSendingAdvice([](const HttpRequestPtr &req,
                                  const HttpResponsePtr &resp) {
    resp->addHeader("X-Frame-Options", "DENY");
});
```

### new_connection (IP ban)

```cpp
app().registerNewConnectionAdvice(
    [](const trantor::InetAddress &peer, const trantor::InetAddress &local) -> bool {
        return !isBanned(peer.toIp());   // false = drop connection
    });
```

## Key rules

1. Register before `app().run()`.
2. Intercepting advice: call callback exactly once.
3. Prefer the 1-arg observer overload when you don't need to intercept.
4. SyncAdvice must stay cheap.

## Error handling

- `advice_type` invalid: list the 11 valid types.
