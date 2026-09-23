# drogon-gen-redis-config Implementation

## 输入解析

从用户输入中提取：
- `name`: 客户端名称（默认 `default`）
- `host`: Redis 主机地址（默认 `127.0.0.1`）
- `port`: Redis 端口（默认 6379）
- `username`: 用户名（默认空）
- `passwd`: 密码（默认空）
- `db`: 数据库编号（默认 0）
- `is_fast`: 是否使用快速模式（默认 `false`）
- `connection_number`: 连接数（默认 1）
- `timeout`: 超时时间（默认 `-1.0`）

## 配置模板

```json
{
  "name": "${name}",
  "host": "${host}",
  "port": ${port},
  "username": "${username}",
  "passwd": "${passwd}",
  "db": ${db},
  "is_fast": ${is_fast},
  "connection_number": ${connection_number},
  "timeout": ${timeout}
}
```

## 文件生成

1. 将模板中的变量替换为实际值
2. 生成 `redis_clients` 片段（用户需手动嵌入到 `config.json`）

## 键名纪律

- **禁止**错误键名：`password`（正确 `passwd`）、`database`（正确 `db`）。
- **禁止**把 `port` 写成字符串（必须是整数）。
- `username` 字段为 Redis 6.0+ ACL 支持，早期版本留空。
- 键名和值必须与上方模板严格一致（源码 `ConfigLoader.cc:606-638`）。
- 键名精确区间为 `loadRedisClients`（`ConfigLoader.cc:600-640`）。两个后备键可被接受但**不推荐**主动生成：`password` 作为 `passwd` 为空时的回退（`ConfigLoader.cc:616-619`）、`number_of_connections` 作为 `connection_number` 为 1 时的回退（`ConfigLoader.cc:620-624`）——DB 客户端同理（`ConfigLoader.cc:553-561`）。
- `is_fast: true` 的客户端**只**能调 `getFastRedisClient()` 获取，`timeout` 为零或负值表示无超时（`config.example.json:91-99`）。

## 头文件与命名空间（v1.9.13 源码核对）

```cpp
#include <drogon/nosql/RedisClient.h>        // 类：drogon::nosql::RedisClient
#include <drogon/nosql/RedisResult.h>        // drogon::nosql::RedisResult（RedisResult.h）
#include <drogon/nosql/RedisException.h>     // drogon::nosql::RedisException（RedisException.h）
#include <drogon/nosql/RedisSubscriber.h>    // drogon::nosql::RedisSubscriber（RedisSubscriber.h）
```

- **禁止**`#include <drogon/redis/RedisClient.h>`（路径不存在）；真实头文件在 `nosql_lib/redis/inc/drogon/nosql/RedisClient.h`。
- 类型别名：`RedisClientPtr = std::shared_ptr<RedisClient>`（`RedisClient.h:357`）。
- 回调类型（生成代码时按此签名写 lambda）：
  - `RedisResultCallback = std::function<void(const RedisResult &)>`（`RedisResult.h:127`）
  - `RedisExceptionCallback = std::function<void(const RedisException &)>`（`RedisException.h:67`）

## execCommandAsync 完整模式

### 客户端获取

```cpp
// 框架 run() 之后才可调用（HttpAppFramework.h:1408-1412 注释明示）
drogon::nosql::RedisClientPtr client = drogon::app().getRedisClient();            // name="default"
drogon::nosql::RedisClientPtr fast  = drogon::app().getFastRedisClient("cache"); // is_fast 客户端
```

签名：`getRedisClient(const std::string &name = "default")` / `getFastRedisClient(const std::string &name = "default")`（`HttpAppFramework.h:1413`/`:1421`）。
**禁止**对未在 `redis_clients` 配置过的名字调 `getRedisClient`——manager 内部 `operator[]` 会插入空指针项，退出析构时解引用崩溃（pay-plugin `PayPlugin.cc:114-117` 注释记录的实测坑）。可选依赖必须先判配置再查询。

### 命令 + 双回调模板

```cpp
client->execCommandAsync(
    [](const drogon::nosql::RedisResult &r) {
        LOG_DEBUG << "redis reply: " << r.getStringForDisplaying();
    },
    [](const drogon::nosql::RedisException &e) {
        LOG_ERROR << "redis error: " << e.what();
    },
    "get %s",
    key.c_str());
```

签名：`execCommandAsync(RedisResultCallback &&, RedisExceptionCallback &&, std::string_view command, ...) noexcept`（`RedisClient.h:128-131`）。
- 失败回调收到的异常类型是 **`RedisException`**（不是 `DrogonDbException`——那是 ORM 层的异常基类，Redis 命名空间没有它）。
- `execCommandSync` 确实存在（`RedisClient.h:162-201`），但内部是 `promise/future` 阻塞等待（`:200` `prom.get_future().get()`）——**禁止**在事件循环线程调用，否则死锁/卡顿。

### 占位符格式语义（防注入）

命令字符串经 hiredis 的 `redisvFormatCommand` 格式化（`RedisConnection.h:74-78` `getFormattedCommand`），占位符语义：

| 占位符 | 参数 | 说明 |
|--------|------|------|
| `%s` | `const char*`（NUL 结尾字符串） | 值含 `\0` 会被截断 |
| `%b` | `const void*` + `size_t` 两个参数 | **二进制安全**，按长度编码 |
| `%d` 等整型 | 整数 | printf 语义 |

- **禁止**把用户输入 `sprintf`/拼接进命令字符串（Redis 注入）；**必须**用占位符传参：`execCommandAsync(ok, err, "set %s %s", key.c_str(), val.c_str())`。
- 二进制值（序列化 blob、密钥）用 `%b`：`execCommandAsync(ok, err, "set %s %b", key.c_str(), data.data(), data.size())`。
- 格式非法时 hiredis 返回 -2，drogon 转成 `RedisException`（`kInternalError`/格式错误，`RedisConnection.h:74-85`）经失败回调传入。

## 订阅模式（真实 API）

订阅入口是 `RedisClient::newSubscriber()`（`RedisClient.h:210`，注释：创建一条**专用于订阅命令的新连接**，由该 RedisClient 托管）。**没有** `subscribeAsync` / `newSubscription` 这样的 API。

```cpp
auto subscriber = client->newSubscriber();   // std::shared_ptr<RedisSubscriber>

subscriber->subscribe("orders.events",
    [](const drogon::nosql::RedisResult &msg) {
        // 消息回调：在该订阅连接的 IO 循环线程触发
        // 禁止阻塞、禁止长计算——会卡住该连接上的后续消息分发
        LOG_DEBUG << "received: " << msg.getStringForDisplaying();
    });

// 模式订阅 / 退订
subscriber->psubscribe("orders.*", onMsg);     // RedisSubscriber.h:42-44
subscriber->unsubscribe("orders.events");      // RedisSubscriber.h:53
subscriber->punsubscribe("orders.*");          // RedisSubscriber.h:56
```

- 签名：`subscribe(channel, RedisMessageCallback &&)` / `psubscribe(pattern, cb)` / `unsubscribe(channel)` / `punsubscribe(pattern)`（`RedisSubscriber.h:38-56`）。
- 同一 channel 多次 `subscribe` 合法：回调按订阅顺序依次调用，一次 `unsubscribe` 移除全部（`RedisSubscriber.h:34-36` 注释）。
- **unsubscribe 防泄漏纪律**：订阅会一直持有连接直到 `unsubscribe()` 被调用、或 subscriber 与创建它的 RedisClient 均析构（`RedisSubscriber.h:26-28` 原文）。持有 subscriber 的类**必须**在析构/`shutdown()` 中对每个活跃 channel 调 `unsubscribe()` 兜底，**禁止**"订阅后丢弃 subscriber 指针"。

## 协程（execCommandCoro）

```cpp
#include <drogon/drogon.h>   // USE_COROUTINE 宏需在编译定义中

drogon::Task<> readCache(std::string key)
{
    try
    {
        auto client = drogon::app().getFastRedisClient();
        auto result = co_await client->execCommandCoro("get %s", key.c_str());
        LOG_DEBUG << result.getStringForDisplaying();
    }
    catch (const drogon::nosql::RedisException &e)
    {
        LOG_ERROR << "redis error: " << e.what();
    }
}
```

签名：`execCommandCoro(std::string_view command, Arguments... args)` 返回 `internal::RedisAwaiter`，`co_await` 得 `RedisResult`，异常经 `co_await` 抛出（`RedisClient.h:274-288`；示例见 `:262-272` 官方注释）。事务有对应的 `newTransactionCoro()`（`RedisClient.h:308-311`）。

## 常用命令速查（execCommandAsync 写法）

```cpp
// GET
client->execCommandAsync(ok, err, "get %s", key.c_str());

// SET + TTL（一步带过期）
client->execCommandAsync(ok, err, "set %s %s ex %d", key.c_str(), val.c_str(), 300);

// INCR
client->execCommandAsync(
    [](const drogon::nosql::RedisResult &r) {
        long long n = r.asInteger();      // 结果取整数
    },
    err, "incr %s", counter.c_str());

// EXPIRE（秒；要毫秒精度用 pexpire + 毫秒值）
client->execCommandAsync(ok, err, "expire %s %d", key.c_str(), 300);

// DEL（可变 key 数用多个 %s）
client->execCommandAsync(ok, err, "del %s %s", k1.c_str(), k2.c_str());
```

注意：`asInteger()` 的可用性以 `RedisResult.h` 的接口为准；写入 SET 的值若可能含 `\0` 或任意字节，改用 `%b` 二进制安全占位符。

## 运行期使用纪律（生成配置时一并提示用户）

- **单例**：通过 `app().getRedisClient()` 获取客户端，**禁止**手动 `std::make_shared<RedisClient>(...)`（框架启动时已创建单例）。
- **全异步**：`RedisClient` 所有操作（`set`/`get`/`lpush` 等）都是异步的，结果经回调返回。**禁止**假设同步完成，**禁止**用 `execCommand<T>` 同步重载（无法获取结果）。用 `execCommandAsync(successCb, failureCb, "CMD", args...)`。
- **错误处理**：`RedisException` 经失败回调传入，**禁止**忽略——失败回调中 `callback(错误响应)` + `LOG_ERROR`，确保响应被发送。
- **订阅防泄漏**（`RedisSubscriber`）：`subscribe()` 后**必须**在合适时机 `unsubscribe()`，否则资源泄漏（源码 `RedisSubscriber.h:26-28`："until unsubscribe() is called ... or the subscriber/RedisClient who creates it no longer exists"）。订阅者析构函数应调用 `unsubscribe()` 兜底。

## 禁止模式清单

- **禁止**错误键名：`password`（应为 `passwd`）、`db_name` / `database`（应为 `db`）、`host` / `port` 层级写错。
- **禁止**手动 `std::make_shared<RedisClient>(...)`——用 `app().getRedisClient()` 单例。
- **禁止**使用同步重载 `execCommand<T>` 期待拿到结果——用 `execCommandAsync(successCb, failureCb, ...)`。
- **禁止**漏掉失败回调：`RedisException` 经失败回调传入，必须 `callback(错误响应)` + `LOG_ERROR`。
- **禁止**订阅后不 `unsubscribe()`（资源泄漏）；订阅者析构应兜底调用。
- **禁止**在事件循环线程做阻塞 Redis 操作——本项目所有 Redis 调用都必须异步。
- **禁止**把用户输入直接拼进命令字符串；参数用列表传递，二进制安全用 `%b`。

## 错误处理

- `port` 不是有效的端口号：返回错误消息
- `db` 不是有效的数据库编号：返回错误消息
- 配置格式错误：返回错误消息
