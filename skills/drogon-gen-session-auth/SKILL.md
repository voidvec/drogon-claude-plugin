---
name: drogon-gen-session-auth
description: 生成基于 drogon Session 的登录/登出/鉴权 handler 代码，含 changeSessionIdToClient 防 fixation。
version: 0.1.0
---

# drogon-gen-session-auth

生成基于 drogon `Session` 的登录 / 登出 / 鉴权 handler 代码。

## 使用场景

当需要实现用户登录、登出、或基于会话的访问控制时，使用此技能生成符合 drogon 会话纪律（M 组）的代码。

## 输入参数

- `route`: 路由路径（如 `/login`、`/logout`）
- `auth_mode`: 模式（`login`、`logout`、`check`）
- `user_field`: 用户标识字段名（可选，默认 `userId`）

## 输出

1. lambda 路由 handler（用 `app().registerHandler`）
2. 正确的 session 读写（`getOptional` / `insert` / `modify`）
3. 登录成功后 `changeSessionIdToClient()` 防 fixation
4. 启动链 `enableSession(timeout)` 提示

## 示例

```
/drogon-gen-session-auth route=/login auth_mode=login
```

## 参考文件
详细实现指南见 `references/code-guide.md`（含参数验证、代码模板、禁止模式清单）。生成代码前先读取该文件。
