# drogon-gen-middleware Implementation

## Input parsing

Extract from user input:
- `middleware_name`: Middleware class name (required)
- `middleware_type`: Type (`logging`/`cors`/`timing`, default `logging`)
- `modify_response`: Whether to modify the response (default `false`)

## Forbidden APIs

- `ADD_MIDDLEWARE` macro — **does not exist**, use `app().registerMiddleware(...)` to register
- `HttpMiddleware<ClassName>` without `AutoCreation` — must write `HttpMiddleware<ClassName, false>`, otherwise `registerMiddleware()`'s `static_assert(!T::isAutoCreation)` causes compilation failure (`HttpAppFramework.h:714-717`)
- `nextCb(req, callback)` — **wrong signature**, `nextCb` accepts exactly one parameter

## Callback type quick reference

| Parameter | Type | Description |
|-----------|------|-------------|
| `nextCb` | `MiddlewareNextCallback` = `std::function<void(std::function<void(const HttpResponsePtr &)> &&)>` | **Accepts exactly one parameter** (downstream response callback) |
| `mcb` | `MiddlewareCallback` = `std::function<void(const HttpResponsePtr &)>` | Final response callback |

## Code generation

### logging type

```cpp
class ${middleware_name} : public drogon::HttpMiddleware<${middleware_name}, false> {
  public:
    void invoke(const drogon::HttpRequestPtr &req,
                drogon::MiddlewareNextCallback &&nextCb,
                drogon::MiddlewareCallback &&mcb) override {
        LOG_INFO << "Request: " << req->methodString() << " " << req->path();

        nextCb([mcb = std::move(mcb)](const drogon::HttpResponsePtr &resp) {
            LOG_INFO << "Response: status=" << resp->getStatusCode();
            mcb(resp);  // must call mcb to pass response through
        });
    }
};

// Register in main():
// app().registerMiddleware(std::make_shared<${middleware_name}>());
```

### cors type

```cpp
class ${middleware_name} : public drogon::HttpMiddleware<${middleware_name}, false> {
  public:
    void invoke(const drogon::HttpRequestPtr &req,
                drogon::MiddlewareNextCallback &&nextCb,
                drogon::MiddlewareCallback &&mcb) override {
        nextCb([mcb = std::move(mcb)](const drogon::HttpResponsePtr &resp) {
            resp->addHeader("Access-Control-Allow-Origin", "*");
            resp->addHeader("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE");
            mcb(resp);  // must call mcb to pass response through
        });
    }
};

// Register in main():
// app().registerMiddleware(std::make_shared<${middleware_name}>());
```

### timing type

```cpp
class ${middleware_name} : public drogon::HttpMiddleware<${middleware_name}, false> {
  public:
    void invoke(const drogon::HttpRequestPtr &req,
                drogon::MiddlewareNextCallback &&nextCb,
                drogon::MiddlewareCallback &&mcb) override {
        auto start = std::chrono::steady_clock::now();

        nextCb([mcb = std::move(mcb), start](const drogon::HttpResponsePtr &resp) {
            auto elapsed = std::chrono::steady_clock::now() - start;
            auto ms = std::chrono::duration_cast<std::chrono::milliseconds>(elapsed).count();
            resp->addHeader("X-Response-Time", std::to_string(ms) + "ms");
            mcb(resp);  // must call mcb to pass response through
        });
    }
};

// Register in main():
// app().registerMiddleware(std::make_shared<${middleware_name}>());
```

### Registration code

```cpp
// In main(), before app().run():
app().registerMiddleware(std::make_shared<${middleware_name}>());
```

## Key rules

1. **`nextCb` accepts exactly one parameter** (downstream response callback), NOT `nextCb(req, callback)`
2. **Must call `mcb(resp)`** to pass the final response — if not called, the response is never sent
3. **Don't swallow `nextCb`** — must call it at some point, otherwise the handler never executes
4. **`mcb` must be moved** into nextCb's callback (`nextCb([mcb = std::move(mcb)](...) { ... })`)

## Error handling

- `middleware_name` is empty: return error message
- `middleware_type` is invalid: return error message listing valid types
