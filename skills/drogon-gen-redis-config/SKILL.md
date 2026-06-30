---
name: drogon-gen-redis-config
description: 生成 drogon 项目的 Redis 配置（config.json 片段）。
version: 0.1.0
---

# drogon-gen-redis-config

生成 drogon 项目的 Redis 配置（`config.json` 片段）。

## 使用场景

当需要配置 Redis 连接时，使用此技能快速生成符合 drogon 约定的 Redis 配置。

## 输入参数

- `name`: 客户端名称（默认 `default`）
- `host`: Redis 主机地址（如 `127.0.0.1`）
- `port`: Redis 端口（默认 6379）
- `username`: 用户名（默认空，Redis 6.0+ ACL 支持）
- `passwd`: 密码（默认空）
- `db`: 数据库编号（默认 0）
- `is_fast`: 是否使用快速模式（默认 `false`）
- `connection_number`: 连接数（默认 1）
- `timeout`: 超时时间（默认 `-1.0`，表示无超时）

## 输出

生成 `config.json` 片段，包含正确的 `redis_clients` 配置。

## 示例

```
/drogon-gen-redis-config host=127.0.0.1 port=6379 db=0
```

生成 Redis 配置片段。