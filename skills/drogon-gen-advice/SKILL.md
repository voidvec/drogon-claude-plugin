---
name: drogon-gen-advice
description: 生成 drogon AOP Advice 代码（11 个内建切面之一），区分拦截型/观察型，含 SyncAdvice 短路。
version: 0.1.0
---

# drogon-gen-advice

生成 drogon AOP（面向切面）Advice 注册代码。drogon 提供 11 个内建切面。

## 使用场景

当需要插入横切逻辑（统一日志、安全拦截、响应头注入、连接级访问控制、会话生命周期监听）时，使用此技能。

## 输入参数

- `advice_type`: 切面类型，取值之一：
  - `sync`（同步拦截，返非空 resp 短路）
  - `pre_routing_obs` / `pre_routing_int`（观察/拦截）
  - `post_routing_obs` / `post_routing_int`
  - `pre_handling_obs` / `pre_handling_int`
  - `post_handling`（观察）
  - `pre_sending`（观察，含静态响应）
  - `http_response_creation`
  - `beginning`
  - `new_connection`
  - `session_start` / `session_destroy`

## 输出

1. 对应 `register*Advice(...)` 注册代码（放在 `app().run()` 之前）
2. 拦截型标注"恰好一次回调"纪律
3. SyncAdvice 返非空短路示例

## 示例

```
/drogon-gen-advice advice_type=pre_routing_obs
```

## 参考文件
详细实现指南见 `references/code-guide.md`（含 11 切面签名表、代码模板、禁止模式清单）。生成代码前先读取该文件。
