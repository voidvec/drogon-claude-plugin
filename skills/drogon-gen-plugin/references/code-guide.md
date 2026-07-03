# drogon-gen-plugin Implementation

## Input parsing

Extract from user input:
- `plugin_name`: Plugin class name (required)
- `purpose`: 用途描述（required）
- `config_keys`: 配置项列表（格式 `key1:type1,key2:type2`，从 `config.json` 的 `plugins[].config` 读取）

## Plugin 规范

Plugin 是 drogon 的**系统级扩展**机制，由框架托管，整个应用生命周期内单实例：

```cpp
class ${plugin_name} : public drogon::Plugin<${plugin_name}> {
  public:
    void initAndStart(const Json::Value &config) override {
        // 第三方库初始化、连接池创建等
        // config 来自 config.json 的 plugins[].config
    }
    void shutdown() override {
        // 资源清理、连接关闭
    }
};
```

### 关键纪律

- **框架托管单实例**：每类型由 `DrClassMap` + `PluginsManager` 管理，整个应用单实例。
- **配置声明**：在 `config.json` 的 `plugins` 数组中声明：
  ```json
  {
    "plugins": [
      {
        "name": "${plugin_name}",
        "config": { /* 传给 initAndStart 的 Json::Value */ }
      }
    ]
  }
  ```
- **初始化时机**：`initAndStart()` 在 `app().run()` **之前**被**同步**调用。**禁止**在其中做阻塞操作（会阻塞框架启动，与"事件循环线程不可阻塞"一致）；耗时初始化走 `std::async` 或独立线程。
- **获取实例**：业务代码用 `app().getPlugin<${plugin_name}>()` 获取单例。**禁止**手动 `new` Plugin。
- 证据：`plugins/Plugin.h:67-71`

## 三者职责边界（Plugin / Filter / Middleware）

三者不得混用——职责不同，注册方式不同，生命周期不同：

| 类型 | 用途 | 注册方式 | 生命周期 |
|------|------|---------|---------|
| **Plugin** | 系统级扩展（连接池、第三方 SDK、全局资源） | 配置文件 `plugins` 数组 | 应用级（启动时初始化，关闭时销毁） |
| **Filter** | 请求拦截（鉴权、限流、输入校验） | `app().registerFilter(...)` | 请求级（每请求链上实例） |
| **Middleware** | 全局处理链（日志、CORS、性能计时） | `app().registerMiddleware(...)` | 请求级（贯穿所有请求） |

**禁止**：
- Plugin 处理请求（用 Filter / Middleware）
- Filter 做全局逻辑（用 Middleware / Plugin）
- Middleware 初始化资源（用 Plugin）

生成 Filter 用 `drogon-gen-filter`，生成 Middleware 用 `drogon-gen-middleware`。

## Code generation

### 类定义 + 头文件

```cpp
// plugins/${plugin_name}.h
#pragma once
#include <drogon/Plugin.h>

class ${plugin_name} : public drogon::Plugin<${plugin_name}> {
  public:
    ${plugin_name}() = default;
    void initAndStart(const Json::Value &config) override;
    void shutdown() override;

    // 业务接口（供其他模块通过 getPlugin<...>() 调用）
    // 按 purpose 暴露相应方法
};
```

### initAndStart / shutdown 实现

```cpp
// plugins/${plugin_name}.cc
#include "${plugin_name}.h"

void ${plugin_name}::initAndStart(const Json::Value &config) {
    int maxConn = config.get("max_connections", 10).asInt();
    // 初始化（耗时操作用 std::async，勿阻塞）
    LOG_INFO << "${plugin_name} started, max_connections=" << maxConn;
}

void ${plugin_name}::shutdown() {
    // 清理资源
    LOG_INFO << "${plugin_name} shut down";
}
```

### 配置片段

```json
{
  "plugins": [
    {
      "name": "${plugin_name}",
      "config": {
        // 按 config_keys 展开
      }
    }
  ]
}
```

## Key rules

1. Plugin 继承 `drogon::Plugin<T>`，实现 `initAndStart` + `shutdown`。
2. `initAndStart` 在 `run()` 前同步调用——**禁止**阻塞，耗时用 `std::async`。
3. 配置经 `config.json` 的 `plugins` 数组声明，`config` 字段传给 `initAndStart`。
4. 业务侧用 `app().getPlugin<T>()()` 获取单例，**禁止**手动 `new`。
5. Plugin 不处理请求；请求拦截用 Filter，全局处理链用 Middleware。

## Error handling

- `plugin_name` 为空：返回错误消息
- `purpose` 为空：返回错误消息
- `config_keys` 格式无效：返回错误消息
