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

## 键名纪律（高频陷阱）

- **禁止**错误键名：`db_name`（正确 `dbname`）、`username`（正确 `user`）、`password`（正确 `passwd`）。
- **禁止**把 `port` 写成字符串（必须是整数）。
- SQLite 用 `filename`（**禁止** `host`/`port`），且 `connection_number` 必须为 1。
- 键名和值必须与上方模板严格一致。

## 运行期错误处理纪律

数据库相关的运行期规则（生成配置时一并提示用户）：

- **`loadConfigFile` 失败**：连接失败时抛 `std::runtime_error`（源码 `ConfigLoader.cc:113/117/124/139/301`）。**必须**在 `loadConfigFile()` 外层 try/catch，捕获后退出或回退到无数据库模式，**禁止**忽略。
- **运行期 `DrogonDbException`**（如唯一键冲突）：在异步 Mapper 的失败回调中 `callback(错误响应)` 并 `LOG_ERROR` 记录，**禁止**忽略异常、**禁止**只写成功回调忘了失败回调。
- **SQL 注入防护**：`Mapper<T>` 方法（`findBy` / `findByCriteria`）自动参数化。**禁止**手动拼接 SQL 字符串；必须手写 SQL 时用 `$1`/`$2` 占位符 + 参数传递。

## 错误处理

- `db_type` 无效：返回错误消息
- SQLite 配置中使用了 `host`/`port`：返回错误消息
- PostgreSQL/MySQL 配置中缺少必需字段：返回错误消息