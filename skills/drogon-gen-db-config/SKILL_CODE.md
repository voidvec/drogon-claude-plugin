# drogon-gen-db-config Implementation

## 输入解析

从用户输入中提取：
- `db_type`: 数据库类型（必需）
- `name`: 客户端名称（默认 `default`）
- `host`: 主机地址（PostgreSQL/MySQL）
- `port`: 端口（PostgreSQL/MySQL）
- `dbname`: 数据库名（PostgreSQL/MySQL）
- `filename`: 文件路径（SQLite）
- `user`: 用户名（PostgreSQL/MySQL）
- `passwd`: 密码（PostgreSQL/MySQL）
- `connection_number`: 连接数（默认 10）

## 配置模板

**postgresql**：
```json
{
  "name": "${name}",
  "rdbms": "postgresql",
  "host": "${host}",
  "port": ${port},
  "dbname": "${dbname}",
  "user": "${user}",
  "passwd": "${passwd}",
  "is_fast": false,
  "connection_number": ${connection_number}
}
```

**mysql**：
```json
{
  "name": "${name}",
  "rdbms": "mysql",
  "host": "${host}",
  "port": ${port},
  "dbname": "${dbname}",
  "user": "${user}",
  "passwd": "${passwd}",
  "is_fast": false,
  "connection_number": ${connection_number}
}
```

**sqlite3**：
```json
{
  "name": "${name}",
  "rdbms": "sqlite3",
  "filename": "${filename}",
  "is_fast": false,
  "connection_number": 1
}
```

## 文件生成

1. 根据 `db_type` 选择对应的配置模板
2. 将模板中的变量替换为实际值
3. 生成 `db_clients` 片段（用户需手动嵌入到 `config.json`）

## 错误处理

- `db_type` 无效：返回错误消息
- SQLite 配置中使用了 `host`/`port`：返回错误消息
- PostgreSQL/MySQL 配置中缺少必需字段：返回错误消息