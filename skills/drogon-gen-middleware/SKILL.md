# drogon-gen-middleware

生成 drogon Middleware（全局请求处理链）类及注册代码。

## When to use

When global request processing is needed (logging, CORS, performance timing), use this skill to generate Middleware code that follows drogon conventions.

## Input parameters

- `middleware_name`: Middleware class name
- `middleware_type`: Type (`logging`, `cors`, `timing`)
- `modify_response`: Whether to modify the response (`true`/`false`, default `false`)

## Output

1. Middleware class header file (extending `HttpMiddleware<ClassName, false>`)
2. `invoke()` implementation (correctly chaining via `nextCb(callback)`)
3. `registerMiddleware()` registration code

## Example

```
/drogon-gen-middleware middleware_name=LogMiddleware middleware_type=logging
```

Generates a request logging Middleware.
