# drogon-gen-db-config

生成 drogon 项目的数据库配置（`config.json` 片段）。

## 使用场景

当需要配置数据库连接时，使用此技能快速生成符合 drogon 约定的数据库配置。

## 输入参数

- `db_type`: 数据库类型（`postgresql`、`mysql`、`sqlite3`）
- `name`: 客户端名称（默认 `default`）
- `host`: 主机地址（PostgreSQL/MySQL）
- `port`: 端口（PostgreSQL/MySQL）
- `dbname`: 数据库名（PostgreSQL/MySQL）
- `filename`: 文件路径（SQLite）
- `user`: 用户名（PostgreSQL/MySQL）
- `passwd`: 密码（PostgreSQL/MySQL）
- `connection_number`: 连接数（默认 10）

## 输出

生成 `config.json` 片段，包含正确的 `db_clients` 配置。

## 示例

```
/drogon-gen-db-config db_type=postgresql host=localhost port=5432 dbname=mydb user=postgres
```

生成 PostgreSQL 配置片段。