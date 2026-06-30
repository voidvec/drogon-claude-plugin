# drogon-gen-filter Implementation

## Input parsing

Extract from user input:
- `filter_name`: Filter class name (required)
- `filter_type`: Filter type (`auth`/`rate_limit`/`input_validation`, default `auth`)
- `reject_status`: HTTP status code when rejected (default `401`)

## Forbidden APIs

- `FILTER_ADD` macro — **does not exist**, use `app().registerFilter(...)` to register
- `HttpFilter<ClassName>` without `AutoCreation` — must write `HttpFilter<ClassName, false>`, otherwise `registerFilter()`'s `static_assert(!T::isAutoCreation)` causes compilation failure (`HttpAppFramework.h:696-699`)
- Returning from `doFilter()` without calling either `fcb` or `fccb` — violates A.1 callback discipline

## Callback type quick reference

| Parameter | Type | Purpose |
|-----------|------|---------|
| `fcb` | `FilterCallback` = `std::function<void(const HttpResponsePtr &)>` | Intercept: respond directly |
| `fccb` | `FilterChainCallback` = `std::function<void()>` | Pass-through: continue chain |

## Code generation

### auth type

```cpp
class ${filter_name} : public drogon::HttpFilter<${filter_name}, false> {
  public:
    void doFilter(const drogon::HttpRequestPtr &req,
                  drogon::FilterCallback &&fcb,
                  drogon::FilterChainCallback &&fccb) override {
        auto token = req->getHeader("Authorization");
        if (token.empty() || !verifyToken(token)) {
            auto resp = drogon::HttpResponse::newHttpJsonResponse(
                Json::Value({{"error", "unauthorized"}}));
            resp->setStatusCode(drogon::k401Unauthorized);
            fcb(resp);  // intercept
            return;
        }
        fccb();  // pass through
    }

  private:
    bool verifyToken(const std::string &token) const {
        // TODO: implement token verification logic
        return false;
    }
};

// Register in main():
// app().registerFilter(std::make_shared<${filter_name}>());
```

### rate_limit type

```cpp
class ${filter_name} : public drogon::HttpFilter<${filter_name}, false> {
  public:
    void doFilter(const drogon::HttpRequestPtr &req,
                  drogon::FilterCallback &&fcb,
                  drogon::FilterChainCallback &&fccb) override {
        auto client_ip = req->getPeerAddr().toIp();
        if (isRateLimited(client_ip)) {
            auto resp = drogon::HttpResponse::newHttpResponse();
            resp->setStatusCode(drogon::k429TooManyRequests);
            resp->setBody("Too many requests");
            fcb(resp);  // intercept
            return;
        }
        fccb();  // pass through
    }

  private:
    bool isRateLimited(const std::string &ip) const {
        // TODO: implement rate limiting logic
        return false;
    }
};

// Register in main():
// app().registerFilter(std::make_shared<${filter_name}>());
```

### Registration code

```cpp
// In main(), before app().run():
app().registerFilter(std::make_shared<${filter_name}>());
```

## Key rules

1. **On intercept: must call `fcb(resp)`** — sends error response, skips handler
2. **On pass-through: must call `fccb()`** — no arguments, continues chain
3. **Never `return` without calling `fcb` or `fccb`** — violates A.1
4. **`fcb` and `fccb` are mutually exclusive** — a code path must call exactly one

## Error handling

- `filter_name` is empty: return error message
- `filter_type` is invalid: return error message listing valid types
