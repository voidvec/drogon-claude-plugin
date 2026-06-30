---
name: drogon-gen-cmake
description: 生成 drogon 项目的 CMakeLists.txt，支持 ORM、Redis、WebSocket、C++20、协程等特性。
version: 0.1.0
---

# drogon-gen-cmake

生成 drogon 项目的 `CMakeLists.txt`，支持 ORM、Redis、WebSocket、C++20、协程等特性。

## 使用场景

当创建一个新的 drogon 项目或需要更新 CMake 配置时，使用此技能快速生成符合 drogon 约定的 CMakeLists.txt。

## 输入参数

- `project_name`: 项目名称（如 `myapp`）
- `enable_orm`: 是否启用 ORM（`true`/`false`，默认 `false`）
- `enable_redis`: 是否启用 Redis（`true`/`false`，默认 `false`）
- `enable_websocket`: 是否启用 WebSocket（`true`/`false`，默认 `false`）
- `cxx_standard`: C++ 标准（`17`/`20`，默认 `20`）
- `use_coroutine`: 是否启用协程（`true`/`false`，默认 `false`）

## 输出

生成 `CMakeLists.txt` 文件，包含完整的 drogon 项目配置。

## 示例

```
/drogon-gen-cmake project_name=myapp enable_orm=true cxx_standard=20 use_coroutine=true
```

生成 `CMakeLists.txt`，包含：
- `find_package(drogon REQUIRED)`
- `target_link_libraries(your_app PRIVATE drogon::drogon drogon::orm_lib)`
- `target_compile_definitions(your_app PRIVATE USE_COROUTINE)`
## 参考文件
详细实现指南见 `references/code-guide.md`（含参数验证、代码模板、禁止模式清单）。生成代码前先读取该文件。
