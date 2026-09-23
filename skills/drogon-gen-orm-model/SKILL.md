---
name: drogon-gen-orm-model
description: 需要从数据库表生成 drogon ORM 模型类（drogon_ctl create model + model.json）、配置关系映射、或把生成模型接入 CMake 时使用。
license: MIT
---

# drogon-gen-orm-model

用 `drogon_ctl create model` 从现有数据库（PostgreSQL / MySQL / SQLite3）生成 ORM 模型类并接入构建。

## 使用场景

当需要从数据库表生成 ORM 模型类（全库或单表 --table）、配置外键关系映射（自动检测 + 手工 relationships）、生成 restful 控制器骨架，或将生成模型接入 CMake（OBJECT library 隔离 + orm_compat.h 兼容 shim）时使用此技能。所有命令行参数与 model.json 字段以 drogon v1.9.13 源码为准。

## 输入参数

- `db_type`: `postgresql` / `mysql` / `sqlite3`
- `tables`: 表名列表（可选；空 = 全库所有表）
- `连接信息来源`: model.json 配置（host/port/dbname/user/passwd；sqlite3 用 filename）或由用户提供
- `relationships`: 是否生成关系映射（可选；外键自动检测 + 手工 has one/has many/many to many，默认关）
- `restful`: 是否同时生成 restful 控制器（可选，默认否）
- `output_dir`: 模型输出目录（可选；默认与 model.json 同目录，`-o` 分离）

## 输出

1. 每表一对 `<ClassName>.h/.cc`（`drogon_model::<dbname>` 命名空间，DO NOT EDIT）
2. `model.json` 生成配置（提交进版本库）
3. CMake 接入片段（OBJECT library 隔离 + orm_compat.h force-include）
4. `Mapper<T>` 插入/查询用法（回调式）

## 示例

```
/drogon-gen-orm-model db_type=postgresql tables=users,roles relationships=true
```

## 参考文件

详细实现指南见 `references/code-guide.md`（含参数验证、drogon_ctl 逐参数说明、生成物约定、CMake 集成、禁止模式清单）。生成代码前先读取该文件。
