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

## 运行期使用纪律（生成配置时一并提示用户）

- **单例**：通过 `app().getRedisClient()` 获取客户端，**禁止**手动 `std::make_shared<RedisClient>(...)`（框架启动时已创建单例）。
- **全异步**：`RedisClient` 所有操作（`set`/`get`/`lpush` 等）都是异步的，结果经回调返回。**禁止**假设同步完成，**禁止**用 `execCommand<T>` 同步重载（无法获取结果）。用 `execCommandAsync(successCb, failureCb, "CMD", args...)`。
- **错误处理**：`RedisException` 经失败回调传入，**禁止**忽略——失败回调中 `callback(错误响应)` + `LOG_ERROR`，确保响应被发送。
- **订阅防泄漏**（`RedisSubscriber`）：`subscribe()` 后**必须**在合适时机 `unsubscribe()`，否则资源泄漏（源码 `RedisSubscriber.h:26-28`："until unsubscribe() is called ... or the subscriber/RedisClient who creates it no longer exists"）。订阅者析构函数应调用 `unsubscribe()` 兜底。

## 错误处理

- `port` 不是有效的端口号：返回错误消息
- `db` 不是有效的数据库编号：返回错误消息
- 配置格式错误：返回错误消息