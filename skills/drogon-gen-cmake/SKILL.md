---
name: drogon-gen-cmake
description: 需要为 drogon 项目编写 CMakeLists.txt（ORM / Redis / 协程 / CSP 视图、Conan 2 或 MSVC 特例）时生成构建脚本。
license: MIT
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
- `find_package(Drogon CONFIG REQUIRED)`
- `target_link_libraries(your_app PRIVATE Drogon::Drogon)`（ORM / Redis / WebSocket 都在这一个目标里，无独立库目标）
- `set(CMAKE_CXX_STANDARD 20)` + `CMAKE_CXX_STANDARD_REQUIRED ON`（协程由 drogon **自身**的 `USE_COROUTINE` 开关决定，**不要**在下游写 `target_compile_definitions(... USE_COROUTINE)`，对已安装的 `Drogon::Drogon` 无效）
## 参考文件
详细实现指南见 `references/code-guide.md`（含参数验证、代码模板、禁止模式清单）。生成代码前先读取该文件。
