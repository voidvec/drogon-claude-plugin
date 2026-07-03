# drogon-gen-lambda-handler Implementation

## Input parsing

Extract:
- `path`: route pattern (required), e.g. `/users/{1}` or `/hello?username={1}`
- `methods`: comma-separated HTTP verbs (default `Get`)
- `middlewares`: comma-separated middleware/filter names (optional)
- `regex`: `true` → use `registerHandlerViaRegex` (default `false`)

## Forbidden patterns

- Mixing lambda routing with classic `HttpController`+`METHOD_ADD` for the same kind of route in one project — pick one style.
- Adding path/query params in `newHttpClient` hostString — host is host only; path goes in the request (applies to client, but easy to confuse).
- Expecting `{name}` (named) capture — the lambda API uses `{1}`, `{2}` positional capture mapped to handler params (HttpAppFramework.h:517-528).

## Key APIs (source-checked, HttpAppFramework.h)

| API | Signature | Source |
|-----|-----------|--------|
| register handler | `template<typename F> HttpAppFramework& registerHandler(pathPattern, F&&, constraints={}, handlerName="")` | 534 |
| register via regex | `template<typename F> HttpAppFramework& registerHandlerViaRegex(regExp, F&&, constraints={}, handlerName="")` | 586 |
| constraints | `std::vector<internal::HttpConstraint>` — mixes verbs + middleware/filter names | 549-558 |

## Path parameter binding

`{N}` is positional. Extra handler params (after `req`, `callback`) receive captured values in order.
Path pattern may also map captures to query string: `/hello?username={1}`.

## Code templates

### basic (positional param)

```cpp
app().registerHandler("/hello?username={1}",
    [](const HttpRequestPtr &req,
       std::function<void(const HttpResponsePtr &)> &&callback,
       const std::string &name) {                           // {1} injected here
        Json::Value json;
        json["message"] = "hello, " + name;
        callback(HttpResponse::newHttpJsonResponse(json));
    },
    {Get});
```

### with middleware + multiple verbs

```cpp
app().registerHandler("/api/data",
    [](const HttpRequestPtr &req,
       std::function<void(const HttpResponsePtr &)> &&callback) {
        callback(HttpResponse::newHttpResponse());
    },
    {Get, Post, "AuthMiddleware", "LogFilter"});             // V.4 mix verbs + names
```

### regex route

```cpp
app().registerHandlerViaRegex("^/items/[0-9]+$",
    [](const HttpRequestPtr &req,
       std::function<void(const HttpResponsePtr &)> &&callback) {
        callback(HttpResponse::newHttpResponse());
    },
    {Get});
```

## Key rules

1. `{N}` positional capture → handler params in order.
2. Constraints vector accepts both verbs and middleware/filter name strings.
3. Don't mix with classic `METHOD_ADD` style in the same project.
4. For regex matching, use `registerHandlerViaRegex`.

## Error handling

- `path` empty: return error.
- `methods` contains an invalid verb: return error listing valid verbs.
