---
name: drogon-gen-rate-limiter
description: 需要 drogon 限流/防滥用、编写 Hodor 插件配置、自定义 429 拒绝响应或编程式 RateLimiter 时使用。
license: MIT
---

# drogon-gen-rate-limiter

生成 drogon 限流方案：Hodor 插件配置或编程式 RateLimiter 代码。

## 使用场景

当需要接口限流或防滥用（全站配额、按 IP/用户收紧、敏感路由防暴力破解）、为 429 响应定制统一 JSON 错误 envelope、或多实例部署需要 Redis 分布式限流时，使用此技能生成字段与 API 均对照 v1.9.13 源码核对的配置与代码。

## 输入参数

- `scope`：限流场景——`global`（全站）/ `ip`（按来源 IP）/ `user`（按用户或会话）/ `route`（特定路由收紧）
- `algorithm`：限流类型——`fixed_window`（固定窗口）/ `sliding_window`（滑动窗口）/ `token_bucket`（令牌桶，默认）
- `capacity`：时间单元内允许的最大请求数（必填，0 等于不限流）
- `time_unit`：时间单元秒数（默认 `60`）
- `routes`:需收紧的路径正则列表，如 `^/oauth2/login`（可选）
- `custom_reject`:是否自定义 429 响应（默认 `true`，生成统一错误 envelope + CORS 头）
- `multi_instance`:多实例部署改用 Redis 分布式限流（默认 `false`）

## 输出

1. Hodor 插件 config.json `plugins` 数组段（含 sub_limits 分层配额）
2. `setRejectResponseFactory` 自定义 429 响应代码（统一错误 JSON envelope + CORS 头保留）
3. 需要时：Filter 内嵌 `RateLimiter`/`SafeRateLimiter` 模板，或 Redis INCR+EXPIRE 分布式限流

## 示例

```
/drogon-gen-rate-limiter scope=ip algorithm=token_bucket capacity=30 time_unit=60 routes=^/api/pay/.*
/drogon-gen-rate-limiter scope=route capacity=3 routes=^/oauth2/login custom_reject=true
```

## 参考文件

详细实现指南见 `references/code-guide.md`（含三方案选型、Hodor 字段源码核对表、禁止模式清单）。生成代码前先读取该文件。
