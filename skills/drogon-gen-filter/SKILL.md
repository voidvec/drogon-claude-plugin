---
name: drogon-gen-filter
description: 生成 drogon Filter（请求拦截器）类及注册代码，支持认证、限流、输入校验等过滤类型。
version: 0.1.0
---

# drogon-gen-filter

生成 drogon Filter（请求拦截器）类及注册代码。

## 使用场景

当需要请求拦截（认证、限流、输入校验）时，使用此技能生成符合 drogon 约定的 Filter 代码。

## 输入参数

- `filter_name`: Filter class name
- `filter_type`: Filter type (`auth`, `rate_limit`, `input_validation`)
- `reject_status`: HTTP status code when rejected (default `401`)

## 输出

1. Filter 类头文件（继承 `HttpFilter<ClassName, false>`）
2. `doFilter()` 实现（正确使用 `fcb` + `fccb`）
3. `registerFilter()` 注册代码

## 示例

```
/drogon-gen-filter filter_name=AuthFilter filter_type=auth
```

生成认证拦截 Filter。

## 参考文件
详细实现指南见 `references/code-guide.md`（含参数验证、代码模板、禁止模式清单）。生成代码前先读取该文件。
