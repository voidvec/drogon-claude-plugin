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

### 完整生命周期（v1.9.13 源码核对）

时序链条（`HttpAppFrameworkImpl.cc:608-693` `run()` + `PluginsManager.cc`）：

1. **构造**：`run()` 内 `initializeAllPlugins`（`HttpAppFrameworkImpl.cc:663-675`）先按配置数组逐个 `createPlugin(name)`——经 `DrClassMap::newSharedObject` 反射构造（`PluginsManager.cc:90-100`），全部构造完再进入下一步。
2. **依赖解析**：每个插件 `setConfig(config)` 后处理 `dependencies` 数组，`addDependency` 建立依赖边（`PluginsManager.cc:56-75`）；**依赖的插件未在配置中声明会 `LOG_FATAL` + `abort`**（`PluginsManager.cc:70-72`）。
3. **initialize（深度优先）**：按声明顺序调 `plugin->initialize()`（`PluginsManager.cc:82-87`）；`initialize()` 先递归初始化依赖再调 `initAndStart(config_)`，循环依赖直接 `LOG_FATAL` + `abort`（`Plugin.h:40-63`）。
4. **run 阶段可用资源**：`initAndStart` 执行时，DB/Redis 客户端已经建好——`run()` 里 `createDbClients`/`createRedisClients`（`HttpAppFrameworkImpl.cc:636-637`）在 `initializeAllPlugins`（`:663`）**之前**；因此在 `initAndStart` 内 `app().getDbClient()` 可用（pay-plugin `PayPlugin.cc:107` 实测）。但普通业务代码在 `run()` 之前**不可**取客户端。
5. **BeginningAdvice 阶段**：所有插件初始化完成后，路由 init，随后 `getLoop()->queueInLoop` 依次执行全部 BeginningAdvice，最后 `startListening()`（`HttpAppFrameworkImpl.cc:676-686`）——见下文「初始化时序」。
6. **shutdown()**：应用退出时 `app().quit()` 在主循环内按初始化**逆序**销毁各组件（`HttpAppFrameworkImpl.cc:1034-1056`）：`stopListening` → 路由 reset → **`pluginsManagerPtr_.reset()`（触发 `~PluginsManager` 按初始化逆序逐个调 `shutdown()`，`PluginsManager.cc:20-29`）** → Redis/DB manager reset → loop quit。两个推论：
   - `shutdown()` 里**仍可安全使用** DB/Redis 客户端做最后清理（它们的销毁在插件之后）；
   - `shutdown()` 在**主事件循环线程**执行，同样禁止阻塞。

### initAndStart 读取配置的正确姿势（pay-plugin 模式）

```cpp
void ${plugin_name}::initAndStart(const Json::Value &config)
{
    // 1. 标量：get(key, 默认值) 一律带 fallback
    const std::string dbClientName = config.get("db_client", "default").asString();
    basePath_ = config.get("base_path", "/api/pay").asString();

    // 2. 子对象：先 isObject() 再用
    const Json::Value &reconcileCfg = config["reconcile"];
    if (reconcileCfg.isObject())
    {
        interval = reconcileCfg.get("interval_seconds", 0).asInt();
    }

    // 3. 数值可选键：isMember + 类型断言双守卫
    if (config.isMember("idempotency_ttl_seconds")
        && config["idempotency_ttl_seconds"].isInt64())
    {
        ttl = config["idempotency_ttl_seconds"].asInt64();
    }

    // 4. 可选基础设施：先判配置键存在再 getXxxClient —— 对未配置的名字调
    //    getRedisClient 会用 operator[] 往 manager map 插入空项，退出析构时
    //    解引用崩溃（pay-plugin PayPlugin.cc:113-125 实测坑）
    if (config.isMember("redis_client"))
    {
        redisClient_ = drogon::app().getRedisClient(config["redis_client"].asString());
    }
}
```

**禁止**：
- 裸 `config["key"].asString()`（键缺失时 jsoncpp 返回默认构造值，静默错误）。
- 对可选客户端**无条件**调 `getRedisClient`/`getDbClient`（见上 4）。
- 静默忽略过时配置键——检测到旧 schema 时给出可操作的迁移报错并 `throw std::runtime_error` 拒绝启动（pay-plugin `PayPlugin.cc:90-101` 的 legacy key 模式）。

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

## 专属 EventLoopThread worker 模式（pay-plugin 实测）

**为何**：插件里的长任务/周期任务（对账扫描、证书刷新、批量推送）**禁止**跑在 app 的 IO 事件循环上——IO loop 被占用即所有请求被卡住。`std::async`/裸 `std::thread` 又没有事件循环语义（定时器、串行化队列）。解法是插件自持一个 `trantor::EventLoopThread`（pay-plugin `PayPlugin.cc:205-233`）：

```cpp
// ${plugin_name}.h
#include <trantor/net/EventLoopThread.h>
std::unique_ptr<trantor::EventLoopThread> workerLoopThread_;
trantor::TimerId certRefreshTimerId_{0};   // 记住定时器 id，shutdown 时失效

// initAndStart 内：
workerLoopThread_ = std::make_unique<trantor::EventLoopThread>("${plugin_name}Worker");
workerLoopThread_->run();
auto *workerLoop = workerLoopThread_->getLoop();

// 周期任务挂 worker 的循环上（不是 app().getLoop()）
startReconcileTimer(workerLoop);

// 一次性启动钩子也投递到 worker，不占 app 主循环
workerLoop->runInLoop([this]() { /* 预热/自注册 */ });
```

worker 上的任务天然在**该线程内串行**（runInLoop 队列语义），插件成员无锁访问仅限"只在 worker 线程碰"的数据；跨线程共享仍需回调/原子量。

## shutdown() 优雅排水模式（骨架）

目标：停定时器 → 停接入 → 排空 worker 上 in-flight 任务 → 再拆线程（pay-plugin `PayPlugin.cc:338-370` 实测）：

```cpp
void ${plugin_name}::shutdown()
{
    // 1. 先让业务停止产生新工作（停对账/调度定时器）
    stopTimers();

    if (workerLoopThread_)
    {
        auto *workerLoop = workerLoopThread_->getLoop();
        // 2. 失效周期定时器（在属主循环上调 invalidateTimer）
        if (certRefreshTimerId_)
        {
            workerLoop->invalidateTimer(certRefreshTimerId_);
            certRefreshTimerId_ = 0;
        }
        // 3. 停外部接入（渠道/SDK 的 stopAll）
        stopChannels();
        // 4. 排水哨兵：向队尾投一个 set_value 任务，future 满足即说明
        //    它之前的所有 in-flight 任务都已执行完
        std::promise<void> drained;
        workerLoop->runInLoop([&drained]() { drained.set_value(); });
        drained.get_future().wait();     // wait() 而非 get()：不吞不抛异常
        // 5. 线程收尾（EventLoopThread 析构 join）
        workerLoopThread_.reset();
    }
    else
    {
        stopChannels();
    }
}
```

纪律：
- `invalidateTimer` **必须**在该定时器所属的循环上调（worker 上的定时器在 workerLoop 上失效）。
- 排水用 `std::promise` + `runInLoop` 哨兵（`PayPlugin.cc:358-361`）；**禁止**用 `sleep`/自旋计数猜任务何时跑完。
- `shutdown()` 在主循环线程执行（`HttpAppFrameworkImpl.cc:1034-1056`），排水 `wait()` 的时间必须有限（worker 任务都应是短任务），否则交换卡死。

## 静态库 DrObject 自动注册丢失（ensureLinked 对策）

Plugin 依赖 `DrObject` 静态初始化自注册（`DrClassMap`）。当插件代码被编译进**静态库**、且宿主没有直接引用其中符号时，链接器会裁剪该 object file——症状是 `app().getPlugin<T>()` 返回空指针、配置里声明了插件却 `createPlugin` 找不到类（pay-plugin `docs/development/plugin_integration.md:46-48`）。

对策（pay-plugin `PayPlugin.cc:20-30`）：库里放一个外部链接的锚函数，宿主 `main()` 首行调用：

```cpp
// 插件库内（PayPlugin.cc:20-30 模式）
namespace ${namespace}
{
// 引用插件类强制链接器保留此 object file（连带 DrObject 注册符号）
void ensureLinked()
{
    static ${plugin_name} *volatile anchor = nullptr;
    (void)anchor;
}
}

// 宿主 main.cc
int main()
{
    ${namespace}::ensureLinked();   // 静态链接安全网，必须最先调用
    drogon::app().loadConfigFile("config.json");
    drogon::app().run();
}
```

连带规则：
- 静态库插件里的控制器**禁止**依赖 `ADD_METHOD_TO` 宏静态注册（同样会被裁剪）；用 `app().registerHandler` 程序化注册（pay-plugin `PayPlugin.cc:235-237` 注释 + `registerHttpHandlers()`）。
- 生成静态库形态的插件时，**必须**同时生成 `ensureLinked()` 并在文档/main 模板中调用（"可选但推荐"仅当宿主 100% 会引用插件符号）。

## 初始化时序：plugin initialize 与 BeginningAdvice

源码顺序（`HttpAppFrameworkImpl.cc:636-686`）：`createDbClients/createRedisClients` → **所有插件 `initAndStart`** → 路由 init → **BeginningAdvice 依次执行** → `startListening()`。authforge 全项目 15 处 `registerBeginningAdvice`（main.cc 8 处 + 库层 7 处）沉淀出的分工：

**放在插件 `initAndStart` 里**（客户端可用、无需完整路由表）：
- 建 DB/Redis 客户端引用、构造服务对象（pay-plugin 全部在 initAndStart 内完成）
- 周期任务/worker 启动
- 配置校验与快速失败

**必须等 BeginningAdvice**（此时全部插件已初始化、全部路由已注册）：
- **getPlugin<T>() 取插件指针并注入**控制器/过滤器的接线——"必须在插件构造之后"（authforge `main.cc:223-226` 注释：`wireControllerPluginDependencies`，回调注册顺序在控制器注册之后）
- **依赖完整路由表的一致性校验**——如 scope/权限注册表 vs `getHandlersInfo()` 比对，`LOG_FATAL` 阻止带病上线（authforge `main.cc:210-217`：`ResourceScopeRegistry::runConsistencyCheck`，注释明言"runs inside run() (after registerAllControllers) so getHandlersInfo() is fully populated"）
- 依赖"监听已开始/主循环已跑"的运行态上报

补充纪律：
- BeginningAdvice 按**注册顺序**执行（authforge `main.cc:236` 注释；`HttpAppFrameworkImpl.cc:675` 遍历 vector），有依赖关系的接线**必须**按依赖序注册。
- main() 里 `run()` **之前**的代码**禁止**调 `getPlugin`/`getDbClient`（插件与客户端都还没建）。

## Key rules

1. Plugin 继承 `drogon::Plugin<T>`，实现 `initAndStart` + `shutdown`。
2. `initAndStart` 在 `run()` 前同步调用——**禁止**阻塞，耗时用 `std::async`。
3. 配置经 `config.json` 的 `plugins` 数组声明，`config` 字段传给 `initAndStart`。
4. 业务侧用 `app().getPlugin<T>()()` 获取单例，**禁止**手动 `new`。
5. Plugin 不处理请求；请求拦截用 Filter，全局处理链用 Middleware。
6. 生命周期：`initAndStart` 时 DB/Redis 客户端已可用；`shutdown()` 按初始化逆序在主循环线程执行，DB/Redis 客户端此刻仍在——**禁止**在 shutdown 里先拆客户端。
7. 长任务/定时器挂插件专属 `trantor::EventLoopThread`，**禁止**占用 app 事件循环。
8. `shutdown()` 排水用 promise 哨兵 + `invalidateTimer`，**禁止** sleep 猜测。
9. 静态库插件**必须**提供并在 main 调用 `ensureLinked()`；控制器注册走 `registerHandler`。
10. 需要插件指针接线或完整路由表的逻辑放 BeginningAdvice，且按依赖序注册。

## 禁止模式清单

- **禁止**在 `initAndStart` 里阻塞（它在 `run()` 前同步执行）；耗时初始化丢 `std::async` 或线程池。
- **禁止**在 `run()` 之前调用 `getPlugin` / `getDbClient`（插件与客户端尚未创建）。
- **禁止**在 `shutdown()` 里先拆 DB/Redis 客户端——客户端此刻仍在，按初始化逆序清理。
- **禁止**占用 app 全局事件循环跑长任务/定时器；用插件专属 `trantor::EventLoopThread`。
- **禁止**用 `sleep` 猜测排水完成；用 promise 哨兵 + `invalidateTimer`。
- **禁止**在业务代码里手动 `new Plugin()`；用 `app().getPlugin<T>()()`。
- **禁止**依赖静态库插件的隐式自动注册——**必须**提供并在 `main` 调用 `ensureLinked()`。

## Error handling

- `plugin_name` 为空：返回错误消息
- `purpose` 为空：返回错误消息
- `config_keys` 格式无效：返回错误消息
