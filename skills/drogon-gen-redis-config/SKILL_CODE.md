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

## 错误处理

- `port` 不是有效的端口号：返回错误消息
- `db` 不是有效的数据库编号：返回错误消息
- 配置格式错误：返回错误消息