---
name: drogon-gen-orm-crud
description: 生成符合 drogon 约定的 ORM CRUD 代码，支持回调式和协程式，覆盖 PostgreSQL、MySQL、SQLite3。
version: 0.1.0
---

# drogon-gen-orm-crud

生成符合 drogon 约定的 ORM CRUD 代码，支持回调式和协程式。

## 使用场景

当需要编写数据库查询/插入/更新/删除代码时，使用此技能快速生成符合 drogon 约定的代码。

## 输入参数

- `db_type`: 数据库类型（`postgresql`、`mysql`、`sqlite3`）
- `table_name`: 表名
- `operation_type`: 操作类型（`select`、`insert`、`update`、`delete`、`batch_insert`）
- `use_coroutine`: 是否使用协程（`true`/`false`，默认 `true`）

## 输出

1. 生成符合 drogon 约定的 ORM CRUD 代码（回调式或协程式）
2. 说明：
   - 如何获取 `Mapper<T>` 或 `CoroMapper<T>`
   - 如何处理异步回调或协程
   - 如何处理错误（`DrogonDbException`）
   - 如何处理事务（如需要）

## 示例

```
/drogon-gen-orm-crud db_type=postgresql table_name=users operation_type=select use_coroutine=true
```

生成协程式的用户查询代码。
## 参考文件
详细实现指南见 `references/code-guide.md`（含参数验证、代码模板、禁止模式清单）。生成代码前先读取该文件。
