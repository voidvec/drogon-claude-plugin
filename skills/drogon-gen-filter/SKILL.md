# drogon-gen-filter

生成 drogon Filter（请求拦截器）类及注册代码。

## When to use

When request interception is needed (authentication, rate limiting, input validation), use this skill to generate Filter code that follows drogon conventions.

## Input parameters

- `filter_name`: Filter class name
- `filter_type`: Filter type (`auth`, `rate_limit`, `input_validation`)
- `reject_status`: HTTP status code when rejected (default `401`)

## Output

1. Filter class header file (extending `HttpFilter<ClassName, false>`)
2. `doFilter()` implementation (correctly using `fcb` + `fccb`)
3. `registerFilter()` registration code

## Example

```
/drogon-gen-filter filter_name=AuthFilter filter_type=auth
```

Generates an authentication interceptor Filter.
