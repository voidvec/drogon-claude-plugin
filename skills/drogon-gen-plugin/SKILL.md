---
name: drogon-gen-plugin
description: 生成 drogon Plugin（系统级扩展）类及配置声明，用于连接池、第三方 SDK 初始化等应用级生命周期管理。
version: 0.1.0
---

# drogon-gen-plugin

生成 drogon Plugin（系统级扩展）类及配置声明。

## 使用场景

当需要系统级扩展（连接池、第三方 SDK 初始化、全局资源管理）时，使用此技能生成符合 drogon 约定的 Plugin 代码。Plugin 在 `app().run()` 之前同步初始化，整个应用生命周期内单实例存在。

**与 Filter / Middleware 的区别**：Plugin 不处理请求，负责应用级初始化与资源管理；Filter 做请求拦截，Middleware 做全局处理链。三者职责不得混用。

## 输入参数

- `plugin_name`: Plugin class name (required)
- `purpose`: 用途描述（如 `redis_pool`、`sdk_init`）
- `config_keys`: 配置项（从 `config.json` 的 `plugins` 数组读取的键，格式 `key:type`）

## 输出

1. Plugin 类头文件（继承 `drogon::Plugin<ClassName>`）
2. `initAndStart(const Json::Value &config)` / `shutdown()` 实现
3. `config.json` 的 `plugins` 数组声明片段
4. 获取插件实例的代码：`app().getPlugin<ClassName>()`

## 示例

```
/drogon-gen-plugin plugin_name=RedisPool purpose=redis_pool config_keys=max_connections:int,timeout:double
```

生成 Redis 连接池 Plugin。

## 参考文件

详细实现指南见 `references/code-guide.md`（含 Plugin 规范、三者职责边界对比、禁止模式清单）。生成代码前先读取该文件。
