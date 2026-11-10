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
- `connection_number`: 连接数（**默认 1**，`ConfigLoader.cc:557`；别名 `number_of_connections` 只在 `connection_number` 解析结果恰为 1 时才被读取，`:558-561`）

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

- 错误键名只有两个：`db_name`（正确 `dbname`）、`username`（正确 `user`；`username` 是 **redis_clients** 段的键，`ConfigLoader.cc:614`，写在 db 段不生效）。
- `password` **不是**错误键：源码先读 `passwd`，为空时回落读 `password`（`ConfigLoader.cc:552-556`），所以它是**合法回落键**，只是非首选。生成时统一写 `passwd`；见到用户已有 `password` 不要当错误改掉。
- `port` / `connection_number` 必须是整数（写成字符串 `asUInt()` 取不到值）。
- SQLite 用 `filename`；`connection_number` 大于 1 是**合法**配置（`DbClientImpl.cc:87-96` 会建出 N 条连接），只是 SQLite 的 loop 数被压成 1（`:62-67`）并由 `SharedMutex` 串行化，并发收益有限——别说成"必须为 1"。
- SQLite 段里的 `host` / `port` / `is_fast` 会被**静默丢弃**：`HttpAppFrameworkImpl.cc:999-1002` 构造 `Sqlite3Config{connectionNum, filename, name, timeout}` 只取这四项，配了不报错、也不生效。
- 键名和值必须与上方模板严格一致。

## 运行期错误处理纪律

数据库相关的运行期规则（生成配置时一并提示用户）：

- **`loadConfigFile` 失败**：抛出的 `std::runtime_error` 全是**配置文件层面**的错误——`:113` 文件不存在、`:117` 无读权限、`:124` 文件名没有扩展名、`:139` JSON/YAML 解析失败、`:301` `static_file_headers` 不是数组；与数据库相关的只有 `:545-549`（PG/MySQL 的 `dbname` 为空）。**数据库连不上不会在这里抛**：SQLite 打开失败只 `LOG_FATAL` + 走失败回调（`orm_lib/src/sqlite3_impl/Sqlite3Connection.cc:116-127`），PG/MySQL 的连接失败在运行期以 `DrogonDbException` / 失败回调呈现。`loadConfigFile()` 外层仍**必须** try/catch，但别把它当成"连接失败的防护"——它管不到连接。
- **运行期 `DrogonDbException`**（如唯一键冲突）：在异步 Mapper 的失败回调中 `callback(错误响应)` 并 `LOG_ERROR` 记录，**禁止**忽略异常、**禁止**只写成功回调忘了失败回调。
- **SQL 注入防护**：`Mapper<T>` 方法（`findBy` / `findOne` / `deleteBy` / `updateBy`）经 `Criteria` 自动参数化。**禁止**手动拼接 SQL 字符串；必须手写 SQL 时用 `$1`/`$2` 占位符 + 参数传递。

## 禁止模式清单

- **禁止**db 段写 `db_name` / `username`（应为 `dbname` / `user`）；`password` 不在禁止之列，它是 `passwd` 为空时的合法回落键。
- **禁止**把 `port` / `connection_number` 写成字符串——必须是整数。
- **禁止**把 SQLite 写成需要 `host` / `port`：只用 `filename`，多写的 `host`/`port`/`is_fast` 会被静默丢弃。`connection_number` 可以大于 1（合法，只是并发收益有限），**禁止**把它说成"必须为 1"这种非法配置。
- **禁止**在 `loadConfigFile()` 外层漏掉 try/catch——但它只挡配置文件层面的错误，挡不住数据库连不上（后者在运行期以 `DrogonDbException` / 失败回调呈现）。
- **禁止**手动拼接 SQL 字符串（SQL 注入）；必须手写 SQL 时用 `$1` / `$2` 占位符 + 参数绑定。
- **禁止**只实现成功回调而漏掉失败回调——`DrogonDbException` 会被静默吞掉。

## 错误处理

- `db_type` 无效：返回错误消息
- SQLite 配置中使用了 `host`/`port`：返回错误消息
- PostgreSQL/MySQL 配置中缺少必需字段：返回错误消息